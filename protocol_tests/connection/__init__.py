"""Connection protocol messages and helpers."""

import json
import re
import uuid
import base64
from collections import namedtuple

from voluptuous import Schema, Optional, And, Extra, Match, Any, Exclusive
from aries_staticagent import Message, crypto, route
from ..schema import MessageSchema, AtLeastOne
from .. import BaseHandler, Suite


TheirInfo = namedtuple(
    'TheirInfo',
    'endpoint, recipients, routing_keys'
)


class KeyReferenceError(Exception):
    """Raised when no matching reference is found for a key."""


class NoSuitableService(Exception):
    """Raised when no DIDComm service is found."""


class DIDDoc(dict):
    """DIDDoc class for creating and verifying DID Docs."""
    # DIDDoc specification is very flexible: https://w3c-ccg.github.io
    # This particular schema covers Ed25519 keys. All key types here:
    # https://w3c-ccg.github.io/ld-cryptosuite-registry/
    EXPECTED_SERVICE_TYPE = 'IndyAgent'
    EXPECTED_SERVICE_SUFFIX = 'indy'

    PUBLIC_KEY_VALIDATOR = Schema({
        "id": str,
        "type": "Ed25519VerificationKey2018",
        "controller": str,
        "publicKeyBase58": str
    })

    VALIDATOR = Schema({
        "@context": "https://w3id.org/did/v1",
        "id": str,
        "publicKey": [PUBLIC_KEY_VALIDATOR],
        # This is not fully correct; see:
        # https://w3c.github.io/did-core/#authentication
        Optional("authentication"): [
            {
                "type": "Ed25519SignatureAuthentication2018",
                "publicKey": str
            },
            PUBLIC_KEY_VALIDATOR,
            str
        ],
        "service": And(
            # Service contains at least one agent service
            AtLeastOne(
                {
                    'id': Match('.*;{}$'.format(EXPECTED_SERVICE_SUFFIX)),
                    'type': EXPECTED_SERVICE_TYPE,
                    'priority': int,
                    'recipientKeys': [str],
                    Optional('routingKeys'): [str],
                    'serviceEndpoint': str
                },
                msg='DID Communication service missing'
            ),
            # And all services match DID Spec
            [
                {
                    "id": str,
                    "type": str,
                    "serviceEndpoint": str,
                    Extra: object  # Allow extra values
                }
            ],
        )
    })

    def validate(self):
        """Validate this DIDDoc."""
        self.update(DIDDoc.VALIDATOR(self))

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

    @classmethod
    def is_reference(cls, key: str):
        """Parse out a key reference if present; return the key otherwise."""
        return '#' in key

    def dereference_key(self, key: str) -> str:
        """Dereference a key from the publicKey array.

        If key is not a reference, simply return the key.
        """
        if not self.is_reference(key):
            return key

        key_reference = key
        found_key = next((
            public_key['publicKeyBase58']  # Get the first publicKeyBase58
            for public_key in self.get('publicKey', [])  # out of publicKey
            if key_reference == public_key['id']  # Where the reference matches the id
        ), None)  # or return None

        if not found_key:
            raise KeyReferenceError(
                'No key found for reference {}'.format(key)
            )

        return found_key

    def get_connection_info(self):
        """Extract connection information from DID Doc."""
        service = next(filter(
            lambda service: service['type'] == DIDDoc.EXPECTED_SERVICE_TYPE,
            self['service']
        ), None)
        if not service:
            raise NoSuitableService(
                'No Service with type {} found in DID Document'
                .format(DIDDoc.EXPECTED_SERVICE_TYPE)
            )

        return TheirInfo(
            # self['publicKey'][0]['controller'],  # did
            service['serviceEndpoint'],  # endpoint
            list(map(
                self.dereference_key,
                service.get('recipientKeys', [])
            )),
            list(map(
                self.dereference_key,
                service.get('routingKeys', [])
            )),
        )


