Aries Protocol Test Suite
=========================

Quickstart Guide
----------------

### Requirements

- Python 3.6 or higher

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
# HTTP Server options
host = "localhost"
port = 3000

# Endpoint reported to other agents
endpoint = "http://localhost:3000"

# List of regular expressions used to select tests.
# If a test name matches at least one regex in this list, it will be selected
# for execution.
tests = [
    "connections*",
]

[config.subject]
# Name and version reported in interop profile
name = "MyAgent"
version = "1.0.0"
# Endpoint used for backchannel
endpoint="http://localhost:3001"
```

Now that you have your configuration file, you can now run the test suite
with:
```sh
$ protocoltest
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

Writing Tests
-------------
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
