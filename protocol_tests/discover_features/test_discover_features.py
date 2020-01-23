"""
Test the discover features protocol family as defined at https://github.com/hyperledger/aries-rfcs/tree/master/features/0031-discover-features.
Roles tested: requester and responder.
"""

import pytest

from aries_staticagent import Message, StaticConnection, Module, route, crypto
from reporting import meta
from ..schema import MessageSchema
from . import Handler

###
### Tests for the requester role
###

async def requester(backchannel, connection, query, comment):
    # In this test case, the agent under test sends a query message to the test suite.
    # The Handler class in __init__.py contains the logic used by the test suite to handle the query message.
    # We must first register this handler.
    handler = Handler()
    connection.route_module(handler)
    count = handler.query_message_count
    # Now tell the agent under test to send a query message
    await backchannel.discover_features_v1_0_requester_start(
        connection, query, comment
    )
    # Make sure an additional message was received
    assert handler.query_message_count == count + 1

@pytest.mark.asyncio
@meta(protocol='discover-features', version='1.0', role='requester', name='query-all')
async def test_query_all(backchannel, connection):
    """The agent under test queries all features of the test suite."""
    await requester(backchannel, connection, ".*", "I want to know all of your features")

@pytest.mark.asyncio
@meta(protocol='discover-features', version='1.0', role='requester', name='query-some')
async def test_query_some(backchannel, connection):
    """The agent under test queries all features of the test suite."""
    resp = await requester(backchannel, connection, ".*bogus.*", "I want to know all of your features")


###
### Tests for the responder role
###

@pytest.mark.asyncio
@meta(protocol='discover-features', version='1.0', role='responder', name='disclose-all')
async def test_disclose_all(connection):
    """Query all features of the agent under test."""
    resp = await responder(connection, ".*", "I want to know all of your features")


@pytest.mark.asyncio
@meta(protocol='discover-features', version='1.0', role='responder', name='disclose-some')
async def test_disclose_some(connection):
    """Query some features of the agent under test."""
    resp = await responder(connection, ".*/discover-features/.*", "I want to know some of your features")
    assert len(resp['protocols']) == 1


async def responder(connection, query, comment):
    """Send a query request and return the response."""
    # Send the request
    req = Message({
        '@type': 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/discover-features/1.0/query',
        'query': query,
        'comment': comment,
    })
    resp = await connection.send_and_await_reply_async(
        req,
        timeout=1
    )
    # Validate the response
    assert resp.mtc.is_authcrypted()
    assert resp.mtc.sender == crypto.bytes_to_b58(connection.recipients[0])
    assert resp.mtc.recipient == connection.verkey_b58
    resp_schema = MessageSchema({
        '@type': 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/discover-features/1.0/disclose',
        '@id': str,
        'protocols': [{
           'pid': str,
           'roles': [str]
        }]
    })
    resp_schema(resp)
    # Return the response
    return resp

