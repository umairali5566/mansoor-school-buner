from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_center(request):
    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")
    paginator = Paginator(notifications, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "notifications/center.html",
        {
            "page_obj": page_obj,
            "notifications": page_obj.object_list,
            "unread_count": Notification.objects.unread_for_user(request.user).count(),
        },
    )


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read(save=True)
    return JsonResponse(
        {
            "ok": True,
            "notification_id": notification.id,
            "unread_count": Notification.objects.unread_for_user(request.user).count(),
        }
    )


@login_required
@require_POST
def mark_all_notifications_read(request):
    unread_qs = Notification.objects.unread_for_user(request.user)
    updated = unread_qs.update(read_at=timezone.now())
    unread_count = Notification.objects.unread_for_user(request.user).count()
    return JsonResponse(
        {
            "ok": True,
            "updated": updated,
            "unread_count": unread_count,
        }
    )
