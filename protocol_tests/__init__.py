""" Protocol Test Helpers """
from contextlib import contextmanager
from functools import reduce
from typing import Dict, Iterable, Union
from warnings import warn
import hashlib
import json

from aries_staticagent import StaticConnection, crypto

from voluptuous import Schema
from voluptuous.error import Invalid, MultipleInvalid


class ValidationError(Exception):
    """When errors on validation"""
    def __init__(self, error: Invalid):
        if isinstance(error, MultipleInvalid):
            super().__init__(
                'Multiple errors found during validation:\n\t' +
                ('\n\t'.join(
                    [
                        str(error)
                        for error in error.errors
                    ]
                ))
            )
        else:
            super().__init__(
                str(error)
            )


class UnexceptedMessageKey(Warning):
    """Warning raised when an unexpected property is found in a message."""


def invalid_into_unexpected(error):
    path = ' @ message[%s]' % ']['.join(map(repr, error.path)) \
        if error.path else ''
    warn(
        'Unexpected Message key found{}'.format(path),
        UnexceptedMessageKey
    )


def is_extra_key_error(error):
    return error.error_message == 'extra keys not allowed'


def MessageSchema(schema, warn_on_extra=True):
    """
    Wrap validation for messages to ensure they are passed as dictionaries.

    Passing as messages results in errors as the validator attempts to mutate
    nested objects into messages which fails when no `@type` attribute is
    available.

    Also wrap errors into collected Validation error and raise extra key errors
    as warnings instead of exceptions.
    """
    __tracebackhide__ = True
    validator = Schema(schema)

    def _ensure_dict_and_validate(msg):
        try:
            return validator(dict(msg))
        except MultipleInvalid as error:
            def split(acc, error):
                extra_errors, not_extra_errors = acc
                if is_extra_key_error(error):
                    extra_errors.append(error)
                else:
                    not_extra_errors.append(error)
                return (extra_errors, not_extra_errors)

            extra_errors, not_extra_errors = reduce(
                split, error.errors, ([], [])
            )

            # Apply invalid_into_unexpected to each error for extra keys
            list(map(invalid_into_unexpected, extra_errors))

            if not_extra_errors:
                # Re-raise the rest
                raise ValidationError(
                    MultipleInvalid(not_extra_errors)
                )
        except Invalid as error:
            if warn_on_extra:
                if is_extra_key_error(error):
                    invalid_into_unexpected(error)
                else:
                    raise ValidationError(error)
            else:
                raise ValidationError(error)

    return _ensure_dict_and_validate


def _recipients_from_packed_message(packed_message: bytes) -> Iterable[str]:
    """
    Inspect the header of the packed message and extract the recipient key.
    """
    try:
        wrapper = json.loads(packed_message)
    except Exception as err:
        raise ValueError("Invalid packed message") from err

    recips_json = crypto.b64_to_bytes(
        wrapper["protected"], urlsafe=True
    ).decode("ascii")
    try:
        recips_outer = json.loads(recips_json)
    except Exception as err:
        raise ValueError("Invalid packed message recipients") from err

    return map(
        lambda recip: recip['header']['kid'], recips_outer['recipients']
    )


class ChannelManager(StaticConnection):
    """
    Manage connections to agent under test.

    The Channel Manager itself is a static connection to the test subject
    allowing it to be used as the backchannel.
    """

    def __init__(self, endpoint: str):
        """
        Initialize Backchannel static connection using predefined identities.

        Args:
            endpoint: HTTP URL of test subjects backchannel endpoint
        """
        test_suite_vk, test_suite_sk = crypto.create_keypair(
            hashlib.sha256(b'aries-protocol-test-suite').digest()
        )
        test_subject_vk, _test_subject_sk = crypto.create_keypair(
            hashlib.sha256(b'aries-protocol-test-subject').digest()
        )
        super().__init__(
            test_suite_vk,
            test_suite_sk,
            test_subject_vk,
            endpoint
        )

        self.frontchannels: Dict[str, StaticConnection] = {}

    @property
    def backchannel(self):
        """Return a reference to the backchannel (self)."""
        return self

    @property
    def test_suite_vk(self):
        """Get test_suite_vk."""
        return self.my_vk

    async def handle(self, packed_message: bytes):
        """
        Route an incoming message to self (the backchannel) or to the
        appropriate frontchannels.
        """
        for recipient in _recipients_from_packed_message(packed_message):
            if recipient == self.my_vk_b58:
                await super().handle(packed_message)
            if recipient in self.frontchannels:
                await self.frontchannels[recipient].handle(packed_message)

    def new_frontchannel(
            self,
            their_vk: Union[bytes, str],
            endpoint: str) -> StaticConnection:
        """
        Create a new connection and add it as a frontchannel.

        Args:
            fc_vk: The new frontchannel's verification key
            fc_sk: The new frontchannel's signing key
            their_vk: The test subject's verification key for this channel
            endpoint: The HTTP URL to the endpoint of the test subject.

        Returns:
            Returns the new front channel (static connection).
        """
        fc_vk, fc_sk = crypto.create_keypair()
        new_fc = StaticConnection(
            fc_vk,
            fc_sk,
            their_vk,
            endpoint
        )
        frontchannel_index = crypto.bytes_to_b58(fc_vk)
        self.frontchannels[frontchannel_index] = new_fc
        return new_fc

    def add_frontchannel(self, connection: StaticConnection):
        """Add an already created connection as a frontchannel."""
        frontchannel_index = crypto.bytes_to_b58(connection.my_vk)
        self.frontchannels[frontchannel_index] = connection

    def remove_frontchannel(self, connection: StaticConnection):
        """
        Remove a frontchannel.

        Args:
            fc_vk: The frontchannel's verification key
        """
        fc_vk = crypto.bytes_to_b58(connection.my_vk)
        if fc_vk in self.frontchannels:
            del self.frontchannels[fc_vk]

    @contextmanager
    def temporary_channel(
            self,
            their_vk=None,
            endpoint=None) -> StaticConnection:
        """Use 'with' statement to use a temporary channel."""
        channel = self.new_frontchannel(their_vk or b'', endpoint or '')
        yield channel
        self.remove_frontchannel(channel)
