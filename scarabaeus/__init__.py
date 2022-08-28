import importlib
import importlib.util
import os
import types
from typing import Callable, Optional


class InvalidPlugin(Exception):
    """Raised when a plugin is not valid, so there is an invalid path or plugin class inside"""
    def __init__(self, msg, plugin, plugin_path):
        self.plugin_name = plugin
        self.plugin_path = plugin_path
        super().__init__(msg)


class InvalidPluginDirectory(Exception):
    """Raised when the load directory of a PluginType is not valid"""
    def __init__(self, dir):
        self.directory = dir
        super().__init__("The plugin directory '" + dir + "' is not valid.")


class PluginInfo:
    """Information about a plugin and data it has access to"""

    name: str
    type: "PluginType"
    shared: dict
    event_handler: list["EventHandler"]
    human_name: Optional[str]
    description: str = ""
    author: str = ""
    version: str = ""
    dependencies: list[str]

    def __init__(
        self,
        cls: "Plugin",
        name: str,
        type: "PluginType",
        shared: dict,
        event_handler: Optional["EventHandler"] = [],
    ):
        self.name = name
        self.human_name = cls.human_name if hasattr(cls, "human_name") else self.name
        self.description = cls.description if hasattr(cls, "description") else ""
        self.author = cls.author if hasattr(cls, "author") else ""
        self.version = cls.version if hasattr(cls, "version") else ""
        self.dependencies = cls.dependencies if hasattr(cls, "dependencies") else []
        self.type = type
        self.shared = shared
        self.event_handler = event_handler


