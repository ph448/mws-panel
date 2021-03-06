# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-02-05 11:04
from __future__ import unicode_literals

from django.db import migrations

PHPLIB_NEW_NAMES = {
 "libawl-php": "awl",
 "libgv-php5": "gv",
 "libmarkdown-php": "markdown",
 "libnusoap-php": "nusoap",
 "libownet-php": "ownet",
 "php5-adodb": "adodb",
 "php5-dev": "dev",
 "php5-sasl": "sasl",
 "php5-cgi": "cgi",
 "php5-enchant": "enchant",
 "php5-fpm": "fpm",
 "php5-xsl": "xsl",
 "php5-gearman": "gearman",
 "php5-geoip": "geoip",
 "php5-gmp": "gmp",
 "php5-gnupg": "gnupg",
 "php5-igbinary": "igbinary",
 "php5-exactimage": "exactimage",
 "php5-gdcm": "gdcm",
 "php5-vtkgdcm": "vtkgdcm",
 "php5-geos": "geos",
 "php5-lasso": "lasso",
 "libfpdf-tpl-php": "fpdf-tpl",
 "libfpdi-php": "fpdi",
 "libgraphite-php": "graphite",
 "libkohana2-modules-php": "kohana2-modules",
 "libkohana2-php": "libkohana2",
 "liboauth-php": "oauth",
 "libpuzzle-php": "puzzle",
 "php5-mapscript": "mapscript",
 "libow-php5": "ow",
 "libarc-php": "arc",
 "php5-mysqlnd-ms": "mysqlnd-ms",
 "php5-svn": "svn",
 "php5-tokyo-tyrant": "tokyo-tyrant",
 "php5-librdf": "rdf",
 "libsparkline-php": "sparkline",
 "php5-uprofiler": "uprofiler",
 "php5-xcache": "xcache",
 "php5-xhprof": "xhprof",
 "php5-imagick": "imagick",
 "php5-imap": "imap",
 "php5-interbase": "interbase",
 "php5-intl": "intl",
 "php5-libvirt-php": "libvirt",
 "php5-mcrypt": "mcrypt",
 "php5-memcache": "memcache",
 "php5-memcached": "memcached",
 "php5-mongo": "mongo",
 "php5-msgpack": "msgpack",
 "php5-oauth": "oauth",
 "php5-odbc": "odbc",
 "php5-pecl-http": "pecl-http",
 "php5-pecl-http-dev": "pecl-http-dev",
 "php5-pgsql": "pgsql",
 "php5-dbg": "dbg",
 "php5-phpdbg": "phpdbg",
 "php5-pinba": "pinba",
 "php5-propro": "propro",
 "php5-propro-dev": "propro-dev",
 "php5-pspell": "pspell",
 "php5-radius": "radius",
 "php5-raphf": "raphf",
 "php5-raphf-dev": "raphf-dev",
 "php5-recode": "recode",
 "php5-redis": "redis",
 "php5-remctl": "remctl",
 "php5-rrd": "rrd",
 "php5-snmp": "snmp",
 "php5-solr": "solr",
 "php5-ssh2": "ssh2",
 "php5-stomp": "stomp",
 "php5-sybase": "sybase",
 "php5-tidy": "tidy",
 "php5-twig": "twig",
 "php5-xdebug": "xdebug",
 "php5-xmlrpc": "xmlrpc",
 "php5-yac": "yac",
 "php5-zmq": "zmq",
 "php5-apcu": "apcu",
}

def rename_phplibs(apps, schema_editor):
    PHPLib = apps.get_model('apimws','PHPLib')
    for lib in PHPLib.objects.all():
        newlib = PHPLib()
        newlib.pk = PHPLIB_NEW_NAMES[lib.pk]
        newlib.description = lib.description
        newlib.available = lib.available
        newlib.save()
        newlib.services.set(lib.services.all())
        newlib.packages.set(lib.packages.all())
        lib.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('apimws', '0013_auto_20190204_1140'),
    ]

    operations = [
        migrations.RunPython(rename_phplibs),
    ]
