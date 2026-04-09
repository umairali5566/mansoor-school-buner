from django.conf import settings

from accounts.models import Student

from .models import ChatHistory


AI_TUTOR_INSTRUCTIONS = """
You are a helpful AI Tutor for school students in SAAMS.
Explain answers in simple, clear language.
Support all common school subjects including Math, Physics, Chemistry, Biology, English, Urdu, Islamiyat, and Computer Science.
If the student asks in Urdu, reply in Urdu.
If the student asks in Roman Urdu, reply in Roman Urdu.
If the student asks in English, reply in English.
If the question is mathematical or numerical, solve it step by step.
If the question is theory-based, explain the concept clearly with short examples.
If the question is grammar-related, give examples and the correct form.
Keep answers student-friendly, concise, and accurate.
Avoid overly complex vocabulary.
If the answer is uncertain, say so honestly and suggest the next learning step.
""".strip()


def _build_context_for_user(user, question):
    student = Student.objects.filter(user=user).first()
    profile_note = ""
    if student is not None:
        profile_note = (
            f"Student class: {student.class_name or 'Unknown'}. "
            f"Student name: {student.display_name}."
        )

    recent_history = ChatHistory.objects.filter(user=user).order_by("-timestamp")[:6]
    conversation_lines = []
    for item in reversed(list(recent_history)):
        conversation_lines.append(f"Student: {item.question}")
        conversation_lines.append(f"AI Tutor: {item.answer}")

    conversation_block = "\n".join(conversation_lines).strip()
    if conversation_block:
        conversation_block = f"Recent conversation:\n{conversation_block}\n\n"

    return (
        f"{profile_note}\n"
        f"{conversation_block}"
        f"Current student question:\n{question.strip()}"
    ).strip()


def generate_ai_tutor_reply(user, question):
    api_key = getattr(settings, "OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("AI Tutor is not configured. Set OPENAI_API_KEY in the environment.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("AI Tutor dependency is missing. Install the openai package.") from exc

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=settings.AI_TUTOR_MODEL,
        instructions=AI_TUTOR_INSTRUCTIONS,
        input=_build_context_for_user(user, question),
        temperature=0.4,
        max_output_tokens=settings.AI_TUTOR_MAX_OUTPUT_TOKENS,
    )
    answer = (getattr(response, "output_text", "") or "").strip()
    if not answer:
        raise RuntimeError("AI Tutor returned an empty response.")
    return answer
