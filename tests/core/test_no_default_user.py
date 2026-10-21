"""AUDIT S1: memory and history have no default user; forgetting user_id is an error, never the owner's data."""
import inspect

import pytest

from atulya.history import ConversationHistory
from tools.plugins.personal.memory import PersonalMemory


@pytest.mark.parametrize("cls,names", [
    (PersonalMemory, ("remember", "forget", "list", "relevant", "update")),
    (ConversationHistory, ("append", "read", "conversations", "search", "delete")),
])
def test_user_id_is_required_keyword(cls, names):
    for name in names:
        parameter = inspect.signature(getattr(cls, name)).parameters["user_id"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, name
        assert parameter.default is inspect.Parameter.empty, name


def test_missing_user_id_fails(project_temp_dir):
    memory = PersonalMemory(project_temp_dir)
    memory.remember("web", "the owner likes mango", user_id="admin")
    with pytest.raises(TypeError):
        memory.list("web")
    with pytest.raises(TypeError):
        memory.forget("web", "mango")
    assert memory.list("web", user_id="admin")
