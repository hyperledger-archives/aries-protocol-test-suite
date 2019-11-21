import pytest

from aries_staticagent import Message, crypto
from aries_staticagent.mtc import (
    CONFIDENTIALITY, INTEGRITY, AUTHENTICATED_ORIGIN,
    DESERIALIZE_OK, NONREPUDIATION
)
from reporting import meta
from ..schema import MessageSchema
from voluptuous import Optional, Required


@pytest.mark.asyncio
@meta(protocol='trust_ping', version='0.1', role='*', name='trust-ping-with-response-requested-true')
async def test_trust_ping_with_response_requested_true(backchannel):

    expected_trust_ping_schema = MessageSchema({
        "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
        "@id": str,
        Optional("~timing"): {
            Optional("out_time"): str,
            Optional("expires_time"): str,
            Optional("delay_milli"): int
        },
        Optional("comment"): str,
        "response_requested": bool
    })

    expected_trust_pong_schema = MessageSchema({
        "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping_response",
        Optional("@id"): str,
        "~thread": {"thid": str},
        Optional("~timing"): {
            Optional("in_time"): str,
            Optional("out_time"): str
        },
        Optional("comment"): str
    })

    trust_ping = Message({
        "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
        # "@id" is added by the staticagent lib
        "response_requested": True
    })
    print('Sending message:', trust_ping.pretty_print())
    trust_pong = await backchannel.send_and_await_reply_async(
        trust_ping,
        timeout=1
    )

    print('Received message:', trust_pong.pretty_print())
    # is auth crypted?----------------------
    assert trust_pong.mtc[
        CONFIDENTIALITY | INTEGRITY | AUTHENTICATED_ORIGIN | DESERIALIZE_OK
    ]
    assert not trust_pong.mtc[NONREPUDIATION]
    # --------------------------------------
    # are you, you and am I, me?
    assert trust_pong.mtc.ad['sender_vk'] == crypto.bytes_to_b58(
        backchannel.their_vk)
    assert trust_pong.mtc.ad['recip_vk'] == crypto.bytes_to_b58(
        backchannel.my_vk)
    # --------------------------------------
    assert expected_trust_pong_schema(trust_pong)
    assert trust_pong['~thread']['thid'] == trust_ping['@id']