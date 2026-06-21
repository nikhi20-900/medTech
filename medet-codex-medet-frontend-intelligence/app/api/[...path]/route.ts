import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

type ApiParams = { params: Promise<{ path?: string[] }> };
type JsonRecord = Record<string, unknown>;

const BACKEND_BASE_URL =
  process.env.MEDET_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const supportedBackendLanguages = new Set(["en", "hi", "bn", "ne", "ta", "kn"]);

const profiles = [
  {
    id: "profile-self",
    name: "Lenin Sarmah",
    relation: "Self",
    age: 28,
    bloodGroup: "O+",
    allergies: ["None known"],
    medicalConditions: ["Seasonal allergies"],
    medicines: ["Vitamin D", "ORS when needed"],
    emergencyContacts: [
      { name: "Family Contact", relation: "Family", phone: "+91 90000 44556" },
    ],
  },
  {
    id: "profile-mother",
    name: "Anita Sarmah",
    relation: "Mother",
    age: 56,
    bloodGroup: "B+",
    allergies: ["Penicillin"],
    medicalConditions: ["High blood pressure"],
    medicines: ["Amlodipine 5 mg"],
    emergencyContacts: [
      { name: "Family Contact", relation: "Family", phone: "+91 90000 44557" },
    ],
  },
];

const reminders = [
  {
    id: "reminder-paracetamol",
    medicineName: "Paracetamol",
    dosage: "500 mg after food",
    time: "8:00 AM",
    period: "morning",
    status: "taken",
  },
  {
    id: "reminder-ors",
    medicineName: "ORS solution",
    dosage: "1 glass slowly",
    time: "1:00 PM",
    period: "afternoon",
    status: "pending",
  },
  {
    id: "reminder-iron",
    medicineName: "Iron tablet",
    dosage: "1 tablet after dinner",
    time: "8:30 PM",
    period: "night",
    status: "pending",
  },
];

const clinics = [
  {
    id: "clinic-rural-family",
    name: "Rural Family Clinic",
    type: "clinic",
    distance: "1.2 km",
    travelTime: "12 min",
    address: "Village market road",
    phone: "+91 90000 12001",
    isOpen: true,
  },
  {
    id: "hospital-district",
    name: "District Civil Hospital",
    type: "hospital",
    distance: "2.4 km",
    travelTime: "18 min",
    address: "District center",
    phone: "+91 90000 12002",
    isOpen: true,
  },
  {
    id: "health-primary",
    name: "Primary Health Centre",
    type: "health_center",
    distance: "3.1 km",
    travelTime: "22 min",
    address: "Block health campus",
    phone: "+91 90000 12003",
    isOpen: true,
  },
  {
    id: "pharmacy-jan-aushadhi",
    name: "Jan Aushadhi Pharmacy",
    type: "pharmacy",
    distance: "800 m",
    travelTime: "8 min",
    address: "Near bus stand",
    phone: "+91 90000 12004",
    isOpen: false,
  },
];

export async function GET(request: NextRequest, context: ApiParams) {
  const path = await getPath(context);

  if (path === "auth/session") {
    return json(createSession({ name: "MEDET User" }, "guest"));
  }

  if (path === "profiles") return json(profiles);
  if (path === "reminders") return json(reminders);
  if (path === "clinics") return json(clinics);

  return proxyToBackend(request, path);
}

export async function POST(request: NextRequest, context: ApiParams) {
  const path = await getPath(context);

  if (path === "chat/stream" || path === "medet/chat/stream") {
    return streamChat(request);
  }

  if (path === "auth/phone") {
    const body = await readJson(request);
    return json(createSession(body, "phone"));
  }

  if (path === "auth/google/session") {
    return json(
      createSession({ name: "Google User", email: "google.user@medet.local" }, "google")
    );
  }

  if (path === "auth/logout") {
    return new Response(null, { status: 204 });
  }

  if (path === "voice/stt") {
    return json({ transcript: "", confidence: 0 });
  }

  if (path === "voice/tts") {
    return new Response(null, { status: 204 });
  }

  return proxyToBackend(request, path);
}

