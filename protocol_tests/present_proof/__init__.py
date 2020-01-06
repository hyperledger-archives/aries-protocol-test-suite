import uuid

from ..issue_credential import Handler as IssueCredentialHandler
from aries_staticagent import Message, route, crypto
from reporting import meta
from voluptuous import Optional
from ..schema import MessageSchema


class Handler(IssueCredentialHandler):
    """
    Present proof protocol family message handler.
    """

    DOC_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/"
    PROTOCOL = "present-proof"
    VERSION = "1.0"
    ROLES = ["prover", "verifier"]
    PP_PID = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/present-proof/1.0"

    def __init__(self, provider):
        super().__init__(provider)

    async def setup_prover(self, schema_name: str, schema_version: str, attrs: dict) -> (str, str):
        # Create a schema and cred def
        schema_id = await self.create_cred_schema(schema_name, schema_version, list(attrs.keys()))
        cred_def_id = await self.create_cred_def(schema_id)
        # Store a credential with these attributes in the test suite wallet
        (offerAttach, offer) = await self.provider.issue_credential_v1_0_issuer_create_credential_offer(cred_def_id)
        (reqAttach, req) = await self.provider.issue_credential_v1_0_holder_create_credential_request(offerAttach)
        credAttach = await self.provider.issue_credential_v1_0_issuer_create_credential(offer, reqAttach, attrs)
        await self.provider.issue_credential_v1_0_holder_store_credential(credAttach, req)
        # return the schema and cred def ids for use by a verifier
        return (schema_id, cred_def_id)

    async def send_request_presentation(self, conn, proof_request: dict) -> str:
        """Send a request-presentation message to the agent under test."""
        (attach, self.proof_request) = await self.provider.present_proof_v1_0_verifier_request_presentation(proof_request)
        id = self.make_uuid()
        msg = Message({
            "@id": id,
            "@type": "{}/request-presentation".format(self.PP_PID),
            'comment': "Request presentation from aries-protocol-test-suite",
            'request_presentations~attach': [
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

    @route("{}/propose-credential".format(PP_PID))
    async def propose_presentation(self, msg, conn):
        """Handle a propose-presentation message. """
        # TODO: implement
        raise NotImplementedError()

    @route("{}/request-presentation".format(PP_PID))
    async def handle_request_presentation(self, msg, conn):
        """Handle an request-presentation message. """
        # Verify the format of the request-presentation message
        self._pp_verify_msg('request-presentation', msg, conn, {
            Optional('comment'): str,
            'request_presentations~attach': [
                {
                    '@id': str,
                    'mime-type': str,
                    'data': {
                        'base64': str
                    }
                }
            ]
        })
        req_attach = msg['request_presentations~attach'][0]['data']['base64']
        # Call the provider to create the credential request
        b64_proof = await self.provider.present_proof_v1_0_prover_create_presentation(req_attach)
        thid = self.thid(msg)
        # Send the request-credential message and wait for the reply
        msg = await conn.send_and_await_reply_async({
            "@type": "{}/presentation".format(self.PP_PID),
            "~thread": {"thid": thid},
            "comment": "This is my proof",
            "presentations~attach": [
                {
                    "@id": self.make_uuid(),
                    "mime-type": "application/json",
                    "data": {"base64": b64_proof}
                },
            ]
        })
        self.add_event("sent_proof")

    @route("{}/presentation".format(PP_PID))
    async def handle_presentation(self, msg, conn):
        """Handle a presentation message. """
        # Verify the presentation message
        self._pp_verify_msg('presentation', msg, conn, {
            Optional('comment'): str,
            'presentations~attach': [
                {
                    '@id': str,
                    'mime-type': str,
                    'data': {
                        'base64': str
                    }
                }
            ]
        })
        attach = msg['presentations~attach'][0]['data']['base64']
        # Call the provider to verify the proof
        attrs = await self.provider.present_proof_v1_0_verifier_verify_presentation(attach, self.proof_request)
        self.add_event("verified")

    def _pp_verify_msg(self, typ, msg, conn, schema):
        assert msg.mtc.is_authcrypted()
        assert msg.mtc.sender == crypto.bytes_to_b58(conn.recipients[0])
        assert msg.mtc.recipient == conn.verkey_b58
        schema['@type'] = "{}/{}".format(self.PP_PID, typ)
        schema['@id'] = str
        msg_schema = MessageSchema(schema)
        msg_schema(msg)
