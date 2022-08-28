import scarabaeus
class Addon(scarabaeus.Plugin):
    dependencies = ["test_addon_2"]
    def __init__(self):
        print(self.dependencies)