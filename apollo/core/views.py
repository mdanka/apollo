from __future__ import absolute_import
from __future__ import unicode_literals
from logging import getLogger
from flask import (
    Blueprint, flash, g, redirect, render_template,
    request, session, url_for
)
from flask.ext.babel import lazy_gettext as _
from apollo.core.forms import (
    generate_event_selection_form, generate_location_edit_form
)
from apollo.core.models import Event, Location, Participant

PAGE_SIZE = 25
core = Blueprint('core', __name__, template_folder='templates',
                 static_folder='static', static_url_path='/core/static')
logger = getLogger(__name__)


def _get_event(container):
    from mongoengine import ValidationError

    try:
        _id = container.get('event')
        if not _id:
            return Event.default()

        event = Event.objects.with_id(_id)
    except (KeyError, TypeError, ValueError, ValidationError) as e:
        logger.exception(e)
        event = Event.default()

    return event


@core.app_errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


@core.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@core.app_errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@core.route('/')
def index():
    event = _get_event(session)
    return event.to_json()


@core.route('/event', methods=['GET', 'POST'])
def event_selection():
    page_title = _('Select event')
    template_name = 'core/event_selection.html'

    if request.method == 'GET':
        form = generate_event_selection_form(g.deployment)
    elif request.method == 'POST':
        form = generate_event_selection_form(g.deployment, request.form)

        if form.validate():
            try:
                event = Event.objects.get(pk=form.event.data)
            except Event.DoesNotExist:
                flash(_('Selected event not found'))
                return render_template(
                    template_name,
                    form=form,
                    page_title=page_title
                )

            session['event'] = event.id
            return redirect(url_for('core.index'))

    return render_template(template_name, form=form, page_title=page_title)


@core.route('/location/<pk>', methods=['GET', 'POST'])
def location_edit(pk):
    template_name = 'core/location_edit_2.html'
    event = _get_event(session)
    location = Location.objects.get_or_404(pk=pk, events=event)
    page_title = _('Edit location: %(name)s', name=location.name)

    if request.method == 'GET':
        form = generate_location_edit_form(event, **location._data)
    else:
        form = generate_location_edit_form(event, request.form)

        if form.validate():
            form.populate_obj(location)
            location.save()

            return redirect(url_for('core.location_list'))

    return render_template(template_name, form=form, page_title=page_title)


@core.route('/participants/<int:page>')
def participant_list(page=1):
    event = _get_event(session)
    page_title = _('Participants')
    template_name = 'core/participant_list.html'

    participants = Participant.objects(events=event).paginate(page=page, per_page=PAGE_SIZE)
    return render_template(template_name, page_title=page_title, participants=participants)
