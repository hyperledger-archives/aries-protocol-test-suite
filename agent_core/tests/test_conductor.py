""" Test Conductor """
import asyncio
import contextlib
import socket
import logging

import pytest
from ariespython import (
    crypto,
    did,
    error,
    wallet
)

from agent_core.compat import create_task
from agent_core.transport.http import HTTPInboundTransport, HTTPOutConnection
from agent_core.transport.websocket import WebSocketOutboundConnection
from agent_core.conductor import Conductor
from agent_core.message import Message
from agent_core.mtc import (
    CONFIDENTIALITY,
    INTEGRITY,
    DESERIALIZE_OK,
    LIMITED_SCOPE,
    AUTHENTICATED_ORIGIN,
    NONREPUDIATION
)

logging.getLogger('indy').setLevel(50)


@pytest.fixture(scope='module')
def event_loop():
    """ Create a session scoped event loop.
        pytest.asyncio plugin provides a default function scoped event loop
        which cannot be used as a dependency to session scoped fixtures.
    """
    return asyncio.get_event_loop()


def _unused_tcp_port():
    """Find an unused localhost TCP port from 1024-65535 and return it."""
    with contextlib.closing(socket.socket()) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture(scope='module')
def unused_tcp_port():
    return _unused_tcp_port()


@pytest.fixture(scope='module')
def wallet_credentials():
    """ Info used to open wallet """
    yield [{'id': 'test'}, {'key': 'test'}]


@pytest.fixture(scope='module')
async def wallet_handle(wallet_credentials):
    """ Wallet handle fixture """
    try:
        await wallet.delete_wallet(*wallet_credentials)
    except error.WalletNotFound:
        pass
    finally:
        await wallet.create_wallet(*wallet_credentials)

    handle = await wallet.open_wallet(*wallet_credentials)

    yield handle

    await wallet.close_wallet(handle)


@pytest.fixture(scope='module')
def connection_queue():
    """ Connection queue used by transport and conductor """
    yield asyncio.Queue()


@pytest.fixture(scope='module')
async def transport_info(unused_tcp_port, connection_queue):
    """ Transport """
    task = None
    port = unused_tcp_port

    if task is None:
        transport_ = HTTPInboundTransport(connection_queue, port=port)
        task = create_task(transport_.accept())

    yield transport_, port

    task.cancel()


@pytest.fixture(scope='module')
async def conductor(wallet_handle, connection_queue):
    """ Conductor fixture """
    con = Conductor(wallet_handle, connection_queue)
    yield con

    await con.shutdown()


@pytest.fixture(scope='module')
async def loopback_relationship(wallet_handle, transport_info):
    _, port = transport_info
    a_did, a_vk = await did.create_and_store_my_did(wallet_handle)
    await did.set_did_metadata(
        wallet_handle,
        a_did,
        {
            'service': {
                'serviceEndpoint': 'http://localhost:%d/' % port
            }
        }
    )

    return a_did, a_vk

@pytest.fixture(scope='module')
async def packed_message(wallet_handle, loopback_relationship):
    """ Get a packed message """
    _, a_vk = loopback_relationship
    yield await crypto.pack_message(
        wallet_handle,
        Message({'@type': 'test/protocol/1.0/test'}).serialize(),
        [a_vk],
        a_vk
    )


@pytest.fixture(scope='module')
async def packed_message_anonymous(wallet_handle, loopback_relationship):
    """ Get a packed message """
    _, a_vk = loopback_relationship
    yield await crypto.pack_message(
        wallet_handle,
        Message({'@type': 'test/protocol/1.0/test'}).serialize(),
        [a_vk]
    )

@pytest.mark.parametrize(
    'endpoint, expected',
    [
        ('http://example.com', HTTPOutConnection),
        ('https://example.com', HTTPOutConnection),
        ('ws://example.com', WebSocketOutboundConnection),
        ('wss://example.com', WebSocketOutboundConnection)
    ]
)
def test_outbound_conn_selection(endpoint, expected):
    assert Conductor.select_outbound_conn_type(endpoint) == expected


@pytest.mark.asyncio
async def test_send(conductor, loopback_relationship):
    """ Test that conductor can send a message """
    a_did, a_vk = loopback_relationship
    send_task = create_task(conductor.send(
        Message({'@type': 'test/protocol/1.0/test'}),
        a_vk,
        to_did=a_did,
        from_key=a_vk
    ))
    conn = await conductor.connection_queue.get()
    await conductor.message_reader(conn)
    msg = await asyncio.wait_for(conductor.recv(), 5)
    assert msg.type == 'test/protocol/1.0/test'
    send_task.cancel()


@pytest.mark.asyncio
async def test_unpack(conductor, packed_message, loopback_relationship):
    """ Test behavior of unpack """
    a_did, a_vk = loopback_relationship

    msg = await conductor.unpack(packed_message)

    assert msg.mtc.ad == {
        'recip_vk': a_vk,
        'sender_vk': a_vk,
        'recip_did': a_did,
        'sender_did': a_did,
    }

    assert msg.mtc[
        AUTHENTICATED_ORIGIN |
        CONFIDENTIALITY |
        DESERIALIZE_OK |
        INTEGRITY
    ]
    assert not msg.mtc[NONREPUDIATION]


@pytest.mark.asyncio
async def test_unpack_anonymous(conductor, packed_message_anonymous, loopback_relationship):
    """ Test behavior of unpack for anonymously packed message """
    a_did, a_vk = loopback_relationship

    msg = await conductor.unpack(packed_message_anonymous)

    assert msg.mtc.ad == {
        'recip_vk': a_vk,
        'sender_vk': None,
        'recip_did': a_did,
        'sender_did': None,
    }

    assert msg.mtc[
        CONFIDENTIALITY |
        DESERIALIZE_OK |
        INTEGRITY
    ]
    assert not msg.mtc[AUTHENTICATED_ORIGIN | NONREPUDIATION]


@pytest.mark.asyncio
async def test_unpack_plaintext(conductor):
    """ Test unpack behavior for plaintext """
    msg = await conductor.unpack(
        Message({'@type': 'test/protocol/1.0/test'}).serialize()
    )

    assert msg.mtc[DESERIALIZE_OK]
    assert not msg.mtc[
        AUTHENTICATED_ORIGIN |
        CONFIDENTIALITY |
        INTEGRITY |
        LIMITED_SCOPE |
        NONREPUDIATION
    ]
