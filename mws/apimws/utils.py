import uuid
from django.forms import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from sitesmanagement.models import VirtualMachine, NetworkConfig, DomainName, EmailConfirmation

def platforms_email_api_request(site, primary):
    network_configuration = NetworkConfig.objects.filter(virtual_machine=None).first()
    vm = VirtualMachine.objects.create(primary=primary, status='requested',
                                       network_configuration=network_configuration, site=site)

    subject = "New request of a VM for the MWS"
    message = "IPv4: " + network_configuration.IPv4 + "\n" \
              "IPv6: " + network_configuration.IPv6 + "\n" \
              "Domain Name: " + network_configuration.mws_domain + "\n" \
              "Attached: autoyast.xml (with IPs, keys)\n" \
              "Please, when ready click here: %s/api/confirm_vm/" % settings.MAIN_DOMAIN \
              + str(vm.id)
    from_email = "mws-admin@cam.ac.uk"
    recipient_list = ('amc203@cam.ac.uk', )
    send_mail(subject, message, from_email, recipient_list, fail_silently=False)


def ip_register_api_request(site, domain_name):
    domain_requested = DomainName.objects.create(name=domain_name, status='requested', site=site)

    subject = "New request of a Domain Name for the MWS"
    message = "Domain Name requested: " + domain_name + "\n" \
              "IPv4: " + site.primary_vm.network_configuration.IPv4 + "\n" \
              "IPv6: " + site.primary_vm.network_configuration.IPv6 + "\n" \
              "Please, when ready click here: %s/api/confirm_dns/" % settings.MAIN_DOMAIN \
              + str(domain_requested.id)
    from_email = "mws-admin@cam.ac.uk"
    recipient_list = ('amc203@cam.ac.uk', )
    send_mail(subject, message, from_email, recipient_list, fail_silently=False)


def email_confirmation(site):
    previous = EmailConfirmation.objects.filter(site=site)
    if previous:
        previous.first().delete()
    email_conf = EmailConfirmation.objects.create(email=site.email, token=uuid.uuid4(), status="pending", site=site)
    subject = "University of Cambridge Managed Web Service: Please confirm your email address"
    message = "Please, confirm your email address by clicking in the following link: " \
              "%s/confirm_email/%d/%s/" % (settings.MAIN_DOMAIN, email_conf.id, email_conf.token)
    from_email = "mws-admin@cam.ac.uk"
    recipient_list = (site.email, )
    send_mail(subject, message, from_email, recipient_list, fail_silently=False)