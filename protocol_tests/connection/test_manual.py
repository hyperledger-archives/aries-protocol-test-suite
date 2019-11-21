""" Manual Connection Protocol tests.
"""
import pytest

from reporting import meta
from . import Invite, Request, Response, Ack, Ping, PingResponse, ProblemReport
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

        thid = request.id

        yield 'request', conn, request

        response = Response(await conn.send_and_await_reply_async(
            request,
            condition=lambda msg: msg.type == Response.TYPE,
            timeout=30
        ))

        yield 'response', conn, thid, response

        response.validate_pre_sig_verify()
        response.verify_sig(invite_info.recipients[0])
        response.validate_post_sig_verify()

        yield 'response_verified', conn, thid, response

        info = response.get_connection_info()
        conn.update(**info._asdict())

        yield 'complete', conn, thid


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
    _conn, _thid, response = await last(interrupt(inviter, on='response'))
    response.validate_pre_sig_verify()


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='response-post-sig-verify-valid')
async def test_response_valid_post(inviter):
    """Response after signature verification is valid."""
    _conn, _thid, response = await last(interrupt(inviter, on='response_verified'))
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
      role='inviter', name='send-problem-report-on-received-response')
async def test_send_problem_report_on_received_request(inviter):
    """Send Problem Report on received Response."""
    conn, thid, response = await last(interrupt(inviter, on='response'))

    problem_report = ProblemReport.make(
        thid,
        ProblemReport.ProblemCode.RESPONSE_PROCESSING_ERROR
    )

    conn.send_async(problem_report)
    # TODO: check that testing agent moved to Null state using backchannel


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='responds-to-ping')
async def test_finish_with_trust_ping(inviter):
    """Inviter responds to trust ping after connection protocol completion."""
    conn, _thid = await last(interrupt(inviter, on='complete'))

    PingResponse(await conn.send_and_await_reply_async(
        Ping.make(True),
        condition=lambda msg: msg.type == PingResponse.TYPE,
        timeout=30
    ))


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='send-ack-to-complete')
async def test_send_ack_on_complete(inviter):
    """Send Ack to complete connection."""
    conn, thid = await last(interrupt(inviter, on='complete'))

    ack = Ack.make(
        thid,
        Ack.Status.OK
    )

    conn.send_async(ack)
    # TODO: "check that testing agent moved to Complete state using backchannel


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

        # Do not drop invite connection
        # ConnectionProblemReport message with key matching invitation key can be received .

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
            yield 'response', invite_conn, conn, response

            response.sign(
                signer=invite_verkey_b58,
                secret=invite_sigkey
            )
            yield 'signed_response', invite_conn, conn, response

            await conn.send_async(response)
            yield 'complete', invite_conn, conn


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


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='invitee', name='send-problem-report-on-received-request')
async def test_send_problem_report_on_request(invitee):
    """Send Problem Report on received Request."""
    conn, request = await last(interrupt(invitee, on='request'))

    problem_report = ProblemReport.make(
        request.id,
        ProblemReport.ProblemCode.REQUEST_PROCESSING_ERROR,
    )

    conn.send_async(problem_report)
    # TODO: check that testing agent moved to Null state using backchannel


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='invitee', name='problem-report-received-on-response-signed-by-signer-key')
async def test_send_response_signed_by_other_key(invitee):
    """Send Connection Response signed by different key. ProblemReport is expected"""
    invite_conn, conn, response = await last(interrupt(invitee, on='response'))

    response.sign(signer=conn.verkey_b58, secret=conn.sigkey)

    await conn.send_async(response)

    ProblemReport(await invite_conn.await_message(
        condition=lambda msg: msg.type == ProblemReport.TYPE,
        timeout=30
    ))
