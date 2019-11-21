"""Schema helpers."""
from functools import reduce
import logging

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


def log_unexpected(error):
    path = ' @ message[%s]' % ']['.join(map(repr, error.path)) \
        if error.path else ''
    logging.getLogger(__name__).warning(
        'Unexpected Message key found{}'.format(path)
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
    __slots__ = ('schema', 'validator', 'allow_extra')

    def __init__(self, schema, allow_extra=True):
        self.schema = schema
        self.validator = Schema(schema)
        self.allow_extra = allow_extra

    def __call__(self, msg):
        __tracebackhide__ = True
        try:
            return self.validator(dict(msg))
        except MultipleInvalid as error:
            if self.allow_extra:
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

                list(map(log_unexpected, extra_errors))

                if not_extra_errors:
                    # Re-raise the rest
                    raise ValidationError(
                        MultipleInvalid(not_extra_errors)
                    )
            else:
                raise ValidationError(error)
        except Invalid as error:
            if self.allow_extra:
                if is_extra_key_error(error):
                    log_unexpected(error)
                else:
                    raise ValidationError(error)
            else:
                raise ValidationError(error)


def is_valid(validator, value):
    """Item validated without errors."""
    try:
        validator(value)
        return True
    except Invalid:
        return False


class AtLeastOne():  # pylint: disable=too-few-public-methods
    """At least one item in a collection matches the given schema."""
    def __init__(self, schema, msg=None):
        self.validator = Schema(schema)
        self.msg = msg

    def __call__(self, collection):
        for item in collection:
            if is_valid(self.validator, item):
                return collection
        if self.msg:
            raise Invalid(self.msg)
        raise Invalid('Item matching schema not found in collection')
