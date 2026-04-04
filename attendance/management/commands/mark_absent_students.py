from datetime import date as dt_date

from django.core.management.base import BaseCommand, CommandError

from attendance.auto_absent import mark_auto_absent


class Command(BaseCommand):
    help = "Mark absent students for a day if they have no attendance record (default cutoff: 10:02 AM local time)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="target_date",
            help="Target date in YYYY-MM-DD format. Defaults to local today.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even before 10:02 AM.",
        )

    def handle(self, *args, **options):
        target_date_raw = options.get("target_date")
        force = bool(options.get("force"))

        target_date = None
        if target_date_raw:
            try:
                target_date = dt_date.fromisoformat(target_date_raw)
            except ValueError as exc:
                raise CommandError("Invalid --date. Use YYYY-MM-DD.") from exc

        result = mark_auto_absent(target_date=target_date, force=force)

        if not result.get("ran"):
            cutoff = result.get("cutoff")
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped: current local time is before cutoff ({cutoff})."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Auto-absent completed for {date}. Created absent: {created}. "
                "Emails sent: {emails}. Marked: {marked}/{total}, Present: {present}, Absent: {absent}.".format(
                    date=result["date"],
                    created=result["created_absent"],
                    emails=result.get("emails_sent", 0),
                    marked=result["marked_count"],
                    total=result["total_students"],
                    present=result["present_count"],
                    absent=result["absent_count"],
                )
            )
        )
