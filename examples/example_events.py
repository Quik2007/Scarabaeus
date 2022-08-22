from src.scarabaeus import EventHandler

eventHandler = EventHandler(allow_unregistered_events=True)

@eventHandler.event(event_name="on_test")
def ping(a, r=""):
    print(a, r)

eventHandler.call("on_test", "b", r="w")