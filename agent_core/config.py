""" Module for storing and updating configuration.
"""
from typing import Dict, Any

from schema import SchemaError, Schema


class InvalidConfigurationException(Exception):
    """ Exception raise on absent required configuration value
    """


class Config:
    """ Configuration class used to store and update configuration information.
    """

    __slots__ = ()

    SCHEMA = {}

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

    @classmethod
    def from_options(cls, options: Dict[str, Any]):
        """ Load configuration from a dictionary """
        conf = cls()
        conf.update(options)
        conf.apply()
        return conf

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
                Schema(self.__class__.SCHEMA).validate(self.__dict__)
            )
        except SchemaError as err:
            error_message = 'Failed to validate configration: ' + \
                    ', '.join([msg for msg in err.autos])
            raise InvalidConfigurationException(error_message) from err
