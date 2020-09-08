"""Connections protocol Backchannel ABC."""

from abc import ABC

from aries_staticagent import Message


class ConnectionsBackchannel(ABC):
    """Backchannel methods for Connections protocol."""
    async def connections_v1_0_inviter_start(self) -> str:
        """Start connections protocol from inviter role."""
        raise NotImplementedError()

    async def connections_v1_0_invitee_start(self, invite):
        """Start connections protocol from invitee role."""
        raise NotImplementedError()

    async def out_of_band_v1_0_use_invitation(self, invite):
        """Use an out of band invitation as created by the suite"""
        raise NotImplementedError()

    async def out_of_band_v1_0_create_invitation(self) -> str:
        """Have the agent under test create an out of band invitation"""
        raise NotImplementedError()
