""" Agent Conductor

    Coordinates sending and receiving of messages from many connections.
"""
import asyncio
from contextlib import suppress
import logging

#from ariespython import crypto

from .compat import create_task
from .message import Message
from .message import Noop


LOGGER = logging.getLogger(__name__)


class UnknownTransportException(Exception):
    """ Thrown on unknown transport in config. """


class Conductor:
    def __init__(self, wallet_handle):
        self.wallet_handle = wallet_handle
        self.inbound_transport = None
        self.outbound_transport = None
        self.transport_options = {}
        self.connection_queue = asyncio.Queue()
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
            if not msg.context:
                # plaintext messages are ignored
                # TODO keeping connection open may be appropriate
                await conn.close()
                continue

            await self.put_message(msg)

            if not msg.context['from_key']:
                # anonymous messages cannot be return routed
                await conn.close()
                continue

            if '~transport' not in msg:
                continue

            if 'pending_message_count' in msg['~transport'] \
                    and msg['~transport']['pending_message_count']:

                # TODO Should only expect remote queue if outbound connection.
                self.schedule_task(
                    self.poll_remote_queue(
                        msg.context['from_key'],
                        msg.context['from_did'],
                        msg.context['to_key']
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
            conn_id = msg.context['from_key']

            if return_route == 'all':
                self.open_connections[conn_id] = conn
                self.schedule_task(
                    self.connection_cleanup(conn, msg.context['from_key']),
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

    async def unpack(self, message: bytes):
        """ Perform processing to convert bytes off the wire to Message. """
        return await utils.unpack(self.wallet_handle, message)

    async def send(self, msg, to_key, **kwargs):
        """ Send message to another agent.
        """
        # TODO: Change to accepting/looking up a service block from DID or key
        # metadata
        from_key = kwargs.get('from_key', None)  # default = None
        to_did = kwargs.get('to_did', None)
        meta = kwargs.get('meta', None)

        if meta is None:
            if not to_did:
                meta = await utils.get_key_metadata(self.wallet_handle, to_key)
            else:
                meta = await utils.get_did_metadata(self.wallet_handle, to_did)

        if to_key not in self.open_connections \
                or self.open_connections[to_key].closed():
            try:
                conn = await self.outbound_transport.open(**meta)
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
        # TODO pending queue and processing of another message calls send,
        # what happens first?
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