class Invite(Message):
    """Invite Message"""
    TYPE = Suite.TYPE_PREFIX + 'connections/1.0/invitation'
    ALT_TYPE = Suite.ALT_TYPE_PREFIX + 'connections/1.0/invitation'
    DID_EXCHANGE_INVITE_TYPE = Suite.TYPE_PREFIX + 'didexchange/1.0/invitation'
    DID_EXCHANGE_INVITE_ALT_TYPE = Suite.ALT_TYPE_PREFIX + 'didexchange/1.0/invitation'
    VALIDATOR = MessageSchema({
        '@type': Any(TYPE, ALT_TYPE, DID_EXCHANGE_INVITE_TYPE, DID_EXCHANGE_INVITE_ALT_TYPE),
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
        b64_invite = crypto.bytes_to_b64(
            bytes(self.serialize(), 'utf-8'), urlsafe=True
        )

        return '{}?c_i={}'.format(self['serviceEndpoint'], b64_invite)

    @classmethod
    def parse_url(cls, invite: str):
        """Parse an invite url, returning a new message."""

        try:
            # If the invite is JSON already
            json.loads(invite)
        except ValueError:
            # If the invite is base64 url
            matches = re.match('(.+)?c_i=(.+)', invite)
            assert matches, 'Improperly formatted invite url!'
            invite = crypto.b64_to_bytes(
                matches.group(2), urlsafe=True
            ).decode('ascii')

        invite_msg = cls.deserialize(invite)

        Invite.validate(invite_msg)

        return invite_msg

    def get_connection_info(self):
        """Get connection information out of invite message."""
        return TheirInfo(
            # None, #did
            self['serviceEndpoint'],
            self['recipientKeys'],
            self.get('routingKeys'),
        )

class HandshakeReuseHandler(BaseHandler):
    """
    Handshake reuse message handler.
    """

    DOC_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/"
    DOC_URI_HTTP = "https://didcomm.org/"
    PROTOCOL = "out-of-band"
    VERSION = "1.0"

    PID = "{}{}/{}".format(DOC_URI_HTTP, PROTOCOL, VERSION)
    ALT_PID= "{}{}/{}".format(DOC_URI, PROTOCOL, VERSION)
    ROLES = ["sender", "receiver"]

    def __init__(self, invite_id):
        super().__init__()
        self.invite_id = invite_id

    @route("{}/handshake-reuse".format(PID))
    async def handle_handshake_reuse(self, msg, conn):
        """ Handle a handshake-reuse message and send the handshake-reuse-accepted message. """
        # Verify the message
        assert msg['~thread']['pthid'] == self.invite_id, 'The pthid of the reuse message should mirror the invitation ID'

        handshake_reuse_accepted = {
            '@type': '{}/{}'.format(HandshakeReuseHandler.PID, 'handshake-reuse-accepted'),
            '@id': str(uuid.uuid4()),
            "~thread": {
                "thid": msg['@id'],
                "pthid": msg['~thread']['pthid']
            }
        }
        await conn.send_async(handshake_reuse_accepted)


    async def send_handshake_reuse(self, conn):
        """ Send a handshake-reuse message and wait for the handshake-reuse-accepted message. """
        id = str(uuid.uuid4())
        handshake_reuse = {
            "@type": '{}/{}'.format(HandshakeReuseHandler.PID, 'handshake-reuse'),
            "@id": id,
            "~thread": {
                "thid": id,
                "pthid": self.invite_id
            }
        }
        handshake_reuse_accepted = await conn.send_and_await_reply_async(
            handshake_reuse,
            condition=lambda msg: msg.type == ('{}/{}'.format(HandshakeReuseHandler.PID, 'handshake-reuse-accepted') 
                                                or '{}/{}'.format(HandshakeReuseHandler.ALT_PID, 'handshake-reuse-accepted')),
            timeout=10,
        )

        assert handshake_reuse_accepted['~thread']['thid'] == id, \
            'The thread id of the reuse accepted message should mirror the reuse message ID'
        assert handshake_reuse_accepted['~thread']['pthid'] == self.invite_id, \
            'The pthid of the reuse accepted message should mirror the invitation ID'


class OutOfBandInvite(Message):
    """Invite with an out of band message"""
    ALT_TYPE = Suite.ALT_TYPE_PREFIX + 'out-of-band/1.0/invitation'
    TYPE = Suite.TYPE_PREFIX + 'out-of-band/1.0/invitation'


    DID_EXCHANGE_TYPES = [Suite.TYPE_PREFIX + 'didexchange/1.0', Suite.ALT_TYPE_PREFIX + 'didexchange/1.0']
    CONNECTION_TYPES = [Suite.TYPE_PREFIX + 'connections/1.0', Suite.ALT_TYPE_PREFIX + 'connections/1.0']

    SUPPORTED_PROTOCOLS = DID_EXCHANGE_TYPES + CONNECTION_TYPES

    VALIDATOR = MessageSchema({
        '@type': Any(TYPE, ALT_TYPE),
        '@id': str,
        Optional('label'): str,
        Optional('goal'): str,
        Optional('goal_code'): Any('issue-vc', 'request-proof', 'create-account', 'p2p-messaging'),
        Any('handshake_protocols', 'request~attach'): [
            Any(
                {
                    '@id': str,
                    'mime-type': str,
                    'data': Exclusive(
                        {'json': object},
                        {'base64': str},
                    )
                },
                str
            )
        ],
        # NOTE: For now we require atleast one service entry until 
        # there's a reliable standard for did-docs/service entries on a ledger
        'service': [
            {
                'id': "#inline",
                'type': 'did-communication',
                'recipientKeys': [str],
                'routingKeys': [],
                'serviceEndpoint': str
            },
            Optional(str)
        ]
    }, default_required=True)

    def validate(self):
        """Validate this invite."""
        OutOfBandInvite.VALIDATOR(self)

    @classmethod
    def make(cls, label, goal, goal_code, verkey, endpoint, publicDid=None, handshake_protocols=None, request_attach=None):
        """Create a new Invite message."""
        inv = cls({
            '@type': OutOfBandInvite.TYPE,
            '@id': str(uuid.uuid4()),
            'label': label,
            'goal': goal,
            'goal_code': goal_code,
            'service': [{
                'id': '#inline',
                'type': 'did-communication',
                'recipientKeys': [verkey],
                'serviceEndpoint': endpoint,
                'routingKeys': []
            }]
        })
        if publicDid:
            inv['service'].append(publicDid)
        if handshake_protocols:
            inv['handshake_protocols'] = handshake_protocols
        if request_attach:
            inv['request~attach'] = request_attach

        return inv

    def to_url(self):
        """Create invite url from message."""
        b64_invite = crypto.bytes_to_b64(
            bytes(self.serialize(), 'utf-8'), urlsafe=True
        )

        return '{}?oob={}'.format(self['service'][0]['serviceEndpoint'], b64_invite)

    @classmethod
    def parse_url(cls, invite: str):
        """Parse an invite url, returning a new message."""

        try:
            # If the invite is JSON already
            json.loads(invite)
        except ValueError:
            # If the invite is base64 url
            matches = re.match('(.+)?oob=(.+)', invite)
            assert matches, 'Improperly formatted invite url!'
            invite = crypto.b64_to_bytes(
                matches.group(2), urlsafe=True
            ).decode('ascii')

        invite_msg = cls.deserialize(invite)
        OutOfBandInvite.validate(invite_msg)

        return invite_msg


    def get_preferred_handshake_protocol(self):
        selected_protocols = list(filter(lambda protocol: (protocol for protocol in OutOfBandInvite.SUPPORTED_PROTOCOLS), self['handshake_protocols']))
        assert len(selected_protocols) > 0, 'No supported handshake protocols found.'

        return selected_protocols[0]

    def get_connection_info(self):
        """Get connection information out of invite message."""

        # NOTE: This will currently only find a full service entry object in the service block
        # Currently, public DIDs alone are not sufficient,
        # due to the fact the there's no concrete methodology to resolve a service block from a DID
        service_entry = list(filter(lambda entry: isinstance(entry, dict), self['service']))
        assert len(service_entry) > 0, 'You must include a full service entry in the invitation. Public DIDs alone are not supported yet'

        return TheirInfo(
            service_entry[0]['serviceEndpoint'],
            service_entry[0]['recipientKeys'],
            service_entry[0]['routingKeys'],
        )

class ConnectionRequest(Message):
    """Connection request Message"""

    ALT_TYPE = Suite.ALT_TYPE_PREFIX + 'connections/1.0/request'
    TYPE = Suite.TYPE_PREFIX + 'connections/1.0/request'
    VALIDATOR = MessageSchema({
        '@type': Any(TYPE, ALT_TYPE),
        '@id': str,
        'label': str,
        'connection': {
            'DID': str,
            'DIDDoc': DIDDoc.VALIDATOR
        }
    })

    def validate(self):
        """Validate this connection request Message."""
        ConnectionRequest.VALIDATOR(self)

    @classmethod
    def make(cls, label, my_did, my_vk, endpoint):
        """Create a connection request Message."""
        return cls({
            '@type': ConnectionRequest.TYPE,
            '@id': str(uuid.uuid4()),
            'label': label,
            'connection': {
                'DID': my_did,
                'DIDDoc': DIDDoc.make(my_did, my_vk, endpoint)
            }
        })

    def get_connection_info(self):
        """Get connection information out of the connection request Message."""
        return DIDDoc(self['connection']['DIDDoc']).get_connection_info()

class ConnectionResponse(Message):
    """Connection response Message"""
    ALT_TYPE = Suite.ALT_TYPE_PREFIX + 'connections/1.0/response'
    TYPE = Suite.TYPE_PREFIX + 'connections/1.0/response'
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
        ConnectionResponse.PRE_SIG_VERIFY_VALIDATOR(self)

    def validate_post_sig_verify(self):
        """Validate this response againts post sig verify schema."""
        ConnectionResponse.POST_SIG_VERIFY_VALIDATOR(self)

    @classmethod
    def make(cls, request_id, my_did, my_vk, endpoint):
        """Create new connection response Message."""
        return cls({
            '@type': ConnectionResponse.TYPE,
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
                        "priority": 0,
                        "recipientKeys": [my_vk],
                        "routingKeys": [],
                        "serviceEndpoint": endpoint,
                    }],
                }
            }
        })

    def sign(self, signer: str, secret: bytes):
        """Sign this connection response message."""
        self['connection~sig'] = crypto.sign_message_field(
            self['connection'],
            signer=signer,
            secret=secret
        )
        del self['connection']

    def verify_sig(self, expected_signer: str):
        """Verify signature on this connection response message."""
        signer, self['connection'] = \
            crypto.verify_signed_message_field(self['connection~sig'])
        assert signer == expected_signer, 'Unexpected signer'
        del self['connection~sig']

    def get_connection_info(self):
        """Get connection information out of connection request Message."""
        return DIDDoc(self['connection']['DIDDoc']).get_connection_info()


