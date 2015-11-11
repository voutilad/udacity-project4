#!/usr/bin/env python

"""
session.py -- ConferenceCentral Session methods;
    uses Google Cloud Endpoints

"""

__author__ = 'voutilad@gmail.com (Dave Voutila)'

from datetime import datetime

import endpoints
from google.appengine.ext import ndb
from protorpc import message_types
from protorpc import messages
from protorpc import remote

from models import BooleanMessage
from models import ConferenceWishlist
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionQueryForm
from models import SessionType
from models import WishlistForm, WishlistForms
from settings import API
from utils import getUserId, getModelByWebKey

SESSION_DEFAULTS = {
    'duration': 60,
    'typeOfSession': SessionType.LECTURE
}

WISHLIST_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1)
)

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)


@API.api_class(resource_name='session')
class SessionApi(remote.Service):
    """Session API for ConferenceCentral"""

    # - - - WishListing - - - - - - - - - - - - - - - - - - -
    @endpoints.method(WISHLIST_REQUEST, SessionForm, path='session/{websafeSessionKey}/wishlist',
                      http_method='PUT', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        prof = self._getProfileFromUser()  # get user Profile
        session = getModelByWebKey(request.websafeSessionKey)  # get session to wishlist

        # see if the wishlist exists

        wishlist = ConferenceWishlist().query(ancestor=prof.key) \
            .filter(ConferenceWishlist.conferenceKey == session.key.parent().urlsafe()) \
            .get()
        if not wishlist:
            conf_key = session.key.parent().urlsafe()
            wishlist = ConferenceWishlist(conferenceKey=conf_key, parent=prof.key)

        # update wishlist
        if session.key not in wishlist.sessionKeys:
            wishlist.sessionKeys.append(session.key.urlsafe())
            wishlist.put()
        else:
            print 'Attempt to add duplicate to wishlist.'

        return self._copySessionToForm(session)

    @endpoints.method(WISHLIST_REQUEST, BooleanMessage, path='session/{websafeSessionKey}/wishlist',
                      http_method='DELETE', name='removeSessionFromWishlist')
    def removeSessionFromWishlist(self, request):
        """
        Removes a Session from a user's wishlist for the containing Conference
        """
        wssk = request.websafeSessionKey
        prof = self._getProfileFromUser()  # get user Profile

        # see if the wishlist exists
        wishlist = ConferenceWishlist().query(ancestor=prof.key).get()
        if not wishlist:
            raise endpoints.NotFoundException('No wishlist found.')

        wishlist.sessionKeys.remove(wssk)
        wishlist.put()

        return BooleanMessage(data=True)

    @endpoints.method(CONF_GET_REQUEST, SessionForms, path='conference/{websafeConferenceKey}/wishlist',
                      http_method='GET', name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """
        Gets the list of sessions wishlisted by a User given a Conference.
        """
        prof = self._getProfileFromUser()  # get user Profile

        wishlist = ConferenceWishlist().query(ancestor=prof.key) \
            .filter(ConferenceWishlist.conferenceKey == request.websafeConferenceKey) \
            .get()

        if not wishlist:
            raise endpoints.NotFoundException('No wishlist for conference with key %s' % request.websafeConferenceKey)

        s_keys = [ndb.Key(urlsafe=sessionKey) for sessionKey in wishlist.sessionKeys]
        sessions = ndb.get_multi(s_keys)

        return SessionForms(items=[self._copySessionToForm(s) for s in sessions])

    @endpoints.method(message_types.VoidMessage, WishlistForms, path='getWishlists',
                      http_method='GET', name='getWishlists')
    def getWishlists(self, request):
        """
        Endpoint for retrieving all wishlists for a requesting user
        """
        # TODO: add max records and sortability
        prof = self._getProfileFromUser()  # get user Profile
        wishlists = ConferenceWishlist.query(ancestor=prof.key).fetch()
        return WishlistForms(
            items=[self._copyWishlistToForm(wishlist) for wishlist in wishlists]
        )

    def _copyWishlistToForm(self, wishlist):
        """
        Converts a wishlist model object into it's rpc message format.
        :param wishlist: ConferenceWishlist object to conver into ConferenceWishlistForm
        :return: ConferenceWishlistForm
        """
        if not wishlist or not isinstance(wishlist, ndb.Model):
            raise endpoints.ServiceException(
                'endpoint cannot create WishlistForm from type %' % str(type(wishlist))
            )

        wf = WishlistForm()
        wf.websafeConfKey = wishlist.conferenceKey
        wf.websafeSessionKeys = wishlist.sessionKeys
        return wf

    # - - - Session objects - - - - - - - - - - - - - - - - -
    @endpoints.method(SessionQueryForm, SessionForms, path='querySessions',
                      http_method='POST', name='querySessions')
    def querySessions(self, request):
        """Queries Session objects in datastore"""

        return SessionForms(items=[])

    @endpoints.method(CONF_GET_REQUEST, SessionForms, path='conference/{websafeConferenceKey}/sessions',
                      http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Given a conference, return all sessions
            Input: websafeConferenceKey
        """
        wsck = request.websafeConferenceKey
        conf_key = ndb.Key(urlsafe=wsck)
        if not conf_key.get():
            raise endpoints.NotFoundException('No conference found with key: %s' % wsck)

        sessions = Session.query(ancestor=conf_key)

        return SessionForms(items=[self._copySessionToForm(session) for session in sessions])

    @endpoints.method(SessionQueryForm, SessionForms,
                      path='getConferenceSessionsByType',
                      http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Given a conference, return all sessions of a specified type (eg lecture, keynote, workshop)"""
        wsck = request.websafeConfKey
        c_key = ndb.Key(urlsafe=wsck)
        if not c_key.get():
            raise endpoints.NotFoundException('No conference found with key: %s' % wsck)

        sessions = Session.query(ancestor=c_key) \
            .filter(Session.typeOfSession == request.typeOfSession)

        return SessionForms(items=[self._copySessionToForm(session) for session in sessions])

    def getSessionsBySpeaker(self, request):
        """Given a speaker, return all sessions given by this particular speaker, across all conferences"""
        pass

    @endpoints.method(SessionForm, SessionForm, path='session',
                      http_method='POST', name='createSession')
    def createSession(self, request):
        """Creates a new session. Only available  to the organizer of the conference"""
        return self._createSessionObject(request)

    def _createSessionObject(self, request):
        """Creates a new Session object and inserts it into storage returning the created value."""
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Session 'name' field required")

        # TODO: GENERICIZE THE RPC/NBD TRANSLATION?!
        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeConfKey']

        # add default values for those missing (both data model & outbound Message)
        for df in SESSION_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SESSION_DEFAULTS[df]
                setattr(request, df, SESSION_DEFAULTS[df])

        # TODO: validate session dates are sane i.e. within the start/end of the conf.
        data['date'] = datetime.strptime(data['date'][:10], '%Y-%m-%d').date()
        data['startTime'] = datetime.strptime(data['startTime'][:6], '%H:%M').time()

        # fetch the key of the ancestor conference
        conf_key = ndb.Key(urlsafe=request.websafeConfKey)
        conf = conf_key.get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConfKey
            )

        # check that user is conference owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException('Only the conference owner can create sessions.')

        s_id = Session.allocate_ids(size=1, parent=conf_key)[0]
        s_key = ndb.Key(Session, s_id, parent=conf_key)
        data['key'] = s_key
        data['conferenceKey'] = request.websafeConfKey

        # create and persist the Session
        # TODO: email organizer?
        Session(**data).put()
        return request

    def _copySessionToForm(self, session):
        """Copy relevant fields from Session to SessionForm."""
        # TODO: genericize!!!
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(session, field.name):
                # matching/common fields between classes
                if field.name in ['date', 'startTime']:
                    setattr(sf, field.name, str(session.date))
                else:
                    setattr(sf, field.name, getattr(session, field.name))
            elif field.name == 'websafeConfKey':
                setattr(sf, field.name, session.key.urlsafe())

        return sf
