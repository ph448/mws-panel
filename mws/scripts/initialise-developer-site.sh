cd /usr/src/app
./manage.py migrate
./manage.py collectstatic --noinput
./manage.py loaddata mwsauth/fixtures/dev_test_users.yaml
./manage.py shell <<EOL
from django.contrib.auth.models import User
from sitesmanagement.tests.tests import pre_create_site
u = User.objects.get(username='test0001')
# need to set this here because creating mwsauth.MWSUser in fixture sets it back to false
u.is_active = True
u.save()
pre_create_site()
EOL
