from .models import Student, Teacher


def user_profile_context(request):
    """
    Provide safe user profile objects for templates.
    Avoids template crashes when role exists but related profile row is missing.
    """
    if not getattr(request.user, "is_authenticated", False):
        return {
            "current_student_profile": None,
            "current_teacher_profile": None,
        }

    role = getattr(request.user, "role", "")
    current_student_profile = None
    current_teacher_profile = None

    if role == "STUDENT":
        current_student_profile = Student.objects.filter(user=request.user).first()
    elif role == "TEACHER":
        current_teacher_profile = Teacher.objects.filter(user=request.user).first()

    return {
        "current_student_profile": current_student_profile,
        "current_teacher_profile": current_teacher_profile,
    }
