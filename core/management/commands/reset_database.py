from django.core.management import BaseCommand, CommandError, call_command
from django.db import connection, transaction
from django.utils.translation import gettext as _


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true")

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError(_("This command deletes all database records. Run it with --yes to confirm."))
        if connection.vendor != "postgresql":
            raise CommandError(_("Database reset is only supported for PostgreSQL."))
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA public CASCADE")
                cursor.execute("CREATE SCHEMA public")
            call_command("migrate", interactive=False, stdout=self.stdout, stderr=self.stderr)
            call_command("seed_demo", stdout=self.stdout, stderr=self.stderr)
        self.stdout.write(self.style.SUCCESS(_("Database reset and demo data loaded.")))
