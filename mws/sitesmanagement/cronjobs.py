"""
The :py:mod:`~sitesmanagement.cronjobs` module contains functions which
implement various scheduled tasks. These tasks are executed by celery as
specified in the settings.

"""

import json
import logging
import subprocess
from datetime import date, timedelta, datetime
from celery import shared_task, Task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Q
from django.utils.timezone import now

from apimws.utils import preallocate_new_site
from sitesmanagement.models import Billing, Site, VirtualMachine, DomainName, ServerType


LOGGER = logging.getLogger('mws')


class FinanceTaskWithFailure(Task):
    """An abstract task which will log an informative error on failure. It is
    intended to be used for tasks which send email to the finance office.

    """
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        LOGGER.error("An error happened when trying to send an email to Finance.\nThe task id is %s.\n\n"
                     "The parameters passed to the task were: %s\n\nThe traceback is:\n%s\n", task_id, args, einfo)


class ScheduledTaskWithFailure(Task):
    """An abstract task which will log an informative error on failure. It is
    intended to be used for general scheduled tasks.

    """
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        LOGGER.error("An error happened when trying to execute an scheduled task.\nThe task id is %s.\n\n"
                     "The parameters passed to the task were: %s\n\nThe traceback is:\n%s\n", task_id, args, einfo)


REMINDER_RENEWAL_SUBJECT = "The annual charge for your managed web server is due on '%s'"
REMINDER_RENEWAL_BODY = (
    "You are receiving this message because your email address, or an email alias that includes you as a recipient, "
    "has been configured as the contact address for the UIS Managed Web Server '%s'.\n\n"
    "The annual charge for your managed web server '%s' is due on '%s'. "
    "Unless you tell us otherwise we will automatically issue an invoice for this on '%s' "
    "based on information from the most recent purchase order you have given us. "
    "Please use the web control panel (under 'billing settings') to check that this information is still current. "
    "If you want to amend your purchase order you can upload a new one. "
    "Your site may be cancelled if we can't successfully invoice for it.\n\n"
    "If you no longer want you site then please either cancel it now (under 'edit the MWS profile'), "
    "or mark it 'Not for renewal' in which case it will be automatically cancelled on '%s'."
)


@shared_task(base=FinanceTaskWithFailure)
def send_reminder_renewal():
    """
    Periodically called to send any warnings about about accounts that are due for renewal.
    """
    support_email = getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')

    kwargs = {
        'from_email': 'Managed Web Service Support <%s>' % support_email,
        'headers': {'Return-Path': support_email}
    }

    # reminder for all accounts requiring renewal 1 to 2 months in the future
    for billing, end_date in renewal_sites_billing(62, 31):
        EmailMessage(
            subject=REMINDER_RENEWAL_SUBJECT % end_date,
            body=REMINDER_RENEWAL_BODY % (billing.site.name, billing.site.name, end_date, end_date, end_date),
            to=[billing.site.email], **kwargs
        ).send()

    # reminder for all accounts requiring renewal less than a month in the future
    for billing, end_date in renewal_sites_billing(31):
        EmailMessage(
            subject="REMINDER: " + REMINDER_RENEWAL_SUBJECT % end_date,
            body=REMINDER_RENEWAL_BODY % (billing.site.name, billing.site.name, end_date, end_date, end_date),
            to=[billing.site.email], **kwargs
        ).send()


def renewal_sites_billing(lower, upper=0):
    """
    :param lower: lower bound in days of the reminder period (less than the end date)
    :param upper: upper bound in days of the reminder period (less than the end date)
    :return: a list of Billing accounts that need a renewal reminder and the period end date for that reminder
    """
    today = now().date()

    due = []
    for billing in Billing.objects.filter(site__end_date__isnull=True, site__subscription=True):
        # increment the start_date in years until it exceeds now to calculate the period_end_date
        period_end_date = billing.site.start_date
        while period_end_date < today:
            period_end_date = period_end_date + relativedelta(months=+12)
        # subtract the lower and upper days values and use this as a range to test whether a reminder is due
        if period_end_date - relativedelta(days=lower) < today < period_end_date - relativedelta(days=upper):
            due.append((billing, period_end_date))
    return due


