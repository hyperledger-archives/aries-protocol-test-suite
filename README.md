Aries Protocol Test Suite
=========================

Quickstart Guide
----------------

### Requirements

- docker (version 19.03.1 or greater)
- docker-compose (version 1.24.1 or greater)
- git
- make

### Configuring and running the Protocol Test Suite manually

After cloning this repository, to build the docker images:
```sh
$ make build
```
This will take a while the first time.

To start the docker containers:
```sh
$ make start
```
This starts two images:

1. test-suite
   This is what runs the test suite.

2. ledger-indy
   A test indy ledger used by the IndyProvider.
   Other non-indy providers may be added as needed.

To login to and run the test-suite manually:
```sh
$ make login
# cp config.sample.toml config.toml
# run-tests
```

To list available tests without running the test suite:
```sh
# protocoltest --collect-only --list
```

Use `protocoltest --help` to see more options:
```
Aries Protocol Test Suite Configuration:
  --sc=SUITE_CONFIG, --suite-config=SUITE_CONFIG
                        Load suite configuration from SUITE_CONFIG
  -S SELECT_REGEX, --select=SELECT_REGEX
                        Run tests matching SELECT_REGEX. Overrides tests
                        selected in configuration.
  -O PATH, --output=PATH
                        Save interop profile to PATH.
  -L, --list            List available tests.
```

To stop the docker containers (after exiting the docker login above):
```sh
$ make stop
```

## Writing your own backchannel ##

In order to automate the protocol test suite to run against your agent, you must implement a backchannel 
that knows how to communicate with your agent to perform certain actions.  This section describes
how to write your own backchannel.

We assume that you are logged into the test-suite container.  Replace ORG below with the name
of your company or organization.

1. Copy `default.py` to `ORG.py`.

2. Edit `ORG.py` and change `ManualBackchannel` to `ORGBackChannel`.

3. Edit `config.toml` and customize appropriately including:
   
   1. Change `default.ManualBackchannel` to `ORG.ORGBackchannel`.

   2. Customize the `[config.subject]` section such as the `endpoint` variable to point to
      your agent.

4. Execute `run-tests`.  This will run your new ORGBackChannel class, but still manually.

5. Re-implement each of the functions in a way that is specific to your agent and does not require any manual action.
   You can do this iteratively, re-running the tests as you go.

6. Once you have finished re-implementing all functions, add support for other protocol families as defined in
   `protocol_tests` sub-directories.  You can just search for all `backchannel.py` files in these
   sub-directories which are named according the protocol family.  For example, see `protocol_tests/issue_credential/backchannel.py`
   for the issue-credential protocol family.
   
## Adding the Protocol Test Suite to your CI (Continous Integration) ##

In the github repository for your agent, create a directory structure similar to the following.
The files `config.toml` and `ORG.py` were described in the previous section.

```
aries-test/
   dockerfile
   src/
      config.toml  
      ORG.py
```

The contents of `dockerfile` are as follows:
```
FROM aries-protocol-test-suite

ADD src /test-suite
```
The `aries-protocol-test-suite` image must be built locally if running locally, or published to a docker registry to which your CI has access.

TODO: Need to publish to dockerhub.

## Writing more tests

A simple example of a protocol test can be found in
[`test_simple_messaging.py`][3]. This test uses the test suite backchannel to
send and receive a simple test ping message and response.

### Async Tests
Tests follow standard `pytest` conventions. However, due to the asynchronous
nature of messaging and SDK calls, most tests will likely need to `await` a
promise and must be marked as asynchronous, e.g.:

```python
@pytest.mark.asyncio
async def test_method():
	await some_async_call()
```

### Assigning Test Meta Information
Tests are assigned meta information to help with test selection and
interoperability profile reporting. To assign meta information to a test, use
the `meta` decorator from the [`reporting`](reporting.py) module:

```python
@pytest.mark.asyncio
@meta(protocol='test', version='1.0', role='initiator', name='test-this')
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
