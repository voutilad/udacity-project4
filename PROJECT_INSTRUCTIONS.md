How will I complete this project?
===

This project is connected to the Developing Scalable Apps with Python courses, but depending on your background 
knowledge you may not need the entirety of the course to complete this project. Here's what you should do:

1. You do not have to do any work on the frontend part of the application to finish this project. All your added 
functionality will be testable via APIs Explorer. More in-depth explanation.

2. Clone the conference application repository.

3. Add Sessions to a Conference
  * Define the following endpoint methods
    * getConferenceSessions(websafeConferenceKey) -- Given a conference, return all sessions
    * getConferenceSessionsByType(websafeConferenceKey, typeOfSession) Given a conference, return all sessions of a 
    specified type (eg lecture, keynote, workshop)
    * getSessionsBySpeaker(speaker) -- Given a speaker, return all sessions given by this particular speaker, 
    across all conferences
    * createSession(SessionForm, websafeConferenceKey) -- open to the organizer of the conference
  * Define Session class and SessionForm
    * Session name
    * highlights
    * speaker
    * duration
    * typeOfSession
    * date
    * start time (in 24 hour notation so it can be ordered).

5. Add Sessions to User Wishlist
  * Define the following Endpoints methods
    * addSessionToWishlist(SessionKey) -- adds the session to the user's list of sessions they are interested in attending
    * getSessionsInWishlist() -- query for all the sessions in a conference that the user is interested in

6. Work on indexes and queries
  * Create indexes
  * Come up with 2 additional queries
  * Solve the following query related problem: Let’s say that you don't like workshops and you don't like sessions 
  after 7 pm. How would you handle a query for all non-workshop sessions before 7 pm? What is the problem for 
  implementing this query? What ways to solve it did you think of?

7. Add a Task
  * When adding a new session to a conference, determine whether or not the session's speaker should be the new 
  featured speaker. This should be handled using App Engine's Task Queue.
  * Define the following endpoints method: getFeaturedSpeaker()
