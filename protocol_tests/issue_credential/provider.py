"""Issue credential protocol family provider abstract base class."""

from abc import ABC


class IssueCredentialProvider(ABC):
    """Provider methods for the issue-credential protocol family."""

    async def issue_credential_v1_0_issuer_create_credential_schema(self, name: str, version: str, attr_names: [str]) -> str:
        """
        Create a credential schema.

        Parameters:
        name (str): The name of the credential schema.
        version (str): The version of the credential schema.
        attr_names (str): The attribute names of the credential schema.

        Returns:
        schema_id (str): The id of the credential schema.
        """
        raise NotImplementedError()

    async def issue_credential_v1_0_issuer_create_credential_definition(self, schema_id: str) -> str:
        """
        Create a credential definition.

        Parameters:
        schema_id (str): The id of the credential schema.

        Returns:
        cred_def_id (str): The id of the credential definition.
        """
        raise NotImplementedError()

    async def issue_credential_v1_0_issuer_create_credential_offer(self, cred_def_id: str) -> (str, any):
        """
        Create a credential offer.

        Parameters:
        cred_def_id (str): a credential definition id

        Returns:
        b64_offer_attach (str): a base64-encoded credential offer attach
        offer_passback (any): An object to pass back to the issuer_create_credential method
        """
        raise NotImplementedError()

    async def issue_credential_v1_0_issuer_create_credential(self, offer_passback: any, request_b64_attach: str, attrs: dict) -> str:
        """
        Create a credential.

        Parameters:
        offer_passback (any): An object returned from issuer_create_credential_offer.
        request_b64_attach (str): a base64-encoded credential request attachment.
        attrs (dict): The attribute names and values to include in the credential being issued.

        Returns:
        b64_attach (str): a base64-encoded credential attach
        """

    async def issue_credential_v1_0_holder_create_credential_request(self, b64_offer_attach: str) -> (str, any):
        """
        Create a credential request.

        Parameters:
        b64_offer_attach (str): a base64-encoded credential offer attach

        Returns:
        b64_request_attach (str): a base64-encoded credential request attach
        cred_req_passback (any): An object to pass back to the holder_store_credential method
        """
        raise NotImplementedError()

    async def issue_credential_v1_0_holder_store_credential(self, b64_credential_attach: str, store_credential_passback: dict) -> None:
        """
        Store a credential.

        Parameters:
        b64_credential_attach (str): a base64-encoded credential attach
        store_credential_passback (dict):  One of the values returned by holder_create_credential_request.

        Returns:
        None.
        """
        raise NotImplementedError()
