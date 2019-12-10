Aries Protocol Test Suite
=========================

Quickstart Guide
----------------

### Requirements

- Python 3.6 or higher


### Installing and configuring the test suite

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

# Backchannel module
backchannel = "default.ManualBackchannel"

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


### Running the test suite

Now that you have your configuration file, you can now run the test suite
with:
```sh
$ apts
```

Use `apts --help` to see more options (the following is a shortened list; most
`pytest` command line options are also usable):
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

A manually operated backchannel is included by default with the test suite. To
run tests using this backchannel, the `-s` option must be specified, i.e.:

```sh
$ apts -s
```
This will prevent `pytest` from capturing `stdin` and `stdout`.


#### Listing available tests

To list available tests without running the test suite:
```sh
$ apts --collect-only --list
```


#### Selecting tests

Test selection can be done through the configuration file or with the `-S`
option. The `-S` takes a regular expression as an argument and selects tests
based on whether the test name matches that expression.

```sh
$ apts -S connections.*inviter.*
```
