""" Protocol Test Helpers """
import asyncio

from schema import Schema

from agent_core.message import Message
from agent_core.compat import create_task
from agent_core import Agent


class MessageSchema():  # pylint: disable=too-few-public-methods
    """ Wrap Schema for better message validation experience """
    def __init__(self, schema_dict):
        self._schema = Schema(schema_dict)

    def validate(self, msg: Message):
        """ Validate message, storing defaults inserted by validation. """
        msg.data = self._schema.validate(msg.data)
        return msg.data


class ExpectMessageTimeout(Exception):
    """ Raised when timed out on expect_message """


class TestingAgent(Agent):
    """ Agent with helpers for testing """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tasks = []

    async def start(self):
        """ Unwrap one layer of asynchrony by not starting the main loop,
            allowing tests to drive the message processing behavior.
        """
        self.logger.info('Starting Agent...')
        transport_tasks = []
        for transport in self.transports:
            self.logger.debug(
                'Starting transport %s',
                type(transport).__name__
            )
            transport_tasks.append(
                create_task(transport.accept())
            )
        self.logger.debug('Starting conductor')
        conductor_task = create_task(self.conductor.start())
        self.tasks = [*transport_tasks, conductor_task]
        self.main_task = asyncio.gather(
            *transport_tasks,
            conductor_task
        )
        await self.main_task

    async def expect_message(self, msg_type: str, timeout: int):
        """ Expect a message of a given type, ignoring other types,
            breaking after timeout
        """
        try:
            return await asyncio.wait_for(
                self._expect_message_loop(msg_type),
                timeout
            )
        except asyncio.TimeoutError:
            self.ok()
            raise ExpectMessageTimeout(
                'Timed out while waiting for message of type %s' % msg_type
            )

    async def _expect_message_loop(self, msg_type: str):
        while True:
            msg = await self.conductor.recv()
            await self.conductor.message_handled()
            if msg.type != msg_type:
                continue

            return msg

    def ok(self):
        """ Make sure the main task has not raised any exceptions in the
            background.
        """
        self.conductor.cleanup_tasks()
        for task in self.tasks:
            try:
                task.result()
            except asyncio.InvalidStateError:
                # Task is still running so it's alive
                pass
        return True
