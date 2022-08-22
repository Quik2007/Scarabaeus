import scarabaeus

event_handler = scarabaeus.EventHandler(False)
event_handler.add("on_simple_event")
plugin_type = scarabaeus.PluginType(
    "Addon",
    shared={"a": "Irgendein Text"},
    load_path="plugins",
    event_handler=event_handler,
)
plugin_type.load_all()
print(plugin_type.plugins)


@event_handler.event("on_simple_event")
def my_event_listener(arg):
    print("Hi!", arg)


event_handler.call("on_simple_event", "Hö")
