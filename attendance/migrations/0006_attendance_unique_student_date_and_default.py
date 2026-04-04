from django.db import migrations, models
import django.utils.timezone


def deduplicate_attendance(apps, schema_editor):
    Attendance = apps.get_model("attendance", "Attendance")
    from django.db.models import Count

    duplicate_groups = (
        Attendance.objects.values("student_id", "date")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )

    for group in duplicate_groups:
        rows = Attendance.objects.filter(
            student_id=group["student_id"],
            date=group["date"],
        ).order_by("id")
        keeper = rows.first()
        if keeper is None:
            continue

        # Keep one row per student/day and prefer "Present" when possible.
        if keeper.status != "Present":
            present_row = rows.filter(status="Present").first()
            if present_row is not None:
                keeper.status = "Present"
                keeper.save(update_fields=["status"])

        rows.exclude(id=keeper.id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0005_alter_attendance_status"),
    ]

    operations = [
        migrations.RunPython(deduplicate_attendance, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="attendance",
            name="date",
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
        migrations.AddConstraint(
            model_name="attendance",
            constraint=models.UniqueConstraint(
                fields=("student", "date"),
                name="unique_student_attendance_per_day",
            ),
        ),
    ]
