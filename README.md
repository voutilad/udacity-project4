# ConferenceCentral - Udacity FullStack Nano-degree Project 4

_For the original ConferenceCentral app, see [https://github.com/udacity/ud858](https://github.com/udacity/ud858)_

*Author*: Dave Voutila

---

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

As a result, I had to update some of the javascript using the Google Client API
js library to point to the new paths.

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

In code:
```
Session.query(Session.startTime < t)
```

Instead, for fields with finite cardinality, the original filter formatting
method will preemptively raise a _BadRequestError_:
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

###

References:
---
* [Creating an API with Implemented with Multiple Classes](https://cloud.google.com/appengine/docs/python/endpoints/create_api#creating_an_api_implemented_with_multiple_classes)
** [Stackoverflow](http://stackoverflow.com/questions/23241390/split-cloud-endpoint-api-over-multiple-classes-and-multiple-files)
