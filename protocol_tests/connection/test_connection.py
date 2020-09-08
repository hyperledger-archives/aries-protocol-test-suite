""" Manual Connection Protocol tests.
"""
from asyncio import wait_for
import pytest

from reporting import meta
from . import Invite, ConnectionRequest, ConnectionResponse, OutOfBandInvite, TheirInfo, HandshakeReuseHandler, DidExchangeResponse, DidExchangeRequest
from .. import interrupt, last, event_message_map, run

from aries_staticagent import Message, crypto, route
from aries_staticagent.mtc import (
    CONFIDENTIALITY, INTEGRITY, AUTHENTICATED_ORIGIN,
    DESERIALIZE_OK, NONREPUDIATION
)

# pylint: disable=redefined-outer-name

# Inviter:

async def _oob_receiver_flow(config, backchannel, temporary_channel):
    """Protocol generator for receiver role."""
    # They create an invitation and give it to me to use

    # Create an OOB invitation through the backchannel
    invite_url = await backchannel.out_of_band_v1_0_create_invitation()

    # Parse the invitation and validate the schema
    invite = OutOfBandInvite.parse_url(invite_url)
    invite.validate()
    yield 'invite', invite

    # Extract the connection information from the invitation
    info = invite.get_connection_info()
    yield 'connection_info', info

    # Find the first supported handshake protocol from the list
    # TODO: If there's no handshake protocols in the list,
    # then we need to handle the request attach instead. Not implemented yet.
    preferred_handshake_protocol = invite.get_preferred_handshake_protocol()
    yield 'preferred_handshake_protocol', preferred_handshake_protocol

    # Let's generate some connection information for the suite
    with temporary_channel(**info._asdict()) as conn:
        # TODO: If the first handshake protocol fails,
        # we should try to create a connection with the next one

        # If we're handling a DID exchange
        if preferred_handshake_protocol in OutOfBandInvite.DID_EXCHANGE_TYPES:

            # Make a DID exchange request
            request = DidExchangeRequest.make(
                conn.did,
                conn.verkey_b58,
                config['endpoint'],
                conn.sigkey,
                'test-oob-connection-started-by-suite-did-exchange'
            )

            yield 'did_exchange_request', request
            # Send out the DID exchange request, wait for the response and validate it
            response = DidExchangeResponse(await conn.send_and_await_reply_async(
                request,
                condition=lambda msg: msg.type == (DidExchangeResponse.TYPE or DidExchangeResponse.ALT_TYPE),
                timeout=10
            ))
            response.validate()

            yield 'did_exchange_response', response

            # We need to update the connection information here so we can
            # properly contact the agent on the other side
            new_info = response.get_connection_info()
            conn.update(**new_info._asdict())

            yield 'new_connection_info', new_info, conn

            # Next, to finish out the flow we have to send out the did exchange compete msg
            complete = {
                "@type": "https://didcomm.org/didexchange/1.0/complete",
                "~thread": {
                    "thid": request["@id"],
                    "pthid": invite["@id"],
                    "sender_order": 1
                }
            }
            await conn.send_async(complete)

            yield 'did_exchange_complete', complete, conn

        # Otherwise, we're dealing with a connection protocol
        elif preferred_handshake_protocol in OutOfBandInvite.CONNECTION_TYPES:

            # Same flow here, except with a different protocol.
            # Make a request, wait for the response, validate the response and update the connection
            request = ConnectionRequest.make(
                'test-oob-connection-started-by-suite-connections',
                conn.did,
                conn.verkey_b58,
                config['endpoint']
            )

            yield 'request', request

            response = ConnectionResponse(await conn.send_and_await_reply_async(
                request,
                condition=lambda msg: msg.type == (ConnectionResponse.TYPE or ConnectionResponse.ALT_TYPE),
                timeout=30
            ))

            yield 'response', response

            response.validate_pre_sig_verify()
            response.verify_sig(info.recipients[0])
            response.validate_post_sig_verify()

            new_info = response.get_connection_info()
            conn.update(**new_info._asdict())

        else:
            raise Exception('No supported handshake protocols found.')

        # Resgister a new handler for the out-of-band handshake reuse.
        handler = HandshakeReuseHandler(invite['@id'])
        conn.route_module(handler)

        # Let's attempt to reuse the invitation here
        await handler.send_handshake_reuse(conn)

    yield 'flow_complete', conn



