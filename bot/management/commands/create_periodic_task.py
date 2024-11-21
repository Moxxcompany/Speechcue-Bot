from django.core.management.base import BaseCommand

from bot.periodic_task import create_periodic_task


class Command(BaseCommand):
    help = 'Sets up the periodic task for checking call status'

    def handle(self, *args, **kwargs):
        create_periodic_task()
        self.stdout.write(self.style.SUCCESS('Periodic task created successfully.'))
