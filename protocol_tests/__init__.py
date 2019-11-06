""" Protocol Test Helpers """
from typing import Dict, Iterable, Union
from contextlib import contextmanager
import hashlib
import json

from schema import Schema

from aries_staticagent import StaticConnection, Message, crypto


class MessageSchema():  # pylint: disable=too-few-public-methods
    """ Wrap Schema for better message validation experience """
    def __init__(self, schema_dict):
        self._schema = Schema(schema_dict)

    def validate(self, msg: Message):
        """ Validate message, storing defaults inserted by validation. """
        msg.update(self._schema.validate(dict(msg)))
        return msg


def _recipients_from_packed_message(packed_message: bytes) -> Iterable[str]:
    """
    Inspect the header of the packed message and extract the recipient key.
    """
    try:
        wrapper = json.loads(packed_message)
    except Exception as err:
        raise ValueError("Invalid packed message") from err

    recips_json = crypto.b64_to_bytes(
        wrapper["protected"], urlsafe=True
    ).decode("ascii")
    try:
        recips_outer = json.loads(recips_json)
    except Exception as err:
        raise ValueError("Invalid packed message recipients") from err

    return map(lambda recip: recip['header']['kid'], recips_outer['recipients'])


class ChannelManager(StaticConnection):
    """
    Manage connections to agent under test.

    The Channel Manager itself is a static connection to the test subject
    allowing it to be used as the backchannel.
    """

    def __init__(self, endpoint: str):
        """
        Initialize Backchannel static connection using predefined identities.

        Args:
            endpoint: HTTP URL of test subjects backchannel endpoint
        """
        test_suite_vk, test_suite_sk = crypto.create_keypair(
            hashlib.sha256(b'aries-protocol-test-suite').digest()
        )
        test_subject_vk, _test_subject_sk = crypto.create_keypair(
            hashlib.sha256(b'aries-protocol-test-subject').digest()
        )
        super().__init__(
            test_suite_vk,
            test_suite_sk,
            test_subject_vk,
            endpoint
        )

        self.frontchannels: Dict[str, StaticConnection] = {}

    @property
    def backchannel(self):
        """Return a reference to the backchannel (self)."""
        return self

    @property
    def test_suite_vk(self):
        """Get test_suite_vk."""
        return self.my_vk

    async def handle(self, packed_message: bytes):
        """
        Route an incoming message to self (the backchannel) or to the
        appropriate frontchannels.
        """
        for recipient in _recipients_from_packed_message(packed_message):
            if recipient == self.my_vk_b58:
                await super().handle(packed_message)
            if recipient in self.frontchannels:
                await self.frontchannels[recipient].handle(packed_message)

    def new_frontchannel(
            self,
            their_vk: Union[bytes, str],
            endpoint: str) -> StaticConnection:
        """
        Create a new connection and add it as a frontchannel.

        Args:
            fc_vk: The new frontchannel's verification key
            fc_sk: The new frontchannel's signing key
            their_vk: The test subject's verification key for this channel
            endpoint: The HTTP URL to the endpoint of the test subject.

        Returns:
            Returns the new front channel (static connection).
        """
        fc_vk, fc_sk = crypto.create_keypair()
        new_fc = StaticConnection(
            fc_vk,
            fc_sk,
            their_vk,
            endpoint
        )
        frontchannel_index = crypto.bytes_to_b58(fc_vk)
        self.frontchannels[frontchannel_index] = new_fc
        return new_fc

    def add_frontchannel(self, connection: StaticConnection):
        """Add an already created connection as a frontchannel."""
        frontchannel_index = crypto.bytes_to_b58(connection.my_vk)
        self.frontchannels[frontchannel_index] = connection

    def remove_frontchannel(self, connection: StaticConnection):
        """
        Remove a frontchannel.

        Args:
            fc_vk: The frontchannel's verification key
        """
        fc_vk = crypto.bytes_to_b58(connection.my_vk)
        if fc_vk in self.frontchannels:
            del self.frontchannels[fc_vk]

    @contextmanager
    def temporary_channel(
            self,
            their_vk=None,
            endpoint=None) -> StaticConnection:
        """Use 'with' statement to use a temporary channel."""
        channel = self.new_frontchannel(their_vk or b'', endpoint or '')
        yield channel
        self.remove_frontchannel(channel)
