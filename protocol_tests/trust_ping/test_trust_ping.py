"""Trust Ping tests."""

import asyncio

import pytest
from voluptuous import Optional, Any

from aries_staticagent import Message, crypto
from aries_staticagent.mtc import (
    CONFIDENTIALITY, INTEGRITY, AUTHENTICATED_ORIGIN,
    DESERIALIZE_OK, NONREPUDIATION
)

from reporting import meta
from ..schema import MessageSchema
from .. import Suite

TYPE = Suite.TYPE_PREFIX + "trust_ping/1.0/ping"
ALT_TYPE = Suite.ALT_TYPE_PREFIX + "trust_ping/1.0/ping"

@pytest.mark.asyncio
@meta(protocol='trust_ping', version='0.1',
      role='receiver', name='responds-to-trust-ping')
async def test_trust_ping_with_response_requested_true(connection):
    """Test that subject responds to trust pings."""

    expected_trust_pong_schema = MessageSchema({
        "@type": Any(TYPE, ALT_TYPE),
        "@id": str,
        "~thread": {"thid": str},
        Optional("~timing"): {
            Optional("in_time"): str,
            Optional("out_time"): str
        },
        Optional("comment"): str
    })

    trust_ping = Message({
        "@type": TYPE,
        # "@id" is added by the staticagent lib
        "response_requested": True
    })
    #print('Sending message:', trust_ping.pretty_print())
    trust_pong = await connection.send_and_await_reply_async(
        trust_ping,
        timeout=1
    )

    #print('Received message:', trust_pong.pretty_print())

    assert trust_pong.mtc.is_authcrypted()
    # are you, you and am I, me?
    assert trust_pong.mtc.sender == crypto.bytes_to_b58(
        connection.recipients[0]
    )
    assert trust_pong.mtc.recipient == connection.verkey_b58

    assert expected_trust_pong_schema(trust_pong)
    assert trust_pong['~thread']['thid'] == trust_ping.id


@pytest.mark.asyncio
@meta(protocol='trust_ping', version='0.1',
      role='sender', name='can-send-trust-ping')
async def test_trust_ping_sender(backchannel, connection):
    """Test that subject sends a trust ping."""
    expected_trust_ping_schema = MessageSchema({
        "@type": Any(TYPE, ALT_TYPE),
        "@id": str,
        Optional("~timing"): {
            Optional("out_time"): str,
            Optional("expires_time"): str,
            Optional("delay_milli"): int
        },
        Optional("comment"): str,
        "response_requested": bool
    })

    with connection.next() as next_msg:
        await backchannel.trust_ping_v1_0_send_ping(connection)
        msg = await asyncio.wait_for(next_msg, 5)

    assert expected_trust_ping_schema(msg)
    assert msg.mtc.is_authcrypted()
    assert msg.mtc.sender == crypto.bytes_to_b58(connection.recipients[0])
    assert msg.mtc.recipient == connection.verkey_b58

    await connection.send_async({
        "@type": TYPE,
        "~thread": {"thid": msg.id},
    })

    # TODO Backchannel verify reciept?
