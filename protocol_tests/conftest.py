""" Test Suite fixture definitions.

    These fixtures define the core functionality of the testing agent.

    For more information on how pytest fixtures work, see
    https://docs.pytest.org/en/latest/fixture.html#fixture
"""

import asyncio
import json
import os

import pytest
from aiohttp import web

from config import load_config
from . import ChannelManager

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
def channel_manager(config):
    """Get channel manager for test suite."""
    manager = ChannelManager(config['subject']['endpoint'])
    yield manager

@pytest.fixture(scope='session')
async def http_endpoint(config, channel_manager):
    """Create http server task."""

    async def handle(request):
        """aiohttp handle POST."""
        response = []
        with channel_manager.reply_handler(response.append):
            await channel_manager.handle(await request.read())

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
    await server_task
    await runner.cleanup()


@pytest.fixture(scope='session')
def backchannel(http_endpoint, channel_manager): # pylint: disable=unused-argument
    """Get backchannel to test subject."""
    yield channel_manager.backchannel
