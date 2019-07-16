Aries Protocol Test Suite
=========================

Quickstart Guide
----------------

### Requirements

- Python 3.6 or higher
- `libindy` either installed as a package or compiled and placed in
  `LD_LIBRARY_PATH`
	- Follow instructions for your platform [here][1].

### Configuring and Running the Protocol Test Suite
After cloning this repository, create and activate a virtual environment to
install dependencies.
```sh
$ python3 -m venv env
$ source env/bin/activate
```

Install dependencies and the test suite package with `pip`
```sh
$ pip install -e .
```

Copy `config.sample.toml` to `config.toml` and edit as needed for your testing
scenario.

`config.sample.toml` shows an example configuration and contains comments
explaining each option:

```toml
## Aries Protocol Test Suite Sample Configuration ##

[config]
# The default name used for wallets created by the test agent.
wallet = "testing-agent"

# Passphrase of wallet
passphrase = "test"

# Specify whether wallets should be ephemeral
ephemeral = true

# Endpoint used in connections
endpoint = "http://localhost:3000/"

# A list of features or protocols to test.
features = [
    "connection.manual",
    #"simple"
    #"basicmessage.manual",
    #"trustping.manual"
]

# Transports to run
[[config.transport]]
name = 'http'
options = {port = 3000}

# More transports can be started by including more transport blocks:
# [[config.transport]]
# name = 'ws'
# options = {port = 3001}

# Uncommenting this block would start a WebSocket transport on port 3001.
# However, please note that an "http+ws" transport is included in the test
# suite, removing any need to run both an "http" and "ws" transport at the same
# time.

# Four different transports are included in the test suite (with potential to
# easily add more as needs are identified):

# "http" - the same transport as included in this configuration. Accepts
# messages as POSTs to http://<hostname>:<port>/

# "ws" - A WebSocket transport, as shown in the commented out example above.
# This transport will accept WebSocket connections at http://<hostname>:<port>/

# "http+ws" - A Combined http and ws transport, running one server to accept
# POSTs and WebSocket connections.

# "std" - A transport that reads messages from Standard In and writes messages
# to Standard Out. This is mostly included for demonstration purposes and likely
# will not work with the current testing setup.

# SNIP...
```

Now that you have your configuration file, you can now run the test suite
with:
```sh
$ protocoltest
```

> _**Note:**_ if you are running tests labelled as "manual" (e.g.
> `connection.manual`), you must include the `-s` option.

`protocoltest` is installed into your `PATH` when you run `pip install -e .`. If
running `protocoltest` doesn't work, it means you skipped that step. You can
alternatively run the script directly:

```sh
$ scripts/protocoltest
```

Use `protocoltest --help` to see more options.

[1]: https://github.com/hyperledger/indy-sdk#installing-the-sdk

Writing Tests
-------------

A simple example of writing a test using the test suite can be found in
[`test_simple_messaging.py`][3]. This test statically connects to another agent
(i.e. it receives the DID, key, and endpoint needed to communicate through
configuration rather than through engaging in a message exchange) and
demonstrates that the two can communicate.

As seen in this example, the test suite and the testing framework provide
several helpers as documented below.

### Async Tests

Tests follow standard `pytest` conventions. However, due to the asynchronous
nature of messaging and SDK calls, most tests will likely need to `await` a
promise and must be marked as asynchronous, e.g.:

```python
@pytest.mark.asyncio
async def test_method():
	await some_async_call()
```

### Marking Features

Tests are grouped as "features" to meaningfully group functionality. For
instance, a group of tests or feature can be created to show that an agent is
capable of fulfilling at least one role of a protocol.

Assigning tests to features is done through `pytest` marks. A single test can be
marked with an annotation:

```python
@pytest.mark.asyncio
@pytest.mark.features('my_feature')
async def test_method():
	await some_async_call()
```

Multiple features can be assigned with a single mark:

```python
@pytest.mark.asyncio
@pytest.mark.features('my_feature', 'my_other_feature')
async def test_method():
	await some_async_call()
```

A python class can also be marked in the same manner, allowing all tests
belonging to that class to be marked with a single annotation:

```python

@pytest.mark.features('my_feature')
class MyTestClass:

	@pytest.mark.asyncio
	async def test_method_marked_with_my_feature(self):
		await some_async_call()

	@pytest.mark.asyncio
	async def test_another_method_also_marked_with_my_feature(self):
		await some_async_call()
```

