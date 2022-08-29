"""
Scarabaeus
Plugins and events in Python. Done right.
"""
import importlib
import importlib.util
import os
from typing import Callable, List, Optional, Type
from types import FunctionType, ModuleType


class InvalidPlugin(Exception):
    """Raised when a plugin is not valid, so there is an invalid path or plugin class inside"""
    def __init__(self, msg: str, plugin: str, plugin_path: str | None = None):
        self.plugin_name = plugin
        self.plugin_path = plugin_path
        super().__init__(msg)

class InvalidPluginDirectory(Exception):
    """Raised when the load directory of a PluginType is not valid"""
    def __init__(self, directory: str):
        self.directory = directory
        super().__init__("The plugin directory '" + directory + "' is not valid.")

class PluginAlreadyLoaded(Exception):
    """Raised when a plugin is already loaded"""
    def __init__(self, plugin: str):
        self.plugin_name = plugin
        super().__init__("The plugin '"+plugin+"' is already loaded.")


class Data:
    """A class that represents shared data, for example between plugins."""
    def __init__(self, name = None, dict: dict = None, **data) -> None:
        self.__data_name__ = name if name else self.__name__
        self.__dict__ |= dict if dict else {} | data 

    def __getitem__(self, item):
        return self.__getattribute__(item)

    def __setitem__(self, item, value) -> None:
        self.__setattr__(item, value)

def __get_as_data_list__(object: Data | dict | list[Data] | dict[str, dict]) -> list:
    if object == None:
        return []
    if isinstance(object, Data):
        return [object]
    if isinstance(object, dict):
        return [Data(name = "data", dict = object)]
    return object

def __set_data_attributes__(cls, datalist:list[Data]):
    for data in datalist:
        setattr(cls, data.__data_name__, data)

class PluginInfo:
    """Information about a plugin and data it has access to"""

    name: str
    type: "PluginType"
    shared: list[Data]
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
        shared: list[Data],
        event_handler: Optional["EventHandler"] = None,
    ):
        self.name = name
        self.human_name = cls.human_name if hasattr(cls, "human_name") else self.name
        self.description = cls.description if hasattr(cls, "description") else ""
        self.author = cls.author if hasattr(cls, "author") else ""
        self.version = cls.version if hasattr(cls, "version") else ""
        self.dependencies = cls.dependencies if hasattr(cls, "dependencies") else []
        self.type = type
        self.shared = shared
        self.event_handler = event_handler if event_handler else []

