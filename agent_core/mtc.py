""" Message Trust Context. See Aries RFC 0029: Message Trust Contexts.

    This file is inspired by the example implementation contained within
    that RFC.
"""
from typing import Dict, Any, Optional
from enum import Flag, auto


class ContextsConflict(Exception):
    """ Thrown when the passed contexts overlap """


class Context(Flag):
    """ Flags for MTC """
    NONE = 0
    SIZE_OK = auto()
    DESERIALIZE_OK = auto()
    KEYS_OK = auto()
    VALUES_OK = auto()
    CONFIDENTIALITY = auto()
    INTEGRITY = auto()
    AUTHENTICATED_ORIGIN = auto()
    NONREPUDIATION = auto()
    PFS = auto()
    UNIQUENESS = auto()
    LIMITED_SCOPE = auto()


LABELS = {
    Context.SIZE_OK: 'size_ok',
    Context.DESERIALIZE_OK: 'deserialize_ok',
    Context.KEYS_OK: 'keys_ok',
    Context.VALUES_OK: 'values_ok',
    Context.CONFIDENTIALITY: 'confidentiality',
    Context.INTEGRITY: 'integrity',
    Context.AUTHENTICATED_ORIGIN: 'authenticated_origin',
    Context.NONREPUDIATION: 'nonrepudiation',
    Context.PFS: 'pfs',
    Context.UNIQUENESS: 'uniqueness',
    Context.LIMITED_SCOPE: 'limited_scope'
}


# Context Shortcuts
NONE = Context.NONE
SIZE_OK = Context.SIZE_OK
DESERIALIZE_OK = Context.DESERIALIZE_OK
KEYS_OK = Context.KEYS_OK
VALUES_OK = Context.VALUES_OK
CONFIDENTIALITY = Context.CONFIDENTIALITY
INTEGRITY = Context.INTEGRITY
AUTHENTICATED_ORIGIN = Context.AUTHENTICATED_ORIGIN
NONREPUDIATION = Context.NONREPUDIATION
PFS = Context.PFS
UNIQUENESS = Context.UNIQUENESS
LIMITED_SCOPE = Context.LIMITED_SCOPE


class MessageTrustContext:
    """ Message Trust Context

        Holds the contexts as well as data associated with message trust
        contexts such as the keys used to encrypt the message and allowing us
        to know that the origin is authenticated, etc.
    """
    __slots__ = '_affirmed', '_denied', 'additional_data'

    def __init__(
            self,
            affirmed: Context = Context.NONE,
            denied: Context = Context.NONE,
            additional_data: Dict[Any, Any] = {}
                ):

        if affirmed & denied != Context.NONE:
            raise ContextsConflict()

        self._affirmed = affirmed
        self._denied = denied
        self.additional_data = additional_data

    @property
    def ad(self):
        return self.additional_data

    @property
    def affirmed(self):
        """ Access affirmed contexts """
        return self._affirmed

    @property
    def denied(self):
        """ Access denied contexts """
        return self._denied

    def __getitem__(self, context: Context):
        if (self._affirmed & context) == context:
            return True
        if (self._denied & context) == context:
            return False
        return None

    def __setitem__(self, context: Context, value: Optional[bool]):
        if not (isinstance(value, bool) or value is None):
            raise TypeError(
                'Value of type bool or None was expected, got %s' % type(value)
            )

        if value is None:
            # Set undefined
            self._affirmed &= ~context
        elif value is True:
            self._affirmed |= context
            self._denied &= ~context
        elif value is False:
            self._denied |= context
            self._affirmed &= ~context

    def __str__(self):
        str_repr = 'mtc:'
        plus = []
        minus = []
        for context, label in LABELS.items():
            if self[context] is True:
                plus.append('+%s' % label)
            elif self[context] is False:
                minus.append('-%s' % label)

        str_repr = ' '.join([str_repr] + plus + minus)
        return str_repr
