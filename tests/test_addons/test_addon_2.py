import sys; sys.path.append("../")
import scarabaeus


class Addon(scarabaeus.Plugin):
    def __init__(self):
        print("Plugin 2")
        # self.require("test_addon_1") # ends up with cyclic import, described in Issue #3
        print(id(self.str))
        self.str = "Changed string by an addon"
        print(id(self.str))
