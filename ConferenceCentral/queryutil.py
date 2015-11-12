#!/usr/bin/env python

"""queryutil.py

Logic related to querying the ConferenceCentral object model.

"""
import endpoints
from protorpc import messages
from protorpc.messages import FieldList
from google.appengine.ext import ndb
from models import Conference, Session, Profile, ConferenceWishlist

__author__ = 'voutilad@gmail.com (Dave Voutila)'

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
        'DURATION' : 'duration'
    },
    ConferenceWishlist: {
        'CONF_KEY': 'conferenceKeys',
        'SESSION_KEYS': 'sessionKeys'
    }
}

SORT_MAP = {
    Conference: Conference.name,
    Session: Session.startTime,
    Profile: Profile.displayName
}

class QueryOperator(messages.Enum):
    """QueryOperator -- enum of valid filter operators for query"""
    EQ = 1
    GT = 2
    GTEQ = 3
    LT = 4
    LTEQ = 5
    NE = 6


class QueryTarget(messages.Enum):
    """QueryTarget -- kind of entity to target with a query"""
    CONFERENCE = 1
    SESSION = 2
    PROFILE = 3


class QueryFilter(messages.Message):
    """
    Query object containing target field, operator, and value
    """
    field = messages.StringField(1, required=True)
    operator = messages.EnumField(QueryOperator, 2, required=True)
    value = messages.StringField(3, required=True)


class QueryForm(messages.Message):
    """
    QueryForm containing one or many QueryMessages as query filters, target kind (e.g. 'Conference'), and the
    max number of results to return.
    """
    target = messages.EnumField(QueryTarget, 1, required=True)
    filters = messages.MessageField(QueryFilter, 2, repeated=True)
    num_results = messages.IntegerField(3, default=20)
    sort_by = messages.StringField(4)
    ancestorWebSafeKey = messages.StringField(5)


def query(query_form, ancestor=None):
    """
    Return formatted query from the submitted filters.
    :param request: QueryForm message
    :return: reference to ndb entity query object
    """
    if not isinstance(query_form, QueryForm):
        raise TypeError('Expected %s but got %s' % (QueryForm, query_form))

    # get a reference to the proper model class and use it to format the filters
    kind = __get_kind(query_form.target)
    inequality_filter, filters = __format_filters(query_form.filters, kind)

    # If exists, sort on inequality filter first
    q = kind.query(ancestor=ancestor)
    if not inequality_filter:
        q = q.order(SORT_MAP[kind])
    else:
        q = q.order(ndb.GenericProperty(inequality_filter))
        q = q.order(SORT_MAP[kind])

    for f in filters:
        # current casting logic. TODO: will need to be expanded upon for dates, etc.
        if f["field"] in ["month", "maxAttendees"]:
            f["value"] = int(f["value"])
        formatted_query = ndb.query.FilterNode(f["field"], f["operator"], f["value"])
        q = q.filter(formatted_query)

    return q


def __get_operator(enum):
    """
    Get the appropriate query filter operator corresponding to the Enum value
    :param enum: QueryOperator
    :return: String with proper ndb.query.FilterNode operator value
    """
    if not isinstance(enum, QueryOperator):
        raise TypeError('expected %s, but got %s' % (type(QueryOperator), type(enum)))

    if enum.name == 'EQ':
        return '='
    elif enum.name == 'GT':
        return '>'
    elif enum.name == 'GTEQ':
        return '>='
    elif enum.name == 'LT':
        return '<'
    elif enum.name == 'LTEQ':
        return '<='
    elif enum.name == 'NE':
        return '!='


def __get_kind(enum):
    """
    Get the proper entity kind given the QueryTarget enum
    :param enum: QueryTarget to resolve
    :return: reference to the proper kind class e.g. Conference, Session, Profile, etc.
    """
    if not isinstance(enum, QueryTarget):
        raise TypeError('expected %s, but got %s' % (type(QueryTarget), type(enum)))

    if enum.name == 'CONFERENCE':
        return Conference
    elif enum.name == 'SESSION':
        return Session
    elif enum.name == 'PROFILE':
        return Profile


def __get_field(kind, field):
    """
    Resolves the proper field to apply a filter against for a given kind
    :param kind: Kind to validate against
    :param field: string of field to get
    :return: valid string name of a kind's field, otherwise raises an exception
    """
    if FIELD_MAP.has_key(kind):
        field_map = FIELD_MAP.get(kind)
        return field_map.get(field, None)
    else:
        raise KeyError('not a supported kind: %s' % kind)


def __format_filters(query_filters, kind):
    """
    Parse, check validity and format user supplied filters.
    :param query_filters: list of QueryFilters to process
    :param filters: entity kind the query is targeting
    :return: tuple of (processed inequality filter, formatted filters (as list of dicts))
    """
    if not isinstance(query_filters, FieldList):
        raise TypeError('expected %s, but got %s' % (type(FieldList), type(query_filters)))

    formatted_filters = []
    inequality_field = None

    for qf in query_filters:
        if not isinstance(qf, QueryFilter):
            raise TypeError('expected %s, but got %s' % (QueryFilter, qf))

        filtr = {'value': qf.value}

        try:
            filtr['field'] = __get_field(kind, qf.field)
            filtr['operator'] = __get_operator(qf.operator)
        except KeyError:
            raise endpoints.BadRequestException("Filter contains invalid field or operator.")

        # Every operation except "=" is an inequality
        if filtr["operator"] != "=":
            # TODO: handle operator of != on a finite field aka our enum fields!
            # Remember that you need to do ndb.query.FilterNode('typeOfSession', 'in', [1, 2])

            # check if inequality operation has been used in previous filters
            # disallow the filter if inequality was performed on a different field before
            # track the field on which the inequality operation is performed
            if inequality_field and inequality_field != filtr['field']:
                raise endpoints.BadRequestException('Inequality filter is allowed on only one field.')
            else:
                inequality_field = filtr['field']

        formatted_filters.append(filtr)
    return inequality_field, formatted_filters


def __convert_inequality(enum_type, value):
    """
    Creates the proper set inequality for filter on an ndb.EnumProperty
    :param enum_type: ndb.EnumProperty used in the filter
    :param value: value of the original inequality
    :return: filter dict {
    """