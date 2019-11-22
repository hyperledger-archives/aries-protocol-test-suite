"""Connections protocol Backchannel ABC."""

from abc import ABC

from aries_staticagent import Message


class ConnectionsBackchannel(ABC):
    """Backchannel methods for Connections protocol."""
    async def connections_v1_0_inviter_start(self) -> Message:
        """Start connections protocol from inviter role."""
        raise NotImplementedError()

    async def connections_v1_0_invitee_start(self, invite):
        """Start connections protocol from invitee role."""
        raise NotImplementedError()
