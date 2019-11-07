""" Manual Connection Protocol tests.
"""
import re
import base64
import uuid

import pytest

from aries_staticagent import Message, crypto
from voluptuous import Schema, Optional
from reporting import meta
from ..schema import MessageSchema, Slot, fill_slots

DIDDOC_SCHEMA = Schema({
    "@context": "https://w3id.org/did/v1",
    "id": str,
    "publicKey": [{
        "id": str,
        "type": "Ed25519VerificationKey2018",
        "controller": str,
        "publicKeyBase58": str
    }],
    "service": [{
        "id": str,
        "type": "IndyAgent",
        "recipientKeys": [str],
        Optional("routingKeys"): [str],
        "serviceEndpoint": str,
    }],
})

INVITE = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/invitation'
INVITE_SCHEMA = MessageSchema({
    '@type': INVITE,
    '@id': str,
    'label': str,
    'recipientKeys': [str],
    Optional('routingKeys'): [str],
    'serviceEndpoint': str,
})

REQUEST = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/request'
REQUEST_SCHEMA = MessageSchema({
    '@type': REQUEST,
    '@id': str,
    'label': str,
    'connection': {
        'DID': str,
        'DIDDoc': DIDDOC_SCHEMA
    }
})

RESPONSE = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/response'
RESPONSE_SCHEMA_PRE_SIG_VERIFY = MessageSchema({
    '@type': RESPONSE,
    '@id': str,
    '~thread': {
        'thid': str,
        Optional('sender_order'): int
    },
    'connection~sig': object
})

RESPONSE_SCHEMA_POST_SIG_VERIFY = MessageSchema({
    '@type': RESPONSE,
    '@id': str,
    '~thread': {
        'thid': str,
        Optional('sender_order'): int
    },
    'connection': {
        'DID': str,
        'DIDDoc': DIDDOC_SCHEMA
    }
})


def parse_invite(invite_url: str) -> Message:
    """ Parse an invite url """
    matches = re.match('(.+)?c_i=(.+)', invite_url)
    assert matches, 'Improperly formatted invite url!'

    invite_msg = Message.deserialize(
        base64.urlsafe_b64decode(matches.group(2)).decode('ascii')
    )

    INVITE_SCHEMA(invite_msg)

    return invite_msg


def build_invite(label: str, connection_key: str, endpoint: str) -> str:
    msg = Message({
        '@type': INVITE,
        'label': label,
        'recipientKeys': [connection_key],
        'serviceEndpoint': endpoint,
        'routingKeys': []
    })

    b64_invite = base64.urlsafe_b64encode(
        bytes(msg.serialize(), 'utf-8')
    ).decode('ascii')

    return '{}?c_i={}'.format(endpoint, b64_invite)


def build_request(
        label: str,
        my_did: str,
        my_vk: str,
        endpoint: str
        ) -> Message:
    """ Construct a connection request. """
    return Message({
        '@type': REQUEST,
        '@id': str(uuid.uuid4()),
        'label': label,
        'connection': {
            'DID': my_did,
            'DIDDoc': {
                "@context": "https://w3id.org/did/v1",
                "id": my_did,
                "publicKey": [{
                    "id": my_did + "#keys-1",
                    "type": "Ed25519VerificationKey2018",
                    "controller": my_did,
                    "publicKeyBase58": my_vk
                }],
                "service": [{
                    "id": my_did + ";indy",
                    "type": "IndyAgent",
                    "recipientKeys": [my_vk],
                    "routingKeys": [],
                    "serviceEndpoint": endpoint,
                }],
            }
        }
    })


def build_response(
        req_id: str,
        my_did: str,
        my_vk: str,
        endpoint: str
        ) -> Message:
    return Message({
        '@type': RESPONSE,
        '@id': str(uuid.uuid4()),
        '~thread': {
            'thid': req_id,
            'sender_order': 0
        },
        'connection': {
            'DID': my_did,
            'DIDDoc': {
                "@context": "https://w3id.org/did/v1",
                "id": my_did,
                "publicKey": [{
                    "id": my_did + "#keys-1",
                    "type": "Ed25519VerificationKey2018",
                    "controller": my_did,
                    "publicKeyBase58": my_vk
                }],
                "service": [{
                    "id": my_did + ";indy",
                    "type": "IndyAgent",
                    "recipientKeys": [my_vk],
                    "routingKeys": [],
                    "serviceEndpoint": endpoint,
                }],
            }
        }
    })


