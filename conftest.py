""" Pytest behavior customizations.
"""

import os
import sys
import time
import re
import logging

import pytest
from _pytest.terminal import TerminalReporter
import toml
from schema import Optional

from config import load_config, default
from agent_core import AgentConfig


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


class SuiteConfig(AgentConfig):
    """ Aries Protocol Test Suite Config class """
    __slots__ = (
        'endpoint',
        'features',
        'static_connection',
        'logging',
    )

    SCHEMA = {
        **AgentConfig.SCHEMA,
        'endpoint': str,
        'features': [str],
        Optional('logging'): {
            'active_logs': [str],
            'log_level': int,
        },
        Optional('static_connection'): {
            'did': str,
            'verkey': str,
            'endpoint': str
        },
    }

    def apply(self):
        super().apply()

        # Apply logging configuration
        if 'logging' in self:
            logging.getLogger().setLevel(logging.WARNING)
            for logger in self['logging']['active_logs']:
                logging.getLogger(logger).setLevel(
                    self['logging']['log_level']
                )


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
        "-F",
        "--feature-select",
        dest='select',
        action='store',
        metavar='SELECT_REGEX',
        help='Run tests matching SELECT_REGEX. '
        'Overrides tests selected in configuration.'
    )


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """ Load Test Suite Configuration. """
    dirname = os.getcwd()
    config_path = config.getoption('suite_config')
    config_path = 'config.toml' if not config_path else config_path
    config_path = os.path.join(dirname, config_path)
    print(
        '\nLoading Agent Test Suite configuration from file: %s\n' %
        config_path
    )

    try:
        config.suite_config = load_config(config_path)
    except FileNotFoundError:
        config.suite_config = default()

    # register additional markers
    config.addinivalue_line(
        "markers", "features(name[, name, ...]):"
        "Define what features the test belongs to."
    )
    config.addinivalue_line(
        "markers", "priority(int): Define test priority for "
        "ordering tests. Higher numbers occur first."
    )

    # Override default terminal reporter for better test output
    reporter = config.pluginmanager.get_plugin('terminalreporter')
    agent_reporter = AgentTerminalReporter(config, sys.stdout)
    config.pluginmanager.unregister(reporter)
    config.pluginmanager.register(agent_reporter, 'terminalreporter')

    # Compile SELECT_REGEX if given
    select_regex = config.getoption('select')
    config.select_regex = re.compile(select_regex) if select_regex else None
    config.features = config.suite_config['features']


def pytest_collection_modifyitems(session, config, items):
    """ Select tests based on config or args. """
    if not items:
        return

    def feature_filter(item):
        feature_names = [
            mark.args for mark in item.iter_markers(name="features")
        ]
        feature_names = [item for sublist in feature_names for item in sublist]
        if feature_names:
            for selected_test in config.features:
                if selected_test in feature_names:
                    item.selected_feature = selected_test
                    return True

        return False

    def regex_feature_filter(item):
        feature_names = [
            mark.args for mark in item.iter_markers(name="features")
        ]
        feature_names = [item for sublist in feature_names for item in sublist]
        for feature in feature_names:
            if config.select_regex.match(feature):
                item.selected_feature = feature
                return True

        return False

    def feature_priority_map(item):
        priorities = [
            mark.args[0] for mark in item.iter_markers(name="priority")
        ]
        if priorities:
            item.priority = sorted(priorities, reverse=True)[0]
        else:
            item.priority = 0
        return item

    def priority_sort(item):
        return item.priority

    filtered_items = items
    if config.select_regex:
        filtered_items = filter(regex_feature_filter, filtered_items)
    if config.features:
        filtered_items = filter(feature_filter, filtered_items)

    priority_mapped_items = map(feature_priority_map, filtered_items)
    items[:] = sorted(priority_mapped_items, key=priority_sort, reverse=True)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """ Customize reporting """
    outcome = yield
    report = outcome.get_result()
    term_reporter = item.config.pluginmanager.get_plugin('terminalreporter')
    if report.when == 'call' and report.failed:
        term_reporter.write_sep(
            '=',
            'Failure! Feature: %s, Test: %s' % (
                item.selected_feature,
                item.name
            ),
            red=True,
            bold=True
        )
        report.toterminal(term_reporter.writer)
