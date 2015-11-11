#!/usr/bin/env python

"""settings.py

Udacity conference server-side Python App Engine app user settings

$Id$

created/forked from conference.py by wesc on 2014 may 24

"""
import endpoints

# Replace the following lines with client IDs obtained from the APIs
# Console or Cloud Console.
WEB_CLIENT_ID = '423376222467-kaokhd2tqgmds8u47dgu8m4euph0h83f.apps.googleusercontent.com'
ANDROID_CLIENT_ID = 'replace with Android client ID'
IOS_CLIENT_ID = 'replace with iOS client ID'
ANDROID_AUDIENCE = WEB_CLIENT_ID
EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID

API = endpoints.api(name='conferenceCentral', version='v1', audiences=[ANDROID_AUDIENCE],
               allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID],
               scopes=[EMAIL_SCOPE])