from django.core.management.base import BaseCommand
from sitesmanagement.models import Vhost

from cryptography import x509
from cryptography.hazmat.backends import default_backend

class Command(BaseCommand):
    args = ''
    help = 'list EV certificates'

    def handle(self, *args, **options):
        # for each Vhost load certificate data into cert
        for ext in cert.extensions:
            if ext.oid == x509.oid.ExtensionOID.CERTIFICATE_POLICIES:
                for v in ext.value:
                    print(v.policy_identifier.dotted_string)

