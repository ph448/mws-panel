from __future__ import absolute_import
import json
import logging
import uuid
from celery import shared_task, Task
from django.core.mail import EmailMessage
from django.conf import settings
from django.core.urlresolvers import reverse
from apimws.vm import new_site_primary_vm
from sitesmanagement.models import EmailConfirmation, NetworkConfig, Site, Service, ServerType
from sitesmanagement.utils import is_camacuk_subdomain
from apimws.ansible import AnsibleTaskWithFailure

LOGGER = logging.getLogger('mws')


class EmailTaskWithFailure(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        LOGGER.error("An error happened when trying to send an email.\nThe task id is %s.\n\n"
                     "The parameters passed to the task were: %s\n\nThe traceback is:\n%s\n", task_id, args, einfo)


@shared_task(base=EmailTaskWithFailure, default_retry_delay=15*60, max_retries=6)  # Retry each 15 minutes for 6 times
def ip_register_api_request(domain_name):
    if is_camacuk_subdomain(domain_name.name):
        return domain_name.special_it("cam.ac.uk subdomain")
    from apimws.ipreg import get_nameinfo
    nameinfo = get_nameinfo(domain_name)
    if 'delegated' in nameinfo and nameinfo['delegated'] == "Y":
        return domain_name.special_it("Delegated domain name")
    if nameinfo['emails']:
        emails = nameinfo['emails']
    elif nameinfo['crsids']:
        emails = map(lambda crsid: crsid+"@cam.ac.uk", nameinfo['crsids'])
    else:
        LOGGER.error("Domain name %s do not have emails or crsids associated in IPREG database.\n"
                     "Received: %s", domain_name.name, json.dumps(nameinfo))
        raise Exception("Domain name %s do not have emails or crsids associated in IPREG database" % domain_name.name)
    EmailMessage(
        subject="Domain name authorisation request for %s" % nameinfo['domain'],
        body="You are receiving this email because you are the administrator of the domain %s.\n\n"
             "The user %s (https://www.lookup.cam.ac.uk/person/crsid/%s) has requested permission to use the domain "
             "name %s for a UIS Managed Web Server website (see http://mws-help.uis.cam.ac.uk/).\n\n"
             "To authorise or reject this request please visit the following URL %s%s. If we don't hear from you "
             "in %s days the request will be automatically %s.\n\n%s"
             "Questions about this message can be referred to mws-support@uis.cam.ac.uk."
             % (nameinfo['domain'], domain_name.requested_by.last_name, domain_name.requested_by.username,
                domain_name.name, settings.MAIN_DOMAIN,
                reverse('apimws.views.confirm_dns', kwargs={'dn_id': domain_name.id, 'token': domain_name.token}),
                settings.MWS_DOMAIN_NAME_GRACE_DAYS,
                "rejected" if nameinfo['exists'] and "C" not in nameinfo['exists'] else "accepted",
                "We have detected that this domain name already exists in the DNS. In order to accept the request "
                "you will have to change the domain name to a CNAME or delete it.\n\n"
                if nameinfo['exists'] and "C" not in nameinfo['exists'] else ""),
        from_email="Managed Web Service Support <%s>"
                   % getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk'),
        to=emails,
        headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
    ).send()


def email_confirmation(site):
    EmailConfirmation.objects.filter(site=site).delete()  # Delete previous one
    EmailConfirmation.objects.create(email=site.email, token=uuid.uuid4(), status="pending", site=site)
    send_email_confirmation.delay(site)


@shared_task(base=EmailTaskWithFailure, default_retry_delay=5*60, max_retries=12)  # Retry each 5 minutes for 1 hour
def send_email_confirmation(site):
    email_conf = EmailConfirmation.objects.filter(site=site)
    if email_conf:
        email_conf = email_conf.first()
        EmailMessage(
            subject="University of Cambridge Managed Web Service: Please confirm your email address",
            body="You are receiving this message because your email address, or an email alias that includes "
                 "you as a recipient, has been configured as the contact address for the UIS Managed Web "
                 "Server '%s'.\n\nPlease, confirm your email address by clicking in the following link: %s%s"
                 % (site.name, settings.MAIN_DOMAIN,
                    reverse('apimws.views.confirm_email', kwargs={'ec_id': email_conf.id, 'token': email_conf.token})),
            from_email="Managed Web Service Support <mws-support@uis.cam.ac.uk>",
            to=[site.email],
            headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
        ).send()


@shared_task(base=EmailTaskWithFailure, default_retry_delay=5*60, max_retries=12)  # Retry each 5 minutes for 1 hour
def finished_installation_email_confirmation(site):
    EmailMessage(
        subject="University of Cambridge Managed Web Service: Your MWS3 server is available",
        body="You are receiving this message because your email address, or an email alias that includes "
             "you as a recipient, has been configured as the contact address for the UIS Managed Web "
             "Server '%s'.\n\nYour MWS3 server is now available. You can access to the web panel of your MWS3 server "
             "by clicking the following link: %s%s" % (site.name, settings.MAIN_DOMAIN, site.get_absolute_url()),
        from_email="Managed Web Service Support <mws-support@uis.cam.ac.uk>",
        to=[site.email],
        headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
    ).send()


def preallocate_new_site(servertype=None):
    """
    Create a new :py:class:`~sitesmanagement.models.Site` object with a unique
    uuid4 as name. The new Site has two
    :py:class:`~sitesmanagement.models.Service` instances associated with it,
    "production" and "test".

    """
    if servertype:
        site = Site.objects.create(name=uuid.uuid4(), disabled=False, preallocated=True, type=servertype)
    else:
        site = Site.objects.create(name=uuid.uuid4(), disabled=False, preallocated=True,
                                   type=ServerType.objects.get(id=1))
    prod_service_netconf = NetworkConfig.get_free_prod_service_config()
    test_service_netconf = NetworkConfig.get_free_test_service_config()
    host_netconf = NetworkConfig.get_free_host_config()
    if not prod_service_netconf or not test_service_netconf or not host_netconf:
        raise Exception('A MWS server cannot be created at this moment because there are no network addresses available')
    prod_service = Service.objects.create(site=site, type='production', network_configuration=prod_service_netconf)
    Service.objects.create(site=site, type='test', network_configuration=test_service_netconf)
    new_site_primary_vm(prod_service, host_netconf)
    LOGGER.info("Preallocated MWS server created '" + str(site.name) + "' with id " + str(site.id))


@shared_task(base=EmailTaskWithFailure, default_retry_delay=15*60, max_retries=6)  # Retry each 15 minutes for 6 times
def domain_confirmation_user(domain_name):
    EmailMessage(
        subject="Domain name %s has been %s" % (domain_name.name, domain_name.status),
        body="You are receiving this message because your email address, or an email alias that includes "
             "you as a recipient, has been configured as the contact address for the UIS Managed Web "
             "Server '%s'.\n\nThe administrator of the domain %s has %s your request.\n\n"
             "Visit the web control panel to know more: %s%s" %
             (domain_name.vhost.service.site.name, domain_name.name, domain_name.status, settings.MAIN_DOMAIN,
              reverse('listdomains', kwargs={'vhost_id': domain_name.vhost.id})),
        from_email="Managed Web Service Support <%s>"
                   % getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk'),
        to=[domain_name.vhost.service.site.email],
        headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
    ).send()

def next_update(time=None):
    """
    Return a time by which we can be reasonably sure the DNS update has run.
    """
    from datetime import datetime, timedelta
    if time is None:
        time = datetime.now()
    return time.replace(minute=54, second=0, microsecond=0) + timedelta(hours=1) \
        if time.minute > 55 \
        else time.replace(minute=54, second=0, microsecond=0)


@shared_task(base=AnsibleTaskWithFailure)
def configure_domain(domain_name):
    service = domain_name.vhost.service
    from apimws.ansible import launch_ansible
    launch_ansible(service)
    domain_confirmation_user.apply_async(args=[domain_name, ])
