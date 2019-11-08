"""Schema helpers."""
from functools import reduce
from warnings import warn

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


class MessageSchema():
    """
    Wrap validation for messages to ensure they are passed as dictionaries.

    Passing as messages results in errors as the validator attempts to mutate
    nested objects into messages which fails when no `@type` attribute is
    available.

    Also wrap errors into collected Validation error and raise extra key errors
    as warnings instead of exceptions.
    """
    __slots__ = ('schema', 'validator', 'warn_on_extra')

    def __init__(self, schema, warn_on_extra=True):
        self.schema = schema
        self.validator = Schema(schema)
        self.warn_on_extra = warn_on_extra

    def __call__(self, msg):
        __tracebackhide__ = True
        try:
            return self.validator(dict(msg))
        except MultipleInvalid as error:
            if self.warn_on_extra:
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
            else:
                raise ValidationError(error)
        except Invalid as error:
            if self.warn_on_extra:
                if is_extra_key_error(error):
                    invalid_into_unexpected(error)
                else:
                    raise ValidationError(error)
            else:
                raise ValidationError(error)
