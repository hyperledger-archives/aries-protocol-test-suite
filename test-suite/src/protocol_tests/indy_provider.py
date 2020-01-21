import json
import aiohttp
import base64
import time
import sys
import hashlib

from .aries_provider import AriesProvider
from indy import anoncreds, wallet, ledger, pool, crypto, did, pairwise, non_secrets, ledger, wallet, blob_storage
from indy.error import IndyError, ErrorCode


class IndyProvider(AriesProvider):
    """
    The indy provider isolates all indy-specific code required by the test suite.
    """

    def __init__(self, config):
        self.ledger_name = config.get('ledger_name', 'arie-test-ledger')
        self.ledger_url = config.get(
            'ledger_url', 'http://ledger-indy:8000/sandbox/pool_transactions_genesis')
        id = config.get('name', 'test')
        key = config.get('pass', 'testpw')
        seed = config.get('seed', '000000000000000000000000Steward1')
        self.cfg = json.dumps({'id': id})
        self.creds = json.dumps({'key': key})
        self.seed = json.dumps({'seed': seed})

    async def setup(self):
        try:
            await wallet.delete_wallet(self.cfg, self.creds)
        except Exception as e:
            pass
        await wallet.create_wallet(self.cfg, self.creds)
        self.wallet = await wallet.open_wallet(self.cfg, self.creds)
        self.master_secret_id = await anoncreds.prover_create_master_secret(self.wallet, None)
        (self.did, self.verkey) = await did.create_and_store_my_did(self.wallet, self.seed)
        # Download the genesis file
        resp = await aiohttp.ClientSession().get(self.ledger_url)
        genesis = await resp.read()
        genesisFileName = "genesis.aries-test"
        with open(genesisFileName, 'wb') as output:
            output.write(genesis)
        await self._open_pool({'genesis_txn': genesisFileName})

    async def issuer_create_credential_schema(self, name: str, version: str, attrs: [str]) -> str:
        (schema_id, schema) = await anoncreds.issuer_create_schema(
            self.did, name, version, json.dumps(attrs))
        schema_request = await ledger.build_schema_request(self.did, schema)
        await ledger.sign_and_submit_request(self.pool,
                                             self.wallet,
                                             self.did,
                                             schema_request)
        return schema_id

    async def issuer_create_credential_definition(self, schema_id) -> str:
        request = await ledger.build_get_schema_request(self.did, schema_id)
        response = await ledger.submit_request(self.pool, request)
        (_, schema) = await ledger.parse_get_schema_response(response)
        (cred_def_id, cred_def_json) = await anoncreds.issuer_create_and_store_credential_def(
            self.wallet, self.did, schema, 'TAG1', 'CL', '{"support_revocation": false}')
        cred_def_request = await ledger.build_cred_def_request(self.did, cred_def_json)
        await ledger.sign_and_submit_request(self.pool, self.wallet, self.did, cred_def_request)
        return cred_def_id

    async def issuer_create_credential_offer(self, cred_def_id: str) -> (str, any):
        offer = await anoncreds.issuer_create_credential_offer(self.wallet, cred_def_id)
        attach = base64.b64encode(offer.encode()).decode()
        return (attach, offer)

    async def issuer_create_credential(self, offer: any, b64_request_attach: any, attrs: dict) -> str:
        req = base64.b64decode(b64_request_attach).decode()
        attrs = json.dumps(self._encode_attrs(attrs))
        (cred_json, _, _) = await anoncreds.issuer_create_credential(self.wallet, offer, req, attrs, None, None)
        attach = base64.b64encode(cred_json.encode()).decode()
        return attach

    async def holder_create_credential_request(self, b64_offer_attach: str) -> (str, dict):
        offer = json.loads(base64.b64decode(b64_offer_attach))
        credDefId = offer['cred_def_id']
        # Get the cred def from the ledger
        (_, credDef) = await self._get_cred_def(credDefId)
        # Create the credential request
        (req_data, req_metadata) = await anoncreds.prover_create_credential_req(
            self.wallet, self.did, json.dumps(offer), credDef, self.master_secret_id)
        b64_request_attach = base64.b64encode(req_data.encode()).decode()
        store_credential_passback = {
            "req_metadata": req_metadata,
            "cred_def": credDef
        }
        return (b64_request_attach, store_credential_passback)

    async def holder_store_credential(self, b64_credential_attach: str, store_credential_passback: dict):
        cred = base64.b64decode(b64_credential_attach).decode()
        pb = store_credential_passback
        await anoncreds.prover_store_credential(self.wallet, None, pb["req_metadata"], cred, pb["cred_def"], None)

    async def _get_cred_def(self, credDefId):
        req = await ledger.build_get_cred_def_request(self.did, credDefId)
        resp = await ledger.submit_request(self.pool, req)
        credDef = await ledger.parse_get_cred_def_response(resp)
        return credDef

    async def _open_pool(self, cfg):
        # Create the pool, but ignore the error if it already exists
        await pool.set_protocol_version(2)
        try:
            await pool.create_pool_ledger_config(self.ledger_name, json.dumps(cfg))
        except IndyError as e:
            if e.error_code != ErrorCode.PoolLedgerConfigAlreadyExistsError:
                raise e
        self.pool = await pool.open_pool_ledger(self.ledger_name, json.dumps(cfg))

    def _encode_attrs(self, attrs: dict) -> dict:
        result = {}
        for name, val in attrs.items():
            result[name] = {
                'raw': val,
                'encoded': self._encode_attr(val),
            }
        return result

    def _encode_attr(self, value) -> str:
        if value is None:
            return '4294967297'  # sentinel 2**32 + 1
        s = str(value)
        try:
            i = int(value)
            if 0 <= i < 2**32:  # it's an i32, leave it (as numeric string)
                return s
        except (ValueError, TypeError):
            pass
        # Compute sha256 decimal string
        hash = hashlib.sha256(value.encode()).digest()
        num = int.from_bytes(hash, byteorder=sys.byteorder, signed=False)
        return str(num)
