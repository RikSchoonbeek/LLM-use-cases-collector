from django.core.management.base import BaseCommand

from collector.services import CollectSubmissionsService

class Command(BaseCommand):
    help = "Collects and processes submissions from the database"

    def handle(self, *args, **options):
        CollectSubmissionsService()()
        self.stdout.write(self.style.SUCCESS('Successfully collected submissions'))
