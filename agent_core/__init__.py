""" Agent Core

    Defines a simple public API for creating and running an agent.
"""
import asyncio
from contextlib import suppress
from typing import Sequence

from ariespython import wallet, error

from .compat import create_task
from .config import Config
from .dispatcher import Dispatcher
from .conductor import Conductor
from .transport import InboundTransport, http, std, websocket, http_plus_ws
from .module import Module


def inbound_transport_str_to_module(transport_str):
    """ Map transport config strings to modules """
    return {
        'http': http.HTTPInboundTransport,
        'std': std.StdInboundTransport,
        'ws': websocket.WebSocketInboundTransport,
        'http+ws': http_plus_ws.HTTPPlusWebSocketTransport
    }[transport_str]


class Agent:
    """ Composed of:
        - Config
        - Transport
        - Conductor
        - Dispatcher

        Agent essentially only combines these sepearate pieces.
    """

    def __init__(
                self,
                wallet_handle,
                config: Config,
                conductor: Conductor,
                transports: Sequence[InboundTransport],
                dispatcher: Dispatcher
                ):

        self.wallet_handle = wallet_handle
        self.config = config
        self.conductor = conductor
        self.transports = transports
        self.dispatcher = dispatcher
        self.main_task = None

    @classmethod
    async def from_config_async(cls, config: Config):
        """ Start agent from config. Fulfills its own dependencies. """

        # Open wallet
        wallet_conf = [{'id': config.wallet}, {'key': config.passphrase}]
        try:
            await wallet.create_wallet(*wallet_conf)
        except error.WalletAlreadyExistsError:
            pass

        wallet_handle = await wallet.open_wallet(*wallet_conf)

        # Create conductor
        conductor = Conductor(wallet_handle)

        # Create inbound transports
        transports = []
        for transport in config.inbound_transports:
            transport_mod = inbound_transport_str_to_module(transport)
            transports.append(
                transport_mod(conductor.connection_queue)
            )

        # Create dispatcher
        dispatcher = Dispatcher()

        return cls(wallet_handle, config, conductor, transports, dispatcher)

    @classmethod
    def from_config(cls, config: Config):
        """ Start agent from config (blocking) """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(cls.from_config_async(config))

    async def start(self):
        """ Start Agent """
        transport_tasks = []
        for transport in self.transports:
            transport_tasks.append(
                create_task(
                    transport.accept(**self.config.transport_options())
                )
            )
        conductor_task = create_task(self.conductor.start())
        main_loop_task = create_task(self.main_loop())
        self.main_task = asyncio.gather(
            *transport_tasks,
            conductor_task,
            main_loop_task
        )
        await self.main_task

    def run(self):
        """ Run the agent """
        loop = asyncio.get_event_loop()
        try:
            print('Starting agent...')
            print('=== Ctrl+c to exit ===')
            loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            print('Exiting...')
            loop.run_until_complete(self.shutdown())

    async def shutdown(self):
        """ Shutdown Agent, raising any encountered exceptions """
        self.main_task.cancel()
        await self.conductor.shutdown()
        with suppress(asyncio.CancelledError):
            await self.main_task

    async def main_loop(self):
        """ Main loop of Agent

            Get received messages from conductor, pass to dispatcher for
            handling
        """
        while True:
            msg = await self.conductor.recv()
            await self.dispatcher.dispatch(msg, self)
            await self.conductor.message_handled()

    async def send(self, *args, **kwargs):
        """ Send a message to another agent. See Conductor.send() for more
            details.
        """
        self.conductor.send(*args, **kwargs)

    async def route(self, msg_type: str):
        """ Route decorator

            Used to explicitly define a handler for a message of a given type.
        """
        return self.dispatcher.route(msg_type)

    async def register_module(self, module: Module):
        """ Register module """
        return self.dispatcher.register_module(module)
