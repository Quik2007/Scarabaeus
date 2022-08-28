import os
import pytest

def test_import():
    global scarabaeus
    import scarabaeus

    assert scarabaeus


def test_simple_plugins():
    plugin_type = scarabaeus.PluginType(
        "Addon", {"str": "Some string", "list": ["list", 1, 2, 3]}, "test_addons/"
    )
    plugin_type.load("test_addon_1")
    plugin_type.load_all()
    assert len(plugin_type.plugins) == len(
        [
            addon
            for addon in os.listdir("test_addons")
            if os.path.isfile("test_addons/" + addon)
        ]
    )
    assert plugin_type.data["str"] == "Changed string by an addon"  # does not work at the moment, described in Issue #4

if __name__ == "__main__":
    def main():
        tests = []
        for name, value in globals().items():
            if name.startswith("test"):
                tests.append(value)
        for test in tests:
            test()
    main()