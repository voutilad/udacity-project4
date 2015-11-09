#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

modified by voutilad@gmail.com for Udacity FullStackDev Project 4
"""
import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb


class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT


class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)

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


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)


class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)


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

class ConferenceWishlist(ndb.Model):
    """ConferenceWishlist --- maintains list of keys of favorite sessions for a given conference"""
    conferenceKey = ndb.StringProperty(required=True)
    sessionKeys = ndb.StringProperty(repeated=True)


class Session(ndb.Model):
    """Session -- Session object"""
    name = ndb.StringProperty(required=True)
    highlights = ndb.StringProperty(repeated=True)
    speaker = ndb.StringProperty()
    duration = ndb.IntegerProperty()
    typeOfSession = ndb.StringProperty() #EnumField: SessionType
    date = ndb.DateProperty()
    startTime = ndb.TimeProperty()
    conferenceKey = ndb.StringProperty()

class SessionForm(messages.Message):
    """SessionForm -- RPC message containing details about a Session"""
    name = messages.StringField(1)
    highlights = messages.StringField(2, repeated=True)
    speaker = messages.StringField(3)
    duration = messages.IntegerField(4)
    typeOfSession = messages.EnumField('SessionType', 5)
    date = messages.StringField(6)
    startTime = messages.StringField(7)
    websafeConfKey = messages.StringField(8)

class SessionForms(messages.Message):
    """SessionForms -- multiple SessionForm's"""
    items = messages.MessageField(SessionForm, 1, repeated=True)

class SessionType(messages.Enum):
    """SessionType -- type of session being held at conference"""
    LECTURE = 1
    KEYNOTE = 2
    WORKSHOP = 3

class Speaker(messages.Message):
    name = messages.StringField(1, required=True)

class WishlistForm(messages.Message):
    """WishlistForm -- RPC message for containing wishlist sessions"""
    websafeSessionKeys = messages.StringField(1, repeated=True)

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

class SessionQueryForm(messages.Message):
    """SessionQueryForm -- Session query inbound form message"""
    websafeConfKey = messages.StringField(1)
    typeOfSession = messages.EnumField('SessionType', 2)

class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)


class ConferenceQueryForms(messages.Message):
    """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form message"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)
