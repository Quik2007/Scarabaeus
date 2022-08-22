import scarabaeus


class App:
    def __init__(self):
        self.thing = "A thing in your app!"
        self.event_handler = scarabaeus.EventHandler(allow_unregistered_events=False)
        plugin_type = scarabaeus.PluginType(
            "Plugin", {"app": self}, "examples/plugins", self.event_handler
        )
        self.event_handler.add("on_test")
        plugin_type.load_all()
        self.event_handler.call("on_test")
        print(self.event_handler.events)


if __name__ == "__main__":
    App()
