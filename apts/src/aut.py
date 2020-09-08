"""AUT (Agent Under Test) Backchannel Implementation."""

import aiohttp

from protocol_tests.backchannel import (
    Backchannel, SubjectConnectionInfo
)
from protocol_tests.connection.backchannel import ConnectionsBackchannel
from protocol_tests.discover_features.backchannel import DiscoverFeaturesBackchannel
from protocol_tests.issue_credential.backchannel import IssueCredentialBackchannel


class AUTBackchannel(Backchannel, ConnectionsBackchannel, DiscoverFeaturesBackchannel, IssueCredentialBackchannel):
    """
    Backchannel for communicating with the AUT (Agent Under Test)
    """
    async def setup(self, config, suite):
        """
        Here is where you perform any setup required to run the test suite to communicate with your AUT (Agent Under Test).
        This includes resetting the state of your AUT from any previous runs.
        """
        print("Setup: config: {}".format(config))
        raise Exception("TODO: implement")

    async def new_connection(self, offer, parameters=None):
        """
        The AUT is receiving a connection offer from APTS.
        The AUT must accept the offer and return a SubjectConnectionInfo object.
        """
        print("The AUT received a connection offer: {}".format(offer))
        # return SubjectConnectionInfo(did, recipients, routing_keys, endpoint)
        raise Exception("TODO: implement")

    async def connections_v1_0_inviter_start(self) -> str:
        """
        The AUT creates an invitation and returns the invitation URL.
        """
        raise Exception("TODO: implement")

    async def connections_v1_0_invitee_start(self, invitation_url):
        """
        The AUT accepts an invitation URL.
        """
        print("Invitation URL: {}".format(invitation_url))
        raise Exception("TODO: implement")

    async def out_of_band_v1_0_create_invitation(self) -> str:
        """
        The AUT creates an out of band invitation and returns the invitation URL.
        """
        raise Exception("TODO: implement")

    async def out_of_band_v1_0_use_invitation(self, invitation_url):
        """
        The AUT accepts an out of band invitation URL.
        """
        print("Invitation URL: {}".format(invitation_url))
        raise Exception("TODO: implement")

    async def discover_features_v1_0_requester_start(self, conn, query=".*", comment=""):
        """
        The AUT sends a discover features query over the 'conn' connection.
        Use either conn.did or conn.verkey_b58 to look up the connection in the AUT.
        """
        print("Discover features: conn={}",conn)
        raise Exception("TODO: implement")

    async def issue_credential_v1_0_issuer_create_cred_schema(self, name, version, attrNames) -> str:
        """
        The AUT creates a credential schema and returns the schema_id.
        """
        raise Exception("TODO: implement")

    async def issue_credential_v1_0_issuer_create_cred_def(self, schema_id: str) -> str:
        """
        The AUT creates a credential definition and returns the cred_def_id.
        """
        raise Exception("TODO: implement")

    async def issue_credential_v1_0_issuer_send_cred_offer(self, conn, cred_def_id, attrs) -> str:
        """
        The AUT sends a credential offer to APTS.
        Use either conn.did or conn.verkey_b58 to look up the connection in the AUT.
        """
        raise Exception("TODO: implement")

    async def issue_credential_v1_0_holder_accept_cred_offer(self, id: str):
        """
        The AUT as the holder accepts a credential offer from APTS.
        Use either conn.did or conn.verkey_b58 to look up the connection in the AUT.
        The 'id' parameter is the "@id" field of the "offer-credential" message.
        """
        raise Exception("TODO: implement")

    async def issue_credential_v1_0_holder_verify_cred_is_stored(self, id: str):
        """
        The AUT as the holder verifies that credential 'id' was stored successfully.
        Throw an exception if the credential was NOT stored successfully.
        """
        raise Exception("TODO: implement")

    async def present_proof_v1_0_verifier_send_proof_request(self, conn, proof_req) -> str:
        """
        The AUT as the verifier sends a proof request via a "request-presentation" message to APTS.
        """
        raise Exception("TODO: implement")

    async def present_proof_v1_0_prover_send_proof(self, id):
        """
        The AUT as the prover sends a proof via a "presentation" message to APTS.
        """
        raise Exception("TODO: implement")

    async def present_proof_v1_0_verifier_verify_proof(self, id: str) -> [dict]:
        """
        The AUT as the verifier verifies the proof sent to it via thread 'id'.
        """
        raise Exception("TODO: implement")

