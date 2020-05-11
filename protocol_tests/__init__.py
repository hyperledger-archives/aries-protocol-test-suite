""" Protocol Test Helpers """
from contextlib import contextmanager
from typing import Dict, Iterable, Union
import copy
import json
import uuid

from aries_staticagent import StaticConnection, Message, Module, crypto
from .backchannel import Backchannel
from .provider import Provider
from .schema import MessageSchema


def _recipients_from_packed_message(packed_message: bytes) -> Iterable[str]:
    """
    Inspect the header of the packed message and extract the recipient key.
    """
    try:
        wrapper = json.loads(packed_message)
    except Exception as err:
        raise ValueError("Invalid packed message") from err

    recips_json = crypto.b64_to_bytes(
        wrapper["protected"], urlsafe=True
    ).decode("ascii")
    try:
        recips_outer = json.loads(recips_json)
    except Exception as err:
        raise ValueError("Invalid packed message recipients") from err

    return map(
        lambda recip: recip['header']['kid'], recips_outer['recipients']
    )


class Suite:
    """
    Manage connections to agent under test.

    The Channel Manager itself is a static connection to the test subject
    allowing it to be used as the backchannel.
    """

    def __init__(self):
        self.frontchannels: Dict[str, StaticConnection] = {}
        self._backchannel = None
        self._provider = None
        self._reply = None

    @property
    def backchannel(self):
        """Return a reference to the backchannel (self)."""
        return self._backchannel

    def set_backchannel(self, backchannel: Backchannel):
        """Set backchannel."""
        self._backchannel = backchannel

    @property
    def provider(self):
        """Return a reference to the provider (self)."""
        return self._provider

    def set_provider(self, provider: Provider):
        """Set provider."""
        self._provider = provider

    @contextmanager
    def reply(self, handler):
        """Handle potential to reply."""
        self._reply = handler
        yield
        self._reply = None

    async def handle(self, packed_message: bytes):
        """
        Route an incoming message the appropriate frontchannels.
        """
        # TODO messages in plaintext cannot be routed
        handled = False
        for recipient in _recipients_from_packed_message(packed_message):
            if recipient in self.frontchannels:
                conn = self.frontchannels[recipient]
                with conn.reply_handler(self._reply):
                    await conn.handle(packed_message)
                    handled = True
        if not handled:
            raise RuntimeError('Inbound message was not handled')

    def new_frontchannel(
            self,
            *,
            their_vk: Union[bytes, str] = None,
            recipients: [Union[bytes, str]] = None,
            routing_keys: [Union[bytes, str]] = None,
            endpoint: str = None) -> StaticConnection:
        """
        Create a new connection and add it as a frontchannel.

        Args:
            fc_vk: The new frontchannel's verification key
            fc_sk: The new frontchannel's signing key
            their_vk: The test subject's verification key for this channel
            endpoint: The HTTP URL to the endpoint of the test subject.

        Returns:
            Returns the new front channel (static connection).
        """
        fc_keys = crypto.create_keypair()
        new_fc = StaticConnection(
            fc_keys,
            their_vk=their_vk,
            endpoint=endpoint,
            recipients=recipients,
            routing_keys=routing_keys
        )
        frontchannel_index = crypto.bytes_to_b58(new_fc.verkey)
        self.frontchannels[frontchannel_index] = new_fc
        return new_fc

    def add_frontchannel(self, connection: StaticConnection):
        """Add an already created connection as a frontchannel."""
        frontchannel_index = crypto.bytes_to_b58(connection.verkey)
        self.frontchannels[frontchannel_index] = connection

    def remove_frontchannel(self, connection: StaticConnection):
        """
        Remove a frontchannel.

        Args:
            fc_vk: The frontchannel's verification key
        """
        frontchannel_index = crypto.bytes_to_b58(connection.verkey)
        if frontchannel_index in self.frontchannels:
            del self.frontchannels[frontchannel_index]

    @contextmanager
    def temporary_channel(
            self,
            *,
            their_vk: Union[bytes, str] = None,
            recipients: [Union[bytes, str]] = None,
            routing_keys: [Union[bytes, str]] = None,
            endpoint: str = None) -> StaticConnection:
        """Use 'with' statement to use a temporary channel."""
        channel = self.new_frontchannel(
            their_vk=their_vk, endpoint=endpoint, recipients=recipients,
            routing_keys=routing_keys
        )
        yield channel
        self.remove_frontchannel(channel)


