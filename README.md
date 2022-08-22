# Scarabaeus

Python plugins and events. Done right.


## Plugins & Plugin types

### Example in a program
```py
import scarabaeus

app_variable = "A text for example"
# Defining a new type of plugin and variables that the plugins of this type should have access to
plugin_type = scarabaeus.PluginType(name="Plugin", shared={"var":app_variable}, load_path="plugins/")
# Loading all plugin files in the load_path directory
plugin_type.load_all()
```

### Example of a plugin
A file in the `plugins/` directory
```py
import scarabaeus

class Plugin(scarabaeus.Plugin):
    def __init__(self):
        # This plugin has access to the variable of the app!
        print(self.var)
```


## Events

### Events in a program
Example:
```py
import scarabaeus

event_handler = scarabaeus.EventHandler(allow_unregistered_events=False)
event_handler.add("on_some_event")


@event_handler.event("on_some_event")
def some_event_listener(some_parameter):
    print(some_parameter)

event_handler.call("on_some_event", "A text that is going to be printed")
```

### Events and plugins

#### EventManager for PluginType
```py
import scarabaeus

event_handler = scarabaeus.EventHandler(allow_unregistered_events=False)
event_handler.add("on_some_event")

app_variable = "A text for example"
plugin_type = scarabaeus.PluginType(name="Plugin", shared={"var":app_variable}, load_path="plugins/", event_handler=event_handler)
plugin_type.load_all()

event_handler.call("on_some_event", "Some text!")
```

#### In plugins

```py
import scarabaeus

class Plugin(scarabaeus.Plugin):
    @scarabaeus.Plugin.event("on_some_event")
    def some_event_listener(self, some_parameter):
        print(some_parameter)
```