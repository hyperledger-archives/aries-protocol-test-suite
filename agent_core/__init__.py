""" Agent Core

    Defines a simple public API for creating and running an agent.
"""
from typing import Sequence

from ariespython import wallet, error

import transport.inbound.standard_in as StdIn
import transport.inbound.http as HttpIn
import transport.inbound.websocket as WebSocketIn
from .config import Config
from .dispatcher import Dispatcher
from .conductor import Conductor
from .transport import InboundTransport


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

    @classmethod
    async def from_config(cls, config: Config):
        """ Start agent from config. Fulfills its own dependencies. """

        # Open wallet
        wallet_conf = [{'id': config.wallet}, {'key': config.passphrase}]
        try:
            await wallet.create_wallet(*wallet_conf)
        except error.WalletItemAlreadyExists:
            pass

        wallet_handle = await wallet.open_wallet(*wallet_conf)

        # Create conductor
        conductor = Conductor(wallet_handle)

        # Create inbound transports
        for transport in config.inbound_transports:
            pass

        # Create dispatcher
        dispatcher = Dispatcher()

        return cls(wallet_handle, config, conductor, [], dispatcher)


    async def open_transports(self):
        pass

    async def send(self, *args, **kwargs):
        self.conductor.send(*args, **kwargs)
