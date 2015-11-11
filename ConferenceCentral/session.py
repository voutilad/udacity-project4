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
from profile import ProfileApi
from utils import getUserId, get_from_webkey

SESSION_DEFAULTS = {
    'duration': 60,
    'typeOfSession': SessionType.LECTURE
}

VOID = message_types.VoidMessage

WISHLIST_REQUEST = endpoints.ResourceContainer(
    VOID,
    websafeSessionKey=messages.StringField(1)
)

CONF_GET_REQUEST = endpoints.ResourceContainer(
    VOID,
    websafeConferenceKey=messages.StringField(1),
)


@API.api_class(resource_name='sessions')
class SessionApi(remote.Service):
    """Session API for ConferenceCentral"""
    #
    # - - - Endpoints - - - - - - - - - - - - - - - - - - -
    #

    # - - - WishListing - - - - - - - - - - - - - - - - - - -
    @endpoints.method(WISHLIST_REQUEST, BooleanMessage, path='wishlist/{websafeSessionKey}',
                      http_method='PUT', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """
        Add a Session to a conference Wishlist
        :param request:
        :return:
        """
        return self._wishlist(request, True)

    @endpoints.method(WISHLIST_REQUEST, BooleanMessage, path='wishlist/{websafeSessionKey}',
                      http_method='DELETE', name='removeSessionFromWishlist')
    def removeSessionFromWishlist(self, request):
        """
        Removes a Session from a user's wishlist for the containing Conference
        """
        return self._wishlist(request, False)

    @endpoints.method(VOID, WishlistForms, path='wishlists',
                      http_method='GET', name='getWishlists')
    def getWishlists(self, request):
        """
        Endpoint for retrieving all wishlists for a requesting user
        """
        # TODO: add max records and sortability
        prof = ProfileApi.getProfileFromUser()  # get user Profile
        wishlists = ConferenceWishlist.query(ancestor=prof.key).fetch()
        return WishlistForms(
            items=[self._copyWishlistToForm(wishlist) for wishlist in wishlists]
        )

    @endpoints.method(SessionQueryForm, SessionForms, path='sessions/query',
                      http_method='POST', name='querySessions')
    def querySessions(self, request):
        """Queries Session objects in datastore"""

        return SessionForms(items=[])


    @endpoints.method(SessionQueryForm, SessionForms, path='sessions/filter/type',
                      http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Given a conference, return all sessions of a specified type (eg lecture, keynote, workshop)"""
        wsck = request.websafeConfKey
        c_key = ndb.Key(urlsafe=wsck)
        if not c_key.get():
            raise endpoints.NotFoundException('No conference found with key: %s' % wsck)

        sessions = Session.query(ancestor=c_key) \
            .filter(Session.typeOfSession == request.typeOfSession)

        return SessionForms(items=[SessionApi.session_to_form(session) for session in sessions])

    @endpoints.method(message_types.VoidMessage, SessionForms, path='sessions/filter/speaker')
    def getSessionsBySpeaker(self, request):
        """Given a speaker, return all sessions given by this particular speaker, across all conferences"""
        pass

    @endpoints.method(SessionForm, SessionForm, path='session',
                      http_method='POST', name='createSession')
    def createSession(self, request):
        """Creates a new session. Only available  to the organizer of the conference"""
        return self._createSessionObject(request)

    #
    # - - - Profile Public Methods - - - - - - - - - - - - - - - - - - -
    #
    @staticmethod
    def session_to_form(session):
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
    #
    # - - - Profile Private Methods - - - - - - - - - - - - - - - - - - -
    #

    @ndb.transactional(xg=True)
    def _wishlist(self, request, add=True):
        """

        :param request: Wishlist RPC Request [VoidMessage, session key in query string]
        :param add: whether to add (True) to the wishlist or remove from a wishlist (False)
        :return: BooleanMessage - True if successful, False if failure
        """
        prof = ProfileApi.getProfileFromUser()  # get user Profile
        session = get_from_webkey(request.websafeSessionKey)  # get session to wishlist

        if not session:
            raise endpoints.NotFoundException('Not a valid session')

        # see if the wishlist exists
        wishlist = ConferenceWishlist().query(ancestor=prof.key) \
            .filter(ConferenceWishlist.conferenceKey == session.key.parent().urlsafe()) \
            .get()

        # User requested to add to the wishlist, so create if needed
        if not wishlist:
            if add:
                # need to create the wishlist first
                conf_key = session.key.parent().urlsafe()
                wishlist = ConferenceWishlist(conferenceKey=conf_key, parent=prof.key)
            else:
                # remove request, but no wishlist!
                raise endpoints.NotFoundException('Nothing wishlisted for Conference')

        # update wishlist by adding/removing session key
        wssk = session.key.urlsafe()
        if wssk not in wishlist.sessionKeys:
            if add:
                # add the key
                wishlist.sessionKeys.append(wssk)
                wishlist.put()
            else:
                # can't remove a nonexistant key
                raise endpoints.NotFoundException('Session not in wishlist for Conference')
        else:
            # key already exists
            if add:
                # session already wishlisted, so return error
                return BooleanMessage(data=False)
            else:
                # remove key from wishlist
                wishlist.sessionKeys.remove(wssk)

                # if wishlist is empty, remove the wishlist. else just update.
                if len(wishlist.sessionKeys) == 0:
                    wishlist.key.delete()
                else:
                    wishlist.put()

        return BooleanMessage(data=True)

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

