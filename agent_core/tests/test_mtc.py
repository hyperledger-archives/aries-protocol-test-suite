""" Test MessageTrustContext """
import pytest

from agent_core.mtc import MessageTrustContext, ContextsConflict
from agent_core.mtc import (
    NONE,
    SIZE_OK,
    DESERIALIZE_OK,
    KEYS_OK,
    CONFIDENTIALITY,
    AUTHENTICATED_ORIGIN,
    UNIQUENESS
)


@pytest.mark.parametrize(
    'plus, minus, expected',
    [
        (SIZE_OK, NONE, 'mtc: +size_ok'),
        (
            SIZE_OK | DESERIALIZE_OK,
            NONE,
            'mtc: +size_ok +deserialize_ok'
        ),
        (
            KEYS_OK | SIZE_OK | DESERIALIZE_OK,
            NONE,
            'mtc: +size_ok +deserialize_ok +keys_ok'
        ),
        (
            SIZE_OK,
            DESERIALIZE_OK,
            'mtc: +size_ok -deserialize_ok'
        ),
        (
            KEYS_OK | SIZE_OK | DESERIALIZE_OK,
            CONFIDENTIALITY | UNIQUENESS,
            'mtc: +size_ok +deserialize_ok +keys_ok '
            '-confidentiality -uniqueness'
        ),
    ]
)
def test_str(plus, minus, expected):
    """ Test stringifying """
    mtc = MessageTrustContext(plus, minus)
    assert str(mtc) == expected


@pytest.mark.parametrize(
    'plus, minus',
    [
        (
            SIZE_OK,
            SIZE_OK
        ),
        (
            SIZE_OK | DESERIALIZE_OK,
            SIZE_OK
        ),
        (
            SIZE_OK | DESERIALIZE_OK | CONFIDENTIALITY,
            CONFIDENTIALITY
        ),
    ]
)
def test_overlapping_affirm_denied_fail(plus, minus):
    """ Test overlapping affirm and denied flags raise error """
    with pytest.raises(ContextsConflict):
        MessageTrustContext(plus, minus)


def test_cannot_alter_attributes():
    """ Test that affirmed and denied attributes can't be altered """
    mtc = MessageTrustContext()

    assert mtc.affirmed == NONE
    assert mtc.denied == NONE

    with pytest.raises(AttributeError):
        mtc.affirmed = CONFIDENTIALITY

    with pytest.raises(AttributeError):
        mtc.denied = CONFIDENTIALITY


def test_get_set():
    """ Test using __getitem__ and __setitem__ for retrieving and changing
        contexts.
    """
    mtc = MessageTrustContext()

    mtc[CONFIDENTIALITY] = True
    assert mtc.affirmed == CONFIDENTIALITY
    assert mtc[CONFIDENTIALITY]
    assert mtc.denied == NONE

    mtc[SIZE_OK] = True
    assert mtc.affirmed == CONFIDENTIALITY | SIZE_OK
    assert mtc[CONFIDENTIALITY | SIZE_OK]
    assert mtc.denied == NONE

    mtc[SIZE_OK] = False
    assert mtc.affirmed == CONFIDENTIALITY
    assert mtc[CONFIDENTIALITY]
    assert not mtc[CONFIDENTIALITY | SIZE_OK]
    assert mtc.denied == SIZE_OK

    mtc[AUTHENTICATED_ORIGIN] = True
    assert mtc.affirmed == CONFIDENTIALITY | AUTHENTICATED_ORIGIN
    assert mtc[CONFIDENTIALITY | AUTHENTICATED_ORIGIN]
    assert mtc.denied == SIZE_OK

    mtc[AUTHENTICATED_ORIGIN] = None
    assert mtc.affirmed == CONFIDENTIALITY
    assert mtc.denied == SIZE_OK
