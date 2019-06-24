import asyncio
import logging

import aiohttp
from aiohttp import web

from compat import create_task
from transport.connection import Connection, ConnectionType

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.getLogger('aiohttp').setLevel(logging.DEBUG)

async def accept(connection_queue, **kwargs):
    routes = [
        web.get('/ws', websocket_handle)
    ]
    app = web.Application()
    app['connection_queue'] = connection_queue
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    server = web.TCPSite(runner=runner, port=kwargs['port'])
    logger.info('Starting on websocket localhost:%s/ws', kwargs['port'])
    print('starting')
    await server.start()

async def websocket_handle(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    ws_conn = WebSocketConnection(ws)
    await request.app['connection_queue'].put(ws_conn)

    try:
        await asyncio.wait_for(ws_conn.wait(), 30)
    except asyncio.TimeoutError:
        await ws_conn.close()

    return ws


class WebSocketConnection(Connection):
    def __init__(self, websocket):
        super().__init__(ConnectionType.DUPLEX)
        self.websocket = websocket

    async def recv(self):
        yield await self.websocket.receive_str()

    async def send(self, msg: str):
        await self.websocket.send_str(msg)

    async def close(self):
        await self.websocket.close()
        await super().close()
