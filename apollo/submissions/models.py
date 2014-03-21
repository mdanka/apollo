from ..core import db
from ..deployments.models import Deployment
from ..formsframework.models import Form
from ..locations.models import Location
from ..participants.models import Participant
from ..users.models import User
from datetime import datetime
from flask.ext.mongoengine import BaseQuerySet
from mongoengine import Q
from pandas import DataFrame


class SubmissionQuerySet(BaseQuerySet):
    # most of the fields below are DBRef fields or not useful to
    # our particular use case.
    DEFAULT_EXCLUDED_FIELDS = [
        'id', 'form', 'created', 'updated', 'location', 'contributor'
    ]

    def filter_in(self, location):
        param = 'location_name_path__{}'.format(location.location_type)
        query_kwargs = {
            param: location.name
        }
        return self(Q(location=location) | Q(**query_kwargs))

    def to_dataframe(self, selected_fields=None, excluded_fields=None):
        if excluded_fields:
            qs = self.exclude(*excluded_fields)
        else:
            qs = self.exclude(*SubmissionQuerySet.DEFAULT_EXCLUDED_FIELDS)
        if selected_fields:
            qs = self.only(*selected_fields)

        return DataFrame(list(qs.as_pymongo()))


# Submissions
class Submission(db.DynamicDocument):
    '''Submissions represent data collected by participants in response to
    questions in Checklist and Critical Incident forms. Submissions are created
    prior to data input and are updated whenever data is received. The only
    exception is for the storage of Critical Incident reports which create
    submissions when data input is received.

    The :class:`core.documents.Submission` model
    is a :class:`mongoengine.DynamicDocument` and hence, most of it's
    functionality isn't stored within the model and gets defined at run time
    depending on the configuration of forms, form groups and form fields.

    :attr:`updated` is a :class:`mongoengine.db.DateTimeField` that stores the
    last time the submission was updated.

    :attr:`created` is a :class:`mongoengine.db.DateTimeField` that stores the
    date of creation for the submission.

    :attr:`contributor` stores the contributing participant for
    this submission.

    :attr:`form` provides a reference to the form that the submission was
    made for.
    '''

    form = db.ReferenceField('Form')
    contributor = db.ReferenceField('Participant')
    location = db.ReferenceField('Location')
    created = db.DateTimeField()
    updated = db.DateTimeField()
    completion = db.DictField()

    deployment = db.ReferenceField(Deployment)

    meta = {
        'queryset_class': SubmissionQuerySet,
    }

    def _update_completion_status(self):
        '''Computes the completion status of each form group for a submission.
        Should be called automatically on save, preferably in the `clean`
        method.'''
        for group in self.form.groups:
            completed = [f.name in self for f in group.fields]

            if all(completed):
                self.completion[group] = 'Complete'
            elif any(completed):
                self.completion[group] = 'Partial'
            else:
                self.completion[group] = 'Missing'


class VersionSequenceField(db.SequenceField):
    '''A subclass of :class: `mongoengine.fields.SequenceField` for
    automatically updating version numbers'''

    def get_sequence_name(self):
        obj_id = self.owner_document.submission._id
        return '_'.join(('version', 'seq', str(obj_id)))


class SubmissionVersion(db.Document):
    '''Stores versions of :class: `core.documents.Submission`
    instances'''
    submission = db.ReferenceField(Submission, required=True)
    data = db.StringField(required=True)
    version = VersionSequenceField()
    timestamp = db.DateTimeField(default=datetime.utcnow())
    changed_by = db.ReferenceField(User, required=True)

    deployment = db.ReferenceField(Deployment)

    meta = {
        'ordering': ['-version', '-timestamp']
    }


class SubmissionComment(db.Document):
    '''Stores user comments.'''
    submission = db.ReferenceField(Submission)
    user = db.ReferenceField(User)
    comment = db.StringField()
    submit_date = db.DateTimeField(default=datetime.utcnow())

    deployment = db.ReferenceField(Deployment)