Python modules can be marked by setting the `pytestmark` variable at the root of
the module:

```python

pytestmark = [
	pytest.mark.features('my_feature')
]


@pytest.mark.asyncio
async def test_method_marked_with_my_feature():
	await some_async_call()

@pytest.mark.asyncio
async def test_another_method_also_marked_with_my_feature():
	await some_async_call()
```

### Test Ordering

In some cases it is useful to explicitly order test execution. This ordering
does not represent dependencies in the tests themselves but rather just an
ordering that logically follows; for example, tests for a connection protocol
may be configured to execute first as an agent that fails to connect is unlikely
to pass later tests.

Tests are ordered based on priority where higher priorities occur first.
Priority is set using a `pytest` mark. Setting priority follows the same rules
for tests, classes, and modules as noted above in [Marking
Fixtures](#Marking-Fixtures).

Example:

```python
@pytest.mark.asyncio
@pytest.mark.features('my_feature')
@pytest.mark.priority(10)
async def test_method():
	await some_async_call()
```

The above test will be executed strictly after all tests with priority greater
than 10, in an undefined order (most likely alphabetical based on test name) for
other tests with priority equal to 10, and strictly before tests with priority
less than 10.

### Fixtures and Agent

#### Config

`config` is a fixture that can be pulled into any test method by including
`config` in the parameter list. This grants access to options configured in your
`config.toml`.

#### Agent

`agent` is also a fixture that can be pulled into any test method by including
`agent` in the parameter list. You will likely need `agent` for every test as
this is how you will interacted with the agent under test. The agent fixture
does _not_ refer to the agent you're testing but rather to the agent internal to
the test suite. This agent holds a wallet, maintains transport level
connections, and enables the sending and receiving of messages in the test
suite.

#### Agent Methods

The following are methods of `agent` that will aid in testing.

##### Agent.send

Send an agent message to a specified recipient.

- **Arguments:**
	- `msg: Message` - the message to be sent
	- `to_key: str` - the Verkey of the recipient

- **Keyword Arguments:**
	- `to_did: str` - the DID of the recipient
	- `from_key: str` - the Verkey of the sender ("our Verkey"). Including this
		argument results in an "auth-crypted" encryption envelope for the
		message.  Omitting this argument results in an "anon-crypted" encryption
		envelope.
	- `service: dict` - A dictionary containing the service info of the intended
		recipient. This is expected to contain a `serviceEndpoint` key-value
		pair.

- **Usage:** When only the required arguments are given, the agent attempts to look
	up service information in the wallet from the `to_key`'s metadata. If a
	`to_did` is given, the agent attempts to look up service information in the
	wallet from the `to_did`'s metadata. If `service` is provided, that service
	information is used and no look up is attempted in the wallet. Giving
	`from_key` only affects whether the resulting message is "auth-" or
	"anon-crypted."

##### Agent.expect_message

Wait for a message of a given type.

- **Arguments:**
	- `msg_type: str` - the type of message to wait for
	- `timeout: int` - the number of seconds to wait
- **Returns** `Message` - the message received

##### Agent.sign_field

Sign a field of a message.

- **Arguments:**
	- `my_vk: str` - the corresponding verkey of the sigkey to use to sign `field`
	- `field: dict` - the field to sign
- **Returns** `dict` - signed field

##### Agent.unpack_signed_field

Unpack a signed field.

- **Arguments:**
	- `signed_field: dict` - the output of `sign_field`
- **Returns** `dict` - the field as it was before signing
- **Usage:** this method asserts that the signature can be verified.

##### Agent.ok

Assert that nothing has halted in the test suite's agent.

### Message Schemas

The test suite makes use of a [flexible schema library][2] to define the
expected structure of messages sent and received by the agent. The test suite
provides a wrapper, `MessageSchema`, around these schemas to make use with agent
messages more straightforward.

`MessageSchema` can be found in [`protocol_tests/__init__.py`][4].

For examples of how to use `MessageSchema`, see [`test_simple_messaging.py`][3]
and [`connection/test_manual.py`][5].  Refer to [the documentation][2] for
general usage of the Schema library.

[2]: https://github.com/keleshev/schema
[3]: protocol_tests/test_simple_messaging.py
[4]: protocol_tests/__init__.py
[5]: protocol_tests/connection/test_manual.py
