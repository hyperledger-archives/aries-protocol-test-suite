import base64
import re
import uuid

from voluptuous import Schema, Optional
from aries_staticagent import Message, crypto
from ..schema import MessageSchema


class DIDDoc(dict):
    """DIDDoc class for creating and verifying DID Docs."""
    VALIDATOR = Schema({
        "@context": "https://w3id.org/did/v1",
        "id": str,
        "publicKey": [{
            "id": str,
            "type": "Ed25519VerificationKey2018",
            "controller": str,
            "publicKeyBase58": str
        }],
        "service": [{
            "id": str,
            "type": "IndyAgent",
            "recipientKeys": [str],
            Optional("routingKeys"): [str],
            "serviceEndpoint": str,
        }],
    })

    def validate(self):
        """Validate this DIDDoc."""
        DIDDoc.VALIDATOR(self)

    @classmethod
    def make(cls, my_did, my_vk, endpoint):
        """Make a DIDDoc dictionary."""
        return cls({
            "@context": "https://w3id.org/did/v1",
            "id": my_did,
            "publicKey": [{
                "id": my_did + "#keys-1",
                "type": "Ed25519VerificationKey2018",
                "controller": my_did,
                "publicKeyBase58": my_vk
            }],
            "service": [{
                "id": my_did + ";indy",
                "type": "IndyAgent",
                "recipientKeys": [my_vk],
                "routingKeys": [],
                "serviceEndpoint": endpoint,
            }],
        })

    def get_connection_info(self):
        """Extract connection informatin from DID Doc."""
        return (
            self['publicKey'][0]['controller'],  # did
            self['publicKey'][0]['publicKeyBase58'],  # vk
            self['service'][0]['serviceEndpoint']  # endpoint
        )


class Invite(Message):
    """Invite Message"""
    TYPE = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/invitation'
    VALIDATOR = MessageSchema({
        '@type': TYPE,
        '@id': str,
        'label': str,
        'recipientKeys': [str],
        Optional('routingKeys'): [str],
        'serviceEndpoint': str,
    })

    def validate(self):
        """Validate this invite."""
        Invite.VALIDATOR(self)

    @classmethod
    def make(cls, label, key, endpoint):
        """Create a new Invite message."""
        return cls({
            '@type': Invite.TYPE,
            'label': label,
            'recipientKeys': [key],
            'serviceEndpoint': endpoint,
            'routingKeys': []
        })

    def to_url(self):
        """Create invite url from message."""
        b64_invite = base64.urlsafe_b64encode(
            bytes(self.serialize(), 'utf-8')
        ).decode('ascii')

        return '{}?c_i={}'.format(self['serviceEndpoint'], b64_invite)

    @classmethod
    def parse_invite(cls, invite_url: str):
        """Parse an invite url, returning a new message."""
        matches = re.match('(.+)?c_i=(.+)', invite_url)
        assert matches, 'Improperly formatted invite url!'

        invite_msg = cls.deserialize(
            base64.urlsafe_b64decode(matches.group(2)).decode('ascii')
        )

        Invite.validate(invite_msg)

        return invite_msg

    def get_connection_info(self):
        """Get connection information out of invite message."""
        return (
            self['recipientKeys'][0],
            self['serviceEndpoint']
        )


class Request(Message):
    """Request Message"""

    TYPE = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/request'
    VALIDATOR = MessageSchema({
        '@type': TYPE,
        '@id': str,
        'label': str,
        'connection': {
            'DID': str,
            'DIDDoc': DIDDoc.VALIDATOR
        }
    })

    def validate(self):
        """Validate this Request Message."""
        Request.VALIDATOR(self)

    @classmethod
    def make(cls, label, my_did, my_vk, endpoint):
        """Create a Request Message."""
        return cls({
            '@type': Request.TYPE,
            '@id': str(uuid.uuid4()),
            'label': label,
            'connection': {
                'DID': my_did,
                'DIDDoc': DIDDoc.make(my_did, my_vk, endpoint)
            }
        })

    def get_connection_info(self):
        """Get connection information out of Request Message."""
        return DIDDoc(self['connection']['DIDDoc']).get_connection_info()


class Response(Message):
    """Response Message"""
    TYPE = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/response'
    PRE_SIG_VERIFY_VALIDATOR = MessageSchema({
        '@type': TYPE,
        '@id': str,
        '~thread': {
            'thid': str,
            Optional('sender_order'): int
        },
        'connection~sig': object
    })
    POST_SIG_VERIFY_VALIDATOR = MessageSchema({
        '@type': TYPE,
        '@id': str,
        '~thread': {
            'thid': str,
            Optional('sender_order'): int
        },
        'connection': {
            'DID': str,
            'DIDDoc': DIDDoc.VALIDATOR
        }
    })

    def validate_pre_sig_verify(self):
        """Validate this response against pre sig verify schema."""
        Response.PRE_SIG_VERIFY_VALIDATOR(self)

    def validate_post_sig_verify(self):
        """Validate this response againts post sig verify schema."""
        Response.POST_SIG_VERIFY_VALIDATOR(self)

    @classmethod
    def make(cls, request_id, my_did, my_vk, endpoint):
        """Create new Response Message."""
        return cls({
            '@type': Response.TYPE,
            '@id': str(uuid.uuid4()),
            '~thread': {
                'thid': request_id,
                'sender_order': 0
            },
            'connection': {
                'DID': my_did,
                'DIDDoc': {
                    "@context": "https://w3id.org/did/v1",
                    "id": my_did,
                    "publicKey": [{
                        "id": my_did + "#keys-1",
                        "type": "Ed25519VerificationKey2018",
                        "controller": my_did,
                        "publicKeyBase58": my_vk
                    }],
                    "service": [{
                        "id": my_did + ";indy",
                        "type": "IndyAgent",
                        "recipientKeys": [my_vk],
                        "routingKeys": [],
                        "serviceEndpoint": endpoint,
                    }],
                }
            }
        })

    def sign(self, signer: str, secret: bytes):
        """Sign this response message."""
        self['connection~sig'] = crypto.sign_message_field(
            self['connection'],
            signer=signer,
            secret=secret
        )
        del self['connection']

    def verify_sig(self, expected_signer: str):
        """Verify signature on this response message."""
        signer, self['connection'] = \
            crypto.verify_signed_message_field(self['connection~sig'])
        assert signer == expected_signer, 'Unexpected signer'
        del self['connection~sig']