class DidExchangeRequest(Message):
    ALT_TYPE = Suite.ALT_TYPE_PREFIX + 'didexchange/1.0/request'
    TYPE = Suite.TYPE_PREFIX + 'didexchange/1.0/request'

    verified_did_doc = {}

    VALIDATOR = MessageSchema({
        '@type': Any(TYPE, ALT_TYPE),
        '@id': str,
        '~thread': {
            'thid': str,
            Optional('sender_order'): int
        },
        'label': str,
        'did': str,
        # NOTE: This field is technically optional and the DIDDoc can be resolved from a did.
        # However as of this time, there's no concrete and agreed-upon way to do this yet.
        'did_doc~attach': {
            'base64': str,
            'jws': {
                'header': {
                    'kid': str
                },
                'protected': str,
                'signature': str
            }
        }
    }, default_required=True)

    @classmethod
    def make(cls, my_did, my_vk, endpoint, sigkey, label):
        """Create new connection response Message."""

        did_doc =  {
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
                "priority": 0,
                "recipientKeys": [my_vk],
                "routingKeys": [],
                "serviceEndpoint": endpoint,
            }],
        }

        resp = cls({
            '@type': DidExchangeRequest.TYPE,
            '@id': str(uuid.uuid4()),
            'label': label,
            'did': my_did,
            'did_doc~attach': jws_sign(did_doc, my_vk, sigkey),
        })

        return resp

    def validate(self):
        """Validate this request against the schema."""
        DidExchangeRequest.VALIDATOR(self)
        jws_verify(self['did_doc~attach']['base64'], self['did_doc~attach']['jws'])

    def get_verified_did_doc(self):
        return eval(base64.b64decode(self['did_doc~attach']['base64']).decode())

    def get_connection_info(self):
        """Get connection information out of the did exchange request message."""
        return DIDDoc(self.get_verified_did_doc()).get_connection_info()

