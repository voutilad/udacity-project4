#!/usr/bin/env python

"""
session.py -- ConferenceCentral Session methods;
    uses Google Cloud Endpoints

"""

import endpoints
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from protorpc import messages
from protorpc import remote
from protorpc.message_types import VoidMessage

import queryutil
from models import BooleanMessage
from models import ConferenceWishlist
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionType
from models import SessionTypeQueryForm, SpeakerQueryForm
from models import Speaker
from models import SpeakerForm
from models import WishlistForms
from profile import ProfileApi
from settings import API
from utils import get_user_id, get_from_webkey, require_oauth

__author__ = 'voutilad@gmail.com (Dave Voutila)'

SESSION_DEFAULTS = {
    'duration': 60,
    'typeOfSession': SessionType.LECTURE
}

WISHLIST_REQUEST = endpoints.ResourceContainer(
    VoidMessage,
    websafeSessionKey=messages.StringField(1)
)

SESSION_PUT_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeSessionKey=messages.StringField(1)
)

SESSION_DELETE_REQUEST = endpoints.ResourceContainer(
    VoidMessage,
    websafeSessionKey=messages.StringField(1)
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
    @endpoints.method(WISHLIST_REQUEST, BooleanMessage,
                      path='wishlist/{websafeSessionKey}',
                      http_method='PUT', name='addSessionToWishlist')
    @require_oauth
    def add_to_wishlist(self, request):
        """
        Add a Session to a ConferenceWishlist
        :param request:
        :return:
        """
        return self._wishlist(request, True)

    @endpoints.method(WISHLIST_REQUEST, BooleanMessage,
                      path='wishlist/{websafeSessionKey}',
                      http_method='DELETE', name='removeSessionFromWishlist')
    @require_oauth
    def remove_from_wishlist(self, request):
        """
        Remove a Session from a ConferenceWishlist
        :param request:
        :return:
        """
        return self._wishlist(request, False)

    @endpoints.method(VoidMessage, WishlistForms, path='wishlists',
                      http_method='GET', name='getWishlists')
    def get_wishlists(self, request):
        """
        Endpoint for retrieving all wishlists for a requesting user
        :param request:
        :return:
        """
        if not isinstance(request, VoidMessage):
            raise endpoints.BadRequestException()

        prof = ProfileApi.profile_from_user()  # get user Profile
        wishlists = ConferenceWishlist.query(ancestor=prof.key).fetch()

        return WishlistForms(
            items=[wishlist.to_form() for wishlist in wishlists]
        )

    @endpoints.method(VoidMessage, SessionForms, path='sessions/querydemo',
                      http_method='GET', name='querySessionsDemo')
    def query_demo(self, request):
        """
        Queries Session objects in datastore
        :param request:
        :return:
        """
        if not isinstance(request, VoidMessage):
            raise endpoints.BadRequestException()

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

        sessions = queryutil.query(query_form)
        return SessionForms(items=self.populate_forms(sessions))

    @endpoints.method(queryutil.QueryForm, SessionForms, path='sessions/query',
                      http_method='POST', name='querySessions')
    def query(self, request):
        """
        Queries Session objects in datastore
        :param request:
        :return:
        """
        ancestor = None
        if request.ancestorWebSafeKey:
            ancestor = ndb.Key(urlsafe=request.ancestorWebSafeKey)

        sessions = queryutil.query(request, ancestor=ancestor)

        return SessionForms(items=self.populate_forms(sessions))

    @endpoints.method(SessionTypeQueryForm, SessionForms,
                      path='sessions/filter/type',
                      http_method='GET', name='getConferenceSessionsByType')
    def get_by_type(self, request):
        """
        Given a conference, return all sessions of a specified type (eg lecture,
         keynote, workshop)
        :param request:
        :return:
        """
        wsck = request.websafeConfKey
        c_key = ndb.Key(urlsafe=wsck)
        if not c_key.get():
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        sessions = Session.query(ancestor=c_key) \
            .filter(Session.typeOfSession == request.typeOfSession)

        return SessionForms(items=self.populate_forms(sessions))

    @endpoints.method(SpeakerQueryForm, SessionForms,
                      path='sessions/filter/speaker',
                      http_method='GET', name='getBySpeaker')
    def get_by_speaker(self, request):
        """
        Given a speaker, return all sessions given by this particular speaker,
        across all conferences
        :param request:
        :return:
        """

        if request.name and not request.title:
            speakers = Speaker.query(Speaker.name == request.name)
        elif not request.name and request.title:
            speakers = Speaker.query(Speaker.title == request.title)
        else:
            speakers = Speaker.query(Speaker.name == request.name) \
                .filter(Speaker.title == request.title)

        speakers.fetch()

        all_sessions = []
        if speakers:
            for speaker in speakers:
                sessions = Session.query(
                    Session.speakerKeys == speaker.key).fetch()
                if sessions:
                    all_sessions += sessions

        return SessionForms(items=self.populate_forms(all_sessions))

    @endpoints.method(SessionForm, SessionForm, path='session',
                      http_method='POST', name='create')
    @require_oauth
    def create(self, request):
        """
        Creates a new Session. Only available to the organizer of the conference
        :param request: SessionForm
        :return: SessionForm
        """
        if not request.websafeConfKey:
            raise endpoints.BadRequestException('Conference key required.')

        # try to prepare the Session instance
        session = self.__prep_new_session(request)

        # see if it exists already
        if session.key.get():
            raise endpoints.ConflictException(
                'Session with key %s already exists' % session.key.urlsafe()
            )

        # deal with Speaker creation/updating
        speakers = [self.__prepare_speaker(form) for form in request.speakers]

        # try the transaction
        request.websafeKey = self._create(session, speakers).urlsafe()

        # Add a task to the queue for getting featured speaker changes
        taskqueue.add(params={'conf_key': request.websafeConfKey},
                      url='/tasks/update_featured_speaker')

        return request

    @endpoints.method(SESSION_PUT_REQUEST, SessionForm,
                      path='session/{websafeSessionKey}',
                      http_method='PUT', name='update')
    @require_oauth
    def update(self, request):
        """
        Attempts to update an existing Session
        :param request: SESSION_GET_REQUEST
        :return: SessionForm
        """
        # first look up current (old) Session and sanity check it
        old_session = ndb.Key(urlsafe=request.websafeSessionKey).get()

        if not old_session:
            raise endpoints.NotFoundException(
                'No session found for key: %s' % request.websafeKey)

        if not isinstance(old_session, Session):
            raise TypeError('key provided is not for a Session')

        # need to populate the new form making sure to get speakers
        new_form = self.populate_form(old_session)

        for field in request.all_fields():
            if field.name != 'websafeSessionKey':
                attr = getattr(request, field.name)
                if attr:
                    setattr(new_form, field.name, attr)

        # deal with Speaker creation/updating
        new_speakers = [self.__prepare_speaker(form) for form in
                        new_form.speakers]

        # the transaction
        session = self._update(old_session, new_form,
                               speakers=new_speakers)

        # Add a task to the queue for getting featured speaker changes
        taskqueue.add(params={'conf_key': session.conferenceKey.urlsafe()},
                      url='/tasks/update_featured_speaker')

        return self.populate_form(session)

    @endpoints.method(SESSION_PUT_REQUEST, BooleanMessage,
                      path='session/{websafeSessionKey}',
                      http_method='DELETE', name='delete')
    @require_oauth
    def delete(self, request):
        """
        Deletes a given Session cleaning up Speakers if needed
        :param request:
        :return:
        """
        session = ndb.Key(urlsafe=request.websafeSessionKey).get()

        if not session:
            return BooleanMessage(data=False)

        speakers = ndb.get_multi(session.speakerKeys)

        return BooleanMessage(data=self._delete(session, speakers))

    #
    # - - - Session Private Methods - - - - - - - - - - - - - - - - - - -
    #

    @ndb.transactional(xg=True)
    def _wishlist(self, request, add=True):
        """
        Transaction to add or remove Session from a ConferenceWishlist given by
         a WishlistRequest
        :param request: Wishlist RPC Request [VoidMessage, session key in query
         string]
        :param add: whether to add (True) to the wishlist or remove from a
        wishlist (False)
        :return: BooleanMessage - True if successful, False if failure
        """
        prof = ProfileApi.profile_from_user()  # get user Profile
        session = get_from_webkey(request.websafeSessionKey)  # get session

        if not session or not isinstance(session, Session):
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
                wishlist = ConferenceWishlist(conferenceKey=conf_key,
                                              parent=prof.key)
            else:
                # remove request, but no wishlist!
                raise endpoints.NotFoundException(
                    'Nothing wishlisted for Conference')

        # update wishlist by adding/removing session key
        s_key = session.key
        if s_key not in wishlist.sessionKeys:
            if add:
                # add the key
                wishlist.sessionKeys.append(s_key)
                wishlist.put()
            else:
                # can't remove a nonexistant key
                raise endpoints.NotFoundException(
                    'Session not in wishlist for Conference')
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

    @ndb.transactional(xg=True)
    def _delete(self, session, speakers=None):
        """
        Delete a session and clean up Speakers, decrementing or removing if
        needed.
        :param session:
        :param speakers:
        :return: True on success, False on failure
        """
        try:
            if speakers:
                for speaker in speakers:
                    speaker.numSessions -= 1

                    if speaker.numSessions < 1:
                        speaker.key.delete()
                    else:
                        speaker.put()

            session.key.delete()
            return True
        except ndb.datastore_errors.Error:
            print '!!! error deleting session'

        return False

    @ndb.transactional(xg=True)
    def _create(self, session, speakers=None):
        """
        Transaction for persisting session and speaker changes
        :param session: Session
        :param speakers: Speaker
        :return: Session Key
        """
        try:
            if speakers:
                for speaker in speakers:
                    session.speakerKeys.append(speaker.put())
            return session.put()

        except ndb.datastore_errors.Error:
            print '!!! failed to create Session'

        return None

    @staticmethod
    def __prep_new_session(session_form):
        """
        Prepare a new Session instance, validating Conference and User details
        :param session_form:
        :return: Session ready for processing of speakers
        """
        if not isinstance(session_form, SessionForm):
            raise TypeError('expected SessionForm')

        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = get_user_id(user)

        if not session_form.name:
            raise endpoints.BadRequestException("Session 'name' field required")

        # fetch the key of the ancestor conference
        conf_key = ndb.Key(urlsafe=session_form.websafeConfKey)
        conf = conf_key.get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % session_form.websafeConfKey
            )

        # check that user is conference owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the conference owner can create sessions.')

        # create Session and set up the parent key
        return Session.from_form(session_form)

    @ndb.transactional(xg=True)
    def _update(self, old_session, session_form, speakers=None):
        """
        Update an existing Session using the new SessionForm message
        :param old_session: old Session instance
        :param session_form: SessionForm with updates
        :param speakers:
        :return: updated Session
        """
        if not isinstance(old_session, Session):
            raise TypeError('expecting %s but got %s' % (Session, old_session))

        new_session = Session.from_form(session_form)

        # deal with decrementing the old ones that aren't on the session anymore
        new_keys = [speaker.key for speaker in speakers]
        for old_key in old_session.speakerKeys:
            if old_key not in new_keys:
                # decrement old speaker's sesssion count. if 0, just delete.
                old_speaker = old_key.get()
                old_speaker.numSessions -= 1
                if old_speaker.numSessions == 0:
                    old_key.delete()
                else:
                    old_speaker.put()

        # put speaker changes for new ones and append their keys
        for speaker in speakers:
            new_session.speakerKeys.append(speaker.put())

        # since session key's use the session name, need to delete the old one
        old_session.key.delete()
        new_session.put()

        return new_session

    @staticmethod
    def __prepare_speaker(speaker_form):
        """
        Handle updating Speaker records and their session counts
        :param speaker_form: SpeakerForm
        :return: Speaker with updates ready to be put()
        """
        if not isinstance(speaker_form, SpeakerForm):
            raise TypeError(
                'expected %s, but got %s' % (SpeakerForm, speaker_form))

        speaker = Speaker.query(Speaker.name == speaker_form.name) \
            .filter(Speaker.title == speaker_form.title) \
            .get()
        if speaker:
            speaker.numSessions += 1
        else:
            speaker = Speaker.from_form(speaker_form)
            speaker.numSessions = 1

        return speaker

    @staticmethod
    def populate_form(session):
        """
        Populate a new SessionForm from a Session, resolving Speakers
        :param session:
        :return:
        """
        speakers = ndb.get_multi(session.speakerKeys)
        return session.to_form([speaker.to_form() for speaker in speakers])

    @staticmethod
    def populate_forms(sessions):
        """
        Since I separated out Speakers from Sessions, need to fetch those back
        onto Sesssions
        when creating forms.
        :param sessions:
        :return:
        """
        session_forms = []

        for session in sessions:
            form = SessionApi.populate_form(session)
            session_forms.append(form)

        return session_forms
