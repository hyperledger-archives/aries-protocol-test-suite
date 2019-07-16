""" Manual Connection Protocol tests.
"""
import re
import base64
import uuid

from ariespython import did
from schema import Optional
import pytest

from agent_core.message import Message
from .. import MessageSchema

DIDDOC_SCHEMA = MessageSchema({
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
        "routingKeys": [str],
        "serviceEndpoint": str,
    }],
})

INVITE = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/invitation'
INVITE_SCHEMA = MessageSchema({
    '@type': INVITE,
    '@id': str,
    'label': str,
    'recipientKeys': [str],
    'routingKeys': [str],
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

    INVITE_SCHEMA.validate(invite_msg)

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
async def test_connection_started_by_tested_agent(config, agent):
    """ Test a connection as started by the agent under test """
    invite_url = input('Input generated connection invite: ')

    invite_msg = parse_invite(invite_url)

    print("\nReceived Invite:\n", invite_msg.pretty_print())

    # Create my information for connection
    (my_did, my_vk) = await did.create_and_store_my_did(
        agent.wallet_handle,
        {}
    )

    # Send Connection Request to inviter
    request = build_request(
        'test-connection-started-by-tested-agent',
        my_did,
        my_vk,
        config.endpoint
    )

    print("\nSending Request:\n", request.pretty_print())

    await agent.send(
        request,
        invite_msg['recipientKeys'][0],
        from_key=my_vk,
        service={'serviceEndpoint': invite_msg['serviceEndpoint']}
    )

    # Wait for response
    print("Awaiting response from tested agent...")
    response = await agent.expect_message(RESPONSE, 30)

    RESPONSE_SCHEMA_PRE_SIG_VERIFY.validate(response)
    print(
        "\nReceived Response (pre signature verification):\n",
        response.pretty_print()
    )

    response['connection'] = \
        await agent.verify_signed_field(response['connection~sig'])
    del response['connection~sig']

    RESPONSE_SCHEMA_POST_SIG_VERIFY.validate(response)
    assert response['~thread']['thid'] == request.id

    print(
        "\nReceived Response (post signature verification):\n",
        response.pretty_print()
    )


@pytest.mark.features("core.manual", "connection.manual")
@pytest.mark.priority(10)
@pytest.mark.asyncio
async def test_connection_started_by_suite(config, agent):
    """ Test a connection as started by the suite. """
    label = 'test-suite-connection-started-by-suite'

    connection_key = await did.create_key(agent.wallet_handle, {})

    invite_str = build_invite(label, connection_key, config.endpoint)

    print("\n\nInvitation encoded as URL: ", invite_str)

    print("Awaiting request from tested agent...")
    request = await agent.expect_message(REQUEST, 30)

    REQUEST_SCHEMA.validate(request)
    print("\nReceived request:\n", request.pretty_print())

    (_, their_vk, their_endpoint) = (
        request['connection']['DIDDoc']['publicKey'][0]['controller'],
        request['connection']['DIDDoc']['publicKey'][0]['publicKeyBase58'],
        request['connection']['DIDDoc']['service'][0]['serviceEndpoint']
    )

    (my_did, my_vk) = await did.create_and_store_my_did(
        agent.wallet_handle,
        {}
    )

    response = build_response(request.id, my_did, my_vk, config.endpoint)
    print(
        "\nSending Response (pre signature packing):\n",
        response.pretty_print()
    )

    response['connection~sig'] = await agent.sign_field(
        connection_key,
        response['connection']
    )
    del response['connection']
    print(
        "\nSending Response (post signature packing):\n",
        response.pretty_print()
    )

    await agent.send(
        response,
        their_vk,
        from_key=my_vk,
        service={'serviceEndpoint': their_endpoint}
    )
