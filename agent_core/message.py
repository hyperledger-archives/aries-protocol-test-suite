""" Define Message base class. """
from collections import UserDict
import json
import re
import uuid

from .module import Semver

class InvalidMessageType(Exception):
    """ Thrown when message type is malformed. """

class Message(UserDict): # pylint: disable=too-many-ancestors
    """ Message base class.
        Inherits from UserDict meaning it behaves like a dictionary.
    """
    MTURI_RE = re.compile(r'(.*?)([a-z0-9._-]+)/(\d[^/]*)/([a-z0-9._-]+)$')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doc_uri, self.protocol, self.version, self.short_type = \
                Message.parse_type_info(self.type)
        try:
            self.version_info = Semver.from_str(self.version)
        except ValueError as err:
            raise InvalidMessageType('Invalid message type version') from err

        if '@id' not in self.data:
            self.data['@id'] = str(uuid.uuid4())

    @property
    def type(self):
        """ Shortcut for msg['@type'] """
        return self['@type']

    @property
    def id(self): # pylint: disable=invalid-name
        """ Shortcut for msg['@id'] """
        return self['@id']

    @property
    def qualified_protocol(self):
        """ Shortcut for constructing qualified protocol identifier from doc_uri and protocol """
        return self.doc_uri + self.protocol

    @staticmethod
    def parse_type_info(message_type_uri):
        """ Parse message type for doc_uri, portocol, version, and short type """
        matches = Message.MTURI_RE.match(message_type_uri)
        if not matches:
            raise InvalidMessageType()

        return matches.groups()

    @staticmethod
    def deserialize(serialized: str):
        """ Deserialize a message from a json string. """
        return Message(json.loads(serialized))

    def serialize(self):
        """ Serialize a message into a json string. """
        return json.dumps(self.data)