class DidExchangeResponse(Message):
    """Did exchange response Message"""
    ALT_TYPE = Suite.ALT_TYPE_PREFIX + 'didexchange/1.0/response'
    TYPE = Suite.TYPE_PREFIX + 'didexchange/1.0/response'

    verified_did_doc = {}

    VALIDATOR = MessageSchema({
        '@type': TYPE,
        '@id': str,
        '~thread': {
            'thid': str,
            Optional('sender_order'): int
        },
        'did': str,
        # NOTE: This field is technically optional and the DIDDoc can be resolved from a did.
        # However as of this time, there's no concrete and agreed-upon way to do this yet.
        'did_doc~attach': {
            'base64': str,
            'jws': {
                'header': {
                    'kid': str
                },
                'protected': str,
                'signature': str
            }
        }
    }, default_required=True)

    def get_verified_did_doc(self):
        return eval(base64.b64decode(self['did_doc~attach']['base64']).decode())

    def get_connection_info(self):
        """Get connection information out of the did exchange response message."""
        return DIDDoc(self.get_verified_did_doc()).get_connection_info()

    def validate(self):
        """Validate this response against the schema."""
        DidExchangeResponse.VALIDATOR(self)
        jws_verify(self['did_doc~attach']['base64'], self['did_doc~attach']['jws'])

    @classmethod
    def make(cls, request_id, my_did, my_vk, endpoint, sigkey):
        """Create new connection response Message."""

        did_doc =  {
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
                "priority": 0,
                "recipientKeys": [my_vk],
                "routingKeys": [],
                "serviceEndpoint": endpoint,
            }],
        }

        resp = cls({
            '@type': DidExchangeResponse.TYPE,
            '@id': str(uuid.uuid4()),
            '~thread': {
                'thid': request_id,
                'sender_order': 0
            },
            'did': my_did,
            'did_doc~attach': jws_sign(did_doc, my_vk, sigkey)
        })

        return resp
    

