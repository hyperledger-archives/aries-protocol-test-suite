""" Test agent
    Start up two agents, manually connecting them, and test messages can be
    passed and responded to.
"""

import asyncio
import logging

import pytest
from ariespython import did

from agent_core import AgentConfig
from agent_core import Agent
from agent_core.message import Message
from agent_core.compat import create_task

CONFIG_ALICE = AgentConfig.from_options({
    'wallet': 'alice-test',
    'passphrase': 'alice-test',
    'ephemeral': True,
    'transports': ['http'],
    'port': 3333
})

CONFIG_BOB = AgentConfig.from_options({
    'wallet': 'bob-test',
    'passphrase': 'bob-test',
    'ephemeral': True,
    'transports': ['http'],
    'port': 4444
})


@pytest.fixture(scope='module')
def event_loop():
    """ Create a session scoped event loop.
        pytest.asyncio plugin provides a default function scoped event loop
        which cannot be used as a dependency to session scoped fixtures.
    """
    return asyncio.get_event_loop()


async def connect_alice_and_bob(alice: Agent, bob: Agent):
    """ Setup connectino between alice and bob """
    logger = logging.getLogger(__name__)
    # Generate connection info for alice
    alice.did, alice.vk = \
        await did.create_and_store_my_did(alice.wallet_handle)

    # Generate connection info for bob
    bob.did, bob.vk = \
        await did.create_and_store_my_did(bob.wallet_handle)
    logger.debug('Bob\'s info: %s, %s, %s', bob.wallet_handle, bob.did, bob.vk)

    # Store bob's info in alice's wallet
    await did.store_their_did(
        alice.wallet_handle,
        {'did': bob.did, 'verkey': bob.vk}
    )
    await did.set_did_metadata(
        alice.wallet_handle,
        bob.did,
        {'service': {'serviceEndpoint': 'http://localhost:4444/'}}
    )

    # Store alice's info in bob's wallet
    await did.store_their_did(
        bob.wallet_handle,
        {'did': alice.did, 'verkey': alice.vk}
    )
    await did.set_did_metadata(
        bob.wallet_handle,
        alice.did,
        {'service': {'serviceEndpoint': 'http://localhost:3333/'}}
    )


@pytest.fixture(scope='module')
async def ALICE():
    alice = await Agent.from_config_async(CONFIG_ALICE)
    alice_task = create_task(alice.start())

    yield alice

    await alice.shutdown()
    alice_task.cancel()


@pytest.fixture(scope='module')
async def BOB():
    bob = await Agent.from_config_async(CONFIG_BOB)
    bob_task = create_task(bob.start())

    yield bob

    await bob.shutdown()
    bob_task.cancel()


@pytest.fixture
async def alice(ALICE):
    yield ALICE
    ALICE.clear_routes()
    ALICE.clear_modules()
    await ALICE.clear_wallet()
    del ALICE.did
    del ALICE.vk


@pytest.fixture
async def bob(BOB):
    yield BOB
    BOB.clear_routes()
    BOB.clear_modules()
    await BOB.clear_wallet()
    del BOB.did
    del BOB.vk


@pytest.mark.asyncio
async def test_agents_can_talk(alice, bob):
    logger = logging.getLogger(__name__)
    await connect_alice_and_bob(alice, bob)

    alice.triggered = asyncio.Event()

    @alice.route('test/protocol/1.0/test')
    async def alice_msg_handle(msg, alice):
        alice.triggered.set()

    await bob.send(
        Message({'@type': 'test/protocol/1.0/test'}),
        alice.vk,
        to_did=alice.did
    )

    assert alice.triggered.is_set()


@pytest.mark.asyncio
async def test_agents_can_talk_both_ways(alice, bob):
    logger = logging.getLogger(__name__)
    await connect_alice_and_bob(alice, bob)

    alice.triggered = asyncio.Event()
    bob.triggered = asyncio.Event()

    @alice.route('test/protocol/1.0/test')
    async def alice_msg_handle(msg, alice):
        logger.debug('Alice got: %s', msg)
        alice.triggered.set()

    @bob.route('test/protocol/1.0/test')
    async def bob_msg_handle(msg, bob):
        logger.debug('Bob got: %s', msg)
        bob.triggered.set()

    logger.debug('Packing message to Alice: %s, %s', alice.did, alice.vk)
    await bob.send(
        Message({'@type': 'test/protocol/1.0/test'}),
        alice.vk,
        to_did=alice.did,
    )

    await alice.send(
        Message({'@type': 'test/protocol/1.0/test'}),
        bob.vk,
        to_did=bob.did,
    )

    await asyncio.wait_for(alice.triggered.wait(), 1)
    assert alice.triggered.is_set()
    await asyncio.wait_for(bob.triggered.wait(), 1)
    assert bob.triggered.is_set()
