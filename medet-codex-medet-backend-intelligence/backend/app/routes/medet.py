from __future__ import annotations
import ollama
import asyncio
import json
import logging
import time
import traceback
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.app.services.conversation_state import state_manager
from backend.app.services.symptom_classifier import classify_symptom
from backend.app.services.response_policy_rules import determine_response_policy
from backend.app.services.triage_prompt_builder import build_policy_aware_prompt
from backend.app.core.errors import MedetAPIError, MedetErrorCode, OllamaUnavailableError
from backend.app.schemas.medet_response import (
    MedetChatRequest,
    MedetErrorResponse,
    MedetResponse,
    normalize_sources,
)
from backend.app.services.language_support import (
    build_multilingual_prompt_context,
    get_followup_text,
)
from backend.app.services.medet_response_builder import build_medet_response

router = APIRouter(prefix="/medet", tags=["medet"])


@router.post(
    "/chat",
    response_model=MedetResponse,
    responses={
        400: {"model": MedetErrorResponse},
        422: {"model": MedetErrorResponse},
        503: {"model": MedetErrorResponse},
        504: {"model": MedetErrorResponse},
    },
)
async def medet_chat(payload: MedetChatRequest) -> MedetResponse:
    """
    Non-streaming Medet response.

    Replace `_generate_ai_response` with the existing Omnix/Ollama/Tavily service
    call in the host app. The response builder is the healthcare-safe integration
    point and should stay independent from retrieval or model providers.
    """
    conversation_id = _conversation_id(payload)
    try:
        ai_text, sources = await _generate_ai_response(
            payload.message,
            payload.input_type,
            payload.language,
            conversation_id,
        )
        return build_medet_response(
            ai_text=ai_text,
            user_message=payload.message,
            sources=sources,
            conversation_id=conversation_id,
            input_type=payload.input_type,
            language=payload.language,
        )
    except asyncio.TimeoutError as exc:
        raise MedetAPIError(
            MedetErrorCode.TIMEOUT,
            "The healthcare AI response took too long. Please try again.",
            status_code=504,
            retryable=True,
        ) from exc
    except MedetAPIError:
        raise
    except Exception as exc:
        raise MedetAPIError(
            MedetErrorCode.UPSTREAM_FAILURE,
            "The healthcare AI service could not complete the request.",
            status_code=503,
            retryable=True,
        ) from exc


@router.post(
    "/chat/stream",
    responses={
        400: {"model": MedetErrorResponse},
        422: {"model": MedetErrorResponse},
        503: {"model": MedetErrorResponse},
        504: {"model": MedetErrorResponse},
    },
)
async def medet_chat_stream(payload: MedetChatRequest) -> StreamingResponse:
    """
    Streaming response that keeps token streaming intact and sends metadata last.

    The frontend can keep rendering streamed text exactly as before, then consume
    the final `metadata` event to show emergency UI cards.
    """
    return StreamingResponse(
        _stream_with_metadata(payload, _conversation_id(payload)),
        media_type="text/event-stream",
    )


async def _stream_with_metadata(
    payload: MedetChatRequest,
    conversation_id: str,
) -> AsyncIterator[str]:
    chunks: list[str] = []
    sources: list[dict[str, str] | str] = []

    try:
        async for event in _stream_ai_response(
            payload.message,
            payload.input_type,
            payload.language,
            conversation_id,
        ):
            if event.get("type") == "source":
                source = event.get("source", {})
                if isinstance(source, (dict, str)):
                    sources.append(source)
                    for normalized_source in normalize_sources([source]):
                        yield _sse(
                            "source",
                            {
                                "type": "source",
                                "source": _model_dump(normalized_source),
                                "input_type": payload.input_type,
                                "language": payload.language,
                                "conversation_id": conversation_id,
                            },
                        )
                continue

            token = str(event.get("content", ""))
            if not token:
                continue

            chunks.append(token)
            yield _sse(
                "token",
                {
                    "type": "token",
                    "content": token,
                    "input_type": payload.input_type,
                    "language": payload.language,
                    "conversation_id": conversation_id,
                },
            )

        structured = build_medet_response(
            ai_text="".join(chunks),
            user_message=payload.message,
            sources=sources,
            conversation_id=conversation_id,
            input_type=payload.input_type,
            language=payload.language,
        )
        yield _sse("metadata", _model_dump(structured))
    except asyncio.TimeoutError:
        yield _sse_error(
            MedetErrorCode.TIMEOUT,
            "The healthcare AI response took too long. Please try again.",
            conversation_id,
            retryable=True,
        )
    except MedetAPIError as exc:
        yield _sse_error(
            exc.code,
            exc.message,
            conversation_id,
            retryable=exc.retryable,
        )
    except Exception:
        yield _sse_error(
            MedetErrorCode.UPSTREAM_FAILURE,
            "The healthcare AI service could not complete the request.",
            conversation_id,
            retryable=True,
        )


