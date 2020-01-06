import json, aiohttp, base64, time, sys, hashlib, random, string

from protocol_tests.provider import Provider
from protocol_tests.issue_credential.provider import IssueCredentialProvider
from indy import anoncreds, wallet, ledger, pool, crypto, did, pairwise, non_secrets, ledger, wallet, blob_storage
from indy.error import IndyError, ErrorCode


class IndyProvider(Provider, IssueCredentialProvider):
    """
    The indy provider isolates all indy-specific code required by the test suite.
    """

    async def setup(self, config):
        if not 'genesis_url' in config:
            raise Exception(
                "The Indy provider requires a 'genesis_url' value in config.toml")
        self.genesis_url = config['genesis_url']
        self.pool_name = config.get('pool_name', 'arie-test')
        id = config.get('name', 'test')
        key = config.get('pass', 'testpw')
        seed = config.get('seed', '000000000000000000000000Steward1')
        self.cfg = json.dumps({'id': id})
        self.creds = json.dumps({'key': key})
        self.seed = json.dumps({'seed': seed})
        try:
            await wallet.delete_wallet(self.cfg, self.creds)
        except Exception as e:
            pass
        await wallet.create_wallet(self.cfg, self.creds)
        self.wallet = await wallet.open_wallet(self.cfg, self.creds)
        self.master_secret_id = await anoncreds.prover_create_master_secret(self.wallet, None)
        (self.did, self.verkey) = await did.create_and_store_my_did(self.wallet, self.seed)
        # Download the genesis file
        resp = await aiohttp.ClientSession().get(self.genesis_url)
        genesis = await resp.read()
        genesisFileName = "genesis.aries-test"
        with open(genesisFileName, 'wb') as output:
            output.write(genesis)
        await self._open_pool({'genesis_txn': genesisFileName})

    async def issue_credential_v1_0_issuer_create_credential_schema(self, name: str, version: str, attrs: [str]) -> str:
        (schema_id, schema) = await anoncreds.issuer_create_schema(
            self.did, name, version, json.dumps(attrs))
        schema_request = await ledger.build_schema_request(self.did, schema)
        await ledger.sign_and_submit_request(self.pool,
                                             self.wallet,
                                             self.did,
                                             schema_request)
        return schema_id

    async def issue_credential_v1_0_issuer_create_credential_definition(self, schema_id) -> str:
        request = await ledger.build_get_schema_request(self.did, schema_id)
        response = await ledger.submit_request(self.pool, request)
        (_, schema) = await ledger.parse_get_schema_response(response)
        (cred_def_id, cred_def_json) = await anoncreds.issuer_create_and_store_credential_def(
            self.wallet, self.did, schema, 'TAG1', 'CL', '{"support_revocation": false}')
        cred_def_request = await ledger.build_cred_def_request(self.did, cred_def_json)
        await ledger.sign_and_submit_request(self.pool, self.wallet, self.did, cred_def_request)
        return cred_def_id

    async def issue_credential_v1_0_issuer_create_credential_offer(self, cred_def_id: str) -> (str, any):
        offer = await anoncreds.issuer_create_credential_offer(self.wallet, cred_def_id)
        attach = base64.b64encode(offer.encode()).decode()
        return (attach, offer)

    async def issue_credential_v1_0_issuer_create_credential(self, offer: any, b64_request_attach: any, attrs: dict) -> str:
        req = base64.b64decode(b64_request_attach).decode()
        attrs = json.dumps(self._encode_attrs(attrs))
        (cred_json, _, _) = await anoncreds.issuer_create_credential(self.wallet, offer, req, attrs, None, None)
        attach = base64.b64encode(cred_json.encode()).decode()
        return attach

    async def issue_credential_v1_0_holder_create_credential_request(self, b64_offer_attach: str) -> (str, dict):
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

    async def issue_credential_v1_0_holder_store_credential(self, b64_credential_attach: str, store_credential_passback: dict):
        cred = base64.b64decode(b64_credential_attach).decode()
        pb = store_credential_passback
        await anoncreds.prover_store_credential(self.wallet, None, pb["req_metadata"], cred, pb["cred_def"], None)

    async def present_proof_v1_0_verifier_request_presentation(self, proof_req: dict) -> (str, str):
        proof_req['nonce'] = self._nonce()
        proof_req_json = json.dumps(proof_req)
        attach = base64.b64encode(proof_req_json.encode()).decode()
        return attach, proof_req_json

    async def present_proof_v1_0_prover_create_presentation(self, b64_request_attach) -> str:
        proof_req_json = base64.b64decode(b64_request_attach).decode()
        # Get the creds for the request from the prover's wallet
        creds_json = await anoncreds.prover_get_credentials_for_proof_req(self.wallet, proof_req_json)
        creds = json.loads(creds_json)
        # Prepare to generate proof from the request and creds in our wallet
        proof_req = json.loads(proof_req_json)
        sa_attrs = proof_req.get('self_attested_attributes', {})
        pr_req_attrs = proof_req.get('requested_attributes', {})
        pr_req_preds = proof_req.get('requested_predicates', {})
        my_creds = {}
        req_attrs = {}
        req_preds = {}
        for ref in pr_req_attrs:  # for all requested attributes
            restrictions = pr_req_attrs[ref].get('restrictions')
            attrCreds = creds['attrs'][ref]
            found = False
            for attrCred in attrCreds:
                ci = attrCred['cred_info']
                found = True
                my_creds[ref] = ci
                if restrictions:
                    req_attrs[ref] = {
                        'cred_id': ci['referent'], 'revealed': True}
            if not restrictions and not ref in sa_attrs:
                raise Exception(
                    "Missing value for self-attested attribute '{}'".format(ref))
        creds = json.loads(creds_json)
        for ref in pr_req_preds:  # for all requested predicates
            predCreds = creds['predicates'][ref]
            for predCred in predCreds:
                ci = predCred['cred_info']
                my_creds[ref] = ci
                if restrictions:
                    req_preds[ref] = {'cred_id': ci['referent']}
        schemas_json, cred_defs_json, revoc_states_json = await self._prover_get_entities_from_ledger(my_creds)
        my_creds_json = json.dumps({
            'self_attested_attributes': sa_attrs,
            'requested_attributes': req_attrs,
            'requested_predicates': req_preds,
        })
        proof_json = await anoncreds.prover_create_proof(
            self.wallet, proof_req_json, my_creds_json,
            self.master_secret_id, schemas_json, cred_defs_json,
            revoc_states_json)
        b64_proof_attach = base64.b64encode(proof_json.encode()).decode()
        return b64_proof_attach

    async def present_proof_v1_0_verifier_verify_presentation(self, b64_proof: str, proof_req_json: str) -> dict:
        proof_json = base64.b64decode(b64_proof).decode()
        proof_req = json.loads(proof_req_json)
        proof = json.loads(proof_json)
        entities = await self._verifier_get_entities_from_ledger(proof)
        schemas_json = json.dumps(entities['schemas'])
        cred_defs_json = json.dumps(entities['cred_defs'])
        revoc_reg_defs_json = json.dumps(entities['revoc_reg_defs'])
        revoc_regs_json = json.dumps(entities['revoc_regs'])
        await anoncreds.verifier_verify_proof(
                proof_req_json, proof_json, schemas_json, cred_defs_json,
                revoc_reg_defs_json, revoc_regs_json)
        return self._get_proof_info(proof_req, proof)

    def _get_proof_info(self, proof_req: dict, proof: dict) -> dict:
        identifiers = proof['identifiers']
        proofs = proof['proof']['proofs']
        attributes = []
        predicates = []
        # Add attested attributes and predicates
        for index in range(len(identifiers)):
            credDefId = identifiers[index]['cred_def_id']
            primaryProof = proofs[index]['primary_proof']
            for proofType in primaryProof:
                ptEle = primaryProof[proofType]
                if 'revealed_attrs' in ptEle:
                    revealedAttrs = ptEle['revealed_attrs']
                    for name in revealedAttrs:
                        attributes.append({
                            'name': name,
                            'value': revealedAttrs[name],
                            'cred_def_id': credDefId,
                        })
                for cmpProof in ptEle:
                    if 'predicate' in cmpProof:
                        predicates.append({
                            'predicate': self._predicate_str(cmpProof['predicate']),
                            'cred_def_id': credDefId,
                        })
        # For each attribute, replace the hash with the raw value
        revealed_attrs = proof['requested_proof']['revealed_attrs']
        for attr in attributes:
            attr['value'] = self._get_raw_for_hash(attr['value'], revealed_attrs)
        # Add self-attested attributes
        sa_attrs = proof['requested_proof']['self_attested_attrs']
        for name, val in sa_attrs.items():
            name = proof_req['requested_attributes'][name]['name']
            attributes.append({'name': name,'value': val})
        proofInfo = {
            'attributes': attributes,
            'predicates': predicates,
        }
        return proofInfo

    def _get_raw_for_hash(self, hash, revealed_attrs) -> str:
        for _, rattr in revealed_attrs.items():
            if rattr['encoded'] == hash:
                raw = rattr['raw']
                return raw
        raise Exception("Hash {} was not found in proof".format(hash))

    def _predicate_str(self, predicate: dict) -> str:
        if predicate.keys() >= {'attr_name', 'p_type', 'value'}:
            return '{} {} {}'.format(predicate['attr_name'], predicate['p_type'], predicate['value'])
        else:
            return json.dumps(predicate, indent=4, sort_keys=True)

    async def _verifier_get_entities_from_ledger(self, proof: dict) -> dict:
        schemas = {}
        cred_defs = {}
        revoc_reg_defs = {}
        revoc_regs = {}
        for item in proof['identifiers']:
            schemaID = item['schema_id']
            (received_schema_id, received_schema) = await self._get_schema(schemaID)
            schemas[received_schema_id] = json.loads(received_schema)
            credDefID = item['cred_def_id']
            (received_cred_def_id, received_cred_def) = await self._get_cred_def(credDefID)
            cred_defs[received_cred_def_id] = json.loads(received_cred_def)
        entities = {
            'schemas': schemas,
            'cred_defs': cred_defs,
            'revoc_reg_defs': revoc_reg_defs,
            'revoc_regs': revoc_regs
        }
        return entities

    async def _prover_get_entities_from_ledger(self, identifiers: dict) -> (str, str, str):
        schemas = {}
        cred_defs = {}
        rev_states = {}
        for item in identifiers.values():
            (received_schema_id, received_schema) = await self._get_schema(item['schema_id'])
            schemas[received_schema_id] = json.loads(received_schema)
            (received_cred_def_id, received_cred_def) = await self._get_cred_def(item['cred_def_id'])
            cred_defs[received_cred_def_id] = json.loads(received_cred_def)
        return json.dumps(schemas), json.dumps(cred_defs), json.dumps(rev_states)

    async def _get_schema(self, schema_id: str):
        get_schema_request = await ledger.build_get_schema_request(self.did, schema_id)
        get_schema_response = await ledger.submit_request(self.pool, get_schema_request)
        return await ledger.parse_get_schema_response(get_schema_response)

    async def _get_cred_def(self, credDefId):
        req = await ledger.build_get_cred_def_request(self.did, credDefId)
        resp = await ledger.submit_request(self.pool, req)
        credDef = await ledger.parse_get_cred_def_response(resp)
        return credDef

    async def _open_pool(self, cfg):
        # Create the pool, but ignore the error if it already exists
        await pool.set_protocol_version(2)
        try:
            await pool.create_pool_ledger_config(self.pool_name, json.dumps(cfg))
        except IndyError as e:
            if e.error_code != ErrorCode.PoolLedgerConfigAlreadyExistsError:
                raise e
        self.pool = await pool.open_pool_ledger(self.pool_name, json.dumps(cfg))

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

    def _nonce(self, strlen=12) -> str:
        """Generate a random nonce consisting of digits of length 'strlen'"""
        return ''.join(random.choice(string.digits) for i in range(strlen))