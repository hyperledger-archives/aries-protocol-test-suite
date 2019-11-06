"""Reporting for aries protocol tests."""
import datetime
import json
from warnings import WarningMessage

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


class TestReport:
    """Collection of information needed to report about a run test."""

    __slots__ = ('function', 'report', 'warnings')

    def __init__(
            self,
            function: TestFunction,
            report: _pytest.runner.TestReport,
            warnings: [WarningMessage]):
        self.function = function
        self.report = report
        self.warnings = warnings

    def flatten(self):
        """Flatten this TestReport object into dictionary."""
        return dict(filter(
            lambda item: bool(item[1]),
            {
                'name': ','.join([
                    self.function.protocol,
                    self.function.version,
                    self.function.role,
                    self.function.name
                ]),
                'description': self.function.description,
                'pass': self.report.outcome == 'passed',
                'info': self.report.longrepr,
                'warnings': list(map(
                    lambda warning: {
                        'message': warning.message,
                        'category': warning.category.__name__
                    },
                    self.warnings
                )),
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
        self.tests: [TestReport] = []

    def add_report(self, report: TestReport):
        """Append test report to tests list."""
        self.tests.append(report)

    def make_report(self) -> dict:
        """Construct flat report dictionary."""
        return {
            '@type': Report.TYPE,
            'suite_version': Report.VERSION,
            'under_test_name': self.under_test_name,
            'under_test_version': self.under_test_version,
            'test_time': self.test_time,
            'results': list(map(lambda tr: tr.flatten(), self.tests))
        }

    def to_json(self, pretty_print=True) -> str:
        """Serialize report to string."""
        if pretty_print:
            return json.dumps(self.make_report(), indent=2)

        return json.dumps(self.make_report)


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
