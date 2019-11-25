""" Demonstrate testing framework. """

import pytest

from aries_staticagent import Message, crypto
from aries_staticagent.mtc import (
    CONFIDENTIALITY, INTEGRITY, AUTHENTICATED_ORIGIN,
    DESERIALIZE_OK, NONREPUDIATION
)
from reporting import meta
from .schema import MessageSchema


@pytest.mark.asyncio
@meta(protocol='simple', version='0.1', role='*', name='simple')
async def test_simple_messaging(connection):
    """Show simple messages being passed to and from the test subject."""

    expected_schema = MessageSchema({
        '@type': 'test/protocol/1.0/test',
        '@id': str,
        'msg': 'pong'
    })

    ping = Message({
        '@type': 'test/protocol/1.0/test',
        'msg': 'ping'
    })
    print('Sending message:', ping.pretty_print())
    pong = await connection.send_and_await_reply_async(
        ping,
        timeout=1
    )

    print('Received message:', pong.pretty_print())

    assert pong.mtc.is_authcrypted()
    assert pong.mtc.sender == crypto.bytes_to_b58(connection.recipients[0])
    assert pong.mtc.recipient == connection.verkey_b58

    assert expected_schema(pong)
