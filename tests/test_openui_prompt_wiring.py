from api.streaming import _webui_ephemeral_system_prompt

WEBUI = {"source": "webui", "session_id": "s1"}


def test_ephemeral_includes_openui_for_webui_when_enabled():
    out = _webui_ephemeral_system_prompt(
        None, surface_context=WEBUI, config_data={"experimental": {"openui": True}})
    assert "```openui" in out
    assert "## Syntax Rules" in out


def test_ephemeral_omits_openui_when_disabled_default():
    out = _webui_ephemeral_system_prompt(
        None, surface_context=WEBUI, config_data={})
    assert "openui" not in out.lower()


def test_ephemeral_omits_openui_for_non_webui_surface_even_if_enabled():
    out = _webui_ephemeral_system_prompt(
        None, surface_context={"source": "telegram"},
        config_data={"experimental": {"openui": True}})
    assert "openui" not in out.lower()


def test_disabled_output_unchanged_by_this_feature():
    # The ephemeral prompt with the flag off must equal the prompt computed with
    # an explicitly-empty experimental block (no openui contribution either way).
    a = _webui_ephemeral_system_prompt(None, surface_context=WEBUI, config_data={})
    b = _webui_ephemeral_system_prompt(None, surface_context=WEBUI,
                                       config_data={"experimental": {"openui": False}})
    assert a == b
    assert "openui" not in a.lower()
