import uuid

from aries_staticagent import Module, Message, route, crypto
from .. import get_provider
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

    PID = "{}{}/{}".format(DOC_URI, PROTOCOL, VERSION)
    ROLES = ["issuer", "holder"]

    def __init__(self):
        super().__init__()

    async def setup(self, config):
        self.provider = await get_provider(config)
        self.reset_events()

    def reset_events(self):
        self.events = []
        self.attrs = None

    def add_event(self, name):
        self.events.append(name)

    def assert_event(self, name):
        assert name in self.events

    @route("{}/{}".format(PID, "propose-credential"))
    async def propose_credential(self, msg, conn):
        """Handle a propose-credential message. """
        # TODO: implement
        raise NotImplementedError()

    async def create_cred_schema(self, name: str, version: str, attr_names: [str]) -> str:
        return await self.provider.issuer_create_credential_schema(name, version, attr_names)

    async def create_cred_def(self, schema_id: str) -> str:
        return await self.provider.issuer_create_credential_definition(schema_id)

    async def send_offer_credential(self, conn, cred_def_id: str, attrs: dict) -> str:
        """Send a credential offer to the agent under test."""
        (attach, self.offer) = await self.provider.issuer_create_credential_offer(cred_def_id)
        id = self.make_uuid()
        self.attrs = attrs
        preview_attrs = self.attrs_to_preview_attrs(attrs)
        msg = Message({
            "@id": id,
            "@type": self.type("offer-credential"),
            'comment': "Credential offer from aries-protocol-test-suite",
            'credential_preview': {
                '@type': 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/issue-credential/1.0/credential-preview',
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

    @route("{}/{}".format(PID, "offer-credential"))
    async def handle_offer_credential(self, msg, conn):
        """Handle an offer-credential message. """
        # Verify the format of the offer-credential message
        self.verify_msg('offer-credential', msg, conn, {
            Optional('comment'): str,
            'credential_preview': {
                '@type': 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/issue-credential/1.0/credential-preview',
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
        (request_attach, passback) = await self.provider.holder_create_credential_request(offer_attach)
        id = msg['@id']
        # Send the request-credential message and wait for the reply
        msg = await conn.send_and_await_reply_async({
            "@type": self.type("request-credential"),
            "~thread": {"thid": id},
            "comment": "some comment",
            "requests~attach": [
                {
                    "@id": id,
                    "mime-type": "application/json",
                    "data": {
                        "base64": request_attach
                    }
                },
            ]
        })
        self.verify_msg('issue-credential', msg, conn, {
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
        await self.provider.holder_store_credential(cred_attach, passback)
        self.add_event("credential_stored")

    @route("{}/{}".format(PID, "request-credential"))
    async def handle_request_credential(self, msg, conn):
        """Handle a request-credential message. """
        # Verify the request-credential message
        self.verify_msg('request-credential', msg, conn, {
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
        cred_attach = await self.provider.issuer_create_credential(self.offer, req_attach, self.attrs)
        id = msg['@id']
        # Send the issue-credential message and wait for the reply
        msg = await conn.send_async({
            "@type": self.type("issue-credential"),
            "~thread": {"thid": id},
            "comment": "some comment",
            "credentials~attach": [
                {
                    "@id": id,
                    "mime-type": "application/json",
                    "data": {
                        "base64": cred_attach
                    }
                },
            ]
        })
        self.add_event("issued")

    def verify_msg(self, typ, msg, conn, schema):
        assert msg.mtc.is_authcrypted()
        assert msg.mtc.sender == crypto.bytes_to_b58(conn.recipients[0])
        assert msg.mtc.recipient == conn.verkey_b58
        schema['@type'] = str(self.type(typ))
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
