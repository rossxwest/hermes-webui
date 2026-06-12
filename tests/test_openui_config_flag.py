def test_openui_disabled_by_default():
    import api.config as c
    assert c.is_openui_enabled({}) is False
    assert c.is_openui_enabled(None) is False
    assert c.is_openui_enabled({"experimental": {}}) is False

def test_openui_enabled_via_experimental_key():
    import api.config as c
    assert c.is_openui_enabled({"experimental": {"openui": True}}) is True

def test_openui_requires_exact_true():
    import api.config as c
    assert c.is_openui_enabled({"experimental": {"openui": "yes"}}) is False
    assert c.is_openui_enabled({"experimental": {"openui": 1}}) is False
