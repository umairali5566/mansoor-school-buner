from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(read_at__isnull=True)


class NotificationManager(models.Manager):
    def get_queryset(self):
        return NotificationQuerySet(self.model, using=self._db)

    def unread_for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.get_queryset().filter(user=user).unread()

    def create_for_user(self, *, user, title, message="", notification_type="SYSTEM", link_url="", metadata=None):
        if not user or not getattr(user, "is_active", False):
            return None
        return self.create(
            user=user,
            title=(title or "").strip()[:140],
            message=(message or "").strip(),
            notification_type=notification_type,
            link_url=(link_url or "").strip(),
            metadata=metadata or {},
        )


class Notification(models.Model):
    TYPE_SYSTEM = "SYSTEM"
    TYPE_ATTENDANCE = "ATTENDANCE"
    TYPE_RESULT = "RESULT"
    TYPE_HOMEWORK = "HOMEWORK"
    TYPE_SECURITY = "SECURITY"

    TYPE_CHOICES = (
        (TYPE_SYSTEM, "System"),
        (TYPE_ATTENDANCE, "Attendance"),
        (TYPE_RESULT, "Result"),
        (TYPE_HOMEWORK, "Homework"),
        (TYPE_SECURITY, "Security"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=140)
    message = models.TextField(blank=True)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    link_url = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(blank=True, null=True, db_index=True)

    objects = NotificationManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "read_at"]),
        ]

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_as_read(self, save=True):
        if self.read_at is None:
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=["read_at"])

    def __str__(self):
        return f"{self.user} - {self.title}"
