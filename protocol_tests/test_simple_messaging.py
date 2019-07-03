""" Demonstrate testing framework. """
import asyncio
# import logging

import pytest
from ariespython import did

from agent_core.message import Message
from . import MessageSchema


async def static_connection(agent, static_connection_info):
    """ Set up connection to static agent """
    their_did = static_connection_info['did']
    their_vk = static_connection_info['verkey']
    their_endpoint = static_connection_info['endpoint']

    await did.store_their_did(
        agent.wallet_handle,
        {
            'did': their_did,
            'verkey': their_vk
        }
    )
    await did.set_did_metadata(
        agent.wallet_handle,
        their_did,
        {
            'service': {
                'serviceEndpoint': their_endpoint
            }
        }
    )

    my_did, my_vk = await did.create_and_store_my_did(
        agent.wallet_handle,
        {'seed': '00000000000000000000000000000000'}
    )

    return my_did, my_vk, their_did, their_vk


@pytest.mark.asyncio
@pytest.mark.features('simple')
async def test_simple_messaging(config, agent):
    """ Show a simple messages being passed to and from tested agent """

    _my_did, my_vk, their_did, their_vk = \
        await static_connection(agent, config['static_connection'])

    expected_schema = MessageSchema({
        '@type': 'test/protocol/1.0/test',
        '@id': str,
        'msg': str
    })

    ping = Message({
        '@type': 'test/protocol/1.0/test',
        'msg': 'ping'
    })
    print('Sending message:', ping.pretty_print())
    await agent.send(
        ping,
        their_vk,
        to_did=their_did,
        from_vk=my_vk
    )

    msg = await agent.expect_message('test/protocol/1.0/test', 1)
    print('Received message:', msg.pretty_print())
    assert expected_schema.validate(msg)

    assert agent.ok()
