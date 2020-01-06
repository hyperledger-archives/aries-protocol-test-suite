import re

from aries_staticagent import Module, route, crypto
from reporting import meta
from voluptuous import Optional
from ..schema import MessageSchema

class Handler(Module):
    """
    Discover features module message handler.
    """

    DOC_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/"
    PROTOCOL = "discover-features"
    VERSION = "1.0"

    PID = "{}{}/{}".format(DOC_URI,PROTOCOL,VERSION)
    ROLES = ["requester","responder"]

    def __init__(self):
        super().__init__()
        self.query_message_count = 0
        # Initialize the protocols array which is sent in the disclose message after receiving a query message
        self.protocols = []
        self.add_protocol(Handler.PID, Handler.ROLES)

    def add_protocol(self, pid, roles):
        self.protocols.append({"pid": pid, "roles": roles})

    @route
    async def query(self, msg, conn):
       """Handle a discover-features query message. """
       # Verify the query message
       assert msg.mtc.is_authcrypted()
       assert msg.mtc.sender == crypto.bytes_to_b58(conn.recipients[0])
       assert msg.mtc.recipient == conn.verkey_b58
       msg_schema = MessageSchema({
           '@type': str(self.type('query')),
           '@id': str,
           'query': str,
           Optional('comment'): str,
       })
       msg_schema(msg)
       query = msg['query']
       # Find the protocols which match the query message
       matchingProtocols = []
       for proto in self.protocols:
          if re.match(query,proto['pid']):
              matchingProtocols.append(proto)
       # Send the disclose message
       await conn.send_async({
          "@type": self.type("disclose"),
          "protocols": matchingProtocols,
       })
       self.query_message_count = self.query_message_count + 1
