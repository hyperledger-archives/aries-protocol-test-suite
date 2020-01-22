"""Trustping protocol Backchannel ABC."""

from abc import ABC

from aries_staticagent import StaticConnection

class TrustPingBackchannel(ABC):
    """Backchannel methods for TrustPing protocol."""

    async def trust_ping_v1_0_send_ping(self, connection: StaticConnection):
        """Send a trustping to the specified connection."""
        raise NotImplementedError()
