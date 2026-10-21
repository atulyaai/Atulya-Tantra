"""A reply printed as a JSON object is never shown or spoken raw (LOG.md gate run 2: news leak)."""
from tools.plugins.brain.textcalls import TextCallFilter


def _run(chunks):
    stream = TextCallFilter()
    shown = "".join(stream.feed(chunk) for chunk in chunks)
    calls, rest = stream.finish()
    return shown, calls, rest


def test_reasoning_only_json_is_dropped():
    shown, calls, rest = _run(['  {"reasoning": "The user is asking', ' for news, use get_news"}'])
    assert shown == "" and calls == [] and rest == ""


def test_truncated_reasoning_json_is_not_released_on_finish():
    for chunks in ([ '{"reasoning": "private unfinished reasoning' ],
                   ['{"analysis": ', '"private", "answer": "unfinished']):
        assert _run(chunks) == ("", [], "")


def test_json_with_answer_speaks_only_the_answer():
    shown, calls, rest = _run(['{"reasoning": "x", "answer": "Here are the headlines."}'])
    assert shown == "" and rest == "Here are the headlines."


def test_json_call_becomes_a_tool_call():
    _shown, calls, rest = _run(['{"name": "get_news", "arguments": {"limit": 3}}'])
    assert [(c.name, c.arguments) for c in calls] == [("get_news", '{"limit": 3}')] and rest == ""


def test_text_starting_with_brace_but_not_json_is_released():
    shown, calls, rest = _run(["{not json} but a real sentence."])
    assert shown + rest == "{not json} but a real sentence." and calls == []


def test_normal_text_streams_immediately_and_later_braces_are_fine():
    stream = TextCallFilter()
    assert stream.feed("Here is ") == "Here is "
    assert stream.feed('{"a": 1} as JSON.') == '{"a": 1} as JSON.'
    assert stream.finish() == ([], "")
