"""Reporting for aries protocol tests."""
import datetime
import json
from collections import namedtuple
from typing import Dict, Union, Sequence

import _pytest
from setup import VERSION

# pylint: disable=too-few-public-methods


def meta(
        protocol: str = None,
        version: str = None,
        role: str = None,
        name: str = None):
    """Set meta information about test functions."""
    def _meta(func):
        func.meta_set = True
        func.protocol = protocol
        func.version = version
        func.role = role
        func.name = name
        return func
    return _meta


class TestFunction:
    """Container for TestFunction information."""

    __slots__ = ('protocol', 'version', 'role', 'name', 'description')

    def __init__(  # pylint: disable=too-many-arguments
            self,
            protocol: str,
            version: str,
            role: str,
            name: str,
            description: str):
        self.protocol = protocol
        self.version = version
        self.role = role
        self.name = name
        self.description = description

    def flatten(self):
        """Flatten for serialization."""
        return {
            'name': self.flat_name,
            'description': self.description,
        }

    @property
    def flat_name(self):
        """
        Flattened name consisting of comma separated protocol, version, role,
        and name.
        """
        return ','.join([self.protocol, self.version, self.role, self.name])

    def __hash__(self):
        return hash(self.flat_name)


class TestReport:
    """Collection of information needed to report about a run test."""

    __slots__ = ('function', 'passed',)

    def __init__(
            self,
            function: TestFunction,
            passed: bool):
        self.function = function
        self.passed = passed

    def flatten(self):
        """Flatten this TestReport object into dictionary."""
        return dict(filter(
            lambda item: isinstance(item[1], bool) or bool(item[1]),
            {
                **self.function.flatten(),
                'pass': self.passed,
            }.items()
        ))


class Report:
    """Protocol Test Suite report helper."""
    # Meta information
    TYPE = "Aries Test Suite Interop Profile v1"
    VERSION = VERSION

    def __init__(self, config: dict):
        self.test_time = '{date:%Y-%m-%dT%H:%M:%S}'.format(
            date=datetime.datetime.utcnow()
        )
        self.under_test_name = config['subject'].get('name', '')
        self.under_test_version = config['subject'].get('version', '')
        self.available_tests: [TestFunction] = []
        self.test_reports: [TestReport] = []
        self.notes: Dict[TestFunction, [str]] = {}

    def add_report(self, report: TestReport):
        """Append test report to test reports list."""
        self.test_reports.append(report)

    def add_test(self, test_fn: TestFunction):
        """Append test function to available tests list."""
        self.available_tests.append(test_fn)

    def add_notes(self, test_fn: TestFunction, note: Union[Sequence[str], str]):
        """Add developer notes for a test."""
        if test_fn not in self.notes:
            self.notes[test_fn.flat_name] = []
        if isinstance(note, str):
            self.notes[test_fn.flat_name].append(note)
        else:
            self.notes[test_fn.flat_name].extend(note)

    def make_report(self) -> dict:
        """Construct flat report dictionary."""
        return {
            '@type': Report.TYPE,
            'suite_version': Report.VERSION,
            'under_test_name': self.under_test_name,
            'under_test_version': self.under_test_version,
            'test_time': self.test_time,
            'results': list(map(lambda tr: tr.flatten(), self.test_reports))
        }

    def flatten_available_tests(self) -> dict:
        """Return flattened list of available tests."""
        return list(map(
            lambda test_fn: test_fn.flatten(),
            self.available_tests
        ))

    def available_tests_json(self, pretty_print=True) -> str:
        """Serialize available tests to string."""
        if pretty_print:
            return json.dumps(self.flatten_available_tests(), indent=2)

        return json.dumps(self.flatten_available_tests())

    def report_json(self, pretty_print=True) -> str:
        """Serialize report to string."""
        if pretty_print:
            return json.dumps(self.make_report(), indent=2)

        return json.dumps(self.make_report())

    def notes_json(self, pretty_print=True) -> str:
        """Serialize notes to string."""
        if pretty_print:
            return json.dumps(self.notes, indent=2)
        return json.dumps(self.notes)

    def save(self, path):
        """Save the test report out to a file."""
        with open(path, 'w') as out_file:
            json.dump(self.make_report(), out_file, indent=2)


class ReportSingleton:
    """Singleton for Report object."""
    _instance = None

    def __new__(cls, config):
        if not ReportSingleton._instance:
            ReportSingleton._instance = Report(config)
        return ReportSingleton._instance

    def __getattr__(self, name):
        return getattr(self._instance, name)

    def __setattr__(self, name, value):
        return setattr(self._instance, name, value)
