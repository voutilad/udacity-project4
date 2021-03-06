#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

modified by voutilad@gmail.com for Udacity FullStackDev Project 4
"""
import httplib
import endpoints
from datetime import datetime
from protorpc import messages
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop


class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT


# - - - - - - - -


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)


class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)


# - - - - - - - -

class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferencesToAttend = ndb.KeyProperty(kind='Conference', repeated=True)

    def to_form(self):
        """
        Creates ProfileForm from the Profile model instance
        :return: ProfileForm
        """
        pf = ProfileForm()
        pf.displayName = self.displayName
        pf.mainEmail = self.mainEmail
        pf.conferenceKeysToAttend = [
            key.urlsafe() for key in self.conferencesToAttend
            ]
        pf.teeShirtSize = TeeShirtSize.lookup_by_name(self.teeShirtSize)

        return pf


class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName = messages.StringField(1)
    teeShirtSize = messages.EnumField('TeeShirtSize', 2)


class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    teeShirtSize = messages.EnumField('TeeShirtSize', 3)
    conferenceKeysToAttend = messages.StringField(4, repeated=True)


# - - - - - - - - - - - - - - - - - - - -


class Conference(ndb.Model):
    """Conference -- Conference object"""
    name = ndb.StringProperty(required=True)
    description = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics = ndb.StringProperty(repeated=True)
    city = ndb.StringProperty()
    startDate = ndb.DateProperty()
    month = ndb.IntegerProperty()  # TODO: do we need for indexing like Java?
    endDate = ndb.DateProperty()
    maxAttendees = ndb.IntegerProperty()
    seatsAvailable = ndb.IntegerProperty()

    def to_form(self, display_name=None):
        """
        Creates RPC Message ConferenceForm representation of a Conference
        :param display_name: Optional display name string for the ConferenceForm
        :return: ConferenceForm
        """
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(self, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(self, field.name)))
                else:
                    setattr(cf, field.name, getattr(self, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, self.key.urlsafe())
        if display_name:
            setattr(cf, 'organizerDisplayName', display_name)
        cf.check_initialized()
        return cf


class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name = messages.StringField(1)
    description = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics = messages.StringField(4, repeated=True)
    city = messages.StringField(5)
    startDate = messages.StringField(6)  # DateTimeField()
    month = messages.IntegerField(7)
    maxAttendees = messages.IntegerField(8)
    seatsAvailable = messages.IntegerField(9)
    endDate = messages.StringField(10)  # DateTimeField()
    websafeKey = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)


class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)


# - - - - - - - - - - - - - - - - - - - -


class ConferenceWishlist(ndb.Model):
    """ConferenceWishlist --- maintains list of keys of favorite sessions for
    a given conference"""
    conferenceKey = ndb.KeyProperty(kind='Conference', required=True)
    sessionKeys = ndb.KeyProperty(kind='Session', repeated=True)

    def to_form(self):
        """
        Creates the ConferenceWishlistForm representation of the model object
        :return: ConferenceWishlistForm
        """
        wf = WishlistForm()
        wf.websafeConfKey = self.conferenceKey.urlsafe()
        wf.websafeSessionKeys = [key.urlsafe() for key in self.sessionKeys]
        return wf


class WishlistForm(messages.Message):
    """WishlistForm -- RPC message for containing wishlist sessions"""
    websafeConfKey = messages.StringField(1)
    websafeSessionKeys = messages.StringField(2, repeated=True)


class WishlistForms(messages.Message):
    """WishlistForms -- RPC message containing multiple WishlistForm's for
    response"""
    items = messages.MessageField(WishlistForm, 1, repeated=True)


# - - - - - - - - - - - - - - - - - - - -


class SessionType(messages.Enum):
    """SessionType -- type of session being held at conference"""
    LECTURE = 1
    KEYNOTE = 2
    WORKSHOP = 3


class Speaker(ndb.Model):
    """Speaker -- Session speaker"""
    name = ndb.StringProperty(required=True)
    title = ndb.StringProperty()
    numSessions = ndb.IntegerProperty(default=0)

    def to_form(self):
        """ Converts Speaker to SpeakerForm messages
        :return: SpeakerForm
        """
        return SpeakerForm(name=self.name, title=self.title,
                           numSessions=self.numSessions)

    @staticmethod
    def from_form(form):
        """ Create a new Speaker model instance from a SpeakerForm
        :param form: SpeakerForm
        :return: Speaker
        """
        if not isinstance(form, SpeakerForm):
            raise TypeError('Expected %s, but given: %s' % (SpeakerForm, form))

        return Speaker(name=form.name,
                       title=form.title,
                       numSessions=form.numSessions,
                       key=ndb.Key(Speaker, form.name + form.title))


class SpeakerForm(messages.Message):
    """SpeakerForm -- Speaker RPC Message for embedding in Session"""
    name = messages.StringField(1, required=True)
    title = messages.StringField(2, required=True)
    numSessions = messages.IntegerField(3)


class Session(ndb.Model):
    """Session -- Session object"""
    name = ndb.StringProperty(required=True)
    highlights = ndb.StringProperty(repeated=True)
    speakerKeys = ndb.KeyProperty(kind='Speaker', repeated=True, indexed=True)
    duration = ndb.IntegerProperty()
    typeOfSession = msgprop.EnumProperty(SessionType, required=True,
                                         indexed=True)
    date = ndb.DateProperty()
    startTime = ndb.TimeProperty()
    conferenceKey = ndb.KeyProperty(kind='Conference')

    def to_form(self, speaker_forms=None):
        """
        Create the corresponding SessionForm RPC message
        :param speaker_forms:
        :return: SessionForm
        """
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(self, field.name):
                # matching/common fields between classes
                if field.name == 'date' and self.date:
                    sf.date = self.date.strftime('%Y-%m-%d')
                elif field.name == 'startTime' and self.startTime:
                    sf.startTime = self.startTime.strftime('%H:%M')
                else:
                    setattr(sf, field.name, getattr(self, field.name))
            elif field.name == 'websafeConfKey':
                setattr(sf, field.name, self.conferenceKey.urlsafe())
        setattr(sf, 'websafeKey', self.key.urlsafe())

        if speaker_forms:
            sf.speakers = speaker_forms

        return sf

    @staticmethod
    def from_form(form):
        """
        Creates a new Session object from the given SessionForm.

        Note: does not set conferenceKey or speakerKeys or even the Session key
        :param form: SessionForm
        :return: Session
        """
        if not isinstance(form, SessionForm):
            raise TypeError('Expected %s but got %s' % (SessionForm, form))

        if form.websafeConfKey:
            conf_key = ndb.Key(urlsafe=form.websafeConfKey)
        else:
            conf_key = None

        s = Session(name=form.name,
                    highlights=form.highlights,
                    duration=form.duration,
                    typeOfSession=form.typeOfSession,
                    conferenceKey=conf_key,
                    parent=conf_key
                    )

        if form.startTime:
            s.startTime = datetime.strptime(form.startTime[:6], '%H:%M').time()
        if form.date:
            s.date = datetime.strptime(form.date[:10], '%Y-%m-%d').date()

        s.key = ndb.Key(Session, s.name, parent=conf_key)

        return s


class SessionForm(messages.Message):
    """SessionForm -- RPC message containing details about a Session"""
    name = messages.StringField(1)
    highlights = messages.StringField(2, repeated=True)
    speakers = messages.MessageField(SpeakerForm, 3, repeated=True)
    duration = messages.IntegerField(4)
    typeOfSession = messages.EnumField(SessionType, 5)
    date = messages.StringField(6)
    startTime = messages.StringField(7)
    websafeConfKey = messages.StringField(8)
    websafeKey = messages.StringField(9)


class SessionForms(messages.Message):
    """SessionForms -- multiple SessionForm's"""
    items = messages.MessageField(SessionForm, 1, repeated=True)


class TeeShirtSize(messages.Enum):
    """TeeShirtSize -- t-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15


# - - - - - - - - - - - - - - - - - - - - - -

class SpeakerQueryForm(messages.Message):
    """"""
    name = messages.StringField(1)
    title = messages.StringField(2)


class SessionTypeQueryForm(messages.Message):
    """SessionQueryForm -- Session query inbound form message"""
    websafeConfKey = messages.StringField(1)
    typeOfSession = messages.EnumField('SessionType', 2)


class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)


class ConferenceQueryForms(messages.Message):
    """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form
    message"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)
