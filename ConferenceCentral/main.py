#!/usr/bin/env python

"""
main.py -- Udacity conference server-side Python App Engine
    HTTP controller handlers for memcache & task queue access

$Id$

created by wesc on 2014 may 24

modified by voutilad@gmail.com for Udacity FullStackDev Project 4

"""

import webapp2
import endpoints
from google.appengine.api import memcache
from google.appengine.api import app_identity
from google.appengine.api import mail
from google.appengine.ext import ndb
from session import SessionApi
from conference import ConferenceApi
from profile import ProfileApi
from models import Session, Speaker, SessionType

# - - - Endpoints Client Api - - -

API_SERVER = endpoints.api_server([ConferenceApi, SessionApi, ProfileApi])  # register API

# - - - Backend Api - - -

class SetAnnouncementHandler(webapp2.RequestHandler):
    """
    Handles creation of announcements
    """

    def get(self):
        """
        Set announcement values in Memcache.
        :return:
        """
        ConferenceApi.cache_announcement()
        self.response.set_status(204)


class SendConfirmationEmailHandler(webapp2.RequestHandler):
    """
    Handles Email confirmation tasks
    """
    def post(self):
        """
        Send email confirming Conference creation.
        :return:
        """
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),  # from
            self.request.get('email'),  # to
            'You created a new Conference!',  # subj
            'Hi, you have created a following '  # body
            'conference:\r\n\r\n%s' % self.request.get(
                'conferenceInfo')
        )


class UpdateFeaturedSpeakersHandler(webapp2.RequestHandler):
    """
    Pick a Featured Speaker for a Conference when Sessions are created/changed
    """
    MEMCACHE_KEY_FORMAT = 'speaker-{conf_key}'

    def update(self, conf_key, speaker):
        """
        Update memcache with the new message for the conference
        :param conf_key: Conference key
        :param speaker: Speaker instance
        :return: announcement
        """
        announcement = 'Featured Speaker: %s' % speaker.name
        m_key = self.MEMCACHE_KEY_FORMAT.format(conf_key=conf_key.urlsafe())
        print 'Setting announcement (%s) with key (%s)' % (announcement, m_key)
        memcache.set(m_key, announcement)
        return announcement

    def post(self):
        """
        Expected to receive Postdata with a web-safe Conference key
        :return:
        """
        wsck = self.request.get('conf_key')
        if not wsck:
            print 'Bad request to UpdateFeaturedSpeakersHandler'
            self.response.set_status(204) # bad request
        else:
            # do it
            conf_key = ndb.Key(urlsafe=wsck)
            keynotes = Session.query(ancestor=conf_key)\
                .filter(Session.typeOfSession == SessionType.KEYNOTE)\
                .fetch()
            if keynotes:
                # take the first keynote presenter and feature them
                s_key = keynotes[0].speakerKeys[0]
                self.update(conf_key, s_key.get())
            else:
                others = Session.query(ancestor=conf_key)\
                    .filter(Session.typeOfSession != SessionType.KEYNOTE)\
                    .get()
                if others:
                    # just grab the first for now...
                    self.update(conf_key, Speaker.query(key=others[0].speakerKeys[0]))
        self.response.set_status(204)


APP = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/update_featured_speaker', UpdateFeaturedSpeakersHandler)
], debug=True)