export async function PUT(request: NextRequest, context: ApiParams) {
  const path = await getPath(context);
  const body = await readJson(request);

  if (path.startsWith("profiles/") || path.startsWith("reminders/")) {
    return json(body);
  }

  return proxyToBackend(request, path);
}

async function streamChat(request: NextRequest) {
  const body = await readJson(request);
  const message = String(body.message ?? "").trim();

  if (!message) {
    return json({ error: { message: "Message is required" } }, 400);
  }

  const backendResponse = await tryBackendChatStream(request, body);
  if (backendResponse) return backendResponse;

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      for (const token of buildFallbackReply(message).split(" ")) {
        controller.enqueue(
          encoder.encode(`event: token\ndata: ${JSON.stringify({ content: `${token} ` })}\n\n`)
        );
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Cache-Control": "no-cache",
      "Content-Type": "text/event-stream; charset=utf-8",
    },
  });
}

async function tryBackendChatStream(request: NextRequest, body: JsonRecord) {
  try {
    const response = await fetch(`${backendBase()}/medet/chat/stream`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        ...forwardAuthorization(request),
      },
      body: JSON.stringify({
        message: body.message,
        language: normalizeBackendLanguage(body.language),
        input_type: body.input_type ?? "text",
        conversation_id: body.conversation_id ?? body.sessionId,
        stream: true,
      }),
      cache: "no-store",
    });

    if (!response.ok || !response.body) return null;

    return new Response(response.body, {
      status: response.status,
      headers: {
        "Cache-Control": "no-cache",
        "Content-Type": response.headers.get("Content-Type") ?? "text/event-stream",
      },
    });
  } catch {
    return null;
  }
}

async function proxyToBackend(request: NextRequest, path: string) {
  try {
    const normalizedPath = path.replace(/^medet\/?/, "");
    const target = new URL(`${backendBase()}/medet/${normalizedPath}`);
    target.search = request.nextUrl.search;
    const requestBody =
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer();

    const response = await fetch(target, {
      method: request.method,
      headers: {
        Accept: request.headers.get("Accept") ?? "application/json",
        "Content-Type": request.headers.get("Content-Type") ?? "application/json",
        ...forwardAuthorization(request),
      },
      body: requestBody && requestBody.byteLength > 0 ? requestBody : undefined,
      cache: "no-store",
    });

    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") ?? "application/json",
      },
    });
  } catch {
    return json({ error: { message: "API route unavailable" } }, 503);
  }
}

async function getPath(context: ApiParams) {
  const { path = [] } = await context.params;
  return path.join("/");
}

async function readJson(request: Request): Promise<JsonRecord> {
  try {
    return (await request.json()) as JsonRecord;
  } catch {
    return {};
  }
}

function json(data: unknown, status = 200) {
  return Response.json(data, { status });
}

function createSession(input: JsonRecord, provider: "phone" | "google" | "guest") {
  const phone = typeof input.phone === "string" ? input.phone : undefined;
  const email = typeof input.email === "string" ? input.email : undefined;
  const name =
    typeof input.name === "string" && input.name.trim()
      ? input.name.trim()
      : provider === "guest"
        ? "Guest User"
        : "MEDET User";

  return {
    user: {
      id: `user-${provider}-${Date.now()}`,
      name,
      phone,
      email,
      provider,
    },
    accessToken: `local-${provider}-${Date.now()}`,
    expiresAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
  };
}

function buildFallbackReply(message: string) {
  if (/chest pain|breathing|breath|unconscious|stroke|bleeding|seizure|poison|burn|heart/i.test(message)) {
    return "This may need urgent medical care. Please call emergency services or go to the nearest hospital now. If possible, ask a family member or neighbor to stay with you while you get help.";
  }

  return "I hear you. I can guide you with simple next steps, but I will not diagnose you. How long has this been happening, and do you have fever, severe pain, dizziness, or trouble breathing?";
}

function normalizeBackendLanguage(language: unknown) {
  const value = typeof language === "string" ? language.toLowerCase() : "en";
  return supportedBackendLanguages.has(value) ? value : "en";
}

function forwardAuthorization(request: NextRequest): Record<string, string> {
  const authorization = request.headers.get("Authorization");
  return authorization ? { Authorization: authorization } : {};
}

function backendBase() {
  return BACKEND_BASE_URL.replace(/\/$/, "");
}
