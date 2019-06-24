import asyncio
import sys
import logging
from transport.connection import Connection, ConnectionType

logger = logging.getLogger(__name__)

class StdConnection(Connection):
    def __init__(self):
        super().__init__(ConnectionType.DUPLEX)
        self.loop = asyncio.get_running_loop()

    async def recv(self):
        while True:
            msg = ''
            line = await self.loop.run_in_executor(None, sys.stdin.readline)
            while line != '\n':
                msg += line
                line = await self.loop.run_in_executor(None, sys.stdin.readline)

            if msg:
                self.close()
                yield msg

    async def send(self, msg):
        print(msg)

async def accept(connection_queue):
    logger.info("Accepting on stdin")
    await connection_queue.put(StdConnection())
