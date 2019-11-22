"""Default implementations."""

import hashlib

from aries_staticagent import StaticConnection, crypto

from protocol_tests.backchannel import Backchannel
from protocol_tests.connection.backchannel import ConnectionsBackchannel


class DefaultBackchannel(Backchannel, ConnectionsBackchannel):
    """Default back channel using agent connection."""
    def __init__(self):
        self.keys = StaticConnection.Keys(*crypto.create_keypair(
            hashlib.sha256(b'aries-protocol-test-suite').digest()
        ))
        self.their_keys = StaticConnection.Keys(*crypto.create_keypair(
            hashlib.sha256(b'aries-protocol-test-subject').digest()
        ))
        self.connection = None

    async def setup(self, config, suite):
        self.connection = StaticConnection(
            self.keys,
            their_vk=self.their_keys.verkey,
            endpoint=config['subject']['endpoint']
        )
        suite.add_frontchannel(self.connection)

    async def reset(self):
        self.connection.send(...)

    async def new_connection(self, info, parameters=None):
        return self.connection.send_and_await_reply_async(...)

    async def connections_v1_0_inviter_start(self):
        return self.connection.send_and_await_reply_async(...)

    async def connections_v1_0_invitee_start(self, invite):
        self.connection.send(invite)