class Plugin:
    """A plugin of a certain PluginType.
    You should not call this directly, use PluginType instead"""
    plugin_info: PluginInfo

    @classmethod
    def __prepare__(
        cls,
        file_name: str,
        plugin_type: "PluginType",
        shared: list[Data] | Data | dict,
        event_handler: "EventHandler" = None,
    ):
        # Setting the plugin info TODO give plugin info as parameter
        cls.plugin_info = PluginInfo(cls, file_name, plugin_type, shared, event_handler)
        
        # Adding the event listeners
        if event_handler:
            event_triggered = [
                attribute
                for attribute in dir(cls)
                if isinstance(getattr(cls, attribute), FunctionType)
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
        # Preparing the shared data
        datalist = __get_as_data_list__(shared)
        __set_data_attributes__(cls, datalist)
        
        # Loading the dependencies
        for plugin_name in cls.plugin_info.dependencies:
            plugin_type.load(plugin_name)

    def __repr__(self):
        return f"{self.plugin_info.type.name} '{self.plugin_info.human_name}' ({self.plugin_info.name})"

    def require(self, plugin_name):
        """Declares a plugin as a dependency and loads it eventually"""
        if plugin_name not in self.plugin_info.dependencies:
            self.plugin_info.type.load(plugin_name=plugin_name)
            self.plugin_info.dependencies.append(plugin_name)

    # This belongs to the events part
    @classmethod
    def event(cls, event_name=None):
        """A decorator to use events in a plugin subclass"""

        def decorator(func):
            if event_name and not isinstance(event_name, FunctionType):
                _event_name = event_name
            else:
                _event_name = func.__name__
            func.__event_triggered__ = True
            try:
                func.__events__.append(_event_name)
            except AttributeError:
                func.__events__ = [_event_name]
            return func

        if not isinstance(event_name, FunctionType):
            return decorator
        else:
            return decorator(event_name)


class PluginType:
    """A type of plugin that can be defined in your application."""
    def __init__(self, name: str,
                shared_data: Data | dict | List[Data | dict] = None,
                load_path: Optional[str] = None,
                event_handler: Optional["EventHandler"] = None,
            )-> None :
        self.name, self.shared, self.load_path = (
            name,
            __get_as_data_list__(shared_data),
            load_path if not load_path or load_path.endswith("/") else load_path + "/",
        )
        __set_data_attributes__(self, self.shared)
        self.plugins = {}
        self.event_handler = event_handler

    def __validate_plugin__(self, plugin: Plugin | None, name: str, full_path: str | None = None) -> None:
        """Validates if a plugin is usable"""
        if not plugin:
            raise InvalidPlugin(
                "Plugin "
                + name
                + " does not contain a class named '"
                + self.name
                + "'",
                name,
                full_path,
            )
        if not issubclass(plugin, Plugin):
            raise InvalidPlugin(
                "The class named '"
                + self.name
                + "' in the plugin '"
                + name
                + "' is not a subclass of Plugin",
                name,
                full_path,
            )

    def __get_plugin_module__(self, plugin_name: str | None, file_name: str | None, full_path: str | None, module_path: str | None) -> tuple[str, str, ModuleType]:
        """Gets the plugin class to init"""
        # Validating args
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
        elif module_path and not plugin_name:
            plugin_name = module_path.split(".")[-1]
        if plugin_name in self.plugins:
            raise PluginAlreadyLoaded(plugin_name)
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

        return file_name, full_path, module

    def load(
        self,
        plugin_name: Optional[str] = None,
        file_name: Optional[str] = None,
        full_path: Optional[str] = None,
        module_path: Optional[str] = None,
        module: Optional[ModuleType] = None,
        plugin: Optional[Type[Plugin]] = None
    ):
        """Loads a plugin by one of plugin name, file name (in load_path), full path, module path, module or plugin (class)"""
        if not plugin:
            if not module:
                try:
                    file_name, full_path, module = self.__get_plugin_module__(plugin_name, file_name, full_path, module_path)
                except PluginAlreadyLoaded:
                    return
            plugin = getattr(module, self.name, None)
        elif not plugin_name:
            raise TypeError("load() has to have both plugin and plugin_name given.")
        self.__validate_plugin__(plugin, plugin_name, full_path)
        # Plugin setup
        plugin.__prepare__(plugin_name, self, self.shared, self.event_handler)

        self.plugins[plugin_name] = plugin()

    def load_all(self, directory = None):
        """Loads all plugins of this type in a given directory or the default load_path of the plugin type"""
        if not directory:
            directory = self.load_path
        if not os.path.exists(directory):
            os.mkdir(directory)
        elif not os.path.isdir(directory):
            raise InvalidPluginDirectory(directory)
        for file in os.listdir(directory):
            if (
                os.path.isfile(directory + "/" + file)
                and len(file) > 3
                and file[-3:] == ".py"
                and not file.startswith("__")
            ):
                self.load(file_name=file)


#
#  Events
#   ~ easy to use, feature rich & using decorators
#


class EventAlreadyExists(Exception):
    """Raised when an event already exists."""
    def __init__(self, event_name):
        self.event_name = event_name
        super().__init__("'" + event_name + "' already exists.")


class EventDoesNotExist(Exception):
    """Raised when an event does not exist and allow_unregistered_events is not enabled."""
    def __init__(self, event_name):
        self.event_name = event_name
        super().__init__("'" + event_name + "' does not exist.")


class EventHandler:
    """The class to use when interacting with events, adding or removing or listening to them."""
    def __init__(self, allow_unregistered_events: bool, events: list = None):
        self.allow_unregistered_events = allow_unregistered_events
        self.events = {}
        if events:
            for event in events:
                self.events[event] = []
        self.__funcs__ = {}
        self.__plugin_types__ = []

    def add(self, *event_names: str):
        """Adds an event to this event handler. Only needen when allow_unregistered events is False."""
        for event_name in event_names:
            if not isinstance(event_name, str):
                raise TypeError("event_name has to be a str")
            if event_name in self.events:
                raise EventAlreadyExists(event_name)
            self.events[event_name] = []

    def call(self, event_name: str, *args, **kwargs):
        """Calls an event with the given name and arguments for listening functions."""
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
        """A decorator that is used to listen to events."""
        def decorator(func):
            self.add_listener(func, event_name)

        if isinstance(event_name, Callable):
            func = event_name
            event_name = None
            return decorator(func)
        if event_name and not isinstance(event_name, str):
            raise TypeError("event_name has to be a str")

        return decorator
