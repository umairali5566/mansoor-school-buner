from .models import Notification


def create_notification(*, user, title, message="", notification_type=Notification.TYPE_SYSTEM, link_url="", metadata=None):
    return Notification.objects.create_for_user(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        link_url=link_url,
        metadata=metadata,
    )


def create_notifications_for_users(*, users, title, message="", notification_type=Notification.TYPE_SYSTEM, link_url="", metadata=None):
    created = 0
    for user in users:
        notification = create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link_url=link_url,
            metadata=metadata,
        )
        if notification is not None:
            created += 1
    return created
