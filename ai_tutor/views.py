import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

try:
    from ratelimit.decorators import ratelimit
except ImportError:
    def ratelimit(*args, **kwargs):
        def decorator(view_func):
            return view_func

        return decorator

from .models import ChatHistory
from .services import generate_ai_tutor_reply


def _student_only(request):
    return getattr(request.user, "role", "") == "STUDENT" and hasattr(request.user, "student")


@login_required
def ai_tutor_chat(request):
    if not _student_only(request):
        return HttpResponseForbidden("Only students can access AI Tutor.")

    history = ChatHistory.objects.filter(user=request.user).order_by("timestamp")
    return render(
        request,
        "ai_tutor/chat.html",
        {
            "history": history,
            "hide_footer": True,
        },
    )


@login_required
@require_POST
@ratelimit(key="user_or_ip", rate="12/m", method="POST", block=True)
def ai_tutor_send(request):
    if not _student_only(request):
        return HttpResponseForbidden("Only students can access AI Tutor.")

    if request.content_type == "application/json":
        payload = json.loads(request.body or "{}")
        question = (payload.get("question") or "").strip()
    else:
        question = (request.POST.get("question") or "").strip()

    if not question:
        return JsonResponse({"ok": False, "error": "Please enter a question."}, status=400)
    if len(question) > 2000:
        return JsonResponse({"ok": False, "error": "Question is too long. Keep it under 2000 characters."}, status=400)

    try:
        answer = generate_ai_tutor_reply(request.user, question)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)

    chat = ChatHistory.objects.create(
        user=request.user,
        question=question,
        answer=answer,
    )
    return JsonResponse(
        {
            "ok": True,
            "question": chat.question,
            "answer": chat.answer,
            "timestamp": chat.timestamp.strftime("%b %d, %Y %I:%M %p"),
        }
    )
