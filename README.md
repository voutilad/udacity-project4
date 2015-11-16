# ConferenceCentral - Udacity FullStack Nano-degree Project 4

_For the original ConferenceCentral app, see [https://github.com/udacity/ud858](https://github.com/udacity/ud858)_

*Author*: Dave Voutila

---

## Running the Application
Assuming you have the Google App Engine SDK installed, running the app is as
simple as running from the root of the project:

``` bash
dev_appserver.py ConferenceCentral
```

Once the local dev server is up and running, navigate to:
 * [localhost:8080](http://localhost:8080) - web app client interface
 * [localhost:8080/_ah/api/explorer](http://localhost:8080/_ah/api/explorer) -
 API Explorer interface

To stop the app, hit CTRL-C on the console and GAE should do a safe shutdown.

## Changes from original ConferenceCentral Project
I've made numerous changes both for purposes of the project requirements as well
as personal design preferences.

### Refactored API into Multiple Modules
I found having all the endpoints and methods defined in a single class in a
simple module rather unwieldy.

Following [Creating an API with Implemented with Multiple Classes](https://cloud.google.com/appengine/docs/python/endpoints/create_api#creating_an_api_implemented_with_multiple_classes)
I decided to break the API up into it's core parts:

* _conferenceCentral.conference_ - [conference.py](./ConferenceCentral/conference.py)
 methods related to Conference objects
* _conferenceCentral.profile_ - [profile.py](./ConferenceCentral/profile.py)
 methods related to user Profile objects
* _conferenceCentral.session_ - [session.py](./ConferenceCentral/session.py)
 methods related to Conference Session objects

As a result, I had to update some of the javascript using the Google Client API js library to point to the new paths.

Also, [app.yaml](./ConferenceCentral/app.yaml) is updated now to account for
the changes and the _endpoints.api_server_ call is now isolated from
the configuration of the API (now located in [settings.py]).

### Switched from Storing Web-safe Keys to ndb.KeyProperty's
In reading more about using Datastore, I decided it was a bit awkward to be
storing web-safe forms of keys as StringProperty's in ndb. Instead, I've swapped
the models to use the ndb.KeyProperty() data type. For example:

``` python
class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferencesToAttend = ndb.KeyProperty(kind='Conference', repeated=True)
```

### Migrated Model->Message Logic to Model Classes
Similar to how I refactored the api code into multiple modules, I also moved
any model to message conversion logic to the model classes themselves. This
cleans up the api classes so they can focus on endpoint logic and conversion
from models to messages is simpler:

``` python
session = Session(name='Keynote for ConfCon', sessionType=SessionType.KEYNOTE)
session_form = session.to_form()
```

### Generic Query Support
I also performed a first pass at generalizing support for querying entities in
ndb. The [queryutil.py](./ConferenceCentral/queryutil.py) module contains
configuration metadata and helper methods allowing either a new endpoint to be
built or old to be converted (for an example, see _conference.ConferenceApi.query()_).

The design builds off the original, flexible query interface for the _Conference_
objects that is exposed in the current web client UI. In essence, I extended the
message to help target particular entity kinds as well as pass any ancestor key
desired for filtering:

``` python
class QueryForm(messages.Message):
    """
    QueryForm containing one or many QueryMessages as query filters, target kind
    (e.g. 'Conference'), and the max number of results to return.
    """
    target = messages.EnumField(QueryTarget, 1, required=True)
    filters = messages.MessageField(QueryFilter, 2, repeated=True)
    num_results = messages.IntegerField(3, default=20)
    sort_by = messages.StringField(4)
    ancestorWebSafeKey = messages.StringField(5)
```

Configuring the different model fields is now based on an enhanced mapping
similar to the original one from the basic ConferenceCentral app:

``` python
# Lookup map for finding queriable field names for different entity kinds
FIELD_MAP = {
    # Kind : Fieldmap
    Conference: {
        # client field name : ndb model name
        'CITY': 'city',
        'TOPIC': 'topics',
        'MONTH': 'month',
        'MAX_ATTENDEES': 'maxAttendees',
    },
    Profile: {
        'SHIRT': 'teeShirtSize'
    },
    Session: {
        'TYPE': 'typeOfSession',
        'DATE': 'date',
        'START_TIME': 'startTime',
        'DURATION': 'duration'
    },
    ConferenceWishlist: {
        'CONF_KEY': 'conferenceKeys',
        'SESSION_KEYS': 'sessionKeys'
    }
}
```

## Data Model
The original Data Model from ConferenceCentral handled Conference and Profile
data. As part of this project, I added Sessions, ConferenceWishlists, and
Speakers to round out the functionality of creating and managing conferences.

### Sessions
Sessions support the required attributes for the project, but importantly
support tracking one or many Speaker keys.

``` python
class Session(ndb.Model):
    """Session -- Session object"""
    name = ndb.StringProperty(required=True)
    highlights = ndb.StringProperty(repeated=True)
    speakerKeys = ndb.KeyProperty(kind='Speaker', repeated=True, indexed=True)
    duration = ndb.IntegerProperty()
    typeOfSession = msgprop.EnumProperty(SessionType, required=True, indexed=True)
    date = ndb.DateProperty()
    startTime = ndb.TimeProperty()
    conferenceKey = ndb.KeyProperty(kind='Conference')
    ...
```

I decided to use the relatively new msgprop.EnumProperty for storing session
types in _typeOfSession_. It results in storing the integer value of the
_SessionType_ enum instead of the string value.

### Wishlists
Wihlisting is represented by instances of the _ConferenceWishlist_ model. Each
user can create many wishlists, one for each Conference.

``` python
class ConferenceWishlist(ndb.Model):
    """ConferenceWishlist --- maintains list of keys of favorite sessions for
    a given conference"""
    conferenceKey = ndb.KeyProperty(kind='Conference', required=True)
    sessionKeys = ndb.KeyProperty(kind='Session', repeated=True)
  ...
```

Using the user's Profile as an ancestor, it's easy to retrieve all
ConferenceWishlist records for the user. Having separate records for each
Conference can facilitate adding hooks to cleanup wishlist records when
Conferences are deleted as well as keeping the data organized to easily
retrieve all wishlisted sessions per conference. (Plus, with a 10MB max record
size, there's a slim chance that if the app never cleaned up old wishlists
having them all appended to a single record could hit the data cap.)

### Speakers
Speakers are modeled with Session's as parents and use the _name_ and _title_
attributes to generate keys. This allows for a few features:

1. Speakers can have the same names, but different "titles" to differentiate
them. Title could be set to actual job title and employer for instance to
keep them distinct.

2. Splitting _name_ and _title_ up allows for more advanced queries where
you can search by name, title, or both. For instance, someone might want to
find sessions where a CEO or CTO is speaking.

``` python
class Speaker(ndb.Model):
    """Speaker -- Session speaker"""
    name = ndb.StringProperty(required=True)
    title = ndb.StringProperty()
    numSessions = ndb.IntegerProperty(default=0)
    ...
```

The _numSessions_ attribute is used similarly to the _seatsAvailable_ in
Conference records. As Speakers are added to Sessions, the field is incremented
to reflect the number of Sessions the Speaker is speaking at. This logic can
be baked into things like picking "Featured Speakers" for instance.

---


## The Query Problem
The question of "find the sessions that start before 7pm and are not workshops"
causes an immediate issue if literally translated into a query similar to
(in psuedocode):
```
AND(startTime < 1900, sessionType != 'WORKSHOP')
```
The problem is Datastore queries must only have *one* inequality statement.

However, since the _sessionType_ field has finite cardinality (and in this
project I've created it as an Enum), we can rewrite the inequality to be an
equality based on the other known values like so:

```
AND(startTime < 1900, sessionType IN ['KEYNOTE', 'LECTURE'])
```

Instead, for fields with finite cardinality like Enums or Text fields used for
things like conference topics, the original filter formatting method will
preemptively raise a _BadRequestError_:
```
BadRequestError: Only one inequality filter per query is supported.
Encountered both typeOfSession and startTime
```

``` json
POST http://localhost:8080/_ah/api/conferenceCentral/v1/sessions/query

{
 "target": "SESSION",
 "filters": [
  {
   "field": "START_TIME",
   "operator": "LT",
   "value": "19:00"
  },
  {
   "field": "TYPE",
   "operator": "NE",
   "value": "WORKSHOP"
  }
 ]
}
```
_Note: you can send a GET to the endpoint /sessions/querydemo to execute the
above if you don't want to perform the POST_

At the moment, the translation logic only happens for EnumProperty, but could be
extended to work with StringProperty as well if a mechanism tracks unique values
and some boundaries are put on cardinality potentially. Might be a good use of
Memcache for storing a list of known values.

### Alternative Solutions

Alternatively, some logic

---

## References:

* [Creating an API with Implemented with Multiple Classes](https://cloud.google.com/appengine/docs/python/endpoints/create_api#creating_an_api_implemented_with_multiple_classes)
* [Stackoverflow - Split Cloud ENdpoint over Multiple Classes](http://stackoverflow.com/questions/23241390/split-cloud-endpoint-api-over-multiple-classes-and-multiple-files)
* [A guide to Python's Function Decorators](http://thecodeship.com/patterns/guide-to-python-function-decorators/)