@pytest.fixture
async def oob_receiver(config, backchannel, temporary_channel):
    """Out of band receiver flow fixture."""
    generator = _oob_receiver_flow(config, backchannel, temporary_channel)
    yield generator
    await generator.aclose()


@pytest.mark.asyncio
@meta(protocol='out-of-band', version='1.0',
      role='receiver', name='oob-receiver-flow')
async def test_oob_receiver_flow(oob_receiver):
    """Test out of band flow as started by the agent under test."""
    await run(oob_receiver)    


async def _oob_sender_flow(config, backchannel, temporary_channel):
    """Protocol generator for sender role."""
    # I create an invite and they use my invite

    # Start off with generating some connection information for the suite
    with temporary_channel() as conn:
        invite_verkey_b58 = conn.verkey_b58
        invite_sigkey = conn.sigkey

        # Make an OOB invitation to send to our AUT
        invite = OutOfBandInvite.make(
            'test-suite-oob-connection-started-by-agent',
            'Test the interoperability of an agent',
            'p2p-messaging',
            invite_verkey_b58,
            config['endpoint'],
            publicDid=conn.did,
            handshake_protocols=["https://didcomm.org/connections/1.0", "https://didcomm.org/didexchange/1.0"]
        )

        yield 'invite', conn, invite

        # Have the AUT use our invitation and wait for the next msg
        with conn.next() as next_request:
            await backchannel.out_of_band_v1_0_use_invitation(invite.to_url())
            msg = await wait_for(next_request, 30)
        
        # If the agent wants to preform a connection protocol
        if msg['@type'] == (ConnectionRequest.TYPE or ConnectionRequest.ALT_TYPE):

            # Validate their connection request
            request = ConnectionRequest(msg)
            request.validate()
            yield 'connection_request', conn, request

            # Make a connection response
            response = ConnectionResponse.make(
                request.id,
                conn.did,
                conn.verkey_b58,
                config['endpoint']
            )

            yield 'connection_response', response

            # Sign it
            response.sign(
                signer=invite_verkey_b58,
                secret=invite_sigkey
            )
            yield 'signed_response', conn, response

            # Update connection info
            info = request.get_connection_info()
            conn.update(**info._asdict())

        # If the agent wants to do a did exchange
        elif msg['@type'] == (DidExchangeRequest.TYPE or DidExchangeRequest.ALT_TYPE):

            # Validate their request
            request = DidExchangeRequest(msg)
            request.validate()

            yield 'didexchange_request', request

            # Make the response
            response = DidExchangeResponse.make(
                request['@id'],
                conn.did,
                conn.verkey_b58,
                config['endpoint'],
                invite_sigkey,
            )

            yield 'didexchange_response', response

            info = request.get_connection_info()
            conn.update(**info._asdict())

            # Send out the response and wait for the did exchange complete message
            complete = (await conn.send_and_await_reply_async(
                response, 
                condition = lambda msg: msg.type == 'https://didcomm.org/didexchange/1.0/complete',
                timeout=10
            ))

            # Double check that the thid and pthid are the proper values
            assert complete["~thread"]["thid"] == request["@id"]
            assert complete["~thread"]["pthid"] == invite["@id"]

        else:
            raise Exception("Expected Connection request or DID exchange request. Found: {}".format(msg['@type']))

        yield 'connection_complete', conn
        
        # Resgister a new handler for the out-of-band handshake reuse.
        handler = HandshakeReuseHandler(invite['@id'])
        conn.route_module(handler)

        # Let's attempt to reuse the invitation here
        await backchannel.out_of_band_v1_0_use_invitation(invite.to_url())

    yield 'flow_complete', conn
        

@pytest.fixture
async def oob_sender(config, backchannel, temporary_channel):
    """Out of band sender flow fixture."""
    generator = _oob_sender_flow(config, backchannel, temporary_channel)
    yield generator
    await generator.aclose()


@pytest.mark.asyncio
@meta(protocol='out-of-band', version='1.0',
      role='sender', name='oob-sender-flow')
async def test_oob_sender_flow(oob_sender):
    """Test out of band flow as started by the suite"""
    await run(oob_sender)    


