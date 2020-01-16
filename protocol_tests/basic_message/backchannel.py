"""Basic Message backchannel ABC."""

from abc import ABC

class BasicMessageBackchannel(ABC):
    """Backchannel methods for basicmessage protocol."""

    async def basic_message_v1_0_send_message(self, content: str):
        """Send a message with content to the test suite."""
        raise NotImplementedError()

    async def basic_message_v1_0_last_received_message(self) -> str:
        """Report the contents of the last received basic message."""
        raise NotImplementedError()
