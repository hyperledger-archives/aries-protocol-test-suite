""" Test HTTP transport """
import logging
import asyncio
import pytest

from agent_core.transport import http, UnsupportedCapability, ConnectionClosed
from agent_core.compat import create_task

LOGGER = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.DEBUG)


@pytest.mark.asyncio
async def test_http(unused_tcp_port_factory):
    """ Test HTTP transport """
    conn_queue = asyncio.Queue()
    port = unused_tcp_port_factory()
    transport = http.HTTPInboundTransport(conn_queue, port=port)

    # Startup transport
    transport_task = create_task(transport.accept())

    # Following tests are done in this order: out in in out
    # Out sends a message and waits for In to respond or will timeout
    # In responds then Out can read the response

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
