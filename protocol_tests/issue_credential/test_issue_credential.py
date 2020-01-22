"""
Test the issue-credential protocol family as defined at https://github.com/hyperledger/aries-rfcs/tree/master/features/0036-issue-credential
Roles tested: issuer and holder.
"""

import pytest
import aiohttp
import time

from aries_staticagent import Message, StaticConnection, Module, route, crypto
from reporting import meta
from ..schema import MessageSchema
from . import Handler

###
# Tests for the issuer role
###


@pytest.mark.asyncio
@meta(protocol='issue-credential', version='1.0', role='issuer', name='issuer-initiated')
async def test_issuer_v1_0_issuer_initiated(backchannel, connection, cred_def1, handler):
    """The agent under test initiates the issuance flow with an offer."""
    handler.reset_events()
    connection.route_module(handler)
    # Send a credential offer to the test-suite.  The remainder of the flow is automatic since the test-suite automatically
    # accepts the offer and stores the credential.
    await backchannel.issue_credential_v1_0_issuer_send_cred_offer(connection, cred_def1, {"name": "Alice", "GPA": 4})
    # Verifies that this results in a credential stored in the test-suite
    handler.assert_event("credential_stored")


@pytest.fixture
async def cred_def1(backchannel, config):
    """The agent under test is the issuer and so it creates the cred def."""
    schema_id = await backchannel.issue_credential_v1_0_issuer_create_cred_schema("Transcript", "1.0", ["name", "GPA"])
    return await backchannel.issue_credential_v1_0_issuer_create_cred_def(schema_id)

###
# Tests for the holder role
###


@pytest.mark.asyncio
@meta(protocol='issue-credential', version='1.0', role='holder', name='issuer-initiated')
async def test_holder_v1_0_issuer_initiated(backchannel, connection, cred_def2, handler):
    """The test suite initiates the issuance flow wth an offer."""
    handler.reset_events()
    connection.route_module(handler)
    # Send a credential offer to the agent under test
    id = await handler.send_offer_credential(connection, cred_def2, {
        "name": "Alice",
        "GPA": "4"
    })
    # Tell the agent under test to accept this credential offer
    await backchannel.issue_credential_v1_0_holder_accept_cred_offer(id)
    # Assert that the test suite has issued a credential
    handler.assert_event("issued")
    # Ensure that the credential was issued and stored successfully at the agent under test
    await backchannel.issue_credential_v1_0_holder_verify_cred_is_stored(id)


@pytest.fixture
async def cred_def2(config, backchannel, handler) -> str:
    """The agent under test is the holder and so the test suite creates the cred def."""
    schema_id = await handler.create_cred_schema("Transcript", "2.0", ["name", "GPA"])
    cred_def_id = await handler.create_cred_def(schema_id)
    return cred_def_id

###
# Common fixture for both roles
###
@pytest.fixture
async def handler(provider):
    """Fixture for the handler"""
    return Handler(provider)
