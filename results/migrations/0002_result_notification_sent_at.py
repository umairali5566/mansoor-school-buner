from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("results", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="result",
            name="notification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
