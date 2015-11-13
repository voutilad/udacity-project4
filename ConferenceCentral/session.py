#!/usr/bin/env python

"""
session.py -- ConferenceCentral Session methods;
    uses Google Cloud Endpoints

"""

__author__ = 'voutilad@gmail.com (Dave Voutila)'

from datetime import datetime

import endpoints
from google.appengine.ext import ndb
from protorpc.message_types import VoidMessage
from protorpc import messages
from protorpc import remote

from models import BooleanMessage
from models import ConferenceWishlist
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionQueryForm
from models import SessionType
from models import WishlistForms
from settings import API
from profile import ProfileApi
from utils import getUserId, get_from_webkey
import queryutil

SESSION_DEFAULTS = {
    'duration': 60,
    'typeOfSession': SessionType.LECTURE
}

WISHLIST_REQUEST = endpoints.ResourceContainer(
    VoidMessage,
    websafeSessionKey=messages.StringField(1)
)

CONF_GET_REQUEST = endpoints.ResourceContainer(
    VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)


@API.api_class(resource_name='sessions')
class SessionApi(remote.Service):
    """
    Session API for ConferenceCentral

    API Conventions:
        /session/* - operates on or returns a single Session record
        /sessions/* - operates on or returns multiple Session records
    """
    #
    # - - - Endpoints - - - - - - - - - - - - - - - - - - -
    #

    # - - - WishListing - - - - - - - - - - - - - - - - - - -
    @endpoints.method(WISHLIST_REQUEST, BooleanMessage, path='wishlist/{websafeSessionKey}',
                      http_method='PUT', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """
        Add a Session to a ConferenceWishlist
        :param request:
        :return:
        """
        return self._wishlist(request, True)

    @endpoints.method(WISHLIST_REQUEST, BooleanMessage, path='wishlist/{websafeSessionKey}',
                      http_method='DELETE', name='removeSessionFromWishlist')
    def removeSessionFromWishlist(self, request):
        """
        Remove a Session from a ConferenceWishlist
        :param request:
        :return:
        """
        return self._wishlist(request, False)

    @endpoints.method(VoidMessage, WishlistForms, path='wishlists',
                      http_method='GET', name='getWishlists')
    def getWishlists(self, request):
        """
        Endpoint for retrieving all wishlists for a requesting user
        :param request:
        :return:
        """
        # TODO: add max records and sortability
        prof = ProfileApi.profile_from_user()  # get user Profile
        wishlists = ConferenceWishlist.query(ancestor=prof.key).fetch()
        return WishlistForms(
            items=[wishlist.to_form() for wishlist in wishlists]
        )

    @endpoints.method(VoidMessage, SessionForms, path='sessions/query',
                      http_method='POST', name='querySessions')
    def querySessions(self, request):
        """
        Queries Session objects in datastore
        :param request:
        :return:
        """
        query_form = queryutil.QueryForm(target=queryutil.QueryTarget.SESSION)
        query_form.filters.append(queryutil.QueryFilter(
            field='TYPE',
            operator=queryutil.QueryOperator.NE,
            value='WORKSHOP'
        ))
        query_form.filters.append(queryutil.QueryFilter(
            field='START_TIME',
            operator=queryutil.QueryOperator.LT,
            value='19:00'
        ))

        stupid_time = datetime.combine(datetime.utcfromtimestamp(0), datetime.strptime('17:00', '%H:%M').time())

        junk = Session.query(Session.typeOfSession.IN([SessionType.LECTURE, SessionType.KEYNOTE]))
        junk = junk.filter(ndb.query.FilterNode('startTime', '<', stupid_time))
        #junk = junk.filter(Session.startTime < datetime.strptime('19:00', '%H:%M').time())
        print 'junk: ' + str(junk)
        sessions = queryutil.query(query_form)
        sessions = junk
        return SessionForms(items=[s.to_form() for s in sessions])


    @endpoints.method(SessionQueryForm, SessionForms, path='sessions/filter/type',
                      http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """
        Given a conference, return all sessions of a specified type (eg lecture, keynote, workshop)
        :param request:
        :return:
        """
        wsck = request.websafeConfKey
        c_key = ndb.Key(urlsafe=wsck)
        if not c_key.get():
            raise endpoints.NotFoundException('No conference found with key: %s' % wsck)

        sessions = Session.query(ancestor=c_key) \
            .filter(Session.typeOfSession == request.typeOfSession)

        return SessionForms(items=[session.to_form() for session in sessions])

    @endpoints.method(SessionQueryForm, SessionForms, path='sessions/filter/speaker')
    def getSessionsBySpeaker(self, request):
        """
        Given a speaker, return all sessions given by this particular speaker, across all conferences
        :param request:
        :return:
        """

        sessions = Session.query().filter(Session.speaker == request.speaker)

        return SessionForms(items=[session.to_form() for session in sessions])

    @endpoints.method(SessionForm, SessionForm, path='session',
                      http_method='POST', name='createSession')
    def createSession(self, request):
        """
        Creates a new session. Only available to the organizer of the conference
        :param request:
        :return:
        """
        return self._create_session(request)

    #
    # - - - Profile Public Methods - - - - - - - - - - - - - - - - - - -
    #

    #
    # - - - Profile Private Methods - - - - - - - - - - - - - - - - - - -
    #

    @ndb.transactional(xg=True)
    def _wishlist(self, request, add=True):
        """
        Transaction to add or remove Session from a ConferenceWishlist given by a WishlistRequest
        :param request: Wishlist RPC Request [VoidMessage, session key in query string]
        :param add: whether to add (True) to the wishlist or remove from a wishlist (False)
        :return: BooleanMessage - True if successful, False if failure
        """
        prof = ProfileApi.profile_from_user()  # get user Profile
        session = get_from_webkey(request.websafeSessionKey)  # get session to wishlist

        if not session:
            raise endpoints.NotFoundException('Not a valid session')

        # see if the wishlist exists
        wishlist = ConferenceWishlist().query(ancestor=prof.key) \
            .filter(ConferenceWishlist.conferenceKey == session.conferenceKey) \
            .get()

        # User requested to add to the wishlist, so create if needed
        if not wishlist:
            if add:
                # need to create the wishlist first
                conf_key = session.key.parent()
                wishlist = ConferenceWishlist(conferenceKey=conf_key, parent=prof.key)
            else:
                # remove request, but no wishlist!
                raise endpoints.NotFoundException('Nothing wishlisted for Conference')

        # update wishlist by adding/removing session key
        s_key = session.key
        if s_key not in wishlist.sessionKeys:
            if add:
                # add the key
                wishlist.sessionKeys.append(s_key)
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
                wishlist.sessionKeys.remove(s_key)

                # if wishlist is empty, remove the wishlist. else just update.
                if len(wishlist.sessionKeys) == 0:
                    wishlist.key.delete()
                else:
                    wishlist.put()

        return BooleanMessage(data=True)


    def _create_session(self, request):
        """
        Creates a new Session object and inserts it into storage returning the created value.
        :param request:
        :return:
        """
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Session 'name' field required")

        # TODO: GENERICIZE THE RPC/NBD TRANSLATION?!
        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeConfKey'] # we store the converted value
        del data['websafeKey']

        # add default values for those missing (both data model & outbound Message)
        for df in SESSION_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SESSION_DEFAULTS[df]
                setattr(request, df, SESSION_DEFAULTS[df])

        # TODO: validate session dates are sane i.e. within the start/end of the conf.
        if data['date']:
            data['date'] = datetime.strptime(data['date'][:10], '%Y-%m-%d').date()
        if data['startTime']:
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
        data['conferenceKey'] = conf_key

        # create and persist the Session
        # TODO: email organizer?
        Session(**data).put()
        return request