_OLLAMA_MODEL = "qwen3:4b"
_OLLAMA_OPTIONS = {"temperature": 0.2, "top_p": 0.8}

logger = logging.getLogger("medet.ollama")


def _build_chat_messages(
    message: str,
    input_type: str,
    language: str,
    conversation_id: str,
) -> list[dict[str, str]]:
    """Run the full prompt pipeline and return the Ollama messages list.

    Pipeline: Conversation State → Symptom Classifier →
    Response Policy → Prompt Builder → message construction.

    Raises MedetAPIError on validation failure.
    """
    prompt_context = build_multilingual_prompt_context(
        message=message,
        language=language,
        input_type=input_type,
    )

    symptom = classify_symptom(message)
    state = state_manager.update(conversation_id, message, symptom)
    policy_ctx = determine_response_policy(state)
    logger.info(
        "response_policy | conv=%s policy=%s max_q=%d self_care=%s",
        conversation_id, policy_ctx.policy.value,
        policy_ctx.max_questions, policy_ctx.allow_self_care,
    )
    extra_context = build_policy_aware_prompt(state, policy_ctx)
    system_instruction = f"{prompt_context.system_instruction}{extra_context}"

    logger.debug("system_instruction (%d chars): %.120s…",
                 len(system_instruction), system_instruction)
    logger.debug("user_message (%d chars): %.120s…",
                 len(prompt_context.user_message), prompt_context.user_message)

    if not prompt_context.system_instruction:
        raise MedetAPIError(
            MedetErrorCode.UPSTREAM_FAILURE,
            "Prompt context has empty system_instruction.",
            status_code=500,
        )
    if not prompt_context.user_message:
        raise MedetAPIError(
            MedetErrorCode.EMPTY_MESSAGE,
            "Prompt context has empty user_message.",
            status_code=400,
        )

    return [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt_context.user_message},
    ]


async def _generate_ai_response(
    message: str,
    input_type: str,
    language: str,
    conversation_id: str,
) -> tuple[str, list[dict[str, str] | str]]:
    """Non-streaming Ollama call used by the /chat endpoint."""
    logger.info("🔥 _generate_ai_response called | conv=%s lang=%s type=%s",
                conversation_id, language, input_type)

    messages = _build_chat_messages(message, input_type, language, conversation_id)

    try:
        logger.info("Calling ollama.chat(model=%r) …", _OLLAMA_MODEL)
        t0 = time.perf_counter()
        response = await asyncio.to_thread(
            ollama.chat,
            model=_OLLAMA_MODEL,
            messages=messages,
            options=_OLLAMA_OPTIONS,
        )
        elapsed = time.perf_counter() - t0
        logger.info("Ollama response received in %.2fs (type=%s)",
                    elapsed, type(response).__name__)
    except ConnectionError as exc:
        logger.error("Ollama connection failed:\n%s", traceback.format_exc())
        raise OllamaUnavailableError(
            "Cannot reach Ollama. Is `ollama serve` running on localhost:11434?"
        ) from exc
    except Exception as exc:
        logger.error("Ollama call failed:\n%s", traceback.format_exc())
        raise OllamaUnavailableError(
            f"Ollama error: {type(exc).__name__}: {exc}"
        ) from exc

    # Extract the answer safely
    try:
        answer = response["message"]["content"]
    except (KeyError, TypeError, IndexError) as exc:
        logger.error("Unexpected Ollama response structure: %s\n%s",
                      response, traceback.format_exc())
        raise MedetAPIError(
            MedetErrorCode.UPSTREAM_FAILURE,
            f"Unexpected Ollama response format: {type(response).__name__}",
            status_code=502,
        ) from exc

    if not answer or not answer.strip():
        logger.warning("Ollama returned an empty answer.")
        raise MedetAPIError(
            MedetErrorCode.UPSTREAM_FAILURE,
            "Ollama returned an empty response.",
            status_code=502,
        )

    logger.info("✅ Ollama answer (%d chars): %.80s…", len(answer), answer)
    return (answer, [])


