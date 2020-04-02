"""Schema helpers."""
import logging

from voluptuous import Schema, Optional, REMOVE_EXTRA, PREVENT_EXTRA
from voluptuous.error import Invalid, MultipleInvalid


class ValidationError(Exception):
    """When errors on validation."""
    def __init__(self, error: Invalid):
        if isinstance(error, MultipleInvalid) and len(error.errors) > 1:
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


def _dict_key_set(dct, prepend=''):
    key_set = set()
    for key in dct.keys():
        key_path = '.'.join([item for item in [prepend, key] if item])
        key_set.add(key_path)
        if isinstance(dct[key], dict):
            key_set.update(_dict_key_set(dct[key], prepend=key_path))
    return key_set


class MessageSchema():  # pylint: disable=too-few-public-methods
    """
    Wrap validation for messages to ensure they are passed as dictionaries.

    Passing as messages results in errors as the validator attempts to mutate
    nested objects into messages which fails when no `@type` attribute is
    available.

    When `allow_extra` is True, unexpected attributes are removed from the
    validated message and a warning is logged.

    If `Should` keys are found, the validated message is checked for missing
    `Should` keys and a warning is logged for each missing.
    """
    __slots__ = ('schema', 'validator', 'extra')

    def __init__(self, schema, allow_extra=True):
        self.schema = schema
        self.extra = REMOVE_EXTRA if allow_extra else PREVENT_EXTRA
        self.validator = Schema(schema, extra=self.extra)


    def __call__(self, msg):
        logger = logging.getLogger(__name__)
        try:
            validated = self.validator(dict(msg))
            validated_key_set = _dict_key_set(validated)
            if self.extra == REMOVE_EXTRA:
                removed = _dict_key_set(msg) - validated_key_set
                if removed:
                    logger.warning(
                        'Unexpected message keys found: %s',
                        ', '.join(sorted(removed))
                    )


            shoulds = Should.find_in(self.schema)
            if shoulds:
                missing_shoulds = shoulds - (validated_key_set & shoulds)
                if missing_shoulds:
                    logger.warning(
                        'SHOULD be present but are missing: %s',
                        ', '.join(sorted(missing_shoulds))
                    )

            return validated

        except Invalid as err:
            raise ValidationError(err) from err


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


class Should(Optional):  # pylint: disable=too-few-public-methods
    """Validator for items described as 'SHOULD' be present and not 'MUST'.

    Behaves the same as `Optional`.
    """
    def __init__(self, key, msg=None, description=None):
        super().__init__(key, msg=msg, description=description)

    @classmethod
    def find_in(cls, dct, path_prepend=''):
        """Recursively descend through dictionary, finding each key marked as
        'Should'.
        """
        should_set = set()
        for key in dct.keys():
            key_path = '.'.join([
                item for item in [path_prepend, str(key)] if item
            ])
            if isinstance(key, cls):
                should_set.add(key_path)
            if isinstance(dct[key], dict):
                should_set.update(cls.find_in(dct[key], key_path))
        return should_set
