""" Test WebSocket Transport """
import asyncio
import pytest

from agent_core.transport import websocket, ConnectionClosed
from agent_core.compat import create_task


@pytest.mark.asyncio
async def test_websocket_transport(unused_tcp_port_factory):
    """ Test WebSocket Transport """
    port = unused_tcp_port_factory()
    conn_queue = asyncio.Queue()
    transport = websocket.WebSocketInboundTransport(conn_queue, port=port)

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

    transport_task.cancel()
    await asyncio.sleep(.25)
