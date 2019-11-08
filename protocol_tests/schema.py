"""Schema helpers."""
from functools import reduce, singledispatch
from typing import Dict, Any
from warnings import warn

from voluptuous import Schema, Optional
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


class Slot():
    """
    Mark a fillable 'slot' in a schema.

    On validation, this will simply act as a validator for the given schema.
    """
    __slots__ = ('name', 'schema', 'default')

    def __init__(
            self,
            name: str,
            schema: Any,
            *,
            default: Any = None):
        self.name = name
        self.schema = Schema(schema)
        self.default = default

    def __call__(self, value):
        return self.schema(value)


@singledispatch
def fill_slots(item, **values: Dict[str, Any]):
    """Fill in slots in a structure."""
    raise ValueError('Cannot fill slots in item of type {}'.format(type(item)))


@fill_slots.register
def _(item: dict, **values: Dict[str, Any]):
    dest = {}
    for key, value in item.items():
        new_value = fill_value(value, key=key, **values)
        if isinstance(key, Optional):
            key = key.schema
        if new_value is not None:
            dest[key] = new_value
    return dest


@fill_slots.register
def _(item: list, **values: Dict[str, Any]):
    return list(map(lambda value: fill_value(value, **values), item))


@fill_slots.register(MessageSchema)
@fill_slots.register(Schema)
def _(item, **values: Dict[str, Any]):
    return fill_slots(item.schema, **values)


@singledispatch
def fill_value(value, _key: Any = None, **_values: Dict[str, Any]):
    """Replace slots with given values."""
    return value


@fill_value.register
def _(value: type, key: Any = None, **values: Dict[str, Any]):
    raise ValueError('Value of primative type {} is invalid'.format(value))


@fill_value.register
def _(value: Slot, key: Any = None, **values: Dict[str, Any]):
    if key and isinstance(key, Optional):
        if value.name not in values and value.default is None:
            return None

    slot = value
    # Validate input for slot
    if slot.name in values:
        return slot.schema(values[slot.name])

    if slot.default is not None:
        if callable(slot.default):
            return slot.default(values)
        return slot.default

    raise KeyError(
        'No value given for slot name {}'.format(slot.name)
    )


@fill_value.register(list)
@fill_value.register(dict)
def _(value, key: Any = None, **values: Dict[str, Any]):
    return fill_slots(value, **values)


@fill_value.register(MessageSchema)
@fill_value.register(Schema)
def _(value, key: Any = None, **values: Dict[str, Any]):
    return fill_slots(value, **values)
