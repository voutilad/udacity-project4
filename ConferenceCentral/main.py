#!/usr/bin/env python

"""
main.py -- Udacity conference server-side Python App Engine
    HTTP controller handlers for memcache & task queue access

$Id$

created by wesc on 2014 may 24

modified by voutilad@gmail.com for Udacity FullStackDev Project 4

"""

import endpoints
import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.ext import ndb

from conference import ConferenceApi
from models import Session, SessionType
from profile import ProfileApi
from session import SessionApi

# - - - Endpoints Client Api - - -


API_SERVER = endpoints.api_server(
    [ConferenceApi, SessionApi, ProfileApi])  # register API


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


class FeaturedSpeakersHandler(webapp2.RequestHandler):
    """
    Pick a Featured Speaker for a Conference when Sessions are created/changed
    """

    @staticmethod
    def update(conf_key, speaker):
        """
        Update memcache with the new message for the conference
        :param conf_key: Conference key
        :param speaker: Speaker instance
        :return: announcement
        """
        s = 'Featured Speaker: %s' % speaker.name
        if speaker.title:
            s += ', ' + speaker.title

        m_key = ConferenceApi.FEATURED_KEY.format(conf_key=conf_key.urlsafe())

        print 'Setting announcement (%s) with key (%s)' % (s, m_key)

        memcache.Client().cas(m_key, s)

        return s

    def post(self):
        """
        Expected to receive Postdata with a web-safe Conference key
        :return:
        """
        wsck = self.request.get('conf_key')
        if not wsck:
            print 'Bad request to FeaturedSpeakersHandler'
            self.response.set_status(204)  # bad request
        else:
            # do it
            conf_key = ndb.Key(urlsafe=wsck)
            keynotes = Session.query(ancestor=conf_key) \
                .filter(Session.typeOfSession == SessionType.KEYNOTE) \
                .fetch()
            if keynotes:
                # take the first keynote presenter and feature them
                s_key = self.get_first_speaker(keynotes)
                self.update(conf_key, s_key.get())
            else:
                others = Session.query(ancestor=conf_key) \
                    .filter(Session.typeOfSession != SessionType.KEYNOTE) \
                    .fetch()
                if others:
                    # just grab the first for now...
                    s_key = self.get_first_speaker(others)
                    self.update(conf_key, s_key.get())
        self.response.set_status(204)

    @staticmethod
    def get_first_speaker(sessions):
        """
        Get the first available speaker in the given sessions
        :param sessions:
        :return:
        """
        for session in sessions:
            if getattr(session, 'speakerKeys'):
                return session.speakerKeys[0]

APP = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/update_featured_speaker', FeaturedSpeakersHandler)
], debug=True)