def jws_sign(did_doc, public_verkey, private_sigkey):
    """ Creates a JWS signature object. """

    # Encode the algorithm for the protected object in the signature.
    protected_obj = json.dumps({"alg":"EdDSA"})
    protected_str = base64.b64encode(protected_obj.encode()).decode()

    # Encode the DIDDoc for the base64 object in the signature.
    b64_did_doc = base64.b64encode(json.dumps(did_doc).encode()).decode()

    # Convert the encoded DIDDoc to bytes and sign it with our b58 private key
    to_sign_bytes = bytes(b64_did_doc, 'ascii')
    signature = crypto.sign_message(
        to_sign_bytes,
        secret=private_sigkey
    )

    # The output of crypto.sign_message is bytes so we need to convert it to b64
    signature_str = crypto.bytes_to_b64(signature, urlsafe=True)

    return {
        'base64': b64_did_doc,
        'jws': {
            'header': { 'kid': 'did:key:' + public_verkey },
            'protected': protected_str,
            'signature': signature_str,
        }
    }

def jws_verify(data, jws_signature):
    """ Verifies a JWS signature"""

    # Let's first check that the algorithm  object in the protected field is up to spec
    protected_obj = eval(base64.b64decode(jws_signature['protected']).decode())
    assert protected_obj == {"alg":"EdDSA"}, "Didn't find {'alg':'EdDSA'} in the proteccted object."

    # Let's convert the fields to bytes so we can verify
    public_verkey = crypto.b58_to_bytes(jws_signature['header']['kid'].split(':')[-1])
    # The bytes to verify follows the format (signature_bytes + data_bytes)
    to_verify_bytes = crypto.b64_to_bytes(jws_signature['signature'], urlsafe=True) + bytes(data,'ascii')

    # Verify the signature with the public key
    signature_verified = crypto.verify_signed_message(
        to_verify_bytes,
        public_verkey
    )

    assert signature_verified, "JWS signature validation failed."
    return True