async def _stream_ai_response(
    message: str,
    input_type: str,
    language: str,
    conversation_id: str,
) -> AsyncIterator[dict[str, object]]:
    """Native Ollama streaming — yields tokens as they arrive from the model.

    Uses ollama.AsyncClient().chat(stream=True) to get true token-by-token
    streaming instead of waiting for the full response.

    Performance metrics (TTFT, total time, tokens/sec) are logged at the end.
    """
    logger.info("🔥 _stream_ai_response called | conv=%s lang=%s type=%s",
                conversation_id, language, input_type)

    chat_messages = _build_chat_messages(
        message, input_type, language, conversation_id,
    )

    # Performance counters
    t_start = time.perf_counter()
    t_first_token: float | None = None
    token_count = 0

    try:
        logger.info("Calling ollama.AsyncClient().chat(model=%r, stream=True) …",
                    _OLLAMA_MODEL)
        client = ollama.AsyncClient()
        stream = await client.chat(
            model=_OLLAMA_MODEL,
            messages=chat_messages,
            stream=True,
            options=_OLLAMA_OPTIONS,
        )

        async for chunk in stream:
            # Extract the token from the streaming chunk
            token = chunk["message"]["content"]
            if not token:
                continue

            token_count += 1
            if t_first_token is None:
                t_first_token = time.perf_counter()
                ttft = t_first_token - t_start
                logger.info(
                    "⚡ TTFT=%.3fs | conv=%s",
                    ttft, conversation_id,
                )

            yield {"type": "token", "content": token}

    except ConnectionError as exc:
        logger.error("Ollama stream connection failed:\n%s",
                     traceback.format_exc())
        raise OllamaUnavailableError(
            "Cannot reach Ollama. Is `ollama serve` running on localhost:11434?"
        ) from exc
    except Exception as exc:
        logger.error("Ollama stream failed:\n%s", traceback.format_exc())
        raise OllamaUnavailableError(
            f"Ollama streaming error: {type(exc).__name__}: {exc}"
        ) from exc

    # Log performance summary
    t_end = time.perf_counter()
    total = t_end - t_start
    tps = token_count / total if total > 0 else 0
    logger.info(
        "📊 stream_perf | conv=%s tokens=%d total=%.2fs "
        "TTFT=%.3fs tok/s=%.1f",
        conversation_id,
        token_count,
        total,
        (t_first_token - t_start) if t_first_token else 0,
        tps,
    )


def _conversation_id(payload: MedetChatRequest) -> str:
    return payload.conversation_id or str(uuid4())


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _sse_error(
    code: MedetErrorCode,
    message: str,
    conversation_id: str,
    *,
    retryable: bool,
) -> str:
    return _sse(
        "error",
        {
            "type": "error",
            "error": {
                "code": code.value,
                "message": message,
                "retryable": retryable,
                "field": None,
            },
            "conversation_id": conversation_id,
        },
    )


def _model_dump(model: object) -> dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    return model.dict()  # type: ignore[attr-defined,no-any-return]
