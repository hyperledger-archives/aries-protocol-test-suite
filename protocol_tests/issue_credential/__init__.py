from aries_staticagent import Module, Message, route, crypto
from reporting import meta
from voluptuous import Optional
from .. import BaseHandler


class Handler(BaseHandler):
    """
    Issue credentials message handler.
    """

    DOC_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/"
    DOC_URI_HTTP = "https://didcomm.org/"
    PROTOCOL = "issue-credential"
    VERSION = "1.0"
    ROLES = ["issuer", "holder"]

    PID = "{}{}/{}".format(DOC_URI_HTTP, PROTOCOL, VERSION)
    ALT_PID = "{}{}/{}".format(DOC_URI, PROTOCOL, VERSION)

    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    @route("{}/propose-credential".format(PID))
    async def propose_credential(self, msg, conn):
        """Handle a propose-credential message. """
        # TODO: implement
        raise NotImplementedError()

    async def create_cred_schema(self, name: str, version: str, attr_names: [str]) -> str:
        return await self.provider.issue_credential_v1_0_issuer_create_credential_schema(name, version, attr_names)

    async def create_cred_def(self, schema_id: str) -> str:
        return await self.provider.issue_credential_v1_0_issuer_create_credential_definition(schema_id)

    async def send_offer_credential(self, conn, cred_def_id: str, attrs: dict) -> str:
        """Send a credential offer to the agent under test."""
        (attach, self.offer) = await self.provider.issue_credential_v1_0_issuer_create_credential_offer(cred_def_id)
        self.attrs = attrs
        preview_attrs = self.attrs_to_preview_attrs(attrs)
        id = self.make_uuid()
        msg = Message({
            "@type": "{}/offer-credential".format(Handler.PID),
            'comment': "Credential offer from aries-protocol-test-suite",
            'credential_preview': {
                '@type': '{}/credential-preview'.format(Handler.PID),
                'attributes': preview_attrs,
            },
            'offers~attach': [
                {
                    '@id': id,
                    'mime-type': "application/json",
                    'data': {
                        'base64': attach
                    }
                }
            ]
        })
        return await self.send_async(msg, conn)

    @route("{}/offer-credential".format(PID))
    async def handle_offer_credential(self, msg, conn):
        """Handle an offer-credential message. """
        # Verify the format of the offer-credential message
        self.verify_msg('offer-credential', msg, conn, Handler.PID, {
            Optional('comment'): str,
            'credential_preview': {
                '@type': '{}/credential-preview'.format(Handler.PID),
                'attributes': [
                    {
                        "name": str,
                        "mime-type": str,
                        "value": str,
                    },
                ],
            },
            'offers~attach': [
                {
                    '@id': str,
                    'mime-type': str,
                    'data': {
                        'base64': str
                    }
                }
            ]
        }, alt_pid=Handler.ALT_PID)
        offer_attach = msg['offers~attach'][0]['data']['base64']
        # Call the provider to create the credential request
        (request_attach, passback) = await self.provider.issue_credential_v1_0_holder_create_credential_request(offer_attach)
        # Send the request-credential message and wait for the reply
        req = {
            "@type": "{}/request-credential".format(self.PID),
            "comment": "some comment",
            "requests~attach": [
                {
                    "@id": self.make_uuid(),
                    "mime-type": "application/json",
                    "data": {
                        "base64": request_attach
                    }
                },
            ]
        }
        reply = await self.send_and_await_reply_async(req, conn)
        self.verify_msg('issue-credential', reply, conn, self.PID, {
            Optional('comment'): str,
            'credentials~attach': [
                {
                    '@id': str,
                    'mime-type': str,
                    'data': {
                        'base64': str
                    }
                }
            ]
        }, alt_pid=self.ALT_PID)
        cred_attach = reply['credentials~attach'][0]['data']['base64']
        await self.provider.issue_credential_v1_0_holder_store_credential(cred_attach, passback)
        self.add_event("credential_stored")

    @route("{}/request-credential".format(PID))
    async def handle_request_credential(self, msg, conn):
        """Handle a request-credential message. """
        # Verify the request-credential message
        self.verify_msg('request-credential', msg, conn, self.PID, {
            Optional('comment'): str,
            'requests~attach': [
                {
                    '@id': str,
                    'mime-type': str,
                    'data': {
                        'base64': str
                    }
                }
            ]
        }, alt_pid=self.ALT_PID)
        req_attach = msg['requests~attach'][0]['data']['base64']
        # Call the provider to create the credential
        cred_attach = await self.provider.issue_credential_v1_0_issuer_create_credential(self.offer, req_attach, self.attrs)
        # Send the issue-credential message and wait for the reply
        msg = {
            "@type": "{}/issue-credential".format(self.PID),
            "comment": "some comment",
            "credentials~attach": [
                {
                    "@id": self.make_uuid(),
                    "mime-type": "application/json",
                    "data": {
                        "base64": cred_attach
                    }
                },
            ]
        }
        await self.send_async(msg, conn)
        self.add_event("issued")

    @route("{}/ack".format(PID))
    async def handle_ack(self, msg, conn):
        """Handle an ack message. """
        # Verify the ack message
        self.verify_msg('ack', msg, conn, self.PID, {}, alt_pid=self.ALT_PID)
        self.add_event("ack")

    def attrs_to_preview_attrs(self, attrs: dict) -> [dict]:
        result = []
        for name, value in attrs.items():
            result.append({
                "name": name,
                "value": value,
            })
        return result
