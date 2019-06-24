import asyncio
import logging
from aiohttp import web
from transport.connection import Connection, ConnectionType

logger = logging.getLogger(__name__)

async def accept(connection_queue, **kwargs):
    routes = [
        web.post('/indy', post_handle)
    ]
    app = web.Application()
    app['connection_queue'] = connection_queue
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    server = web.TCPSite(runner=runner, port=kwargs['port'])
    logger.info('Starting on localhost: %s', kwargs['port'])
    await server.start()

async def post_handle(request):
    msg = await request.read()
    conn = HTTPConnection(msg)
    await request.app['connection_queue'].put(conn)

    try:
        await asyncio.wait_for(conn.wait(), 5)
    except asyncio.TimeoutError:
        await conn.close()

    if conn.new_msg:
        return web.Response(body=conn.new_msg)

    raise web.HTTPAccepted()

class HTTPConnection(Connection):
    def __init__(self, msg):
        super().__init__(ConnectionType.RECV)
        self.msg = msg
        self.new_msg = None

    async def recv(self):
        self.set_send()
        yield self.msg

    async def send(self, new_msg):
        self.new_msg = new_msg
        await self.close()
