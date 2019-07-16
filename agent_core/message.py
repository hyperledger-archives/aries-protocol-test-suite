""" Define Message base class. """
from collections import UserDict
import json
import re
import uuid

from schema import Schema, Optional, Regex, SchemaError

from .utils import Semver


class InvalidMessage(Exception):
    """ Thrown when message is malformed. """


MTURI_RE = re.compile(r'(.*?)([a-z0-9._-]+)/(\d[^/]*)/([a-z0-9._-]+)$')


def generate_id():
    """ Generate a message id. """
    return str(uuid.uuid4())


def parse_type_info(message_type_uri):
    """ Parse message type for doc_uri, portocol, version, and short type.
    """
    matches = MTURI_RE.match(message_type_uri)
    if not matches:
        raise InvalidMessage()

    return matches.groups()


MESSAGE_SCHEMA = Schema({
    '@type': Regex(MTURI_RE),
    Optional('@id', default=generate_id): str,
    Optional(str): object
})


class Message(dict):
    """ Message base class.
        Inherits from UserDict meaning it behaves like a dictionary.
    """
    __slots__ = (
        'mtc',
        'doc_uri',
        'protocol',
        'version',
        'version_info',
        'short_type'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.update(MESSAGE_SCHEMA.validate(dict(self)))
        except SchemaError as err:
            raise InvalidMessage('Invalid message type') from err

        self.doc_uri, self.protocol, self.version, self.short_type = \
            parse_type_info(self.type)

        try:
            self.version_info = Semver.from_str(self.version)
        except ValueError as err:
            raise InvalidMessage('Invalid message type version') from err

    @property
    def type(self):
        """ Shortcut for msg['@type'] """
        return self['@type']

    @property
    def id(self):  # pylint: disable=invalid-name
        """ Shortcut for msg['@id'] """
        return self['@id']

    @property
    def qualified_protocol(self):
        """ Shortcut for constructing qualified protocol identifier from
            doc_uri and protocol
        """
        return self.doc_uri + self.protocol

    # Serialization
    @staticmethod
    def deserialize(serialized: str):
        """ Deserialize a message from a json string. """
        try:
            return Message(json.loads(serialized))
        except json.decoder.JSONDecodeError as err:
            raise InvalidMessage('Could not deserialize message') from err

    def serialize(self):
        """ Serialize a message into a json string. """
        return json.dumps(self)

    def pretty_print(self):
        return json.dumps(self, indent=2)


class Noop(Message):  # pylint: disable=too-many-ancestors
    """ Noop message """
    def __init__(self, **kwargs):
        super().__init__({
            '@type': 'noop/noop/0.0/noop'
        })

        return_route = kwargs.get('return_route', False)
        if return_route:
            self['~transport']['return_route'] = 'all'
