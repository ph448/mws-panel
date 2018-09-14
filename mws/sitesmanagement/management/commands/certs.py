from __future__ import print_function, unicode_literals                                                                                                                                       
from django.core.management.base import BaseCommand
from sitesmanagement.models import Site, Vhost

from cryptography import x509
from cryptography.hazmat.backends import default_backend

class Command(BaseCommand):
    help = 'MWS client certificate utilities'

    ACTIONS = [
        'get', # get object
        'info', # get properties of object
    ]

    def add_arguments(self, parser):
        parser.add_argument('action', choices=ACTIONS)
        parser.add_argument('--all', '-A', action='store_true', help='')
        parser.add_argument('--site', '-s', action='store', help='site id')
        parser.add_argument('--vhost', '-h', action='store', help='vhost id')
        parser.add_argument('--file', '-f', action='store', help='filename to read')
        parser.add_argument('--output', '-o', action='store', help='filename to write')

    def get_attr_or_none(self, obj=None, attr=None):
        '''retrieve an attribute from a Vhost or None if not found'''
        if obj:
            try:
                return getattr(obj, attr)
            except:
                return None

    def get_certificate_extension(self, cert=None, extension=None):
        '''get certificate extension by OID'''
        response = {}
        if cert:
           for ext in cert.extensions:
                if ext.oid == extension:
                    response[ext.oid] = []
                    for value in ext.value:
                        response[ext.oid].append(value)
        return response

    def handle(self, *args, **options):
        if options['action'] == 'info':
            
        pass
