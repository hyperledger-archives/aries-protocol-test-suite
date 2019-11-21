""" Manual Connection Protocol tests.
"""
from time import sleep

import pytest

from reporting import meta
from . import Invite, Request, Response, Ack, Ping, PingResponse, ConnectionStatus
from .. import run, BackChannel


# pylint: disable=redefined-outer-name

# Inviter:


async def _inviter(config, temporary_channel):
    """Inviter protocol generator."""

    back_channel = BackChannel(config['back_channel_endpoint'])

    invite = Invite.parse_invite(
        back_channel.send(BackChannel.Action.START_CONNECTION_AS_INVITER)
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

        PingResponse(await conn.send_and_await_reply_async(
            Ping.make(True),
            condition=lambda msg: msg.type == PingResponse.TYPE,
            timeout=30
        ))

        sleep(1)

        assert ConnectionStatus.COMPLETE.value == back_channel.send(BackChannel.Action.GET_CONNECTION_STATE)

        back_channel.send(BackChannel.Action.RESET_CONNECTION)


@pytest.fixture
async def inviter(config, temporary_channel):
    """Inviter fixture."""
    generator = _inviter(config, temporary_channel)
    yield generator
    await generator.aclose()


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='inviter', name='auto-can-be-inviter')
async def test_auto_connection_started_by_tested_agent(inviter):
    """Test a connection as started by the agent under test."""
    await run(inviter)


async def _invitee(config, temporary_channel):
    """Protocol generator for Invitee role."""

    back_channel = BackChannel(config['back_channel_endpoint'])

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

        back_channel.send(BackChannel.Action.START_CONNECTION_AS_INVITEE, invite.serialize())

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

            await conn.send_and_await_reply_async(
                response,
                condition=lambda msg: msg.type == Ack.TYPE,
                timeout=30
            )
            yield 'complete', invite_conn, conn

        sleep(1)

        assert ConnectionStatus.COMPLETE.value == back_channel.send(BackChannel.Action.GET_CONNECTION_STATE)

        back_channel.send(BackChannel.Action.RESET_CONNECTION)


@pytest.fixture
async def invitee(config, temporary_channel):
    """Invitee fixture."""
    generator = _invitee(config, temporary_channel)
    yield generator
    await generator.aclose()


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0',
      role='invitee', name='auto-can-be-invitee')
async def test_auto_connection_started_by_suite(invitee):
    """Test a connection as started by the suite."""
    await run(invitee)
