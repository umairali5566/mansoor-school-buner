from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("homework", "0004_homework_due_date_homework_subject_homework_teacher"),
    ]

    operations = [
        migrations.AddField(
            model_name="homework",
            name="notification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
