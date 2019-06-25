""" Define HTTP Transports """
import asyncio
import logging

from aiohttp import web
import aiohttp

from . import InboundConnection, OutboundConnection,\
        ConnectionCapabilities, InboundTransport, CannotOpenConnection

LOGGER = logging.getLogger(__name__)


async def post_handle(self, request):
    """ Post handler """
    msg = await request.read()
    conn = HTTPInboundConnection(msg)
    await request.app['connection_queue'].put(conn)

    try:
        await asyncio.wait_for(conn.wait(), 5)
    except asyncio.TimeoutError:
        await conn.close()

    if conn.new_msg:
        return web.Response(body=conn.new_msg)

    raise web.HTTPAccepted()


class HTTPInboundTransport(InboundTransport):
    """ HTTP Inbound Transport """
    async def accept(self, **options):
        routes = [
            web.post('/', post_handle)
        ]
        app = web.Application()
        app.add_routes(routes)
        app['connection_queue'] = self.connection_queue
        runner = web.AppRunner(app)
        await runner.setup()
        server = web.TCPSite(runner=runner, port=options['port'])
        LOGGER.info('Starting on localhost:%s', options['port'])
        await server.start()


class HTTPInboundConnection(InboundConnection):
    """ HTTP Inbound Connection """
    def __init__(self, msg):
        super().__init__(ConnectionCapabilities.RECV)
        self.msg = msg
        self.new_msg = None

    async def recv(self):
        self.set_send()
        yield self.msg

    async def send(self, msg):
        self.new_msg = msg
        await self.close()


class HTTPOutConnection(OutboundConnection):
    """ HTTP Outbound Connection """
    def __init__(self, endpoint):
        super().__init__(ConnectionCapabilities.SEND)
        self.endpoint = endpoint
        self.new_msg = None

    @classmethod
    async def open(cls, **service):
        if 'serviceEndpoint' not in service:
            raise CannotOpenConnection()

        return cls(service['serviceEndpoint'])

    async def send(self, msg):
        async with aiohttp.ClientSession() as session:
            headers = {'content-type': 'application/ssi-agent-wire'}
            async with session.post(
                    self.endpoint,
                    data=msg,
                    headers=headers
                        ) as resp:

                if resp.status != 202:
                    self.new_msg = await resp.read()
                    self.set_recv()
                else:
                    self.close()

    async def recv(self):
        self.close()
        yield self.new_msg
