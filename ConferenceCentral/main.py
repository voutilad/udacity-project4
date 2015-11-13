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
from google.appengine.api import app_identity
from google.appengine.api import mail
from session import SessionApi
from conference import ConferenceApi
from profile import ProfileApi

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
    def post(self):
        """
        Expected to receive Postdata with a web-safe Conference key
        :return:
        """
        wsck = self.request.get('conf_key')
        if not wsck:
            self.response.set_status(400) # bad request
        else:
            # do it
            print 'Updating Featured Speaker for conference: %s' % wsck
            self.response.set_status(204)


APP = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/update_featured_speaker', UpdateFeaturedSpeakersHandler)
], debug=True)

