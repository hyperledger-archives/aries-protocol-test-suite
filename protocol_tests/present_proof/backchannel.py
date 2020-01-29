"""Present proof protocol backchannel ABC."""

from abc import ABC


class PresentProofBackchannel(ABC):
    """Backchannel methods for present-proof protocol."""

    async def present_proof_v1_0_verifier_send_proof_request(self, connection, proof_request) -> str:
        """
        The agent under test sends a proof request and returns the thread ID.
        """
        raise NotImplementedError()

    async def present_proof_v1_0_verifier_verify_proof(self, id: str) -> dict:
        """
        The agent under test verifies a proof and returns the attributes and their values.
        """
        raise NotImplementedError()
