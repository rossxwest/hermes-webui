from api.openui_prompt import openui_prompt_fragment

WEBUI = {"source": "webui", "session_id": "s1"}
OTHER = {"source": "telegram", "session_id": "s1"}


def test_fragment_present_for_webui_when_enabled():
    out = openui_prompt_fragment(True, WEBUI)
    assert "```openui" in out
    assert "## Syntax Rules" in out
    assert "Card(" in out               # component spec is included
    # the bundle's conflicting intro must be stripped:
    assert "ENTIRE response must be valid openui-lang" not in out


def test_fragment_empty_when_flag_off():
    assert openui_prompt_fragment(False, WEBUI) == ""


def test_fragment_empty_for_non_webui_surface():
    assert openui_prompt_fragment(True, OTHER) == ""


def test_fragment_empty_when_surface_missing():
    assert openui_prompt_fragment(True, None) == ""
