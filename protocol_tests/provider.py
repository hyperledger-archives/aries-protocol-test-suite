"""Abstract base class for pluggable providers."""

from abc import ABC


class Provider(ABC):
    """
    Provider Abstract Base Class.

    A provider should implement each of the methods relevant to
    their provider and testing scenario.
    """

    async def setup(self, config, suite) -> None:
        """
        Prepare the provider for use in a clean start state.

        Parameters:
        config (dict): The configuration information.
        suite (Suite): The test suite.

        Returns:
        None.
        """
        raise NotImplementedError()

    async def reset(self):
        """
        Reset the provider to a blank state.
        """
        raise NotImplementedError()
