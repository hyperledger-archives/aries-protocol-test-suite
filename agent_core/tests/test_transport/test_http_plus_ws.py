""" Test HTTP+WebSocket Transport """
import logging
import asyncio
import pytest

from agent_core.transport import http, websocket, http_plus_ws, \
        ConnectionClosed, UnsupportedCapability
from agent_core.compat import create_task

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_http_websocket_transport(unused_tcp_port_factory):
    """ Test HTTP+WebSocket Transport """
    port = unused_tcp_port_factory()
    conn_queue = asyncio.Queue()
    transport = http_plus_ws.HTTPPlusWebSocketTransport(conn_queue, port=port)

    transport_task = create_task(transport.accept())

    out_conn = await websocket.WebSocketOutboundConnection.open(
        serviceEndpoint='http://localhost:%d/' % port
    )

    assert out_conn.is_duplex()

    in_conn = await conn_queue.get()

    assert in_conn.is_duplex()

    await out_conn.send(b'test')

    async for msg in in_conn.recv():
        assert msg == b'test'
        break

    await in_conn.send(b'test2')

    async for msg in out_conn.recv():
        assert msg == b'test2'
        break

    await asyncio.sleep(.05)

    await out_conn.close()
    await in_conn.close()

    with pytest.raises(ConnectionClosed):
        await out_conn.send(b'test')

    with pytest.raises(ConnectionClosed):
        await in_conn.send(b'test')

    # OUT
    LOGGER.debug('Opening outbound connection')
    out_conn = await http.HTTPOutConnection.open(
        serviceEndpoint='http://localhost:%d/' % port
    )

    assert out_conn.can_send()

    with pytest.raises(UnsupportedCapability):
        out_conn.ensure_recv()

    LOGGER.debug('Sending test')
    send_task = create_task(out_conn.send('test'))
    # Need to respond to this send in the same thread so create task

    # IN
    LOGGER.debug('Popping connection off inbound connection queue.')
    in_conn = await asyncio.wait_for(conn_queue.get(), .05)

    LOGGER.debug('Reading received msg from inbound connection')
    assert in_conn.can_recv()

    with pytest.raises(UnsupportedCapability):
        in_conn.ensure_send()

    async for msg in in_conn.recv():
        assert msg == b'test'

    # IN
    assert in_conn.can_send()
    LOGGER.debug('Sending test from inbound connection to outbound')
    await in_conn.send('test')

    await asyncio.sleep(.05)

    # OUT
    assert out_conn.can_recv()
    LOGGER.debug('Reading response from inbound conn on outbound')
    async for msg in out_conn.recv():
        LOGGER.debug('got msg: %s', msg)
        assert msg == b'test'

    # Make sure proper exceptions get raised
    with pytest.raises(ConnectionClosed):
        await in_conn.send('test')

    with pytest.raises(ConnectionClosed):
        await out_conn.send('test')

    # Cleanup
    transport_task.cancel()
    send_task.cancel()
