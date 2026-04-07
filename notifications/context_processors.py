from .models import Notification


def notification_context(request):
    if not getattr(request.user, "is_authenticated", False):
        return {
            "topbar_notifications": [],
            "topbar_unread_notifications_count": 0,
        }

    notifications = list(
        Notification.objects.filter(user=request.user)
        .only("id", "title", "message", "notification_type", "link_url", "created_at", "read_at")
        .order_by("-created_at")[:8]
    )
    unread_count = Notification.objects.unread_for_user(request.user).count()

    return {
        "topbar_notifications": notifications,
        "topbar_unread_notifications_count": unread_count,
    }
