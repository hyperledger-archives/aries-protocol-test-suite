""" Manual Connection Protocol tests.
"""
import json

import pytest

from reporting import meta
from . import Invite, Request, Response
from .. import interrupt, last, event_message_map, run

# pylint: disable=redefined-outer-name

# Inviter:


async def _inviter(config, temporary_channel):
    """Inviter protocol generator."""
    invite = Invite.parse_invite(
        input('Input generated connection invite: ')
    )

    yield 'invite', invite

    # Create my information for connection
    invite_info = invite.get_connection_info()
    with temporary_channel(**invite_info._asdict()) as conn:

        yield 'before_request', conn

        request = Request.make(
            'test-connection-started-by-tested-agent',
            conn.did,
            conn.verkey_b58,
            config['endpoint']
        )

        yield 'request', conn, request

        response = Response(await conn.send_and_await_reply_async(
            request,
            condition=lambda msg: msg.type == Response.TYPE,
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
async def inviter(config, temporary_channel):
    """Inviter fixture."""
    generator = _inviter(config, temporary_channel)
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
            '@type': 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping',
            'response_requested': True
        },
        condition=lambda msg: msg.type ==
        'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping_response',
        timeout=5,
    )


# Invitee:

async def _invitee(config, temporary_channel):
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
        print("\n\nInvitation as JSON:", invite.serialize())

        invite_url = invite.to_url()
        print("\n\nInvitation encoded as URL:", invite_url)

        request = Request(await invite_conn.await_message(
            condition=lambda msg: msg.type == Request.TYPE,
            timeout=30
        ))
        request.validate()
        yield 'request', invite_conn, request

    # Drop invite connection by exiting "with" context (no longer listening for
    # messages with key matching invitation key).

    # Extract their new connection info
    info = request.get_connection_info()

    # Set up connection for relationship.
    with temporary_channel(**info._asdict()) as conn:
        response = Response.make(
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
async def invitee(config, temporary_channel):
    """Invitee fixture."""
    generator = _invitee(config, temporary_channel)
    yield generator
    await generator.aclose()


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='invitee', name='can-be-invitee')
async def test_connection_started_by_suite(invitee):
    """Test a connection as started by the suite."""
    await run(invitee)
