""" Agent Core

    Defines a simple public API for creating and running an agent.
"""
import asyncio
from typing import Sequence

from ariespython import wallet, error

from .config import Config
from .dispatcher import Dispatcher
from .conductor import Conductor
from .transport import InboundTransport, http, std, websocket, http_plus_ws


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
        transports = []
        for transport in config.inbound_transports:
            transport_mod = inbound_transport_str_to_module(transport)
            transports.append(
                transport_mod(conductor.connection_queue)
            )

        # Create dispatcher
        dispatcher = Dispatcher()

        return cls(wallet_handle, config, conductor, transports, dispatcher)

    async def send(self, *args, **kwargs):
        self.conductor.send(*args, **kwargs)
