import os, subprocess, tempfile
UIJS = os.path.join(os.path.dirname(__file__), '..', 'static', 'ui.js')

def _extract(name):
    src = open(UIJS, encoding='utf-8').read()
    start = src.find("function %s(" % name)
    assert start >= 0, "%s not found in ui.js" % name
    i = src.find("{", start); depth = 1; i += 1
    while i < len(src) and depth:
        depth += (src[i] == "{") - (src[i] == "}"); i += 1
    return src[start:i]

def _run(js):
    tf = tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8')
    tf.write(js); tf.close()
    try:
        return subprocess.run(["node", tf.name], capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(tf.name)

def test_card_html_has_sandboxed_iframe():
    js = _extract("_openuiCardHTML") + "\nprocess.stdout.write(_openuiCardHTML('NONCE123'));\n"
    out = _run(js)
    assert 'sandbox="allow-scripts"' in out
    assert 'allow-same-origin' not in out          # opaque-origin isolation must hold
    assert '/static/vendor/openui/host.html' in out
    assert 'data-nonce="NONCE123"' in out
    assert 'class="openui-card"' in out

def test_nonce_is_nonempty_and_varies():
    js = _extract("_openuiNonce") + "\nprocess.stdout.write(_openuiNonce()+'\\n'+_openuiNonce());\n"
    a, b = _run(js).strip().split("\n")
    assert a and b and a != b
