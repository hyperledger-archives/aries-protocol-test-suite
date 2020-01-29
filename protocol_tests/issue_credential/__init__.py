import uuid

from aries_staticagent import Module, Message, route, crypto
from reporting import meta
from voluptuous import Optional
from ..schema import MessageSchema


class Handler(Module):
    """
    Issue credentials message handler.
    """

    DOC_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/"
    PROTOCOL = "issue-credential"
    VERSION = "1.0"
    ROLES = ["issuer", "holder"]
    IC_PID = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/issue-credential/1.0"

    def __init__(self, provider):
        super().__init__()
        self.provider = provider
        self.events = []

    def add_event(self, name):
        self.events.append(name)

    def assert_event(self, name):
        assert name in self.events

    def reset_events(self):
        self.events = []
        self.attrs = None

    @route("{}/propose-credential".format(IC_PID))
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
        id = self.make_uuid()
        self.attrs = attrs
        preview_attrs = self.attrs_to_preview_attrs(attrs)
        msg = Message({
            "@id": id,
            "@type": "{}/offer-credential".format(self.IC_PID),
            'comment': "Credential offer from aries-protocol-test-suite",
            'credential_preview': {
                '@type': '{}/credential-preview'.format(self.IC_PID),
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
        await conn.send_async(msg)
        return id

    @route("{}/offer-credential".format(IC_PID))
    async def handle_offer_credential(self, msg, conn):
        """Handle an offer-credential message. """
        # Verify the format of the offer-credential message
        self._ic_verify_msg('offer-credential', msg, conn, {
            Optional('comment'): str,
            'credential_preview': {
                '@type': '{}/credential-preview'.format(self.IC_PID),
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
        })
        offer_attach = msg['offers~attach'][0]['data']['base64']
        # Call the provider to create the credential request
        (request_attach, passback) = await self.provider.issue_credential_v1_0_holder_create_credential_request(offer_attach)
        thid = self.thid(msg)
        # Send the request-credential message and wait for the reply
        msg = await conn.send_and_await_reply_async({
            "@type": "{}/request-credential".format(self.IC_PID),
            "~thread": {"thid": thid},
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
        })
        self._ic_verify_msg('issue-credential', msg, conn, {
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
        })
        cred_attach = msg['credentials~attach'][0]['data']['base64']
        await self.provider.issue_credential_v1_0_holder_store_credential(cred_attach, passback)
        self.add_event("credential_stored")

    @route("{}/request-credential".format(IC_PID))
    async def handle_request_credential(self, msg, conn):
        """Handle a request-credential message. """
        # Verify the request-credential message
        self._ic_verify_msg('request-credential', msg, conn, {
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
        })
        req_attach = msg['requests~attach'][0]['data']['base64']
        # Call the provider to create the credential
        cred_attach = await self.provider.issue_credential_v1_0_issuer_create_credential(self.offer, req_attach, self.attrs)
        thid = self.thid(msg)
        # Send the issue-credential message and wait for the reply
        msg = await conn.send_async({
            "@type": "{}/issue-credential".format(self.IC_PID),
            "~thread": {"thid": thid},
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
        })
        self.add_event("issued")

    def _ic_verify_msg(self, typ, msg, conn, schema):
        assert msg.mtc.is_authcrypted()
        assert msg.mtc.sender == crypto.bytes_to_b58(conn.recipients[0])
        assert msg.mtc.recipient == conn.verkey_b58
        schema['@type'] = "{}/{}".format(self.IC_PID, typ)
        schema['@id'] = str
        msg_schema = MessageSchema(schema)
        msg_schema(msg)

    def make_uuid(self) -> str:
        return uuid.uuid4().urn[9:]

    def attrs_to_preview_attrs(self, attrs: dict) -> [dict]:
        result = []
        for name, value in attrs.items():
            result.append({
                "name": name,
                "value": value,
            })
        return result

    def thid(self, msg) -> str:
        if "~thread" in msg:
            return msg["~thread"]["thid"]
        return msg["@id"]