@shared_task(base=FinanceTaskWithFailure)
def check_subscription():
    today = now().date()
    # Check which sites still do not have a billing associated, warn or cancel them based on
    # how many days ago they were created
    sites = Site.objects.filter(billing__isnull=True, end_date__isnull=True, start_date__isnull=False)
    for site in sites:
        if (today - site.start_date) >= timedelta(days=31):
            # Cancel site
            EmailMessage(
                subject="Your managed web server has been cancelled",
                body="You are receiving this message because your email address, or an email alias that includes "
                     "you as a recipient, has been configured as the contact address for the UIS Managed Web "
                     "Server '%s'.\n\nYour managed web server '%s' has been cancelled because we haven't received "
                     "payment information for it." % (site.name, site.name),
                from_email="Managed Web Service Support <mws-support@uis.cam.ac.uk>",
                to=[site.email],
                headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
            ).send()
            site.cancel()
        elif ((today - site.start_date) == timedelta(days=15)) or ((today - site.start_date) >= timedelta(days=24)):
            # Warning 15 days before and each day in the last week before deadline
            EmailMessage(
                subject="Remember to upload a purchase order for your managed web server",
                body="You are receiving this message because your email address, or an email alias that includes "
                     "you as a recipient, has been configured as the contact address for the UIS Managed Web "
                     "Server '%s'.\n\nPlease upload a purchase order using the control web panel to pay for your "
                     "managed web server '%s'.\n\nIf you don't upload a valid purchase order before %s your site "
                     "'%s' will be automatically cancelled." % (site.name, site.name,
                                                                site.start_date+timedelta(days=30), site.name),
                from_email="Managed Web Service Support <mws-support@uis.cam.ac.uk>",
                to=[site.email],
                headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
            ).send()
    # Cancel sites with subscription finished
    if today.month == 2 and today.day == 29:
        last_year = date(today.year-1, 3, 1)
    else:
        last_year = date(today.year-1, today.month, today.day)
    sites = Site.objects.filter(end_date__isnull=True, start_date__lt=last_year, subscription=False)
    for site in sites:
        # Cancel site
        EmailMessage(
            subject="Your managed web server has been cancelled",
            body="You are receiving this message because your email address, or an email alias that includes "
                 "you as a recipient, has been configured as the contact address for the UIS Managed Web "
                 "Server '%s'.\n\nYour managed web server '%s' has been cancelled per your requested." %
                 (site.name, site.name),
            from_email="Managed Web Service Support <mws-support@uis.cam.ac.uk>",
            to=[site.email],
            headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
        ).send()
        site.cancel()


