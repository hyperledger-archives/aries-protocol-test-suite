""" Pytest behavior customizations.
"""

import os
import sys
import time
import re
import itertools
import logging

import pytest
from _pytest.terminal import TerminalReporter

from config import load_config, default
from reporting import ReportSingleton, TestFunction, TestReport


class AgentTerminalReporter(TerminalReporter):
    """ Customized PyTest Output """
    @pytest.hookimpl(trylast=True)
    def pytest_sessionstart(self, session):
        self._session = session
        self._sessionstarttime = time.time()

    def pytest_runtest_logstart(self, nodeid, location):
        line = self._locationline(nodeid, *location)
        self.write_sep('=', line, bold=True)
        self.write('\n')


def pytest_addoption(parser):
    """ Load in config path. """
    group = parser.getgroup(
        "Aries Protocol Test Suite Configuration",
        "Aries Protocol Test Suite Configuration",
        after="general"
    )
    group.addoption(
        "--sc",
        "--suite-config",
        dest='suite_config',
        action="store",
        metavar="SUITE_CONFIG",
        help="Load suite configuration from SUITE_CONFIG",
    )
    group.addoption(
        "-S",
        "--select",
        dest='select',
        action='store',
        metavar='SELECT_REGEX',
        help='Run tests matching SELECT_REGEX. '
        'Overrides tests selected in configuration.'
    )
    group.addoption(
        "-O",
        "--output",
        dest="save_path",
        action="store",
        metavar="PATH",
        help="Save interop profile to PATH."
    )
    group.addoption(
        "-L",
        "--list",
        dest="list_tests",
        action="store_true",
        help="List available tests."
    )
    group.addoption(
        "--show-dev-notes",
        dest="dev_notes",
        action="store_true",
        help="Output log messages generated during testing for developers\n"
             "take note of."
    )


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """ Load Test Suite Configuration. """
    dirname = os.getcwd()
    config_path = config.getoption('suite_config')
    config_path = 'config.toml' if not config_path else config_path
    config_path = os.path.join(dirname, config_path)
    print(
        '\nAttempting to load configuration from file: %s\n' %
        config_path
    )

    try:
        config.suite_config = load_config(config_path)
    except FileNotFoundError:
        config.suite_config = default()
    config.suite_config['save_path'] = config.getoption('save_path')

    # Override default terminal reporter for better test output when not capturing
    if config.getoption('capture') == 'no':
        reporter = config.pluginmanager.get_plugin('terminalreporter')
        agent_reporter = AgentTerminalReporter(config, sys.stdout)
        config.pluginmanager.unregister(reporter)
        config.pluginmanager.register(agent_reporter, 'terminalreporter')

    # Compile select regex and test regex if given
    select_regex = config.getoption('select')
    config.select_regex = re.compile(select_regex) if select_regex else None
    config.tests_regex = list(map(
        re.compile, config.suite_config['tests']
    ))


def pytest_collection_modifyitems(session, config, items):
    """Select tests based on config or args."""
    # pylint: disable=protected-access
    if not items:
        return

    report = ReportSingleton(session.config.suite_config)

    def add_to_report(item):
        if callable(item._obj) and hasattr(item._obj, 'meta_set'):
            func = item._obj
            test_fn = TestFunction(
                protocol=func.protocol,
                version=func.version,
                role=func.role,
                name=func.name,
                description=func.__doc__
            )
            item.meta_name = test_fn.flatten()['name']
            report.add_test(test_fn)
        return item

    def test_regex_filter(item):
        for regex in config.tests_regex:
            if regex.match(item.meta_name):
                return True
        return False

    item_pipeline = map(add_to_report, items)
    if config.select_regex:
        item_pipeline = filter(
            lambda item: bool(config.select_regex.match(item.meta_name)),
            item_pipeline
        )
    elif config.tests_regex:
        item_pipeline = filter(
            test_regex_filter,
            item_pipeline
        )

    remaining = list(item_pipeline)
    deselected = list(set(items)-set(remaining))

    # Report the deselected items to pytest
    config.hook.pytest_deselected(items=deselected)

    items[:] = remaining


@pytest.hookimpl()
def pytest_report_collectionfinish(config, startdir, items):
    """Print available tests if option set."""
    if config.getoption('list_tests'):
        reporter = config.pluginmanager.get_plugin('terminalreporter')
        reporter.write('\n')
        reporter.write_sep('-', 'Available Tests', bold=False, yellow=True)
        return ReportSingleton(config.suite_config).available_tests_json()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """ Customize reporting """
    outcome = yield
    report = outcome.get_result()

    setattr(item, "report_" + report.when, report)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Write Interop Profile to terminal summary."""
    if config.getoption('collectonly'):
        return

    report = ReportSingleton(config.suite_config)

    if config.getoption('dev_notes'):
        terminalreporter.write('\n')
        terminalreporter.write_sep(
            '=', 'Developer Notes', bold=True
        )
        terminalreporter.write('\n')
        terminalreporter.write(report.notes_json())
        terminalreporter.write('\n')



    terminalreporter.write('\n')
    terminalreporter.write_sep(
        '=', 'Interop Profile', bold=True
    )
    terminalreporter.write('\n')
    terminalreporter.write(report.report_json())
    terminalreporter.write('\n')


@pytest.fixture(scope='session')
def report(config):
    """Report fixture."""
    report_instance = ReportSingleton(config)
    yield report_instance
    save_path = config.get('save_path')
    if save_path:
        report_instance.save(save_path)


@pytest.fixture
def report_on_test(request, caplog, report):
    """Universally loaded fixture for getting test reports."""
    yield
    passed = False
    if hasattr(request.node, 'report_call') and \
            request.node.report_call.outcome == 'passed':
        passed = True


    test_fn = TestFunction(
        protocol=request.function.protocol,
        version=request.function.version,
        role=request.function.role,
        name=request.function.name,
        description=request.function.__doc__
    )

    report.add_report(TestReport(test_fn, passed))

    notes = itertools.chain([
        records for when in ('setup', 'call', 'teardown')
        for records in caplog.get_records(when)
    ])
    notes = filter(
        lambda log_rec: log_rec.levelno >= logging.WARNING,
        notes
    )
    notes = map(
        lambda log_rec: log_rec.message,
        notes
    )
    report.add_notes(
        test_fn,
        notes
    )
