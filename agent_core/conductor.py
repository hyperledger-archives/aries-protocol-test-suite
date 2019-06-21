import asyncio
from contextlib import suppress
import logging

from indy import crypto

from compat import create_task
from config import Config
from hooks import self_hook_point
from messages.message import Message
from messages.noop import Noop
import indy_sdk_utils as utils
from transport.connection import CannotOpenConnection
import transport.inbound.standard_in as StdIn
import transport.outbound.standard_out as StdOut
import transport.inbound.http as HttpIn
import transport.outbound.http as HttpOut
import transport.inbound.websocket as WebSocketIn

class UnknownTransportException(Exception): pass

class Conductor:
    hooks = {}
    def __init__(self):
        self.logger = None
        self.wallet_handle = None
        self.inbound_transport = None
        self.outbound_transport = None
        self.transport_options = {}
        self.connection_queue = asyncio.Queue()
        self.open_connections = {}
        self.pending_queues = {}
        self.message_queue = asyncio.Queue()
        self.hooks = Conductor.hooks.copy()
        self.async_tasks = asyncio.Queue()

    @staticmethod
    def in_transport_str_to_mod(transport_str):
        return {
            'stdin': StdIn,
            'http': HttpIn,
            'ws': WebSocketIn
        }[transport_str]

    @staticmethod
    def out_transport_str_to_mod(transport_str):
        return {
            'stdout': StdOut,
            'http': HttpOut,
        }[transport_str]

    @classmethod
    def from_wallet_handle_config(cls, wallet_handle, config: Config):
        conductor = cls()
        conductor.wallet_handle = wallet_handle
        conductor.transport_options = config.transport_options()
        conductor.logger = logging.getLogger(__name__)
        conductor.logger.setLevel(config.log_level)

        try:
            conductor.inbound_transport = \
                    Conductor.in_transport_str_to_mod(config.inbound_transport)
            conductor.outbound_transport = \
                    Conductor.out_transport_str_to_mod(config.outbound_transport)
        except KeyError:
            raise UnknownTransportException

        return conductor

    def schedule_task(self, coro, can_cancel=True):
        task = create_task(coro)
        self.async_tasks.put_nowait((can_cancel, task))

    async def start(self):
        inbound_task = create_task(
            self.inbound_transport.accept(
                self.connection_queue,
                **self.transport_options
            )
        )
        accept_task = create_task(self.accept())
        await asyncio.gather(inbound_task, accept_task)

    async def shutdown(self):
        try:
            await asyncio.wait_for(self.message_queue.join(), 5)
        except asyncio.TimeoutError:
            self.logger.warning('Could not join queue; cancelling processors.')

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
        while True:
            self.logger.debug('Accepted new connection')
            conn = await self.connection_queue.get()
            self.schedule_task(self.message_reader(conn))

    async def put_message(self, message):
        self.message_queue.put_nowait(message)

    async def message_reader(self, conn):
        await conn.recv_lock.acquire()
        async for msg_bytes in conn.recv():
            if not msg_bytes:
                continue
            self.logger.debug('Received message bytes: %s', msg_bytes)

            msg = await self.unpack(msg_bytes)
            if not msg.context:
                # plaintext messages are ignored
                await conn.close() # TODO keeping connection open may be appropriate
                continue

            await self.put_message(msg)

            if not msg.context['from_key']:
                # anonymous messages cannot be return routed
                await conn.close()
                continue

            if not '~transport' in msg:
                continue

            if 'pending_message_count' in msg['~transport'] \
                    and msg['~transport']['pending_message_count']:

                # TODO Should only expect remote queue if outbound connection.
                self.schedule_task(
                    self.pump_remote_queue(
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
                self.schedule_task(self.connection_cleanup(conn, msg.context['from_key']), False)
                if conn_id in self.pending_queues:
                    self.schedule_task(self.send_pending(conn, self.pending_queues[conn_id]), False)

            elif return_route == 'none' and conn_id in self.open_connections:
                del self.open_connections[conn_id]

            elif return_route == 'thread':
                # TODO Implement thread return route
                pass

        conn.recv_lock.release()

    async def connection_cleanup(self, conn, conn_id):
        await conn.wait()
        if conn_id in self.open_connections:
            del self.open_connections[conn_id]

    async def recv(self):
        msg = await self.message_queue.get()
        return msg

    async def message_handled(self):
        self.message_queue.task_done()

    @self_hook_point
    async def unpack(self, message: bytes):
        """ Perform processing to convert bytes off the wire to Message. """
        return await utils.unpack(self.wallet_handle, message)

    async def send(self, msg, to_key, **kwargs):
        from_key = kwargs.get('from_key', None) #default = None
        to_did = kwargs.get('to_did', None)
        meta = kwargs.get('meta', None)

        if meta == None:
            if not to_did:
                meta = await utils.get_key_metadata(self.wallet_handle, to_key)
            else:
                meta = await utils.get_did_metadata(self.wallet_handle, to_did)

        if to_key not in self.open_connections or self.open_connections[to_key].closed():
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

        if not conn.closed() and conn.can_recv() and not conn.recv_lock.locked():
            self.schedule_task(self.message_reader(conn))

    async def send_pending(self, conn, queue):
        # TODO pending queue and processing of another message calls send, what happens first?
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

    async def pump_remote_queue(self, to_key, to_did, from_key):
        noop = Noop(return_route=True)
        await self.send(noop, to_key, to_did=to_did, from_key=from_key)
