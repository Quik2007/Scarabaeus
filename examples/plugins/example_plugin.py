class Plugin:
    # All of this information is optional and automatically generated if not set
    human_name = "The example plugin"  # The hman-readable version of the name, which will be used for users, defaults to file name without .py
    description = "Some short plugin description"
    author = "Some author"
    version = "1.0"
    dependencies = ["other_plugin"]

    def __init__(self):
        print(self.plugin_info)
