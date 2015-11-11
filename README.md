ConferenceCentral - Udacity FullStack Nanodegree Project 4
=====

Course code for Building Scalable Apps with Google App Engine in Python class

_Author: Dave Voutila_

Changes from original ConferenceCentral
---
I've made numerous changes both for purposes of the project requirements as well as personal design preferences.

### Refactored API into Multiple Modules
I found having all the endpoints and methods defined in a single class in a simple module rather unwieldy. 
Following [Creating an API with Implemented with Multiple Classes](https://cloud.google.com/appengine/docs/python/endpoints/create_api#creating_an_api_implemented_with_multiple_classes) 
I decided to break the API up into it's core parts:

* _conferenceCentral.conference_ - [conference.py] methods related to Conference objects
* _conferenceCentral.profile_ - [profile.py] methods related to user Profile objects
* _conferenceCentral.session_ - [session.py] methods related to Conference Session objects

As a result, I had to update some of the javascript using the Google Client API js library to point to the new paths.

Also, [app.yaml] is updated now to account for the changes and the _endpoints.api_server_ call is now isolated from 
the configuration of the API (now located in [settings.py]).

### 

References:
---
* [Creating an API with Implemented with Multiple Classes](https://cloud.google.com/appengine/docs/python/endpoints/create_api#creating_an_api_implemented_with_multiple_classes)
** [Stackoverflow](http://stackoverflow.com/questions/23241390/split-cloud-endpoint-api-over-multiple-classes-and-multiple-files)

