""" Agent Core

    Defines a simple public API for creating and running an agent.
"""
from contextlib import suppress
from typing import Sequence
import argparse
import asyncio
import getpass
import logging
import sys


from schema import Optional
import toml
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
        self.logger = logging.getLogger(__name__)

        self.wallet_handle = wallet_handle
        self.config = config
        self.conductor = conductor
        self.transports = transports
        self.dispatcher = dispatcher
        self.main_task = None

    @classmethod
    async def from_config_async(cls, config: Config):
        """ Start agent from config. Fulfills its own dependencies. """
        logger = logging.getLogger(__name__)
        logger.info('Creating Agent from config')

        # Open wallet
        wallet_conf = [{'id': config['wallet']}, {'key': config['passphrase']}]
        if config['ephemeral']:
            try:
                logger.debug('Ephemeral is True; trying to delete wallet')
                await wallet.delete_wallet(*wallet_conf)
            except error.WalletNotFoundError:
                pass

        try:
            logger.debug('Creating wallet')
            await wallet.create_wallet(*wallet_conf)
        except error.WalletAlreadyExistsError:
            pass

        logger.debug('Opening wallet')
        wallet_handle = await wallet.open_wallet(*wallet_conf)

        # Create conductor
        conductor = Conductor(wallet_handle)

        # Create inbound transports
        transports = []
        for transport_info in config['transport']:
            transport_mod = inbound_transport_str_to_module(transport_info['name'])
            transports.append(
                transport_mod(
                    conductor.connection_queue,
                    **transport_info['options']
                )
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
        self.logger.info('Starting Agent...')
        transport_tasks = []
        for transport in self.transports:
            self.logger.debug(
                'Starting transport %s',
                type(transport).__name__
            )
            transport_tasks.append(
                create_task(transport.accept())
            )
        self.logger.debug('Starting conductor')
        conductor_task = create_task(self.conductor.start())
        self.logger.debug('Starting Agent main loop')
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
        await wallet.close_wallet(self.wallet_handle)

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
        return await self.conductor.send(*args, **kwargs)

    def route(self, msg_type: str):
        """ Route decorator

            Used to explicitly define a handler for a message of a given type.
        """
        return self.dispatcher.route(msg_type)

    def clear_routes(self):
        """ Clear routes registered on agent. """
        return self.dispatcher.clear_routes()

    def register_module(self, module: Module):
        """ Register module """
        return self.dispatcher.register_module(module)

    def clear_modules(self):
        """ Clear registered modules. """
        return self.dispatcher.clear_modules()

    async def clear_wallet(self):
        """ Close wallet """
        try:
            await wallet.close_wallet(self.wallet_handle)
        except error.WalletInvalidHandle:
            return

        wallet_conf = [
            {'id': self.config['wallet']},
            {'key': self.config['passphrase']}
        ]
        try:
            await wallet.delete_wallet(*wallet_conf)
        except error.WalletNotFoundError:
            pass

        try:
            await wallet.create_wallet(*wallet_conf)
        except error.WalletAlreadyExistsError:
            self.logger.error('Wallet was not deleted during clear_wallet')

        self.wallet_handle = await wallet.open_wallet(*wallet_conf)
        self.conductor.wallet_handle = self.wallet_handle


class AgentConfig(Config):
    """ Configuration class used to store and update configuration information.
    """

    __slots__ = (
        'wallet',
        'passphrase',
        'ephemeral',
        'transport',
    )

    SCHEMA = {
        'wallet': str,
        'passphrase': str,
        Optional('ephemeral', default=False): bool,
        Optional('transport', default=[{'name': 'http', 'port': 3000}]): [
            {'name': str, 'options': object}
        ]
    }

    def transport_options(self):
        """ Get options relevant to transport """
        return {'port': self['port']} if self['port'] else {}


class CliAgentConfig(AgentConfig):
    """ Agent Configuration with options helpful for configuring from CLI
    """

    __slots__ = (
        'config',
        'log_level',
        'log_suppress',
        'log_include'
    )

    SCHEMA = {
        **AgentConfig.SCHEMA,
        Optional('config'): str,
        Optional('log_level', default=50): int,
        Optional('log_suppress', default=[]): [str],
        Optional('log_include', default=[]): [str],
    }

    @staticmethod
    def get_arg_parser():
        """ Construct an argument parser that matches our configuration.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '-c',
            '--config',
            dest='config',
            metavar='FILE',
            type=str,
            help='Load configuration from FILE',
        )
        transport_group = parser.add_argument_group(
            'transport',
            'Options for configuring transport methods'
        )
        transport_group.add_argument(
            '-i',
            '--inbound-transport',
            dest='transports',
            metavar='TRANSPORT',
            nargs='+',
            help='Set the inbound transports',
            default=argparse.SUPPRESS
        )
        transport_group.add_argument(
            '--port',
            dest='port',
            metavar='PORT',
            type=int,
            help='Run inbound transport on PORT',
            default=argparse.SUPPRESS
        )

        class PasswordPromptAction(argparse.Action):
            """ Action for retrieving password from config or prompting
                on cli (if possible).
            """
            def __init__(self, option_strings, dest=None, nargs='?', default=None,
                         required=False, type=None, metavar=None, help=None):
                super(PasswordPromptAction, self).__init__(
                    option_strings=option_strings, dest=dest,
                    nargs=nargs, default=default, required=required, metavar=metavar,
                    type=type, help=help
                )

            def __call__(self, parser, args, values, option_string=None):
                if not values:
                    if sys.stdin.isatty():
                        passphrase = getpass.getpass("Passphrase: ")
                    else:
                        passphrase = sys.stdin.readline().rstrip()
                else:
                    passphrase = values

                setattr(args, self.dest, passphrase)

        wallet_group = parser.add_argument_group(
            'wallet',
            'Wallet configuration options'
        )

        wallet_group.add_argument(
            '-w',
            '--wallet',
            dest='wallet',
            metavar='WALLET',
            type=str,
            help='Specify wallet',
            default=argparse.SUPPRESS
        )
        wallet_group.add_argument(
            '-p',
            '--passphrase',
            dest='passphrase',
            action=PasswordPromptAction,
            metavar='PASS',
            type=str,
            help='Wallet passphrase; '
            'Prompted at execution if PASS is ommitted',
            default=argparse.SUPPRESS
        )
        wallet_group.add_argument(
            '--ephemeral',
            dest='ephemeral',
            action='store_true',
            help='Use ephemeral wallets',
            default=argparse.SUPPRESS
        )

        class VAction(argparse.Action):
            def __init__(self, option_strings, dest, nargs=None, const=None,
                         default=None, type=None, choices=None, required=False,
                         help=None, metavar=None):
                super(VAction, self).__init__(option_strings, dest, nargs, const,
                                              default, type, choices, required,
                                              help, metavar)
                self.values = 50

            def __call__(self, parser, args, values, option_string=None):
                # print('values: {v!r}'.format(v=values))
                if values is None:
                    self.values -= 10
                else:
                    try:
                        self.values -= int(values) * 10
                    except ValueError:
                        self.values -= (values.count('v') + 1) * 10
                setattr(args, self.dest, self.values)

        logging_group = parser.add_mutually_exclusive_group()
        logging_group.add_argument(
            '-v',
            nargs='?',
            action=VAction,
            dest='log_level',
            metavar='VERBOSITY',
            help='Set verbosity; -v VERBOSITY or -v, -vv, -vvv',
            default=argparse.SUPPRESS
        )
        logging_group.add_argument(
            '--log-level',
            action='store',
            dest='log_level',
            metavar='LOGLEVEL',
            type=int,
            help='Set log level manually; 50 is CRITICAL, 0 is TRACE',
            default=argparse.SUPPRESS
        )
        parser.add_argument(
            '--log-suppress',
            metavar='LOGGER',
            dest='log_suppress',
            nargs='+',
            help='Suppress logs from LOGGER(s)',
            default=argparse.SUPPRESS
        )
        parser.add_argument(
            '--log-include',
            metavar='LOGGER',
            dest='log_include',
            nargs='+',
            help='Include logs from LOGGER(s)',
            default=argparse.SUPPRESS
        )
        return parser

    @classmethod
    def from_file(cls, config_path: str):
        """ Create config object from toml file.
        """
        return cls.from_options(toml.load(config_path)['config'])

    @classmethod
    def from_args(cls):
        """ Create config object from command line arguments.

            Configuration file will also be opened if specified by args.
        """
        parser = cls.get_arg_parser()
        options = parser.parse_known_args()[0].__dict__

        if options['config']:
            options = {
                **toml.load(options['config'])['config'],
                **options
                # By placing options last, the cli args get priority
            }

        return cls.from_options(options)

    def apply(self):
        """ Validate updates to the configuration """
        super().apply()

        logging_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)-8s %(name)s : %(message)s')
        logging_handler.setFormatter(formatter)
        logging.getLogger().addHandler(logging_handler)
        logging.getLogger(__name__.split('.')[0]).setLevel(self['log_level'])
        for logger in self['log_include']:
            logging.getLogger(logger).setLevel(self['log_level'])
        for logger in self['log_suppress']:
            logging.getLogger(logger).setLevel(logging.CRITICAL)
