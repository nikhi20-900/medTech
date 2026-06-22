MEDET relies too heavily on Qwen to decide what questions to ask.

Current flow:

User Message
→ Qwen
→ Emergency Detector
→ Safety Layer
→ Response Builder

This causes:

* Inconsistent follow-up questions
* Chatty responses
* Weak symptom collection
* Variable triage quality

Goal:

Implement a deterministic symptom classification layer before the LLM.

Target architecture:

User Message
→ Symptom Classifier
→ Follow-up Question Engine
→ Emergency Detector
→ Qwen
→ Safety Layer
→ Response Builder

Requirements:

1. Create symptom_classifier.py

Create a lightweight rule-based symptom classifier.

Initial categories:

* respiratory
* cardiac
* neurological
* gastrointestinal
* pregnancy
* injury
* general

Return:

@dataclass
class SymptomCategory:
name: str
severity: str

Example:

“I have fever and cough”
→ respiratory

“I have chest pain”
→ cardiac

“I am pregnant and have fever”
→ pregnancy

2. Create followup_questions.py

Create symptom-specific question banks.

Example:

respiratory:

* How many days have you had these symptoms?
* What is your temperature?
* Is your cough dry or producing mucus?
* Are you having trouble breathing?

cardiac:

* When did the chest pain start?
* Does it spread to your arm or jaw?
* Are you sweating or feeling dizzy?

pregnancy:

* How many weeks pregnant are you?
* What is your temperature?
* Do you have bleeding or abdominal pain?

Provide a function:

get_followup_questions(category: str) -> list[str]

3. Integrate with _generate_ai_response()

Before calling Ollama:

* Classify symptoms
* Retrieve follow-up questions
* Build structured context

Inject into system prompt:

Detected symptom category: 

Preferred follow-up questions:

* Question 1
* Question 2
* Question 3

Use these questions whenever information is missing.

4. Preserve existing architecture

Do NOT break:

* Emergency detector
* Medical safety guard
* Healthcare cards
* Streaming API
* Conversation IDs
* Multilingual support

5. Improve prompt reliability

Ensure Qwen receives:

* Symptom category
* Severity
* Suggested follow-up questions

while still following the existing response format rules.

6. Code quality requirements

* Type hints everywhere
* Dataclasses where appropriate
* Clean separation of concerns
* Production-ready structure
* No hardcoded logic inside medet.py
* Create reusable service modules
* Follow existing project style

7. Deliverables

Provide:

* New files
* Modified imports
* Exact code changes
* Explanation of integration points
* Test cases

Test inputs:

“I have fever and cough”

“I have chest pain and sweating”

“I am pregnant and have fever”

“I have severe headache and blurry vision”

“I have stomach pain and vomiting”

Expected outcome:

MEDET should ask smarter symptom-specific questions before relying on Qwen reasoning, producing more consistent triage conversations.