@pytest.mark.features("core.manual", "connection.manual")
@pytest.mark.priority(10)
@pytest.mark.asyncio
@meta(protocol='connections', version='1.0', role='inviter', name='can-start')
async def test_connection_started_by_tested_agent(config, temporary_channel):
    """Test a connection as started by the agent under test."""
    invite_url = input('Input generated connection invite: ')

    invite_msg = parse_invite(invite_url)

    print("\nReceived Invite:\n", invite_msg.pretty_print())

    # Create my information for connection
    with temporary_channel(
            invite_msg['recipientKeys'][0],
            invite_msg['serviceEndpoint']) as conn:

        did = crypto.bytes_to_b58(conn.my_vk[:16])
        my_vk_b58 = crypto.bytes_to_b58(conn.my_vk)

        # Send Connection Request to inviter
        request = build_request(
            'test-connection-started-by-tested-agent',
            did,
            my_vk_b58,
            config['endpoint']
        )

        print("\nSending Request:\n", request.pretty_print())
        print("Awaiting response from tested agent...")
        response = await conn.send_and_await_reply_async(
            request,
            condition=lambda msg: msg.type == RESPONSE,
            timeout=30
        )

        RESPONSE_SCHEMA_PRE_SIG_VERIFY(response)
        print(
            "\nReceived Response (pre signature verification):\n",
            response.pretty_print()
        )

        signer, response['connection'] = \
            crypto.verify_signed_message_field(response['connection~sig'])
        assert signer == invite_msg['recipientKeys'][0], 'Unexpected signer'
        del response['connection~sig']

        RESPONSE_SCHEMA_POST_SIG_VERIFY(response)
        assert response['~thread']['thid'] == request.id

        print(
            "\nReceived Response (post signature verification):\n",
            response.pretty_print()
        )

        # To send more messages, update conn's their_vk and endpoint
        # to those disclosed in the response.


@pytest.mark.features("core.manual", "connection.manual")
@pytest.mark.priority(10)
@pytest.mark.asyncio
@meta(protocol='connections', version='1.0', role='invitee', name='can-receive')
async def test_connection_started_by_suite(config, temporary_channel):
    """ Test a connection as started by the suite. """

    with temporary_channel() as conn:
        invite_str = build_invite(
            'test-suite-connection-started-by-suite',
            conn.my_vk_b58,
            config['endpoint']
        )

        print('Encoding invitation:', parse_invite(invite_str))

        print("\n\nInvitation encoded as URL: ", invite_str)

        print("Awaiting request from tested agent...")
        def condition(msg):
            print(msg)
            return msg.type == REQUEST
        request = await conn.await_message(
            condition=condition,
            timeout=30
        )

        REQUEST_SCHEMA(request)
        print("\nReceived request:\n", request.pretty_print())

        (_, conn.their_vk_b58, conn.endpoint) = (
            request['connection']['DIDDoc']['publicKey'][0]['controller'],
            request['connection']['DIDDoc']['publicKey'][0]['publicKeyBase58'],
            request['connection']['DIDDoc']['service'][0]['serviceEndpoint']
        )
        conn.their_vk = crypto.b58_to_bytes(conn.their_vk_b58)

        conn.my_vk, conn.my_sk = crypto.create_keypair()
        conn.did = crypto.bytes_to_b58(conn.my_vk[:16])
        conn.my_vk_b58 = crypto.bytes_to_b58(conn.my_vk)

        response = build_response(
            request.id,
            conn.did,
            conn.my_vk_b58,
            config['endpoint']
        )

        print(
            "\nSending Response (pre signature packing):\n",
            response.pretty_print()
        )

        response['connection~sig'] = crypto.sign_message_field(
            response['connection'],
            signer=conn.my_vk_b58,
            secret=conn.my_sk
        )
        del response['connection']
        print(
            "\nSending Response (post signature packing):\n",
            response.pretty_print()
        )

        await conn.send_async(response)
