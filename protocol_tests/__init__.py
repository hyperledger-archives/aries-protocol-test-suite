""" Protocol Test Helpers """
import asyncio
import base64
import json
import struct  # TODO don't use struct
import time

from schema import Schema
from ariespython import crypto

from agent_core.message import Message
from agent_core.compat import create_task
from agent_core import Agent


class MessageSchema():  # pylint: disable=too-few-public-methods
    """ Wrap Schema for better message validation experience """
    def __init__(self, schema_dict):
        self._schema = Schema(schema_dict)

    def validate(self, msg: Message):
        """ Validate message, storing defaults inserted by validation. """
        msg.update(self._schema.validate(dict(msg)))
        return msg


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

    async def verify_signed_field(self, signed_field: Message):
        """ Unpack and verify a signed message field """
        data_bytes = base64.urlsafe_b64decode(signed_field['sig_data'])
        signature_bytes = base64.urlsafe_b64decode(
            signed_field['signature'].encode('ascii')
        )
        assert await crypto.crypto_verify(
            signed_field['signer'],
            data_bytes,
            signature_bytes
        ), "Signature verification failed on field {}!".format(signed_field)

        fieldjson = data_bytes[8:]
        return json.loads(fieldjson)


    async def sign_field(self, my_vk, field_value):
        timestamp_bytes = struct.pack(">Q", int(time.time()))

        sig_data_bytes = timestamp_bytes + json.dumps(field_value).encode('ascii')
        sig_data = base64.urlsafe_b64encode(sig_data_bytes).decode('ascii')

        signature_bytes = await crypto.crypto_sign(
            self.wallet_handle,
            my_vk,
            sig_data_bytes
        )
        signature = base64.urlsafe_b64encode(
            signature_bytes
        ).decode('ascii')

        return {
            "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec"
                     "/signature/1.0/ed25519Sha512_single",
            "signer": my_vk,
            "sig_data": sig_data,
            "signature": signature
        }

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
