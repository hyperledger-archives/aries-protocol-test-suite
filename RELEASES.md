Version 0.1.0 (2019-07-17)
==========================

This is the initial release of the Aries Protocol Test Suite. Much of the work
here was strongly influenced by the [Indy Agent Test
Suite](https://github.com/hyperledger/indy-agent/tree/master/test_suite). This
test suite supersedes the Indy Agent Test Suite as the Indy Agent community
migrates to the Hyperledger Aries Project.

Tests
-----
- [A simple messaging test between the suite and a static
	agent](protocol_tests/test_simple_messaging.py)
- [Manual connection tests from Indy Agent Test
	Suite](protocol_tests/connection/test_manual.py)

Test Suite Improvements
-----------------------
(Improvements relative to the Indy Agent Test Suite)

- Core of the test suite is now a more fully featured agent
	- Return routing support
	- Improved transport handling
	- Expect messages based on message type (helps reduce false negatives)
