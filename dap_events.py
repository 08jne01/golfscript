class Command:
    def __init__(self, obj):
        self.obj = obj

    def __getitem__(self,key):
        return self.obj[key]

    def command_type(self):
        return self.obj["command"]

    def raw(self):
        return self.obj

    def response(self,body=None,msg='success'):
        success = True
        if msg != 'success':
            success = False

        obj = {
            "type" : "response",
            "request_seq" : self.obj["seq"],
            "success" : success,
            "command" : self.command_type(),
            "message" : msg
        }

        if body:
            obj["body"] = body

        return obj


class Event:
    def __init__(self, event_type):
        self.obj = {
            "type" : "event",
            "event" : event_type,
        }

    def set_body(self,obj):
        self.obj["body"] = obj

    def event(self):
        return self.obj

def stop_event(reason):
    event = Event('stopped')
    event.set_body({
        "reason" : reason,
        "allThreadsStopped" : True,
        "threadId" : 0,
        "text" : "Stopped!"
    })

    return event