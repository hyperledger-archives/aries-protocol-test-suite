""" Test Dispatcher """
import asyncio
from collections import namedtuple
import pytest

from agent_core.dispatcher import Dispatcher, NoRegisteredRouteException
from agent_core.module import Module, route_def
from agent_core.message import Message

MockMessage = namedtuple('MockMessage', ['type', 'test'])

@pytest.mark.asyncio
async def test_routing():
    """ Test that routing works in agent. """
    dispatcher = Dispatcher()

    called_event = asyncio.Event()

    @dispatcher.route('testing_type')
    async def route_gets_called(msg, **kwargs):
        kwargs['event'].set()

    test_msg = MockMessage('testing_type', 'test')
    await dispatcher.dispatch(test_msg, event=called_event)

    assert called_event.is_set()

@pytest.mark.asyncio
async def test_module_routing_explicit_def():
    """ Test that routing to a module works. """

    dispatcher = Dispatcher()
    called_event = asyncio.Event()

    class TestModule(Module):
        DOC_URI = ''
        PROTOCOL = 'test_protocol'
        VERSION = '1.0'

        routes = {}

        @route_def(routes, 'test_protocol/1.0/testing_type')
        async def route_gets_called(self, msg, **kwargs):
            kwargs['event'].set()

    mod = TestModule()
    dispatcher.route_module(mod)

    test_msg = Message({'@type': 'test_protocol/1.0/testing_type', 'test': 'test'})
    await dispatcher.dispatch(test_msg, event=called_event)

    assert called_event.is_set()

@pytest.mark.asyncio
async def test_module_routing_simple():
    """ Test that routing to a module works. """
    dispatcher = Dispatcher()
    called_event = asyncio.Event()

    class TestModule(Module):
        DOC_URI = ''
        PROTOCOL = 'test_protocol'
        VERSION = '1.0'

        async def testing_type(self, msg, *args, **kwargs):
            kwargs['event'].set()

    mod = TestModule()
    dispatcher.route_module(mod)

    test_msg = Message({'@type': 'test_protocol/1.0/testing_type', 'test': 'test'})
    await dispatcher.dispatch(test_msg, event=called_event)

    assert called_event.is_set()

@pytest.mark.asyncio
async def test_module_routing_many():
    """ Test that routing to a module works. """
    dispatcher = Dispatcher()
    dispatcher.called_module = None
    routed_event = asyncio.Event()

    class TestModule1(Module):
        DOC_URI = ''
        PROTOCOL = 'test_protocol'
        VERSION = '1.0'

        async def testing_type(self, msg, *args, **kwargs):
            kwargs['dispatcher'].called_module = 1
            kwargs['event'].set()

    class TestModule2(Module):
        DOC_URI = ''
        PROTOCOL = 'test_protocol'
        VERSION = '2.0'

        async def testing_type(self, msg, *args, **kwargs):
            kwargs['dispatcher'].called_module = 2
            kwargs['event'].set()

    dispatcher.route_module(TestModule1())
    dispatcher.route_module(TestModule2())

    test_msg = Message({'@type': 'test_protocol/1.0/testing_type', 'test': 'test'})
    await dispatcher.dispatch(test_msg, event=routed_event, dispatcher=dispatcher)
    await routed_event.wait()

    assert routed_event.is_set()
    assert dispatcher.called_module == 1

    routed_event.clear()

    test_msg = Message({'@type': 'test_protocol/2.0/testing_type', 'test': 'test'})
    await dispatcher.dispatch(test_msg, event=routed_event, dispatcher=dispatcher)
    await routed_event.wait()

    assert routed_event.is_set()
    assert dispatcher.called_module == 2

@pytest.mark.asyncio
async def test_module_routing_no_matching_version():
    """ Test that routing to a module works. """
    dispatcher = Dispatcher()
    called_event = asyncio.Event()

    class TestModule(Module):
        DOC_URI = ''
        PROTOCOL = 'test_protocol'
        VERSION = '1.0'

        async def testing_type(self, msg, *args, **kwargs):
            kwargs['event'].set()

    mod = TestModule()
    dispatcher.route_module(mod)

    test_msg = Message({'@type': 'test_protocol/3.0/testing_type', 'test': 'test'})
    with pytest.raises(NoRegisteredRouteException):
        await dispatcher.dispatch(test_msg, event=called_event)

@pytest.mark.asyncio
async def test_module_routing_minor_version_different():
    """ Test that routing to a module works. """
    dispatcher = Dispatcher()
    called_event = asyncio.Event()

    class TestModule(Module):
        DOC_URI = ''
        PROTOCOL = 'test_protocol'
        VERSION = '1.4'

        async def testing_type(self, msg, *args, **kwargs):
            kwargs['event'].set()

    mod = TestModule()
    dispatcher.route_module(mod)

    test_msg = Message({'@type': 'test_protocol/1.0/testing_type', 'test': 'test'})
    await dispatcher.dispatch(test_msg, event=called_event)

    assert called_event.is_set()