@shared_task(base=ScheduledTaskWithFailure)
def check_backups():
    try:
        result = subprocess.check_output(["userv", "mws-admin", "mws_check_backups"], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        LOGGER.error("An error happened when checking ook backups in ent.\n\n"
                     "The output from the command was: %s\n", e.output)
        raise e
    except Exception as e:
        LOGGER.error("An error happened when checking ook backups in ent.\n\n"
                     "The output from the command was: %s\n", e)
        raise e
    try:
        result = json.loads(result)
    except Exception as e:
        LOGGER.error("An error happened when checking ook backups in ent.\n\n"
                     "Result is not in json format: %s\n", result)
        raise e
    for failed_backup in result['failed']:
        LOGGER.error("A backup for the host %s did not complete last night", failed_backup)

    for vm in VirtualMachine.objects.filter(Q(service__site__deleted=False, service__site__disabled=False,
                                              service__site__start_date__lt=(date.today() - timedelta(days=1)),
                                              service__status__in=('ansible', 'ansible_queued', 'ready')) & (
                                                Q(service__site__end_date__isnull=True) |
                                                Q(service__site__end_date__gt=date.today()))
                                            ):
        if not filter(lambda host: host.startswith(vm.name), result['ok']+result['failed']):
            LOGGER.error("A backup for the host %s did not complete last night", vm.name)


@shared_task(base=ScheduledTaskWithFailure)
def delete_cancelled():
    """Delete sites that were cancelled 2 weeks ago and were never paid for"""
    sites_cancelled_never_paid = Site.objects.filter(end_date__isnull=False, billing=None,
                                                     end_date__lt=(datetime.today()-timedelta(weeks=2)).date())
    for site in sites_cancelled_never_paid:
        LOGGER.info("The Site %s has been deleted because it was cancelled more than 2 weeks ago and was never paid for"
                    % site.name)
    sites_cancelled_never_paid.delete()

    """Delete sites that were cancelled 8 weeks ago"""
    sites_cancelled = Site.objects.filter(end_date__isnull=False,
                                          end_date__lt=(datetime.today()-timedelta(weeks=8)).date())
    for site in sites_cancelled:
        LOGGER.info("The Site %s has been deleted because it was cancelled more than 8 weeks ago" % site.name)
    sites_cancelled.delete()


@shared_task(base=ScheduledTaskWithFailure)
def check_num_preallocated_sites():
    """
    A :py:class:`~.ScheduledTaskWithFailure` which checks, for each
    :py:class:`~sitesmanagement.models.ServerType` how many pre-allocated
    :py:class:`~sitesmanagement.models.Site` instances there are. If that is
    smaller than the number which should be pre-allocated, allocate a new one
    via :py:func:`apimws.utils.preallocate_new_site`.

    """
    for servertype in ServerType.objects.all():
        if Site.objects.filter(preallocated=True, type=servertype).count() < servertype.preallocated:
            preallocate_new_site(servertype=servertype)


@shared_task(base=ScheduledTaskWithFailure)
def send_warning_last_or_none_admin():
    for site in Site.objects.filter(Q(start_date__isnull=False) &
                                    (Q(end_date__isnull=True) | Q(end_date__gt=date.today()))):
        num_admins = len(site.list_of_active_admins())
        if num_admins == 1:
            site.days_without_admin = 0
            site.save()
            if datetime.today().weekday() == 0:
                EmailMessage(
                    subject="Your UIS Managed Web Server '%s' has only one administrator" % site.name,
                    body="You are receiving this message because your email address, or an email alias that includes "
                         "you as a recipient, has been configured as the contact address for the UIS Managed Web "
                         "Server '%s'.\n\nThe Managed Web Server '%s' only has a single administrator. This could be "
                         "a problem if some action is required in their absence, or if they leave the University "
                         "since the site would then be automatically suspended. To avoid this, and to stop these "
                         "emails, please add at least one additional administrator via the control panel at %s\n\n"
                         % (site.name, site.name, settings.MAIN_DOMAIN),
                    from_email="Managed Web Service Support <%s>"
                               % getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk'),
                    to=[site.email],
                    headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
                ).send()
        elif num_admins == 0:
            if site.days_without_admin > 7:
                site.suspend_now("No site admin for more than a week")
                site.disable()
                EmailMessage(
                    subject="Your UIS Managed Web Server '%s' has been suspended" % site.name,
                    body="You are receiving this message because your email address, or an email alias that includes "
                         "you as a recipient, has been configured as the contact address for the UIS Managed Web "
                         "Server '%s'.\n\nThe Managed Web Server '%s' had no administrators for the last week "
                         "and has therefore been automatically suspended. It will be deleted in 2 weeks if no action "
                         "is taken.\n\nIf you think this should had not have happened, contact %s\n\n"
                         % (site.name, site.name,
                            getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')),
                    from_email="Managed Web Service Support <%s>"
                               % getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk'),
                    to=[site.email],
                    headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
                ).send()
            else:
                site.days_without_admin += 1
                site.save()
                EmailMessage(
                    subject="Your UIS Managed Web Server '%s' will be suspended" % site.name,
                    body="You are receiving this message because your email address, or an email alias that includes "
                         "you as a recipient, has been configured as the contact address for the UIS Managed Web "
                         "Server '%s'.\n\nThe Managed Web Server '%s' has no administrators and it will be suspended "
                         "in %s days if you do not contact %s and arrange to have at lease one administrator "
                         "added.\n\n" % (
                            site.name, site.name, str(8-site.days_without_admin),
                            getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')
                         ),
                    from_email="Managed Web Service Support <%s>"
                               % getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk'),
                    to=[site.email],
                    headers={'Return-Path': getattr(settings, 'EMAIL_MWS3_SUPPORT', 'mws-support@uis.cam.ac.uk')}
                ).send()
        else:
            site.days_without_admin = 0
            site.save()


@shared_task
def reject_or_accepted_old_domain_names_requests():
    # number of days grace before a domain name request is denied
    grace_days = settings.MWS_DOMAIN_NAME_GRACE_DAYS

    for domain_name in DomainName.objects.filter(status='requested',
                                                 requested_at__lt=(now()-timedelta(days=grace_days))):
        from apimws.ipreg import get_nameinfo
        nameinfo = get_nameinfo(domain_name.name)
        if nameinfo['exists'] and "C" not in nameinfo['exists']:
            domain_name.reject_it(("This domain name request has been automatically denied due to the lack of answer "
                                   "from the domain name administrator after "
                                   "%s days.") % (grace_days,))
        else:
            domain_name.accept_it()

@shared_task
def validate_domains():
    '''
    Iterate over DomainName objects and delete all that have been in the 'deleted' for over grace_days,
    then set the remaining to:
     - global if they are visible to (currently) Google's nameservers
     - private if they are onl`y available to the Cambridge nameservers
     - deleted if they are visible to none of the above.
    '''
    grace_days = settings.MWS_DOMAIN_NAME_GRACE_DAYS
    active_states = ['accepted', 'private', 'global', 'deleted']

    for domainname in DomainName.objects.filter(status__in=active_states):
        if domainname.status == 'deleted':
            expiry = now - (now()-timedelta(days=grace_days)):
            if domainname.updated_at <= expiry:
                domainname.delete()
        else:
            status = domainname.validate()
            if status != domainname.status:
                domainname.save()

