"""
Utility functions for Conference Central
"""

import json
import os
import time
import uuid

import endpoints
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from models import Conference


def get_user_id(user, id_type="email"):
    """
    Get user id
    :param user:
    :param id_type:
    :return:
    """
    if id_type == "email":
        return user.email()

    if id_type == "oauth":
        """A workaround implementation for getting userid."""
        auth = os.getenv('HTTP_AUTHORIZATION')
        bearer, token = auth.split()
        token_type = 'id_token'
        if 'OAUTH_USER_ID' in os.environ:
            token_type = 'access_token'
        url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?%s=%s'
               % (token_type, token))
        user = {}
        wait = 1
        for i in range(3):
            resp = urlfetch.fetch(url)
            if resp.status_code == 200:
                user = json.loads(resp.content)
                break
            elif resp.status_code == 400 and 'invalid_token' in resp.content:
                url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?%s=%s'
                       % ('access_token', token))
            else:
                time.sleep(wait)
                wait += i
        return user.get('user_id', '')

    if id_type == "custom":
        # implement your own user_id creation and getting algorythm
        # this is just a sample that queries datastore for an existing profile
        # and generates an id if profile does not exist for an email
        profile = Conference.query(Conference.organizerUserId == user.email())
        if profile:
            return profile.id()
        else:
            return str(uuid.uuid1().get_hex())


# --- Added by Dave Voutila <voutilad@gmail.com>


def require_oauth(func):
    """
    Decorator to check if a user is executing the request with OAuth
    :param func: wrapping func
    :return:
    """

    def func_wrapper(*args, **kwargs):
        if not endpoints.get_current_user():
            raise endpoints.UnauthorizedException('Authorization required')
        return func(*args, **kwargs)

    return func_wrapper


def get_from_webkey(websafe_key, model=None):
    """
    Fetches the key for a given model by the provided websafeKey value while
    validating an instance of the model exists.

    :param websafe_key: web-safe string key of model instance to lookup
    :param model: (optional) ndb.Model type (e.g. Conference) to validate
    against instance
    :return: ndb.Key()
    """
    try:
        key = ndb.Key(urlsafe=websafe_key)
    except TypeError:
        print '!!! Asked to resolve a bogus key: %s' % websafe_key
        return None

    obj = key.get()
    if not obj:
        err = 'No instance found with key: {key}'.format(key=websafe_key)
        raise endpoints.NotFoundException(err)

    if model and type(model) != type(obj):
        err = 'Instance is {got} instead of {expected}'.format(got=type(obj),
                                                               expected=type(
                                                                   model))
        raise endpoints.NotFoundException(err)

    return obj
