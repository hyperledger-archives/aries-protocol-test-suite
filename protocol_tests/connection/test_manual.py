""" Manual Connection Protocol tests.
"""
import pytest

from aries_staticagent import crypto
from reporting import meta
from . import Invite, Request, Response


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0', role='inviter', name='can-start')
async def test_connection_started_by_tested_agent(config, temporary_channel):
    """Test a connection as started by the agent under test."""
    invite = Invite.parse_invite(
        input('Input generated connection invite: ')
    )

    print("\nReceived Invite:\n", invite.pretty_print())

    # Create my information for connection
    invite_key, invite_endpoint = invite.get_connection_info()
    with temporary_channel(invite_key, invite_endpoint) as conn:

        # Send Connection Request to inviter
        request = Request.make(
            'test-connection-started-by-tested-agent',
            conn.did,
            conn.my_vk_b58,
            config['endpoint']
        )

        print("\nSending Request:\n", request.pretty_print())
        print("Awaiting response from tested agent...")
        response = Response(await conn.send_and_await_reply_async(
            request,
            condition=lambda msg: msg.type == Response.TYPE,
            timeout=30
        ))

        response.validate_pre_sig_verify()
        print(
            "\nReceived Response (pre signature verification):\n",
            response.pretty_print()
        )
        response.verify_sig(invite_key)
        response.validate_post_sig_verify()

        assert response['~thread']['thid'] == request.id

        print(
            "\nReceived Response (post signature verification):\n",
            response.pretty_print()
        )

        # To send more messages, update conn's their_vk and endpoint
        # to those disclosed in the response.


@pytest.mark.asyncio
@meta(protocol='connections', version='1.0', role='invitee', name='can-receive')
async def test_connection_started_by_suite(config, temporary_channel):
    """Test a connection as started by the suite."""

    with temporary_channel() as conn:
        invite = Invite.make(
            'test-suite-connection-started-by-suite',
            conn.my_vk_b58,
            config['endpoint']
        )
        invite_url = invite.to_url()

        print("\n\nInvitation encoded as URL: ", invite_url)

        print("Awaiting request from tested agent...")
        request = Request(await conn.await_message(
            condition=lambda msg: msg.type == Request.TYPE,
            timeout=30
        ))

        request.validate()
        print("\nReceived request:\n", request.pretty_print())

        # Update connection information with request info
        _, conn.their_vk_b58, conn.endpoint = request.get_connection_info()
        conn.their_vk = crypto.b58_to_bytes(conn.their_vk_b58)

        # Update connection relationship keys (replacing invite keys)
        conn.my_vk, conn.my_sk = crypto.create_keypair()
        conn.did = crypto.bytes_to_b58(conn.my_vk[:16])
        conn.my_vk_b58 = crypto.bytes_to_b58(conn.my_vk)

        response = Response.make(
            request.id,
            conn.did,
            conn.my_vk_b58,
            config['endpoint']
        )

        print(
            "\nSending Response (pre signature packing):\n",
            response.pretty_print()
        )

        response.sign(signer=conn.my_vk_b58, secret=conn.my_sk)
        print(
            "\nSending Response (post signature packing):\n",
            response.pretty_print()
        )

        await conn.send_async(response)
