""" Agent Conductor

    Coordinates sending and receiving of messages from many connections.
"""
import asyncio
from contextlib import suppress
import logging

from ariespython import crypto, did, error

from .transport import CannotOpenConnection
from .transport.http import HTTPOutConnection
from .compat import create_task
from .message import Message, Noop
from .mtc import (
    MessageTrustContext,
    CONFIDENTIALITY,
    INTEGRITY,
    AUTHENTICATED_ORIGIN,
    DESERIALIZE_OK,
    NONREPUDIATION,
    LIMITED_SCOPE,
    # PFS?
)


LOGGER = logging.getLogger(__name__)


class Conductor:
    def __init__(self, wallet_handle, connection_queue=asyncio.Queue()):
        self.wallet_handle = wallet_handle
        self.connection_queue = connection_queue
        self.open_connections = {}
        self.pending_queues = {}
        self.message_queue = asyncio.Queue()
        self.async_tasks = asyncio.Queue()

    def schedule_task(self, coro, can_cancel=True):
        """ Schedule a task for execution. """
        task = create_task(coro)
        self.async_tasks.put_nowait((can_cancel, task))

    async def start(self):
        await self.accept()

    async def shutdown(self):
        """ Close down conductor, cleaning up scheduled tasks. """
        try:
            await asyncio.wait_for(self.message_queue.join(), 5)
        except asyncio.TimeoutError:
            LOGGER.warning('Could not join queue; cancelling processors.')

        for _, conn in self.open_connections.items():
            await conn.close()

        while not self.async_tasks.empty():
            can_cancel, task = self.async_tasks.get_nowait()
            if can_cancel:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            else:
                await task

    async def accept(self):
        """ Start accepting connections. """
        while True:
            conn = await self.connection_queue.get()
            LOGGER.debug('Accepted new connection')
            self.schedule_task(self.message_reader(conn))

    async def put_message(self, message):
        """ Put message to message queue """
        self.message_queue.put_nowait(message)

    async def message_reader(self, conn):
        """ Process messages from a connection. """
        await conn.recv_lock.acquire()
        async for msg_bytes in conn.recv():
            if not msg_bytes:
                continue
            LOGGER.debug('Received message bytes: %s', msg_bytes)

            msg = await self.unpack(msg_bytes)
            LOGGER.debug('Unpacked message: %s', msg)
            if not msg.mtc[CONFIDENTIALITY | INTEGRITY]:
                LOGGER.debug('Message is plaintext; skipping')
                # plaintext messages are ignored
                # TODO keeping connection open may be appropriate
                await conn.close()
                continue

            LOGGER.debug('Putting message to message queue')
            await self.put_message(msg)

            LOGGER.debug('Return Route processing')
            if not msg.mtc[AUTHENTICATED_ORIGIN]:
                LOGGER.debug('Message is anonymous; not return routing')
                # anonymous messages cannot be return routed
                await conn.close()
                continue

            if '~transport' not in msg:
                LOGGER.debug('No ~transport decorator; skipping')
                continue

            if 'pending_message_count' in msg['~transport'] \
                    and msg['~transport']['pending_message_count']:

                # TODO Should only expect remote queue if outbound connection.
                self.schedule_task(
                    self.poll_remote_queue(
                        msg.mtc.ad['sender_vk'],
                        msg.mtc.ad['sender_did'],
                        msg.mtc.ad['recip_vk']
                    ),
                    False
                )

            if 'return_route' not in msg['~transport']:
                if not conn.can_recv():
                    # Can't get any more messages and not marked as
                    # return_route so close
                    await conn.close()
                # Connection thinks there are more messages so don't close
                continue

            # Return route handling
            return_route = msg['~transport']['return_route']
            conn_id = msg.mtc.ad['sender_vk']

            if return_route == 'all':
                self.open_connections[conn_id] = conn
                self.schedule_task(
                    self.connection_cleanup(conn, conn_id),
                    False
                )
                if conn_id in self.pending_queues:
                    self.schedule_task(
                        self.send_pending(conn, self.pending_queues[conn_id]),
                        False
                    )

            elif return_route == 'none' and conn_id in self.open_connections:
                del self.open_connections[conn_id]

            elif return_route == 'thread':
                # TODO Implement thread return route
                pass

        conn.recv_lock.release()

    async def connection_cleanup(self, conn, conn_id):
        """ Connection cleanup task. """
        await conn.wait()
        if conn_id in self.open_connections:
            del self.open_connections[conn_id]

    async def recv(self):
        """ Pop msg off message queue and return """
        msg = await self.message_queue.get()
        return msg

    async def message_handled(self):
        """ Notify queue of message handling complete """
        self.message_queue.task_done()

    async def unpack(self, encryption_envelope: bytes):
        """ Perform processing to convert bytes off the wire to Message. """
        try:
            message_bytes, recip_vk, sender_vk = await crypto.unpack_message(
                self.wallet_handle,
                encryption_envelope
            )
            message = Message.deserialize(message_bytes)
            message.mtc = MessageTrustContext(
                # Since we got this far...
                CONFIDENTIALITY | INTEGRITY | DESERIALIZE_OK,  # Affirmed
                # Standard encryption envelope is repudiable
                NONREPUDIATION  # Denied
            )

            message.mtc.ad['recip_vk'] = recip_vk
            try:
                message.mtc.ad['recip_did'] = await did.did_for_key(
                    self.wallet_handle,
                    recip_vk
                )
            except error.WalletItemNotFound:
                message.mtc.ad['recip_did'] = None

            if sender_vk:
                message.mtc[AUTHENTICATED_ORIGIN] = True
                message.mtc.ad['sender_vk'] = sender_vk
                try:
                    message.mtc.ad['sender_did'] = await did.did_for_key(
                        self.wallet_handle,
                        sender_vk
                    )
                except error.WalletItemNotFound:
                    message.mtc.ad['sender_did'] = None
            else:
                message.mtc[AUTHENTICATED_ORIGIN] = False
                message.mtc.ad['sender_vk'] = None
                message.mtc.ad['sender_did'] = None

            return message
        except error.CommonInvalidStructure:
            # Message wasn't actually encrypted, let's try just deserializing
            pass

        message = Message.deserialize(encryption_envelope)
        message.mtc = MessageTrustContext(
            DESERIALIZE_OK,
            CONFIDENTIALITY | INTEGRITY | NONREPUDIATION |
            AUTHENTICATED_ORIGIN | LIMITED_SCOPE  # | PFS?
        )

        return message

    async def send(self, msg, to_key, **kwargs):
        """ Send message to another agent.
        """
        from_key = kwargs.get('from_key', None)  # default = None
        to_did = kwargs.get('to_did', None)
        service = kwargs.get('service', None)

        if service is None:
            if not to_did:
                metadata = await did.get_key_metadata(
                    self.wallet_handle,
                    to_key
                )
                service = metadata['service']
            else:
                metadata = await did.get_did_metadata(
                    self.wallet_handle,
                    to_did
                )
                service = metadata['service']

        if to_key not in self.open_connections \
                or self.open_connections[to_key].closed():
            try:
                # TODO: Connection type based on service block
                conn = await HTTPOutConnection.open(**service)
            except CannotOpenConnection:
                if to_key not in self.pending_queues:
                    self.pending_queues[to_key] = asyncio.Queue()
                self.pending_queues[to_key].put_nowait((msg, to_key, from_key))
                return
        else:
            conn = self.open_connections[to_key]

        wire_msg = await crypto.pack_message(
            self.wallet_handle,
            msg.serialize(),
            [to_key],
            from_key
        )

        await conn.send(wire_msg)

        if not conn.closed() \
                and conn.can_recv() \
                and not conn.recv_lock.locked():
            self.schedule_task(self.message_reader(conn))

    async def send_pending(self, conn, queue):
        """ Send messages off of pending queue. """
        # TODO: pending queue and processing of another message calls send,
        # what happens first?
        # TODO: Send lock?
        while conn.can_send() and not queue.empty():
            msg, to_key, from_key = queue.get_nowait()

            if '~transport' not in msg:
                msg['~transport'] = {}

            msg['~transport']['pending_message_count'] = queue.qsize()

            wire_msg = await crypto.pack_message(
                self.wallet_handle,
                msg.serialize(),
                [to_key],
                from_key
            )

            await conn.send(wire_msg)

    async def poll_remote_queue(self, to_key, to_did, from_key):
        """ Retrieve messages on a remote queue by sending a noop. """
        noop = Noop(return_route=True)
        await self.send(noop, to_key, to_did=to_did, from_key=from_key)
