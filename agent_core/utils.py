import re
from operator import is_not
from functools import partial
from semver import VersionInfo, parse

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

