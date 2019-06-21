""" Dispatcher """
import logging
from typing import Optional

from sortedcontainers import SortedSet

from .message import Message

class NoRegisteredRouteException(Exception):
    """ Thrown when message has no registered handlers """

class Dispatcher:
    """ One of the fundamental aspects of an agent responsible for dispatching messages to
        appropriate handlers.
    """
    def __init__(self):
        self.routes = {}
        self.modules = {} # Protocol identifier URI to module
        self.module_versions = {} # Doc URI + Protocol to list of Module Versions
        self.logger = logging.getLogger(__name__)

    def route(self, msg_type: str):
        """ Register route decorator. """
        def register_route_dec(func):
            self.logger.debug('Setting route for %s to %s', msg_type, func)
            self.routes[msg_type] = func
            return func

        return register_route_dec

    def route_module(self, mod):
        """ Register a module for routing.
            Modules are routed to based on protocol and version. Newer versions
            are favored over older versions. Major version number must match.
        """
        # Register module
        self.modules[type(mod).protocol_identifer_uri] = mod

        # Store version selection info
        version_info = type(mod).version_info
        qualified_protocol = type(mod).qualified_protocol
        if not qualified_protocol in self.module_versions:
            self.module_versions[qualified_protocol] = SortedSet()

        self.module_versions[qualified_protocol].add(version_info)

    def get_closest_module_for_msg(self, msg: Message):
        """ Find the closest appropriate module for a given message.
        """
        if not msg.qualified_protocol in self.module_versions:
            return None

        registered_version_set = self.module_versions[msg.qualified_protocol]
        for version in reversed(registered_version_set):
            if msg.version_info.major == version.major:
                return self.modules[msg.qualified_protocol + '/' + str(version)]
            if msg.version_info.major > version.major:
                break

        return None

    async def dispatch(self, msg: Message, *args, **kwargs):
        """ Dispatch message to handler. """
        if msg.type in self.routes:
            await self.routes[msg.type](msg, *args, **kwargs)
            return

        mod = self.get_closest_module_for_msg(msg)
        if mod:

            # If routes have been statically defined in a module, attempt to route based on type
            if hasattr(mod, 'routes') and \
                    msg.type in mod.routes:
                await mod.routes[msg.type](mod, msg, *args, **kwargs)
                return

            # If no routes defined in module, attempt to route based on method matching
            # the message type name
            if hasattr(mod, msg.short_type) and \
                    callable(getattr(mod, msg.short_type)):

                await getattr(mod, msg.short_type)(
                    msg,
                    *args,
                    **kwargs
                )
                return

        raise NoRegisteredRouteException
