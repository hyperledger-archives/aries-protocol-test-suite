""" Module base class """

from .utils import Semver


def route_def(routes, msg_type):
    """ Route definition decorator """
    def _route_def(func):
        routes[msg_type] = func
    return _route_def


class InvalidModule(Exception):
    """ Thrown when module is malformed. """


class MetaModule(type):
    """ MetaModule:
        Ensures Module classes are well formed and provides convenience methods
    """
    def __new__(cls, name, bases, dct):
        if 'DOC_URI' not in dct:
            raise InvalidModule('DOC_URI missing from module definition')
        if 'PROTOCOL' not in dct:
            raise InvalidModule("PROTOCOL missing from module definition")
        if 'VERSION' not in dct:
            raise InvalidModule('VERSION missing from module definition')

        return type.__new__(cls, name, bases, dct)

    _normalized_version = None
    _version_info = None

    @property
    def version(cls):
        """ Convenience property: access VERSION """
        return cls.VERSION

    @property
    def normalized_version(cls):
        """ Convenience property: get normalized version info string """
        if not cls._normalized_version:
            version_info = cls.version_info
            cls._normalized_version = str(version_info)
        return cls._normalized_version

    @property
    def version_info(cls):
        """ Convenience property: get version info (major, minor, patch, etc.)
        """
        if not cls._version_info:
            cls._version_info = Semver.from_str(cls.VERSION)
        return cls._version_info

    @property
    def protocol(cls):
        """ Convenience property: access PROTOCOL """
        return cls.PROTOCOL

    @property
    def doc_uri(cls):
        """ Convenience property: access DOC_URI """
        return cls.DOC_URI

    @property
    def qualified_protocol(cls):
        """ Convenience property: build qualified protocol identifier """
        return cls.DOC_URI + cls.PROTOCOL

    @property
    def protocol_identifer_uri(cls):
        """ Convenience property: build full protocol identifier """
        return cls.qualified_protocol + '/' + cls.normalized_version


class Module(metaclass=MetaModule):  # pylint: disable=too-few-public-methods
    """ Base Module class """
    DOC_URI = None
    PROTOCOL = None
    VERSION = None
