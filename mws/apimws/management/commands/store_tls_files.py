from django.core.management.base import NoArgsCommand, CommandError
from sitesmanagement.models import Vhost


class Command(NoArgsCommand):
    args = "{ <vhost_id> <hash> }"
    help = "Stores the TLS key hash in the database"

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError("All arguments need to be supplied")
        try:

            vhost = Vhost.objects.get(id=args[0])
        except Vhost.DoesNotExist:
            raise CommandError("Vhost not found")

        vhost.certificate = None
        vhost.tls_enabled = True
        vhost.save()