async def interrupt(generator, on: str = None):  # pylint: disable=invalid-name
    """Yield from protocol generator until yielded event matches on."""
    async for event, *data in generator:
        yield [event, *data]
        if on and event == on:
            return


async def yield_messages(generator):
    """Yield only the event and messages from generator."""
    async for event, *data in generator:
        yield [
            event,
            *list(filter(
                lambda item: isinstance(item, Message),
                data
            ))
        ]


async def collect_messages(generator):
    """Executor for protocol generators, returning all yielded messages."""
    messages = []
    async for _event, yielded in yield_messages(generator):
        messages.extend(map(
            # Must deep copy to get an accurate snapshot of the data
            # at the time it was yielded.
            copy.deepcopy,
            yielded
        ))
    return messages


async def event_message_map(generator):
    """
    Executor for protocol generators, returning map of event to the yielded
    messages for that event.
    """
    map_ = {}
    async for event, *messages in yield_messages(generator):
        map_[event] = list(map(
            # Must deep copy to get an accurate snapshot of the data
            # at the time it was yielded.
            copy.deepcopy,
            messages
        ))
    return map_


async def event_data_map(generator):
    """
    Executor for protocol generators, returning map of event to the yielded
    data for that event.
    """
    map_ = {}
    async for event, *data in generator:
        map_[event] = data
    return map_


async def last(generator):
    """Executor for protocol generators, returning the last yielded value."""
    last_data = None
    async for _event, *data in generator:
        last_data = data

    if len(last_data) == 1:
        return last_data[0]
    return last_data


async def run(generator):
    """
    Executor for protocol generators that simply runs the generator to
    completion.
    """
    async for _event, *_data in generator:
        pass


class BaseHandler(Module):
    """
    Base protocol handler to handle common tasks across all protocols such as thread decorators.
    """

    DOC_URI = "null_DOC_URI"
    PROTOCOL = "null_PROTOCOL"
    VERSION = "null_VERSION"

    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self.reset_thread_state()
        self.reset_events()

    def reset_thread_state(self):
        self.thid = None
        self.sender_order = -1
        self.received_orders = {}

    def reset_events(self):
        self.events = []
        self.attrs = None

    def add_event(self, name):
        self.events.append(name)

    def assert_event(self, name):
        assert name in self.events

    def verify_msg(self, typ, msg, conn, pid, schema):
        assert msg.mtc.is_authcrypted()
        assert msg.mtc.sender == crypto.bytes_to_b58(conn.recipients[0])
        assert msg.mtc.recipient == conn.verkey_b58
        schema['@type'] = "{}/{}".format(pid, typ)
        schema['@id'] = str
        msg_schema = MessageSchema(schema)
        msg_schema(msg)
        self._received_msg(msg, conn)

    async def send_async(self, msg, conn):
        id = self._prepare_to_send_msg(msg)
        await conn.send_async(msg)
        return id

    async def send_and_await_reply_async(self, msg, conn):
        self._prepare_to_send_msg(msg)
        return await conn.send_and_await_reply_async(msg)

    def _received_msg(self, msg, conn):
        msgId = msg["@id"]
        thid = msgId
        senderId = conn.verkey_b58
        senderOrder = 0
        receivedOrders = {}
        foundThid = False
        if "~thread" in msg:
            thread = msg["~thread"]
            if "thid" in thread:
                thid = thread["thid"]
                foundThid = True
            if "sender_order" in thread:
                senderOrder = thread["sender_order"]
            if "received_orders" in thread:
                receivedOrders = thread["received_orders"]
        if self.thid:
            if not foundThid:
                raise RuntimeError(
                    'Received message without a ~thread.thid field but is a continuation of thread "{}"; message: {}'.format(self.thid, msg))
            if not self.thid == thid:
                raise RuntimeError(
                    'Received message and was expecting ~thread.thid to be "{}" but found "{}"; message: {}'.format(self.thid, thid, msg))
        elif not msgId == thid:
            raise RuntimeError(
                'There is no existing thread but received a message in which "@id" and "~thread.thid" fields differ; message: {}'.format(msg))
        self.thid = thid

    def _prepare_to_send_msg(self, msg):
        if not "@id" in msg:
            msg["@id"] = self.make_uuid()
        id = msg["@id"]
        self.sender_order += 1
        if self.thid:
            msg["~thread"] = {
                "thid": self.thid,
                "sender_order": self.sender_order,
                "received_orders": self.received_orders
            }
        else:
            self.thid = id
        return id

    def make_uuid(self) -> str:
        return uuid.uuid4().urn[9:]
