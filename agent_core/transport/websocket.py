import asyncio
import logging

import aiohttp
from aiohttp import web

from . import Connection, InboundConnection, OutboundConnection,\
        ConnectionCapabilities, InboundTransport, CannotOpenConnection

LOGGER = logging.getLogger(__name__)


async def websocket_handle(request):
    """ Handle websocket """
    websocket = web.WebSocketResponse()
    await websocket.prepare(request)

    ws_conn = WebSocketInboundConnection(websocket)
    await request.app['connection_queue'].put(ws_conn)

    await ws_conn.wait()

    return websocket


class WebSocketInboundTransport(InboundTransport):
    """ WebSocket Inbound Transport """
    async def accept(self):
        routes = [
            web.get('/', websocket_handle)
        ]
        app = web.Application()
        app['connection_queue'] = self.connection_queue
        app.add_routes(routes)
        runner = web.AppRunner(app)
        await runner.setup()
        server = web.TCPSite(runner=runner, port=self.options['port'])
        LOGGER.info(
            'Starting on websocket localhost:%s/ws',
            self.options['port']
        )
        await server.start()


class WebSocketConnection(Connection):
    """ WebSocket Inbound connection """
    def __init__(self, websocket, session=None):
        super().__init__(ConnectionCapabilities.DUPLEX)
        self.session = session
        self.websocket = websocket

    @classmethod
    async def open(cls, **service):
        """ Actively open a WebSocketConnection """
        if 'serviceEndpoint' not in service:
            raise CannotOpenConnection()

        session = aiohttp.ClientSession()
        websocket = await session.ws_connect(
            service['serviceEndpoint']
        )

        return cls(websocket, session)

    async def recv(self):
        LOGGER.debug('Websocket recv loop')
        self.ensure_recv()
        async for msg in self.websocket:
            yield msg.data.encode('ascii')


    async def send(self, msg: bytes):
        self.ensure_send()
        await self.websocket.send_str(msg.decode('ascii'))

    async def close(self):
        await self.websocket.close()
        if self.session:
            await self.session.close()
        await super().close()


class WebSocketInboundConnection(WebSocketConnection, InboundConnection):
    """ All the same code but helpful to distinguish between in and out """


class WebSocketOutboundConnection(WebSocketConnection, OutboundConnection):
    """ All the same code but helpful to distinguish between in and out """
