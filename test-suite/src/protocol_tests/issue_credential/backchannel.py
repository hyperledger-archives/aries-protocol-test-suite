"""Issue credential protocol backchannel ABC."""

from abc import ABC


class IssueCredentialBackchannel(ABC):
    """Backchannel methods for issue-credential protocol."""

    async def issue_credential_v1_0_ledger_init(self, config):
        """Prepare the agent under test to interact with the ledger specified by config"""
        raise NotImplementedError()

    async def issue_credential_v1_0_issuer_create_cred_schema(self, name, version, attrNames) -> str:
        """
        The agent under test creates a credential schema and returns the schema id.
        """
        raise NotImplementedError()

    async def issue_credential_v1_0_issuer_create_cred_def(self, schema_id: str) -> str:
        """
        The agent under test creates a credential definition and returns the cred def id.
        """
        raise NotImplementedError()

    async def issue_credential_v1_0_issuer_send_cred_offer(self, conn, cred_def, attrs) -> str:
        """The issuer sends a credential offer and returns the message id."""
        raise NotImplementedError()

    async def issue_credential_v1_0_holder_accept_cred_offer(self, id: str):
        """The holder accepts a credential offer."""
        raise NotImplementedError()

    async def issue_credential_v1_0_holder_verify_cred_is_stored(self, id: str):
        """The holder checks to make sure that the credential is stored."""
        raise NotImplementedError()
