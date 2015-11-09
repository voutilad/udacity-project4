import json
import os
import time
import uuid

import endpoints
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from models import Conference

def getUserId(user, id_type="email"):
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
                wait = wait + i
        return user.get('user_id', '')

    if id_type == "custom":
        # implement your own user_id creation and getting algorythm
        # this is just a sample that queries datastore for an existing profile
        # and generates an id if profile does not exist for an email
        profile = Conference.query(Conference.mainEmail == user.email())
        if profile:
            return profile.id()
        else:
            return str(uuid.uuid1().get_hex())

# --- Added by Dave Voutila <voutilad@gmail.com>

def getModelByWebKey(websafeKey, model=None):
    """
    Fetches the key for a given model by the provided websafeKey value while validating an instance of the model exists.

    :param websafeKey: web-safe string key of model instance to lookup
    :param model: (optional) ndb.Model type (e.g. Conference) to validate against instance
    :return: ndb.Key()
    """
    key = ndb.Key(urlsafe=websafeKey)
    obj = key.get()
    if not obj:
        err = 'No instance found with key: {key}'.format(key=websafeKey)
        raise endpoints.NotFoundException(err)

    if model and type(model) != type(obj):
        err = 'Instance is {got} instead of {expected}'.format(got=type(obj), expected=type(model))
        raise endpoints.NotFoundException(err)

    return obj
