#!/usr/bin/env python

"""
profile.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

"""

import endpoints
from google.appengine.ext import ndb
from protorpc.message_types import VoidMessage
from protorpc import remote

from models import Profile
from models import ProfileForm
from models import ProfileMiniForm
from models import TeeShirtSize
from settings import API
from utils import get_user_id, require_oauth

__author__ = 'voutilad@gmail.com (Dave Voutila)'


@API.api_class(resource_name='profiles')
class ProfileApi(remote.Service):
    """Profile API"""
    #
    # - - - Endpoints - - - - - - - - - - - - - - - - - - -
    #

    @endpoints.method(VoidMessage, ProfileForm,
                      path='profile', http_method='GET', name='getProfile')
    @require_oauth
    def get(self, request):
        """
        Return user Profile
        :param request:
        :return:
        """
        if not isinstance(request, VoidMessage):
            raise endpoints.BadRequestException()

        return self._do_profile()

    @endpoints.method(ProfileMiniForm, ProfileForm,
                      path='profile', http_method='POST', name='saveProfile')
    @require_oauth
    def save(self, request):
        """
        Update & return user profile.
        :param request:
        :return:
        """

        return self._do_profile(request)

    #
    # - - - Profile Public Methods - - - - - - - - - - - - - - - - - - -
    #

    @staticmethod
    def profile_from_user():
        """
        Return user Profile from datastore, creating new one if non-existent.
        :return: Profile model for the current endpoint user
        """
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = get_user_id(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key=p_key,
                displayName=user.nickname(),
                mainEmail=user.email(),
                teeShirtSize=str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile  # return Profile

    #
    # - - - Profile Private Methods - - - - - - - - - - - - - - - - - - -
    #

    def _do_profile(self, save_request=None):
        """
        Get user Profile and return to user, possibly updating it first.
        :param save_request: ProfileForm with updates (if any) for the Profile
        :return: ProfileForm for the current endpoints user
        """
        # get user Profile
        prof = self.profile_from_user()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        # if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        # else:
                        #    setattr(prof, field, val)
                        prof.put()

        # return ProfileForm
        return prof.to_form()
