"""Read-only diagnostic: is the OpenUI prompt fragment actually being produced
for a given profile's config? Run this with the SAME python that runs the WebUI.

Usage:
  python scripts/openui_diag.py                 # uses the active/default config
  python scripts/openui_diag.py <PROFILE_HOME>  # checks a specific profile home
                                                 # (the dir whose config.yaml the
                                                 #  session reads via
                                                 #  get_config_for_profile_home)

It mutates nothing. It mirrors exactly what _webui_ephemeral_system_prompt does:
is_openui_enabled(cfg) + openui_prompt_fragment(enabled, {'source':'webui'}).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


def main():
    from api.config import is_openui_enabled
    from api.openui_prompt import openui_prompt_fragment, _spec_loaded  # type: ignore

    home = sys.argv[1] if len(sys.argv) > 1 else None
    if home:
        from api.config import get_config_for_profile_home
        cfg = get_config_for_profile_home(home)
        src = "get_config_for_profile_home(%r)" % home
    else:
        from api.config import get_config
        cfg = get_config()
        src = "get_config() [active/default]"

    enabled = is_openui_enabled(cfg)
    frag = openui_prompt_fragment(enabled, {"source": "webui"})

    print("config source        :", src)
    print("experimental block   :", (cfg.get("experimental") if isinstance(cfg, dict) else "<cfg not a dict>"))
    print("vendored spec loaded :", _spec_loaded)
    print("is_openui_enabled    :", enabled)
    print("fragment length      :", len(frag))
    print("fragment present?    :", "YES — agent WILL be taught openui-lang" if frag
          else "NO — agent will NOT receive openui-lang")
    if frag:
        print("--- first 200 chars of the injected fragment ---")
        print(frag[:200])
    else:
        print()
        print("Fix: set the following in THIS profile's config.yaml, then restart the WebUI:")
        print("  experimental:")
        print("    openui: true")
        if not _spec_loaded:
            print("ALSO: the vendored language spec failed to load "
                  "(static/vendor/openui/openui-system-prompt.txt missing?) — "
                  "the fragment is empty regardless of the flag.")


if __name__ == "__main__":
    main()
