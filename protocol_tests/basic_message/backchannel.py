"""Basic Message backchannel ABC."""

from abc import ABC
from aries_staticagent import StaticConnection


class BasicMessageBackchannel(ABC):
    """Backchannel methods for basicmessage protocol."""

    async def basic_message_v1_0_send_message(
            self, connection: StaticConnection, content: str
    ):
        """Send a message with content to the test suite."""
        raise NotImplementedError()

    async def basic_message_v1_0_get_message(
            self, connection: StaticConnection, msg_id: str
    ) -> str:
        """Report the contents of the last received basic message."""
        raise NotImplementedError()
