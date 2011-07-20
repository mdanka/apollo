from django.conf.urls.defaults import *
from django.conf import settings
from tastypie.resources import ModelResource
from tastypie.api import Api
import inspect
# iteratively import all resources
for app in settings.INSTALLED_APPS:
    try:
        exec 'from %s.api import *' % app
    except ImportError:
        pass

api = Api()

# dynamically load all the resources
local_vars = locals()
resources = filter(lambda klass: inspect.isclass(local_vars[klass]) \
    and issubclass(local_vars[klass], ModelResource) and local_vars[klass] != ModelResource, local_vars.keys())

for resource in resources:
    api.register(local_vars[resource]())
    
urlpatterns = patterns('',
    url(r'^api/', include(api.urls)),
)

#authentication urls
urlpatterns += patterns('',
    (r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'psc/login.html'}),
    (r'^accounts/logout/$', 'django.contrib.auth.views.logout_then_login')
)
