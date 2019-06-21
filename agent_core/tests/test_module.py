import pytest

from agent_core.module import Module, route_def, Semver, InvalidModule

def test_module_def():

    class TestModule(Module):
        DOC_URI = 'test_doc_uri/'
        PROTOCOL = 'test_protocol'
        VERSION = '1.0'

    assert TestModule.version == '1.0'
    assert TestModule.normalized_version == '1.0.0'
    assert TestModule.version_info == Semver(1, 0, 0)
    assert TestModule.protocol == 'test_protocol'
    assert TestModule.doc_uri == 'test_doc_uri/'
    assert TestModule.qualified_protocol == 'test_doc_uri/test_protocol'
    assert TestModule.protocol_identifer_uri == 'test_doc_uri/test_protocol/1.0.0'


def test_module_missing_attrs():

    with pytest.raises(InvalidModule):
        class TestModule1(Module):
            DOC_URI = 'test_doc_uri/'
            PROTOCOL = 'test_protocol'

    with pytest.raises(InvalidModule):
        class TestModule2(Module):
            DOC_URI = 'test_doc_uri/'
            VERSION = '1.0'

    with pytest.raises(InvalidModule):
        class TestModule3(Module):
            PROTOCOL = 'test_protocol'
            VERSION = '1.0'

def test_module_routes_transfered_to_instance():

    class TestModule(Module):
        DOC_URI = 'test_doc_uri/'
        PROTOCOL = 'test_protocol'
        VERSION = '1.0'

        TYPE_STEM = DOC_URI + PROTOCOL + '/' + VERSION + '/'

        routes = {}

        @route_def(routes, TYPE_STEM + 'testing')
        async def tesing(self, agent, msg, *args, **kwargs):
            pass

    instance = TestModule()
    assert instance.routes
