from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0006_attendance_unique_student_date_and_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="notification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="attendance",
            name="notification_status",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
    ]
