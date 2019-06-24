""" Transport Classes """

import asyncio
from enum import Flag, auto


class UnsupportedMethodException(Exception):
    """ When Connection type does not support a given method.
    """


class CannotOpenConnection(Exception):
    """ When a connection cannot be opened for the given relationship metadata.
    """


class ConnectionCapabilities(Flag):
    """ Define Connection type """
    UNDEFINED = 0
    RECV = auto()
    SEND = auto()
    DUPLEX = RECV | SEND


class Connection:
    """ Connection Base Class. Tracks the capabilities of the underlying
        transport method which can change depending on the connection state.

        These state transitions are codified in subclasses of Connection.
    """
    def __init__(self, flags=ConnectionCapabilities.UNDEFINED):
        self.flags = flags
        self.recv_lock = asyncio.Lock()
        self.done = asyncio.Event()

    async def recv(self):
        """ Receive bytes over connection """
        raise UnsupportedMethodException()

    async def send(self, msg: str):
        """ Send bytes over connection """
        raise UnsupportedMethodException()

    async def wait(self):
        """ Wait for connection to close """
        await self.done.wait()

    async def close(self):
        """ Close connection """
        self.done.set()

    def closed(self):
        """ Get connection closed state """
        return self.done.is_set()

    def can_send(self):
        """ Connection can send? """
        return self.flags & ConnectionCapabilities.SEND

    def can_recv(self):
        """ Connection can recv? """
        return self.flags & ConnectionCapabilities.RECV

    def is_duplex(self):
        """ Connection is duplex? """
        return self.flags & ConnectionCapabilities.DUPLEX

    def set_duplex(self):
        """ Change connection capabilities to duplex """
        self.flags = ConnectionCapabilities.DUPLEX

    def set_send(self):
        """ Change connection capabilities to send """
        self.flags = ConnectionCapabilities.SEND

    def set_recv(self):
        """ Change connection capabilities to recv """
        self.flags = ConnectionCapabilities.RECV


class InboundTransport:
    """ Inbound Transport base class """
    def __init__(self, connection_queue):
        self.connection_queue = connection_queue

    async def accept(self, **options):
        """ Accept connection loop. This method should construct a connection
            and place it on the connection queue.
        """

    async def shutdown(self):
        """ Terminate inbound transport """


class InboundConnection(Connection):
    """ Inbound Connection base class """


class OutboundConnection(Connection):
    """ Outbound Connection base class """
    @classmethod
    async def open(cls, **service):
        """ Open outbound connection """
        raise CannotOpenConnection()
