#!/usr/bin/env python

"""queryutil.py

Logic related to querying the ConferenceCentral object model.

"""
from datetime import datetime

import endpoints
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from protorpc import messages
from protorpc.messages import FieldList

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
        'DURATION': 'duration',
        'HIGHLIGHTS': 'highlights'
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
    QueryForm containing one or many QueryMessages as query filters, target kind
     (e.g. 'Conference'), and the
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
    :param query_form: QueryForm message
    :param ancestor: ancestor Key
    :return: reference to ndb entity query object
    """
    if not isinstance(query_form, QueryForm):
        raise TypeError('Expected %s but got %s' % (QueryForm, query_form))

    # get a reference to the proper model class and use it to format the filters
    kind = __get_kind(query_form.target)
    inequality_filter, filters = __format_filters(query_form.filters, kind)

    # If exists, sort on inequality filter first
    q = kind(parent=ancestor).query(ancestor=ancestor)
    if not inequality_filter:
        q = q.order(SORT_MAP[kind])
    else:
        q = q.order(ndb.GenericProperty(inequality_filter))
        q = q.order(SORT_MAP[kind])

    for f in filters:
        # current casting logic.
        if f["field"] in ["month", "maxAttendees"]:
            f["value"] = int(f["value"])
        elif f['field'] in ['startTime']:
            # need to pass build time object
            filter_time = __parse_time(f['value'], '%H:%M')
            f['value'] = filter_time
        formatted_query = ndb.query.FilterNode(f['field'], f['operator'],
                                               f['value'])
        q = q.filter(formatted_query)

    print 'Built query: %s' % str(q)
    return q


def __get_operator(enum):
    """
    Get the appropriate query filter operator corresponding to the Enum value
    :param enum: QueryOperator
    :return: String with proper ndb.query.FilterNode operator value
    """
    if not isinstance(enum, QueryOperator):
        raise TypeError(
            'expected %s, but got %s' % (type(QueryOperator), type(enum)))

    if enum == QueryOperator.EQ:
        return '='
    elif enum == QueryOperator.GT:
        return '>'
    elif enum == QueryOperator.GTEQ:
        return '>='
    elif enum == QueryOperator.LT:
        return '<'
    elif enum == QueryOperator.LTEQ:
        return '<='
    elif enum == QueryOperator.NE:
        return '!='


def __get_kind(enum):
    """
    Get the proper entity kind given the QueryTarget enum
    :param enum: QueryTarget to resolve
    :return: reference to the proper kind class e.g. Conference, Session,
    Profile, etc.
    """
    if not isinstance(enum, QueryTarget):
        raise TypeError(
            'expected %s, but got %s' % (type(QueryTarget), type(enum)))

    if enum == enum.CONFERENCE:
        return Conference
    elif enum == enum.SESSION:
        return Session
    elif enum == enum.PROFILE:
        return Profile


def __get_field(kind, field):
    """
    Resolves the proper field to apply a filter against for a given kind
    :param kind: Kind to validate against
    :param field: string of field to get
    :return: valid string name of a kind's field, otherwise raises an exception
    """
    if kind in FIELD_MAP:
        field_map = FIELD_MAP.get(kind)
        return field_map.get(field, None)
    else:
        raise KeyError('not a supported kind: %s' % kind)


def __format_filters(query_filters, kind):
    """
    Parse, check validity and format user supplied filters.
    :param query_filters: list of QueryFilters to process
    :param kind: entity kind the query is targeting
    :return: tuple of (processed inequality filter, formatted filters (as list
    of dicts))
    """
    if not isinstance(query_filters, FieldList):
        raise TypeError(
            'expected %s, but got %s' % (type(FieldList), type(query_filters)))

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
            raise endpoints.BadRequestException(
                "Filter contains invalid field or operator.")

        # Every operation except "=" is an inequality
        if filtr["operator"] != "=":
            # TODO: handle operator of != on a finite field aka our enum fields!
            # Remember that you need to do
            # ndb.query.FilterNode('typeOfSession', 'in', [1, 2])

            # check if inequality operation has been used in previous filters
            # disallow the filter if inequality was performed on a different
            # field before track the field on which the inequality operation
            # is performed
            if isinstance(getattr(kind, str(filtr['field'])),
                          msgprop.EnumProperty):
                # we need to convert these to 'in' query filters
                filtr['operator'] = 'in'

                # get dict representation of the Enum, delete the key we want
                # to exclude
                # TODO: This is super hacky...gotta be a better way.
                enum_dict = getattr(kind, str(filtr['field'])).\
                    _enum_type.to_dict()
                del enum_dict[filtr['value']]

                # build the filter values (ints) since our FilterNode needs to
                # use the underlying ints
                filtr['value'] = enum_dict.values()
            else:
                if inequality_field and inequality_field != filtr['field']:
                    raise endpoints.BadRequestException(
                        'Inequality filter is allowed on only one field.')
                else:
                    inequality_field = filtr['field']

        formatted_filters.append(filtr)
    return inequality_field, formatted_filters


def __parse_time(time_string, time_format):
    """
    Parses a time string in HH:MM format and properly sets the year to the
    epoch date of 1970

    This gets around an issue where a raw datetime.time gets turned into a
    datetime.date by
    GAE with a date set to 1-1-1900 instead of 1-1-1970
    :param time_string: string with raw date
    :param time_format: string with the time format to use for parsing
    :return: datetime.time
    """
    return datetime.combine(
        datetime.utcfromtimestamp(0),
        datetime.strptime(time_string, time_format).time()
    )
