from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0007_attendance_notification_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="marked_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="attendance",
            name="marked_by",
            field=models.CharField(
                choices=[
                    ("FACE", "Face Recognition"),
                    ("MANUAL", "Teacher Manual"),
                    ("AUTO_ABSENT", "Auto Absent"),
                    ("SYSTEM", "System"),
                ],
                default="SYSTEM",
                max_length=20,
            ),
        ),
    ]
