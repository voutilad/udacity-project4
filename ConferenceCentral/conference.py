#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

from datetime import datetime

import endpoints
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from protorpc import message_types
from protorpc.message_types import VoidMessage
from protorpc import messages
from protorpc import remote

from models import BooleanMessage
from models import Session
from models import SessionForms
from models import Conference
from models import ConferenceWishlist
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForms
from models import ConflictException
from models import Profile
from models import StringMessage
from settings import API
from utils import getUserId

import queryutil
from profile import ProfileApi

__author__ = 'voutilad@gmail.com (Dave Voutila)'

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

CONF_DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"],
}

CONF_GET_REQUEST = endpoints.ResourceContainer(
    VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1)
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@API.api_class(resource_name='conferences')
class ConferenceApi(remote.Service):
    """
    Conference API v1.0

    API Conventions:
        /conference/* - operates on or returns a single Conference record
        /conferences/* - operates on or returns multiple Conference records

    """

    #
    # - - - Endpoints - - - - - - - - - - - - - - - - - - -
    #
    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
                      http_method='POST', name='createConference')
    def create(self, request):
        """
        Creates a new Conference object
        :param request: ConferenceForm message with Conference details
        :return: created ConferenceForm for new Conference
        """
        return self._create(request)

    @endpoints.method(CONF_POST_REQUEST, ConferenceForm, path='conference/{websafeConferenceKey}',
                      http_method='PUT', name='updateConference')
    def update(self, request):
        """
        Update conference w/provided fields & return w/updated info from given ConferenceForm
        :param request: Conference POST Request [ConferenceForm, conference key string]
        :return: Updated ConferenceForm
        """
        return self._update(request)

    @endpoints.method(CONF_GET_REQUEST, ConferenceForm, path='conference/{websafeConferenceKey}',
                      http_method='GET', name='getConference')
    def get(self, request):
        """
        Return requested conference (by websafeConferenceKey).
        :param request: Conference GET Request [Void, conference key in query string]
        :return: matching ConferenceForm
        """
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return conf.to_form(getattr(prof, 'displayName'))

    @endpoints.method(VoidMessage, ConferenceForms, path='conferences/created',
                      http_method='POST', name='getConferencesCreated')
    def get_created(self, request):
        """
        Return Conferences created by the requesting User
        :param request: Void RPC Message
        :return: ConferenceForms containing user-created ConferenceForm's
        """
        if not isinstance(request, message_types.VoidMessage):
            raise endpoints.BadRequestException()

        # make sure user is auth'd
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[conf.to_form(getattr(prof, 'displayName')) for conf in confs]
        )

    @endpoints.method(CONF_GET_REQUEST, SessionForms, path='conference/{websafeConferenceKey}/sessions',
                      http_method='GET', name='getConferenceSessions')
    def get_sessions(self, request):
        """
        Given a conference, return all sessions.
        :param request: Conference GET Request [Void, query string with conference key]
        :return: SessionForms with matching SessionForm's
        """
        wsck = request.websafeConferenceKey
        conf_key = ndb.Key(urlsafe=wsck)
        if not conf_key.get():
            raise endpoints.NotFoundException('No conference found with key: %s' % wsck)

        sessions = Session.query(ancestor=conf_key)

        return SessionForms(items=[s.to_form() for s in sessions])

    @endpoints.method(CONF_GET_REQUEST, SessionForms, path='conference/{websafeConferenceKey}/wishlist',
                      http_method='GET', name='getSessionsInWishlist')
    def get_wishlist(self, request):
        """
        Gets the list of sessions wishlisted by a User given a Conference.
        :param request: Conference GET Request [VoidMessage, conference key in query string]
        :return: SessionForms
        """
        prof = ProfileApi.profile_from_user()  # get user Profile

        wishlist = ConferenceWishlist().query(ancestor=prof.key) \
            .filter(ConferenceWishlist.conferenceKey == request.websafeConferenceKey) \
            .get()

        if not wishlist:
            raise endpoints.NotFoundException('No wishlist for conference with key %s' % request.websafeConferenceKey)

        s_keys = [ndb.Key(urlsafe=sessionKey) for sessionKey in wishlist.sessionKeys]
        sessions = ndb.get_multi(s_keys)

        return SessionForms(items=[s.to_form for s in sessions])

    @endpoints.method(ConferenceQueryForms, ConferenceForms, path='conferences/query',
                      http_method='POST', name='queryConferences')
    def query(self, request):
        """
        Query Conferences in Datastore
        :param request: ConferenceQueryForms with one or many ConferenceQueryForm's
        :return: ConferenceForms with matching ConferenceForm's, if any
        """
        # convert message types for now until we fix the js client side logic
        query_filters = [
            queryutil.QueryFilter(
                field=f.field,
                operator=queryutil.QueryOperator.lookup_by_name(f.operator),
                value=f.value) for f in request.filters]
        query_form = queryutil.QueryForm(target=queryutil.QueryTarget.CONFERENCE,
                                         filters=query_filters)
        conferences = queryutil.query(query_form)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        if not profiles or profiles == [None]:
            # bootstrapping issue as the user hasn't created their profile obj
            profiles = [Profile(key=org) for org in organisers]

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            if hasattr(profile, 'displayName'):
                names[profile.key.id()] = getattr(profile, 'displayName')
            else:
                # Chances are someone wasn't forced to set their displayName yet!
                names[profile.key.id()] = ''

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[conf.to_form(names[conf.organizerUserId]) for conf in conferences]
        )

    @endpoints.method(VoidMessage, ConferenceForms, path='conferences/attending',
                      http_method='GET', name='getConferencesToAttend')
    def get_attending(self, request):
        """
        Get Conferences the calling user is attending (i.e. registered for)
        :param request:
        :return: ConferenceForms
        """
        if not isinstance(request, message_types.VoidMessage):
            raise endpoints.BadRequestException()

        prof = ProfileApi.profile_from_user()  # get user Profile
        conf_keys = prof.conferencesToAttend # Changed from original code since now we store Keys

        if len(conf_keys) == 0:
            # user hasn't registered for anything, so bail out of this method
            return ConferenceForms()

        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[conf.to_form(names[conf.organizerUserId])
                                      for conf in conferences]
                               )

    # --- Registration ---

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage, path='conference/{websafeConferenceKey}/register',
                      http_method='POST', name='registerForConference')
    def register(self, request):
        """
        Register user for a given Conference
        :param request: Conference GET Request [Void, Conference key in query string]
        :return: BooleanMessage with True if successful, False if failure
        """
        return self._register(request)

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage, path='conference/{websafeConferenceKey}/unregister',
                      http_method='DELETE', name='unregisterFromConference')
    def unregister(self, request):
        """
        Unregister user for selected conference.
        :param request: Conference GET Request [Void, Conference key in query string]
        :return: BooleanMessage with True if successful deregistration, False if failure
        """
        return self._register(request, reg=False)

    @endpoints.method(VoidMessage, StringMessage, path='conferences/announcements',
                      http_method='GET', name='getAnnouncement')
    def get_announcement(self, request):
        """
        Get Announcement from Memcache
        :param request: VoidMessage
        :return:
        """
        if not isinstance(request, message_types.VoidMessage):
            raise endpoints.BadRequestException()

        return StringMessage(data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or '')

    @endpoints.method(VoidMessage, ConferenceForms, path='conferences/filterPlayground',
                      http_method='GET', name='filterPlayground')
    def filter_playground(self, request):
        """
        Filter Playground method
        :param request:
        :return:
        """
        if not isinstance(request, message_types.VoidMessage):
            raise endpoints.BadRequestException()

        form = queryutil.QueryForm()
        form.target = queryutil.QueryTarget.CONFERENCE
        qfilter = queryutil.QueryFilter(
            field='CITY',
            operator=queryutil.QueryOperator.EQ,
            value='London'
        )
        form.filters = [qfilter]

        q = queryutil.query(form)

        return ConferenceForms(items=[conf.to_form() for conf in q])

    #
    # - - - Conference Public Methods - - - - - - - - - - - - - - - - - - -
    #

    @staticmethod
    def cache_announcement():
        """
        Create Announcement & assign to memcache; used by memcache cron job & putAnnouncement().

        :return: announcement string
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement

    #
    # - - - Conference Private Methods - - - - - - - - - - - - - - - - - - -
    #

    def _create(self, request):
        """
        Create or update Conference object, returning ConferenceForm/request.
        :param request:
        :return:
        """
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in CONF_DEFAULTS:
            if data[df] in (None, []):
                data[df] = CONF_DEFAULTS[df]
                setattr(request, df, CONF_DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
                              'conferenceInfo': repr(request)},
                      url='/tasks/send_confirmation_email'
                      )
        return request

    @ndb.transactional()
    def _update(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # copy ConferenceForm/ProtoRPC Message into dict
        # data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return conf.to_form(getattr(prof, 'displayName'))

    def _query(self, request):
        """
        Return formatted query from the submitted filters.
        :param request:
        :return:
        """
        return queryutil.query(request)

    @ndb.transactional(xg=True)
    def _register(self, request, reg=True):
        """
        Register or unregister user for selected conference.
        :param request: RPC Message Request with a urlsafe Conference Key
        :param reg: whether to register (True) or unregister (False) the requesting User
        :return: BooleanMessage - True if successful, False if failure
        """
        prof = ProfileApi.profile_from_user()  # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        conf = c_key.get()
        if not conf:
            raise endpoints.NotFoundException('No conference found for key')

        # register
        if reg:
            # check if user already registered otherwise add
            if c_key in prof.conferencesToAttend:
                raise ConflictException('Already registered for this conference')

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException('There are no seats available.')

            # register user, take away one seat
            prof.conferencesToAttend.append(c_key)
            conf.seatsAvailable -= 1

            # update datastore
            prof.put()
            conf.put()

        # un-register
        else:
            # check if user already registered
            if c_key in prof.conferencesToAttend:
                # unregister user, add back one seat
                prof.conferencesToAttend.remove(c_key)
                conf.seatsAvailable += 1

                # update datastore
                prof.put()
                conf.put()
            else:
                return BooleanMessage(data=False)

        return BooleanMessage(data=True)
