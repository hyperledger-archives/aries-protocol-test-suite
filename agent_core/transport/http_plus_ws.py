""" Combined http and websocket inbound transports """
import logging

from aiohttp import web

from . import InboundTransport
from .http import post_handle
from .websocket import websocket_handle

LOGGER = logging.getLogger(__name__)


class HTTPPlusWebSocketTransport(InboundTransport):
    """Combined http and websocket inbound transports"""
    async def accept(self):
        routes = [
            web.get('/', websocket_handle),
            web.post('/', post_handle)
        ]
        app = web.Application()
        app['connection_queue'] = self.connection_queue
        app.add_routes(routes)
        runner = web.AppRunner(app)
        await runner.setup()
        server = web.TCPSite(runner=runner, port=self.options['port'])
        LOGGER.info(
            'Starting on http and ws on localhost:%s',
            self.options['port']
        )
        await server.start()
