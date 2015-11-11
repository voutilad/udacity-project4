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
    def get(self):
        """Set Announcement in Memcache."""
        ConferenceApi._cacheAnnouncement()
        self.response.set_status(204)


class SendConfirmationEmailHandler(webapp2.RequestHandler):
    def post(self):
        """Send email confirming Conference creation."""
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),  # from
            self.request.get('email'),  # to
            'You created a new Conference!',  # subj
            'Hi, you have created a following '  # body
            'conference:\r\n\r\n%s' % self.request.get(
                'conferenceInfo')
        )

APP = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
], debug=True)

