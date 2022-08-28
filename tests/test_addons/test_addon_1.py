import sys; sys.path.append("../")
import scarabaeus


class Addon(scarabaeus.Plugin):
    dependencies = ["test_addon_2"]
