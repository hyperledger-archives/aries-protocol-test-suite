Writing Tests
=============

A simple example of a protocol test can be found in
[`test_simple_messaging.py`][3]. This test uses the test suite backchannel to
create and open a new connection and then sends a simple message and expects a
simple response.

## Asynchronous Tests

Tests follow standard `pytest` conventions. As the sending and receiving of
messages are asynchronous, most tests will likely need to `await` a promise and
must be marked as asynchronous, e.g.:

```python
@pytest.mark.asyncio
async def test_method():
	await some_async_call()
```

## Test Meta Information

Tests are assigned meta information to help with test selection and
interoperability profile reporting. To assign meta information to a test, use
the `meta` decorator from the [`reporting`](reporting.py) module:

```python
@pytest.mark.asyncio
@meta(protocol='test', version='1.0', role='initiator', name='test-this')
async def test_method():
	await some_async_call()
```

## Testing Protocols

A convention used for testing complex protocols is to use an asynchronous python
generator. This enables the starting and stopping of protocols to insert logic
at the beginning, middle, or end of a protocol.
