"""Discover features protocol backchannel ABC."""

from abc import ABC

from aries_staticagent import Message

class DiscoverFeaturesBackchannel(ABC):
    """Backchannel methods for discover-features protocol."""

    async def discover_features_v1_0_requester_start(self, verkey, query=".*", comment=None):
        """Start discover-features protocol from the requester role."""
        raise NotImplementedError()

