import os
import sys

import pytest

sys.path.append("../")

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
    assert plugin_type.shared["str"] == "Changed string by an addon"