class PluginType:
    def __init__(self, name: str,
        shared: dict = {},
        load_path: Optional[str] = None,
        event_handler=None,
    ):
        self.name, self.shared, self.load_path = (
            name,
            shared,
            load_path if not load_path or load_path.endswith("/") else load_path + "/",
        )
        self.plugins = {}
        self.event_handler = event_handler

    def load(
        self,
        plugin_name: Optional[str] = None,
        file_name: Optional[str] = None,
        full_path: Optional[str] = None,
        module_path: Optional[str] = None,
    ):
        if (
            bool(plugin_name) + bool(file_name) + bool(full_path) + bool(module_path)
            != 1
        ):
            raise TypeError(
                "PluginType.load() needs exactly one of these parameters: plugin_name, file_name, full_path or module_path"
            )
        if not isinstance(plugin_name or file_name or full_path or module_path, str):
            raise TypeError(
                "One of plugin_name, file_name, full_path or module_path has to be of type 'str' not '"
                + str(type(plugin_name or file_name or full_path or module_path))
                + "'"
            )
        # Resolving module path of plugin
        if plugin_name:
            file_name = plugin_name + ".py"
        if file_name:
            full_path = (self.load_path if self.load_path else "") + file_name
        if full_path and not plugin_name:
            plugin_name = full_path.split("/")[-1][:-3]
        if plugin_name in self.plugins:
            return
        if not os.path.isfile(full_path):
            raise InvalidPlugin(
                "Plugin named '"
                + plugin_name
                + "' at '"
                + full_path
                + "' does not exist.",
                plugin_name,
                full_path,
            )
        if module_path:
            module = importlib.import_module(module_path)
        else:
            spec = importlib.util.spec_from_file_location(plugin_name, full_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        # Getting & Checking plugin
        plugin = getattr(module, self.name, None)
        if not plugin:
            raise InvalidPlugin(
                "Plugin "
                + plugin_name
                + " does not contain a class named '"
                + self.name
                + "'",
                plugin_name,
                full_path,
            )
        if not issubclass(plugin, Plugin):
            raise InvalidPlugin(
                "The class named '"
                + self.name
                + "' in the plugin '"
                + plugin_name
                + "' is not a subclass of Plugin",
                plugin_name,
                full_path,
            )
        # Plugin setup
        plugin.__prepare__(plugin, plugin_name, self, self.shared, self.event_handler)

        for n in self.shared:
            setattr(plugin, n, self.shared[n])
        self.plugins[plugin_name] = plugin()

    def load_all(self):
        if not os.path.exists(self.load_path):
            os.mkdir(self.load_path)
        elif not os.path.isdir(self.load_path):
            raise
        for f in os.listdir(self.load_path):
            if (
                os.path.isfile(self.load_path + "/" + f)
                and len(f) > 3
                and f[-3:] == ".py"
                and not f.startswith("__")
            ):
                self.load(file_name=f)


class Plugin:
    plugin_info: PluginInfo
    """This class should not be called directly, use PluginType instead."""

    def __prepare__(
        cls,
        file_name: str,
        plugin_type: PluginType,
        shared: dict,
        event_handler: "EventHandler" = None,
    ):
        cls.plugin_info = PluginInfo(cls, file_name, plugin_type, shared, event_handler)
        if event_handler:
            # Adding the listeners
            event_triggered = [
                attribute
                for attribute in dir(cls)
                if callable(getattr(cls, attribute))
                and attribute.startswith("__") is False
                and getattr(getattr(cls, attribute), "__event_triggered__", None)
            ]
            for method_name in event_triggered:
                method = getattr(cls, method_name)
                method.__plugin_listener__ = cls  # The plugin
                cls.plugin_info.event_handler.__funcs__[method] = method.__events__
                for event in method.__events__:
                    if (
                        not cls.plugin_info.event_handler.allow_unregistered_events
                        and event not in cls.plugin_info.event_handler.events
                    ):
                        raise EventDoesNotExist(event)
                    try:
                        cls.plugin_info.event_handler.events[event].append(method)
                    except KeyError:
                        cls.plugin_info.event_handler.events[event] = [method]
        for n in shared:
            setattr(cls, n, shared[n])
            print(id(shared[n]))
        for plugin_name in cls.plugin_info.dependencies:
            plugin_type.load(plugin_name)

    def __repr__(self):
        return f"{self.plugin_info.type.name} '{self.plugin_info.human_name}' ({self.plugin_info.name})"

    def require(self, plugin_name):
        if plugin_name not in self.plugin_info.dependencies:
            self.plugin_info.type.load(plugin_name=plugin_name)
            self.plugin_info.dependencies.append(plugin_name)

    # This belongs to the events part
    @classmethod
    def event(cls, event_name=None):
        """A decorator to use events in a plugin subclass"""

        def decorator(fn):
            if event_name and not isinstance(event_name, types.FunctionType):
                _event_name = event_name
            else:
                _event_name = fn.__name__
            fn.__event_triggered__ = True
            try:
                fn.__events__.append(_event_name)
            except AttributeError:
                fn.__events__ = [_event_name]
            return fn

        if not isinstance(event_name, types.FunctionType):
            return decorator
        else:
            return decorator(event_name)


#
#  Events
#   ~ easy to use, feature rich & using decorators
#


class EventAlreadyExists(Exception):
    def __init__(self, event_name):
        self.event_name = event_name
        super().__init__("'" + event_name + "' already exists.")


class EventDoesNotExist(Exception):
    def __init__(self, event_name):
        self.event_name = event_name
        super().__init__("'" + event_name + "' does not exist.")


class EventHandler:
    def __init__(self, allow_unregistered_events: bool, events: list = []):
        self.allow_unregistered_events = allow_unregistered_events
        self.events = {}
        for event in events:
            self.events[event] = []
        self.__funcs__ = {}
        self.__plugin_types__ = []

    def add(self, *event_names: str):
        for event_name in event_names:
            if not isinstance(event_name, str):
                raise TypeError("event_name has to be a str")
            if event_name in self.events:
                raise EventAlreadyExists(event_name)
            self.events[event_name] = []

    def call(self, event_name: str, *args, **kwargs):
        if not isinstance(event_name, str):
            raise TypeError("event_name has to be a str")
        if not self.allow_unregistered_events and event_name not in self.events:
            raise EventAlreadyExists(event_name)
        if event_name not in self.events:
            return

        for func in self.events[event_name]:
            if hasattr(func, "__plugin_listener__"):
                plugins = func.__plugin_listener__.__plugin_type__.plugins
                for plugin_name in plugins:
                    if isinstance(plugins[plugin_name], func.__plugin_listener__):
                        plugin = plugins[plugin_name]
                        break
                func(plugin, *args, **kwargs)

            else:
                func(*args, **kwargs)

    def add_listener(self, func: Callable, event_name: Optional[str] = None):
        """Adds a event listener to a function. If event_name is not specified it defaults to the name of the given function"""
        if not event_name:
            event_name = func.__name__
        if not self.allow_unregistered_events and event_name not in self.events:
            raise EventDoesNotExist(event_name)
        try:
            if func in self.events[event_name]:
                return
            self.events[event_name].append(func)
        except KeyError:
            self.events[event_name] = [func]

        try:
            self.__funcs__[func].append(event_name)
        except KeyError:
            self.__funcs__[func] = [event_name]

    def remove_listener(self, func: Callable, event_name: Optional[str] = None):
        """Removes a event listener from a function. If event_name is not specified it removes all event listeners of that function"""
        if not event_name:
            for event in self.__funcs__[func]:
                self.events[event].remove(func)
            del self.__funcs__[func]
        else:
            self.__funcs__[func].remove(event)
            self.events[event].remove(func)

    def event(self, event_name=None):
        def decorator(func):
            self.add_listener(func, event_name)

        if isinstance(event_name, Callable):
            func = event_name
            event_name = None
            return decorator(func)
        if event_name and not isinstance(event_name, str):
            raise TypeError("event_name has to be a str")

        return decorator
