from django.db.models.signals import post_save
from django.dispatch import receiver

from notifications.email_service import send_result_notification

from .models import Result


@receiver(post_save, sender=Result)
def result_notification_on_create(sender, instance, created, **kwargs):
    update_fields = kwargs.get("update_fields")
    should_try_send = created or (
        instance.notification_sent_at is None and (
            update_fields is None or "notification_sent_at" not in update_fields
        )
    )

    if should_try_send:
        send_result_notification(instance)
