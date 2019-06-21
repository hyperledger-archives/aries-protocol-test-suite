""" Module for storing and updating configuration.
"""
import sys
import getpass

import argparse
from typing import Dict, Any
import toml


class InvalidConfigurationException(Exception):
    """ Exception raise on absent required configuration value
    """


class Config:
    """ Configuration class used to store and update configuration information.
    """

    config: str
    wallet: str
    passphrase: str
    ephemeral: bool
    inbound_transport: str
    outbound_transport: str
    num_messages: int
    port: int
    log_level: int
    halt_on_error: bool

    def __init__(self):
        self.config: str = None
        self.wallet: str = None
        self.passphrase: str = None
        self.ephemeral: bool = None
        self.inbound_transport: str = None
        self.outbound_transport: str = None
        num_messages: int = None
        self.port: int = None
        self.log_level: int = None
        self.halt_on_error: bool = False

    @staticmethod
    def default_options():
        return {
            'wallet': 'agent',
            'passphrase': 'default',
            'ephemeral': False,
            'inbound_transport': 'stdin',
            'outbound_transport': 'stdout',
            'num_messages': -1,
            'port': None,
            'log_level': 50,
            'halt_on_error': False,
        }

    @staticmethod
    def get_arg_parser():
        """ Construct an argument parser that matches our configuration.
        """
        class PasswordPromptAction(argparse.Action):
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

        parser = argparse.ArgumentParser(
            description='Agent',
            #prog='agent'
        )
        parser.add_argument(
            '-c',
            '--config',
            dest='config',
            metavar='FILE',
            type=str,
            help='Load configuration from FILE'
        )
        parser.add_argument(
            '-i',
            '--inbound-transport',
            dest='inbound_transport',
            metavar='INBOUND_TRANSPORT',
            type=str,
            help='Set the inbound transport type'
        )
        parser.add_argument(
            '-o',
            '--outbound-transport',
            dest='outbound_transport',
            metavar='OUTBOUND_TRANSPORT',
            type=str,
            help='Set the outbound transport type'
        )
        parser.add_argument(
            '-w',
            '--wallet',
            dest='wallet',
            metavar='WALLET',
            type=str,
            help='Specify wallet',
            required=True,
        )
        parser.add_argument(
            '-p',
            '--passphrase',
            dest='passphrase',
            action=PasswordPromptAction,
            metavar='PASS',
            type=str,
            help='Wallet passphrase; Prompted at execution if PASS is ommitted',
            required=True
        )
        parser.add_argument(
            '--ephemeral',
            dest='ephemeral',
            action='store_true',
            help='Use ephemeral wallets'
        )
        parser.add_argument(
            '-n',
            '--num',
            dest='num_messages',
            metavar='NUM',
            type=int,
            help='Process NUM number of messages and stop'
        )
        parser.add_argument(
            '--port',
            dest='port',
            metavar='PORT',
            type=int,
            help='Run inbound transport on PORT'
        )
        parser.add_argument(
            '--halt-on-error',
            dest='halt_on_error',
            action='store_true',
            help='Halt when processing fails'
        )
        logging_group = parser.add_mutually_exclusive_group()
        logging_group.add_argument(
            '-v',
            nargs='?',
            action=VAction,
            dest='log_level',
            metavar='VERBOSITY',
            help='Set verbosity; -v VERBOSITY or -v, -vv, -vvv'
        )
        logging_group.add_argument(
            '--log-level',
            action='store',
            dest='log_level',
            metavar='LOGLEVEL',
            help='Set log level manually; 50 is CRITICAL, 0 is TRACE'
        )
        return parser

    def load_options_from_file(self, config_path: str):
        options = toml.load(config_path)
        self.update(options, soft=True)


    @staticmethod
    def from_file(config_path: str):
        """ Create config object from toml file.
        """
        conf = Config()
        conf.load_options_from_file(config_path)
        return conf

    @staticmethod
    def from_args_file_defaults():
        conf = Config()
        parser = Config.get_arg_parser()
        parser.parse_known_args(namespace=conf)
        if conf.config:
            conf.load_options_from_file(conf.config)

        conf.update(Config.default_options(), soft=True)
        return conf

    def update(self, options: Dict[str, Any], **kwargs):
        """ Load configuration from the options dictionary.
        """
        soft = 'soft' in kwargs and kwargs['soft']

        for var in self.__dict__:
            if var in options and options[var] is not None:
                if not isinstance(options[var], Config.__annotations__[var]):
                    err_msg = 'Configuration option {} is an invalid type'.format(var)
                    raise InvalidConfigurationException(err_msg)

                if soft:
                    if self.__dict__[var] is None:
                        self.__dict__[var] = options[var]
                else:
                    self.__dict__[var] = options[var]

    def transport_options(self):
        return {'port': self.port} if self.port else {}


if __name__ == '__main__':

    print("TESTING CONFIGURATION")
    CONFIG = Config.from_args_file_defaults()
    print(CONFIG.__dict__)
