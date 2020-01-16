""" Test Suite fixture definitions.

    These fixtures define the core functionality of the testing agent.

    For more information on how pytest fixtures work, see
    https://docs.pytest.org/en/latest/fixture.html#fixture
"""

import asyncio
import json
import os
from importlib import import_module
from contextlib import suppress

import pytest
from aiohttp import web

from . import Suite
from .backchannel import SuiteConnectionInfo

# pylint: disable=redefined-outer-name

@pytest.fixture(scope='session')
def event_loop():
    """ Create a session scoped event loop.

        pytest.asyncio plugin provides a default function scoped event loop
        which cannot be used as a dependency to session scoped fixtures.
    """
    return asyncio.get_event_loop()


@pytest.fixture(scope='session')
def config(pytestconfig):
    """ Get suite configuration.
    """
    yield pytestconfig.suite_config

@pytest.fixture(scope='session')
def suite():
    """Get channel manager for test suite."""
    yield Suite()

@pytest.fixture(scope='session')
async def http_endpoint(config, suite):
    """Create http server task."""

    async def handle(request):
        """aiohttp handle POST."""
        response = []
        with suite.reply(response.append):
            await suite.handle(await request.read())

        if response:
            return web.Response(body=response.pop())

        raise web.HTTPAccepted()

    app = web.Application()
    app.router.add_post('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config['host'], config['port'])
    server_task = asyncio.ensure_future(site.start())
    yield
    server_task.cancel()
    with suppress(asyncio.CancelledError):
        await server_task
    await runner.cleanup()


@pytest.fixture(scope='session')
async def backchannel(config, http_endpoint, suite):
    """Get backchannel to test subject."""
    if 'backchannel' in config and config['backchannel']:
        path_parts = config['backchannel'].split('.')
        mod_path, class_name = '.'.join(path_parts[:-1]), path_parts[-1]
        mod = import_module(mod_path)
        backchannel_class = getattr(mod, class_name)
    else:
        from default import ManualBackchannel
        backchannel_class = ManualBackchannel

    suite.set_backchannel(backchannel_class())
    await suite.backchannel.setup(config, suite)
    yield suite.backchannel
    await suite.backchannel.close()


@pytest.fixture(scope='session')
def temporary_channel(http_endpoint, suite):
    """Get contextmanager for using a temporary channel."""
    yield suite.temporary_channel


@pytest.fixture
async def connection(config, temporary_channel, backchannel):
    """Fixture for active connection"""
    with temporary_channel() as conn:
        info = SuiteConnectionInfo(
            conn.did,
            conn.verkey_b58,
            'test-suite',
            config['endpoint']
        )
        their_info = await backchannel.new_connection(info)
        conn.update(**their_info._asdict())
        yield conn
