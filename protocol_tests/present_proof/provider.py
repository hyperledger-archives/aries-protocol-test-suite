"""Present proof protocol family provider abstract base class."""

from abc import ABC


class PresentProofProvider(ABC):
    """Provider methods for the present-proof protocol family."""

    async def present_proof_v1_0_verifier_request_presentation(self, proof_req: dict) -> (str, any):
        """
        Create a presentation request.

        Parameters:
        proof_req (dict): a proof request.  (For now, this is the indy format)

        Returns:
        b64_request_attach (str) - A base-64 encoded presentation request attachment
        request_presentation (any) - An opaque presentation request to pass to present_proof_v1_0_verifier_verify_presentation 
        """
        raise NotImplementedError()

    async def present_proof_v1_0_prover_create_presentation(self, b64_request_attach) -> str:
        """
        Create a presentation request.

        Parameters:
        b64_request_attach (str): a base-64 encoded presentation request attachment

        Returns:
        b64_presentation_attach (str) - A base-64 encoded presentation attachment
        """

    async def present_proof_v1_0_verifier_verify_presentation(self, b64_presentation_attach: str, request_presentation: any) -> dict:
        """
        Verify a presentation.

        Parameters:
        b64_presentation_attach (str): a base64-encoded presentation attach
        request_presentation (any):  The 2nd value returned by present_proof_v1_0_verifier_request_presentation

        Returns:
        The attributes and predicates which were verified.
        """
        raise NotImplementedError()