async def _inviter(config, backchannel, temporary_channel):
    """Inviter protocol generator."""
    invite = Invite.parse_url(await backchannel.connections_v1_0_inviter_start())

    yield 'invite', invite

    # Create my information for connection
    invite_info = invite.get_connection_info()
    with temporary_channel(**invite_info._asdict()) as conn:

        yield 'before_request', conn

        request = ConnectionRequest.make(
            'test-connection-started-by-tested-agent',
            conn.did,
            conn.verkey_b58,
            config['endpoint']
        )

        yield 'request', conn, request

        response = ConnectionResponse(await conn.send_and_await_reply_async(
            request,
            condition=lambda msg: msg.type == (ConnectionResponse.TYPE or ConnectionResponse.ALT_TYPE),
            timeout=30
        ))

        yield 'response', conn, response

        response.validate_pre_sig_verify()
        response.verify_sig(invite_info.recipients[0])
        response.validate_post_sig_verify()

        yield 'response_verified', conn, response

        info = response.get_connection_info()
        conn.update(**info._asdict())

        yield 'complete', conn


@pytest.fixture
async def inviter(config, backchannel, temporary_channel):
    """Inviter fixture."""
    generator = _inviter(config, backchannel, temporary_channel)
    yield generator
    await generator.aclose()


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='can-be-inviter')
async def test_connection_started_by_tested_agent(inviter):
    """Test a connection as started by the agent under test."""
    await run(inviter)


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='response-pre-sig-verify-valid')
async def test_response_valid_pre(inviter):
    """Response before signature verification is valid."""
    _conn, response = await last(interrupt(inviter, on='response'))
    response.validate_pre_sig_verify()


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='response-post-sig-verify-valid')
async def test_response_valid_post(inviter):
    """Response after signature verification is valid."""
    _conn, response = await last(interrupt(inviter, on='response_verified'))
    response.validate_post_sig_verify()


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='response-thid-matches-request')
async def test_response_thid_matches_request(inviter):
    """Response's thread has thid matching id of request."""
    message_map = await event_message_map(inviter)
    request = message_map['request'][0]
    response = message_map['response'][0]
    assert '~thread' in response
    assert 'thid' in response['~thread']
    assert response['~thread']['thid'] == request.id


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='responds-to-ping')
async def test_finish_with_trust_ping(inviter):
    """Inviter responds to trust ping after connection protocol completion."""
    conn = await last(interrupt(inviter, on='complete'))
    await conn.send_and_await_reply_async(
        {
            '@type': 'https://didcomm.org/trust_ping/1.0/ping',
            'response_requested': True
        },
        condition=lambda msg: msg.type == ('https://didcomm.org/trust_ping/1.0/ping_response' 
                                                    or 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping_response'),
        timeout=5,
    )

# Invitee:

async def _invitee(config, backchannel, temporary_channel):
    """Protocol generator for Invitee role."""
    with temporary_channel() as invite_conn:
        invite_verkey_b58 = invite_conn.verkey_b58
        invite_sigkey = invite_conn.sigkey
        invite = Invite.make(
            'test-suite-connection-started-by-suite',
            invite_conn.verkey_b58,
            config['endpoint']
        )

        yield 'invite', invite_conn, invite

        with invite_conn.next() as next_request:
            await backchannel.connections_v1_0_invitee_start(invite.to_url())
            request = ConnectionRequest(await wait_for(next_request, 30))

        request.validate()
        yield 'request', invite_conn, request

    # Drop invite connection by exiting "with" context (no longer listening for
    # messages with key matching invitation key).

    # Extract their new connection info
    info = request.get_connection_info()

    # Set up connection for relationship.
    with temporary_channel(**info._asdict()) as conn:
        response = ConnectionResponse.make(
            request.id,
            conn.did,
            conn.verkey_b58,
            config['endpoint']
        )
        yield 'response', conn, response

        response.sign(
            signer=invite_verkey_b58,
            secret=invite_sigkey
        )
        yield 'signed_response', conn, response

        await conn.send_async(response)
        yield 'complete', conn


@pytest.fixture
async def invitee(config, backchannel, temporary_channel):
    """Invitee fixture."""
    generator = _invitee(config, backchannel, temporary_channel)
    yield generator
    await generator.aclose()


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='invitee', name='can-be-invitee')
async def test_connection_started_by_suite(invitee):
    """Test a connection as started by the suite."""
    await run(invitee)
