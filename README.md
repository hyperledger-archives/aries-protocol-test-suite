Aries Protocol Test Suite
=========================

# REPOSITORY STATUS: Archived

**This repository has been archived. In its place, we recommend you use the [Aries Agent Test Harness] instead.
The latest Aries Agent Test Harness test run results can be seen at this site: [https://aries-interop.info].**

--------------

[Aries Agent Test Harness]: https://github.com/hyperledger/aries-agent-test-harness
[https://aries-interop.info]: https://aries-interop.info

## Introduction

The Aries Protocols Test Suite, or **APTS** for short, allows you to test your agent for Aries compatibility.

## Prerequisites

* docker version 19.03.8 or later
* docker-compose version 1.25.4 or later
* git version 2.24.2 or later

## How to test your agent

This section describes how to automate the testing of your agent using APTS.

### Getting started

1. Clone the `aries-protocol-test-suite` locally if you have not already done so:

   ```
   git clone git@github.com:hyperledger/aries-protocol-test-suite.git
   ```

2. Build the docker containers

   ```
   cd aries-protocol-test-suite
   docker-compose build
   ```
   
3. Start the local ledger

   ```
   docker-compose up -d ledger
   ```
   
4. Run the Aries Protocol Test Suite

   ```
   docker-compose up apts
   ```
   
   This run will fail ending with output similar to the following:
   
   ```
   apts      | =========================== short test summary info ============================
   apts      | FAILED protocol_tests/connection/test_connection.py::test_connection_started_by_tested_agent
   apts      | !!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
   apts      | ======================= 1 failed, 9 deselected in 0.11s ========================
   apts exited with code 1
   ```
   
   The reason that it failed is because APTS does not yet know how to communicate with your agent.  This is the subject of the next two sections.
   
### Integrating APTS into your agent's repository

Integrating APTS into your agent's repository may vary based upon how your agent's repository is structured.  You may adapt these instructions accordingly for your agent.

Let `<AGENT_DIR>` be your agent's local repository directory.

1. Copy the `aries-protocol-test-suite/apts` directory to `<AGENT_DIR>/apts`.

2. Set the name and version of your agent by editing `<AGENT_DIR>/apts/src/config.toml` file and changing these lines near the bottom of the file.

    ```
    name = "AGENT UNDER TEST"
    version = "1.0.0"
    ```
    
    You do not need to change anything else in `config.toml` now; however, you should familiarize yourself with the configuration options.
    
3. If you do not already have a local ledger container for your agent, copy the `aries-protocol-test-suite/ledger` directory to `<AGENT_DIR>/ledger`.

4. Create or customize the `<AGENT_DIR>/docker-compose.yml` file.

   If you do not already have an `<AGENT_DIR>/docker-compose.yml` file, create it by copying the one from `aries-protocol-test-suite/docker-compose.yml`.  Then add one or more service entries required to run your agent.
   
   If you already have an `<AGENT_DIR>/docker-compose.yml` file, add and customize the `apts` and optionally the `ledger` services from the `aries-protocol-test-suite/docker-compose.yml` file.
   
5. Ensure that you can build and run APTS from your agent's repository as you did from the aries-protocol-test-suite repository.
   
   ```
   docker-compose build apts ledger
   docker-compose up -d ledger
   docker-compose up apts
   ```
   
   The output of the final command in which you ran APTS should be the same as before.
   
   Next, let's customize APTS to communicate with your agent.

### Customizing APTS to communicate with your agent

In order to customize APTS to communicate with your agent, you will need to modify the `<AGENT_DIR>/apts/src/aut.py` file.  This file contains many methods which are specific to the AUT (Agent Under Test) and therefore need to be implemented as seen by the following lines:

```
raise Exception("TODO: implement")
``` 

In order to methodically work your way through implementing one method at a time, you can see which method is required next by APTS by looking at the output from your run.

For example, your initial output will be similar to the following:

```
apts      |     async def setup(self, config, suite):
apts      |         """
apts      |         Here is where you perform any setup required to run the test suite to communicate with your AUT (Agent Under Test).
apts      |         This includes resetting the state of your AUT from any previous runs.
apts      |         """
apts      |         print("Setup: config: {}".format(config))
apts      | >       raise Exception("TODO: implement")
apts      | E       Exception: TODO: implement
apts      | 
apts      | aut.py:23: Exception
apts      | ---------------------------- Captured stdout setup -----------------------------
apts      | Setup: config: {'host': 'apts', 'port': 4000, 'endpoint': 'http://apts:4000', 'backchannel': 'aut.AUTBackchannel', 'provider': 'indy_provider.IndyProvider', 'ledger_name': 'local', 'ledger_url': 'http://ledger:8000/sandbox/pool_transactions_genesis', 'seed': '000000000000000000000000STEWARD1', 'tests': ['connections.*', 'issue-credential.*', 'present-proof.*'], 'subject': {'name': 'AGENT UNDER TEST', 'version': '1.0.0', 'endpoint': 'http://apts:4001'}, 'save_path': None}
```

Therefore, the first method to implement is the `setup` method.  This is where you perform anything necessary in order to setup and reset the state of your AUT.

Also note the `Setup: config: ` values under the `Captured stdout setup` section which you may use.  If needed, other config values may be added to the `<AGENT_DIR>/apts/src/config.toml` file in order to setup your agent.

After you have implemented the `setup` method, re-run the test suite as follows and look at the output to see which method to implement next:

```
docker-compose up apts
```

Iteratively continue this process until all tests run successfully.

Once complete, congratulations!  You are ready to run APTS in your CI/CD pipeline.


## Running Locally

If you prefer not using docker for some reason, this section describes how to run APTS locally.

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

To list available tests without running the test suite:
```sh
$ protocoltest --collect-only --list
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

## Writing Tests

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
