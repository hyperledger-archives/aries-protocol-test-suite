"""Abstract Base Class for Pluggable Backchannels."""

from abc import ABC
from collections import namedtuple

ConnectionInfo = namedtuple(
    'ConnectionInfo', 'did, verkey, label, endpoint'
)

GenerationParameters = namedtuple(
    'GenerationParameters', 'seed, label'
)


class Backchannel(ABC):
    """
    Backchannel Abstract Base Class.

    Pluggable Backchannels should implement each of the methods relevant to
    their agent and testing scenario.
    """

    async def setup(self, config, suite):
        """
        Setup Backchannel for operation.

        Args:
            config (dict): Test Suite configuration.
        """
        raise NotImplementedError()

    async def reset(self):
        """
        Reset the agent to a blank state. May also require repopulating
        with any backchannel information.
        """
        raise NotImplementedError()

    async def new_connection(
            self,
            info: ConnectionInfo,
            parameters: GenerationParameters = None
    ) -> ConnectionInfo:
        """
        Setup a connection in the agent. This will result in a usable
        Frontchannel for tests.

        Args:
            info (ConnectionInfo): information for the test suite that the
            agent under test will store.

            parameters (GenerationParameters): optional values passed to the
            agent under test to generate their connection information.

        Returns:
            ConnectionInfo: returned connection info from test subject.
        """
        raise NotImplementedError()
