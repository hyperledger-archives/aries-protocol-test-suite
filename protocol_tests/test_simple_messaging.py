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
async def test_simple_messaging(backchannel):
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
    pong = await backchannel.send_and_await_reply_async(
        ping,
        timeout=1
    )

    print('Received message:', pong.pretty_print())

    assert pong.mtc[
        CONFIDENTIALITY | INTEGRITY | AUTHENTICATED_ORIGIN | DESERIALIZE_OK
    ]
    assert not pong.mtc[NONREPUDIATION]
    assert pong.mtc.ad['sender_vk'] == crypto.bytes_to_b58(backchannel.their_vk)
    assert pong.mtc.ad['recip_vk'] == crypto.bytes_to_b58(backchannel.my_vk)

    assert expected_schema.validate(pong)
