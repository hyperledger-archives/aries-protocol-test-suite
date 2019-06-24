""" Define transports that read and write to stdin and stdout """

import asyncio
import sys
import logging
from transport import InboundConnection, OutboundConnection, \
        ConnectionCapabilities, InboundTransport

LOGGER = logging.getLogger(__name__)


class StdInboundTransport(InboundTransport):
    """ Standard In Transport """
    async def accept(self, **options):
        LOGGER.info("Accepting on stdin")
        await self.connection_queue.put(StdInConnection())


class StdInConnection(InboundConnection):
    """ Standard In Connection """
    def __init__(self):
        super().__init__(ConnectionCapabilities.RECV)
        self.loop = asyncio.get_running_loop()

    async def recv(self):
        while True:
            msg = ''
            line = await self.loop.run_in_executor(None, sys.stdin.readline)
            while line != '\n':
                msg += line
                line = await self.loop.run_in_executor(
                    None,
                    sys.stdin.readline
                )

            if msg:
                self.close()
                yield msg


class StdOutConnection(OutboundConnection):
    """ Standard Out Connection """
    def __init__(self):
        super().__init__(ConnectionCapabilities.SEND)
        self.loop = asyncio.get_running_loop()

    @classmethod
    async def open(cls, **service):
        return cls()

    async def send(self, msg: str):
        await self.loop.run_in_executor(None, print, msg)
