import aiohttp
import logging
from transport.connection import Connection, ConnectionType, CannotOpenConnection

logger = logging.getLogger(__name__)

class HTTPOutConnection(Connection):
    def __init__(self, endpoint):
        super().__init__(ConnectionType.SEND)
        self.endpoint = endpoint
        self.new_msg = None

    async def send(self, msg):
        async with aiohttp.ClientSession() as session:
            headers = {'content-type': 'application/ssi-agent-wire'}
            async with session.post(self.endpoint, data=msg, headers=headers) as resp:
                if resp.status != 202:
                    self.new_msg = await resp.read()
                    self.set_recv()
                else:
                    self.close()

    async def recv(self):
        self.close()
        yield self.new_msg

async def open(**metadata):
    if 'their_endpoint' not in metadata:
        raise CannotOpenConnection()

    return HTTPOutConnection(metadata['their_endpoint'])
