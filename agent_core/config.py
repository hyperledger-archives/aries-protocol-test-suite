""" Module for storing and updating configuration.
"""
import sys
import getpass
import argparse
import logging
from typing import Dict, Any

from schema import SchemaError, Schema, Optional, Use
import toml


class InvalidConfigurationException(Exception):
    """ Exception raise on absent required configuration value
    """


class Config:
    """ Configuration class used to store and update configuration information.
    """

    __slots__ = (
        'config',
        'wallet',
        'passphrase',
        'ephemeral',
        'inbound_transports',
        'port',
        'log_level',
        'log_suppress',
        'log_include'
    )

    CONFIG_SCHEMA = {
        Optional('config'): str,
        'wallet': str,
        'passphrase': str,
        Optional('ephemeral'): bool,
        Optional('inbound_transports', default=['http']): [str],
        Optional('port'): int,
        Optional('log_level', default=50): int,
        Optional('log_suppress', default=[]): [str],
        Optional('log_include', default=[]): [str],
    }

    def __getitem__(self, index):
        """ Get config option """
        return getattr(self, index, None)

    @property
    def __dict__(self):
        """ Get dictionary representation of config """
        def _dict_gen(slotted_object):
            for slot in slotted_object.__slots__:
                attr = getattr(slotted_object, slot, None)
                if attr is None:
                    continue
                yield (slot, attr)

        return dict(_dict_gen(self))

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
            # prog='agent'
        )
        parser.add_argument(
            '-c',
            '--config',
            dest='config',
            metavar='FILE',
            type=str,
            help='Load configuration from FILE',
        )
        parser.add_argument(
            '-i',
            '--inbound-transport',
            dest='inbound_transports',
            metavar='INBOUND_TRANSPORT',
            nargs='+',
            help='Set the inbound transport type',
            default=argparse.SUPPRESS
        )
        parser.add_argument(
            '-w',
            '--wallet',
            dest='wallet',
            metavar='WALLET',
            type=str,
            help='Specify wallet',
            default=argparse.SUPPRESS
        )
        parser.add_argument(
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
        parser.add_argument(
            '--ephemeral',
            dest='ephemeral',
            action='store_true',
            help='Use ephemeral wallets',
            default=argparse.SUPPRESS

        )
        parser.add_argument(
            '--port',
            dest='port',
            metavar='PORT',
            type=int,
            help='Run inbound transport on PORT',
            default=argparse.SUPPRESS

        )
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
    def from_options(cls, options: Dict[str, Any]):
        conf = cls()
        conf.update(options)
        conf.apply()
        return conf

    @classmethod
    def from_file(cls, config_path: str):
        """ Create config object from toml file.
        """
        return cls.from_options(toml.load(config_path))

    @classmethod
    def from_args(cls):
        """ Create config object from command line arguments.

            Configuration file will also be opened if specified by args.
        """
        parser = cls.get_arg_parser()
        options = parser.parse_known_args()[0].__dict__

        if options['config']:
            options = {
                **toml.load(options['config']),
                **options
                # By placing options last, the cli args get priority
            }

        return cls.from_options(options)

    def update(self, options: Dict[str, Any]):
        """ Load configuration from the options dictionary.
        """
        for slot in self.__slots__:
            if slot in options and options[slot] is not None:
                setattr(self, slot, options[slot])

    def apply(self):
        """ Validate updates to the configuration """
        try:
            self.update(  # Update with defaults added by Schema
                Schema(self.__class__.CONFIG_SCHEMA).validate(self.__dict__)
            )
        except SchemaError as err:
            error_message = 'Failed to validate configration: ' + \
                    ', '.join([msg for msg in err.autos])
            raise InvalidConfigurationException(error_message) from err

        logging_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)-8s %(name)s : %(message)s')
        logging_handler.setFormatter(formatter)
        logging.getLogger().addHandler(logging_handler)
        logging.getLogger(__name__.split('.')[0]).setLevel(self['log_level'])
        for logger in self['log_include']:
            logging.getLogger(logger).setLevel(self['log_level'])
        for logger in self['log_suppress']:
            logging.getLogger(logger).setLevel(logging.CRITICAL)

    def transport_options(self):
        """ Get options relevant to transport """
        return {'port': self['port']} if self['port'] else {}


if __name__ == '__main__':

    print("TESTING CONFIGURATION")
    CONFIG = Config.from_args()
    print(CONFIG.__dict__)
