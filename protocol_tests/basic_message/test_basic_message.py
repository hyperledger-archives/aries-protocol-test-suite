"""Test BasicMessage protocol as defined at:
https://github.com/hyperledger/aries-rfcs/tree/master/features/0095-basic-message
"""

import asyncio
import datetime
import random
import string

import pytest
from aries_staticagent import Message
from voluptuous import Match

from reporting import meta
from ..schema import MessageSchema

ISO_8601_REGEX = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])(?: |T)(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$'

MSG_TYPE = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/basicmessage/1.0/message'
PROBLEM = 'did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/report-problem/1.0/problem-report'

MSG_VALID = MessageSchema({
    '@type': MSG_TYPE,
    '@id': str,
    '~l10n': {'locale': str},
    'sent_time': Match(ISO_8601_REGEX),
    'content': str
})

def timestamp():
    """Return UTC in ISO 8601 format."""
    return datetime.datetime.utcnow().isoformat()


def random_string(length=10):
    """Generate a random string."""
    return ''.join(
        random.choice(string.ascii_letters)
        for i in range(length)
    )


@pytest.mark.asyncio
@meta(protocol='basicmessage', version='1.0', role='receiver',
      name='can-process-message')
async def test_receiver(backchannel, connection):
    """Agent under test can receive and handle basic messages."""
    content = random_string()
    msg = Message({
        '@type': MSG_TYPE,
        '~l10n': {'locale': 'en'},
        'sent_time': timestamp(),
        'content': content
    })
    assert MSG_VALID(msg)
    await connection.send_async(msg)
    reported = await backchannel.basic_message_v1_0_last_received_message()
    assert content == reported


@pytest.mark.asyncio
@meta(protocol='basicmessage', version='1.0', role='sender',
      name='send-message')
async def test_sender(backchannel, connection):
    """Agent under test can send a well-formatted message."""
    content = random_string()

    with connection.next() as next_msg:
        await backchannel.basic_message_v1_0_send_message(content)
        msg = await asyncio.wait_for(next_msg, 30)

    assert MSG_VALID(msg)
    assert msg['content'] == content


@pytest.mark.asyncio
@meta(protocol='basicmessage', version='1.0', role='receiver',
      name='reports-no-locale')
async def test_no_locale(connection):
    """Agent under test sends problem report on missing locale information."""
    with connection.next() as next_msg:
        await connection.send_async(Message({
            '@type': MSG_TYPE,
            'sent_time': timestamp(),
            'content': random_string()
        }))
        msg = await asyncio.wait_for(next_msg, 5)
    assert msg.type == PROBLEM


@pytest.mark.asyncio
@meta(protocol='basicmessage', version='1.0', role='receiver',
      name='reports-no-sent-time')
async def test_no_sent_time(backchannel, connection):
    """Agent under test sends problem report on missing sent time."""
    with connection.next() as next_msg:
        await connection.send_async(Message({
            '@type': MSG_TYPE,
            '~l10n': {'locale': 'en'},
            'content': random_string()
        }))
        msg = await asyncio.wait_for(next_msg, 5)
    assert msg.type == PROBLEM

@pytest.mark.asyncio
@meta(protocol='basicmessage', version='1.0', role='receiver',
      name='reports-no-content')
async def test_no_content(backchannel, connection):
    """Agent under test sends problem report on missing content."""
    with connection.next() as next_msg:
        await connection.send_async(Message({
            '@type': MSG_TYPE,
            '~l10n': {'locale': 'en'},
            'sent_time': timestamp(),
        }))
        msg = await asyncio.wait_for(next_msg, 5)
    assert msg.type == PROBLEM
