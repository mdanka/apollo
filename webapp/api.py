from tastypie.resources import ModelResource
from tastypie.authentication import Authentication
from tastypie.authorization import Authorization, DjangoAuthorization
from tastypie.constants import ALL, ALL_WITH_RELATIONS
from tastypie import fields
from webapp.models import *
from rapidsms.models import Contact, Connection, Backend
from rapidsms.contrib.messagelog.models import Message

class LocationTypeResource(ModelResource):
    parent = fields.ForeignKey('self', 'parent', readonly=True, null=True, blank=True)
    
    class Meta:
        queryset = LocationType.objects.all()
        resource_name = 'location_type'
        filtering = {
            'name': ALL,
            'code': ALL,
            'parent': ALL_WITH_RELATIONS,
        }
        ordering = ['name', 'code']


class LocationResource(ModelResource):
    type = fields.ForeignKey(LocationTypeResource, 'type', readonly=True, null=True, blank=True)
    parent = fields.ForeignKey('self', 'parent', readonly=True, null=True, blank=True)
    
    class Meta:
        queryset = Location.objects.select_related()
        resource_name = 'location'
        filtering = {
            'name': ALL,
            'code': ALL,
            'type': ALL_WITH_RELATIONS,
            'parent': ALL_WITH_RELATIONS,
        }
        ordering = ['name', 'code']


class ContactRoleResource(ModelResource):
    class Meta:
        queryset = ObserverRole.objects.all()
        resource_name = 'contact_role'


class BackendResource(ModelResource):
    class Meta:
        queryset = Backend.objects.all()
        resource_name = 'backend'


class ConnectionResource(ModelResource):
    backend = fields.ForeignKey(BackendResource, 'backend', full=True)

    class Meta:
        queryset = Connection.objects.select_related()
        resource_name = 'connection'
        allowed_methods = ['get', 'put']
        authentication = Authentication()
        authorization = Authorization()
        filtering = {
            'identity': ALL,
        }
        ordering = ['identity']


class ContactResource(ModelResource):
    role = fields.ForeignKey(ContactRoleResource, 'role', full=True)
    location = fields.ForeignKey(LocationResource, 'location', full=True)
    supervisor = fields.ForeignKey('self', 'supervisor', null=True, blank=True, full=True)
    connections = fields.ToManyField(ConnectionResource, 'connection_set', readonly=True, full=True)
    
    class Meta:
        queryset = Contact.objects.select_related()
        resource_name = 'contact'
        allowed_methods = ['get', 'put', 'post', 'delete']
        authentication = Authentication()
        authorization = Authorization()


class ChecklistFormResource(ModelResource):
    class Meta:
        queryset = ChecklistForm.objects.all()
        resource_name = 'checklist_form'   


class ChecklistQuestionTypeResource(ModelResource):
    class Meta:
        queryset = ChecklistQuestionType.objects.all()
        resource_name = 'checklist_question_type'


class ChecklistQuestionOptionResource(ModelResource):
    class Meta:
        queryset = ChecklistQuestionOption.objects.all()
        resource_name = 'checklist_question_option'


class ChecklistQuestionResource(ModelResource):
    form = fields.ForeignKey(ChecklistFormResource, 'form', readonly=True)
    type = fields.ForeignKey(ChecklistQuestionTypeResource, 'type', readonly=True)
    options = fields.ToManyField(ChecklistQuestionOptionResource, 'options', readonly=True, full=True)
    
    class Meta:
        queryset = ChecklistQuestion.objects.select_related()
        resource_name = 'checklist_question'


class ChecklistResponseResource(ModelResource):
    question = fields.ForeignKey(ChecklistQuestionResource, 'question', readonly=True)
    
    class Meta:
        queryset = ChecklistResponse.objects.select_related()
        resource_name = 'checklist_response'
        allowed_methods = ['get', 'put', 'post', 'delete']
        authentication = Authentication()
        authorization = Authorization()


class ChecklistResource(ModelResource):
    location = fields.ForeignKey(LocationResource, 'location', full=True)
    observer = fields.ForeignKey(ContactResource, 'observer', full=True)
    responses = fields.ToManyField(ChecklistResponseResource, 'responses', full=True)
    
    class Meta:
        queryset = Checklist.objects.select_related()
        resource_name = 'checklist'
        allowed_methods = ['get', 'put', 'post', 'delete']
        authentication = Authentication()
        authorization = Authorization()


class IncidentFormResource(ModelResource):
    class Meta:
        queryset = IncidentForm.objects.all()
        resource_name = 'incident_form'

class IncidentResponseResource(ModelResource):
    form = fields.ForeignKey(IncidentFormResource, 'form', readonly=True)
    
    class Meta:
        queryset = IncidentResponse.objects.select_related()
        resource_name = 'incident_response'
        allowed_methods = ['get', 'put', 'post', 'delete']
        authentication = Authentication()
        authorization = Authorization()


class IncidentResource(ModelResource):
    location = fields.ForeignKey(LocationResource, 'location', full=True)
    observer = fields.ForeignKey(ContactResource, 'observer', full=True)
    responses = fields.ToManyField(IncidentResponseResource, 'responses', full=True)
    
    class Meta:
        queryset = Incident.objects.select_related()
        resource_name = 'incident'
        allowed_methods = ['get', 'put', 'post', 'delete']
        authentication = Authentication()
        authorization = Authorization()
        filtering = {
            'date': ALL,
            'observer': ALL_WITH_RELATIONS,
            'location': ALL_WITH_RELATIONS,
        }
        ordering = ['location', 'date', 'observer']
        
class MessageResource(ModelResource):
    contact = fields.ForeignKey(ContactResource, 'contact', full=True, readonly=True, null=True, blank=True)
    connection = fields.ForeignKey(ConnectionResource, 'connection', readonly=True, full=True)
    
    class Meta:
        queryset = Message.objects.select_related('contact', 'connection', 'connection__backend', 'connection__contact', 'contact__role', 'contact__location')
        resource_name = 'message'
        filtering = {
            'text': ('contains',),
            'direction': ('exact',),
            'connection': ALL_WITH_RELATIONS,
        }
        ordering = ['date', 'direction', 'connection', 'contact']