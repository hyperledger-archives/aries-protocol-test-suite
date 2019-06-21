import re
from operator import is_not
from functools import partial

from semver import VersionInfo, parse

class InvalidModule(Exception): pass

def route_def(routes, msg_type):
    """ Route definition decorator """
    def _route_def(func):
        routes[msg_type] = func
    return _route_def

class Semver(VersionInfo):
    """ Wrapper around the more complete VersionInfo class from semver package.

        This wrapper enables abbreviated versions in message types (i.e. 1.0 not 1.0.0).
    """
    SEMVER_RE = re.compile(
        r'^(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?$'
    )

    def __init__(self, *args):
        super().__init__(*args)

    @staticmethod
    def from_str(version_str):
        matches = Semver.SEMVER_RE.match(version_str)
        if matches:
            args = list(matches.groups())
            if not matches.group(3):
                args.append('0')
            return Semver(*map(int, filter(partial(is_not, None), args)))

        parts = parse(version_str)
        return Semver(
            parts['major'], parts['minor'], parts['patch'],
            parts['prerelease'], parts['build'])

class MetaModule(type):
    def __new__(cls, name, bases, dct):
        if not 'DOC_URI' in dct:
            raise InvalidModule('DOC_URI missing from module definition')
        if not 'PROTOCOL' in dct:
            raise InvalidModule("PROTOCOL missing from module definition")
        if not 'VERSION' in dct:
            raise InvalidModule('VERSION missing from module definition')

        return type.__new__(cls, name, bases, dct)

    _normalized_version = None
    _version_info = None

    @property
    def version(cls):
        return cls.VERSION

    @property
    def normalized_version(cls):
        if not cls._normalized_version:
            version_info = cls.version_info
            cls._normalized_version = str(version_info)
        return cls._normalized_version

    @property
    def version_info(cls):
        if not cls._version_info:
            cls._version_info = Semver.from_str(cls.VERSION)
        return cls._version_info

    @property
    def protocol(cls):
        return cls.PROTOCOL

    @property
    def doc_uri(cls):
        return cls.DOC_URI

    @property
    def qualified_protocol(cls):
        return cls.DOC_URI + cls.PROTOCOL

    @property
    def protocol_identifer_uri(cls):
        return cls.qualified_protocol + '/' + cls.normalized_version

class Module(metaclass=MetaModule):
    DOC_URI = None
    PROTOCOL = None
    VERSION = None
