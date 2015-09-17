from django.contrib import admin
from reversion import VersionAdmin
from apimws.models import AnsibleConfiguration, ApacheModules, PHPLib


class AnsibleConfigurationAdmin(VersionAdmin):

    model = AnsibleConfiguration
    list_display = ('key', 'value', 'service')


admin.site.register(AnsibleConfiguration, AnsibleConfigurationAdmin)
admin.site.register(ApacheModules, VersionAdmin)
admin.site.register(PHPLib, VersionAdmin)
