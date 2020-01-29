"""
Test the present-proof protocol family as defined at https://github.com/hyperledger/aries-rfcs/tree/master/features/0037-present-proof
Roles tested: prover and verifier.
"""

import pytest
import aiohttp
import time

from aries_staticagent import Message, StaticConnection, Module, route, crypto
from reporting import meta
from ..schema import MessageSchema
from . import Handler

###
# Tests for the prover role
###


@pytest.mark.asyncio
@meta(protocol='present-proof', version='1.0', role='prover', name='verifier-initiated')
async def test_present_proof_v1_0_prover_verifier_initiated(backchannel, connection, cred_def, handler):
    """The test suite begins the present-proof flow by sending a request-presentation message to the agent-under-test."""
    handler.reset_events()
    # The test suite sends a proof request to the agent-under-test
    proof_request = {
        "name": "aries-test-proof-request1",
        "version": "1.0",
        "requested_attributes": {
            "str1_referent": {
                "name": "name",
                "restrictions": [{"cred_def_id": cred_def}]
            }
        },
        "requested_predicates": {
            "int1_referent": {
                "name": "age",
                "p_type": ">=",
                "p_value": 21,
                "restrictions": [{"cred_def_id": cred_def}]
            }
        }
    }
    id = await handler.send_request_presentation(connection, proof_request)
    # The agent-under-test sends a proof for this proof request
    await backchannel.present_proof_v1_0_prover_send_proof(id)
    # Make sure the proof was verified by the test-suite
    handler.assert_event("verified")


@pytest.fixture
async def cred_def(handler, connection, backchannel):
    schema_id = await handler.create_cred_schema("ProverSchema", "1.0", ["name", "age"])
    cred_def_id = await handler.create_cred_def(schema_id)
    id = await handler.send_offer_credential(connection, cred_def_id, {
        "name": "Alice",
        "age": "25"
    })
    await backchannel.issue_credential_v1_0_holder_accept_cred_offer(id)
    return cred_def_id

###
# Tests for the verifier role
###


@pytest.mark.asyncio
@meta(protocol='present-proof', version='1.0', role='verifier', name='prover-initiated')
async def test_present_proof_v1_0_issuer_initiated(backchannel, connection, handler):
    """The agent-under-test begins the present-proof flow by sending a request-presentation message to the agent-under-test."""
    handler.reset_events()
    # Initialize the test suite with a credential
    (schema_id, cred_def_id) = await handler.setup_prover("VerifierSchema", "1.0", {"str1": "str1val", "int1": "10"})
    # Tell the agent-under-test to send a proof request
    # Valid restriction types are: schema_id, schema_issuer_did, schema_name, schema_version, issuer_did, cred_def_id
    proof_request = {
        "name": "aries-test-proof-request1",
        "version": "1.0",
        "requested_attributes": {
            "str1_referent": {
                "name": "str1",
                "restrictions": [{"cred_def_id": cred_def_id}]
            }
        },
        "requested_predicates": {
            "int1_referent": {
                "name": "int1",
                "p_type": ">=",
                "p_value": 5,
                "restrictions": [{"cred_def_id": cred_def_id}]
            }
        }
    }
    id = await backchannel.present_proof_v1_0_verifier_send_proof_request(connection, proof_request)
    handler.assert_event("sent_proof")
    await backchannel.present_proof_v1_0_verifier_verify_proof(id)

###
# Common fixture for both roles
###
@pytest.fixture
async def handler(provider, connection):
    """Fixture for the handler"""
    handler = Handler(provider)
    connection.route_module(handler)
    return handler
