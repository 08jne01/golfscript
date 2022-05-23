import socket
import json
import re
import threading
import os
import copy

import gs_interpreter
import dap_events

HOST = "127.0.0.1"
PORT = 65432
pattern = re.compile(r"Content-Length: (\d*)\s+({.+})")


class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.message_queue = []
        self.command_queue = []
        self.quit = False


    def send_msg(self, obj):
        self.message_queue.append(obj)

    def get_command(self):
        if self.command_queue:
            obj =  self.command_queue.pop(0)
            return dap_events.Command(obj)

        return None

    def process_message(self,data):
        data = data.decode()
        result = pattern.match(data)

        length, body = result.groups()

        msg = None
        if len(body) <= int(length):
            msg = json.loads(body)
        else:
            raise Exception("Missing Data")

        return msg

    def receive(self):
        while not self.quit:
            try:
                data = self.conn.recv(1024)
                if not data:
                    return
                self.command_queue.append(self.process_message(data))
            except OSError:
                self.quit = True
            except Exception as e:
                print(e)

    def send(self):
        while not self.quit:
            if self.message_queue:
                try:
                    obj = self.message_queue.pop(0)
                    msg = json.dumps(obj)
                    msg = "Content-Length: {}\r\n\r\n{}".format(len(msg), msg)
                    self.conn.send(msg.encode('utf8'))
                except Exception as e:
                    print(e)
        
        
    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.socket:
            self.socket.bind((self.host,self.port))
            self.socket.listen()

            self.conn,self.client_addr = self.socket.accept()

                #self.receive()
            self.receive_thread = threading.Thread(target=self.receive)
            self.send_thread = threading.Thread(target=self.send)

            self.receive_thread.start()
            self.send_thread.start()


            print("Connected by {}".format(self.client_addr))

    def stop(self):
        self.quit = True
        self.socket.close()
        self.receive_thread.join()
        self.send_thread.join()



class Debugger:
    def __init__(self, server):
        self.interpreter = None
        self.server = server
        self.quit = False
        self.running = False
        self.source = None
        self.run_to_frame = None

        self.command_map = {
            "initialize" : self.initialize,
            "launch" : self.launch,
            "disconnect" : self.disconnect,
            "setBreakpoints" : self.set_breakpoints,
            "setExceptionBreakpoints" : self.set_exception_breakpoints,
            "threads" : self.get_threads,
            "pause" : self.pause,
            "stackTrace" : self.get_callstack,
            "evaluate" : self.evaluate,
            "scopes": self.scopes,
            "disassemble": self.disassemble,
            "stepIn" : self.step_in,
            "stepOut" : self.step_out,
            "next" : self.next
        }

        self.variables = {

        }

    def run(self):
        while not self.quit:
            command = self.server.get_command()
            if command != None and command["command"] in self.command_map:
                self.command_map[command["command"]](command)

            if self.interpreter:
                if self.running:
                    self.interpreter.execute_instruction()

                if self.interpreter.done():
                    event = dap_events.Event("exited")
                    event.set_body({"exitCode" : 0})
                    self.server.send_msg(event.event())
                    self.quit = True

    def step_in(self,command):
        self.server.send_msg(command.response())
        self.interpreter.execute_instruction()
        event = dap_events.stop_event("step")
        self.server.send_msg(event.event())

    def step_out(self,command):
        self.server.send_msg(command.response())
        frame = len(self.interpreter.call_stack) - 1
        while len(self.interpreter.call_stack) > frame:
            self.interpreter.execute_instruction()

        event = dap_events.stop_event("step")
        self.server.send_msg(event.event())

    def next(self,command):
        self.server.send_msg(command.response())
        frame = len(self.interpreter.call_stack)
        self.interpreter.execute_instruction()

        while len(self.interpreter.call_stack) > frame:
            self.interpreter.execute_instruction()

        event = dap_events.stop_event("step")
        self.server.send_msg(event.event())

    def disassemble(self,command):
        address = command["arguments"]["memoryReference"]
        address = int(address,16)

        frame,ip = self.from_address(address)
        
        

        instructions = []

        if frame < len(self.interpreter.call_stack):
            block = copy.deepcopy(self.interpreter.call_stack[frame])
            block.set_ip(0)
            items = []
            item = block.get_next_item(0)
            while item != None:
                items.append(str(item))
                item = block.get_next_item(0)

            offset = 0
            for i,token in  enumerate(items):
                instruction = {
                    "address" : "0x{:06x}".format(self.to_address(frame,offset)),
                    "instruction" : token,
                }

                if i == 0:
                    instruction["location"] = {
                        "name" : self.filename,
                        "path" : self.source
                    }

                instructions.append(instruction)
                offset += len(token)

        self.server.send_msg(command.response({
            "instructions" : instructions
        }))


        

    def scopes(self,command):
        body = {
            "scopes" : [{
                "name" : "built-ins",
                "variablesReference" : 0,
                "indexedVariables" : 1,
                "expensive" : False
            }]
        }

        self.server.send_msg(command.response(body))



    def evaluate(self,command):
        expression =  command["arguments"]["expression"]
        
        result = "undefined"
        if expression in self.interpreter.symbols:
            result = str(self.interpreter.symbols[expression])
        
        self.server.send_msg(command.response({
            "result" : result
        }))


    def get_callstack(self,command):
        start = command["arguments"]["startFrame"]
        levels = command["arguments"]["levels"]

        frames = self.collect_stack_frames(start,levels)

        self.server.send_msg(command.response({
            "stackFrames" : frames,
            #"totalFrames" : len(frames)

        }))

    def pause(self, command):
        self.running = False
        self.server.send_msg(command.response())

        event = dap_events.stop_event("paused")
        self.server.send_msg(event.event())

    def get_threads(self,command):
        self.server.send_msg(command.response({
            "threads" : [{
                "id" : 0,
                "name" : "main",
            }]
        }))

    def set_exception_breakpoints(self,command):
        self.server.send_msg(command.response())

    def set_breakpoints(self,command):
        breakpoints = command["arguments"]["breakpoints"]

        response_breakpoints = []
        for breakpoint in breakpoints:
            breakpoint["verified"] = True
            response_breakpoints.append(breakpoint)

        self.server.send_msg(command.response({
            "breakpoints" : breakpoints
        }))


    def disconnect(self,command):
        self.quit = True
        self.server.send_msg(command.response())

    def launch(self,command):
        script = command["arguments"]["script"]
        self.source = script
        head, self.filename = os.path.split(self.source)
        try:
            f = open(script, "r")
            txt = f.read()
            f.close()
            txt = txt.replace('\r','')
            self.interpreter = gs_interpreter.Interpreter(txt)
            self.text = txt
            self.lines = txt.split('\n')
            self.server.send_msg(command.response()) 

            event = dap_events.Event('initialized')
            self.server.send_msg(event.event())

            self.server.send_msg(dap_events.stop_event('entry').event())
            
            #event = dap_events.Event('stopped')
            #event.set_body({
                #"reason" : "entry"
            #})
            #self.server.send_msg(event.event())

        except IOError:
            self.server.send_msg(command.response(None,'error: file not found'))          

    def initialize(self, command):
        capabilities = {
            "supportsConfigurationDoneRequest" : False,
            "supportsSetVariable" : True,
            "supportsFunctionBreakpoints" : False,
            "supportsConditionalBreakpoints" : False,
            "supportsHitConditionalBreakpoints" : False,
            "supportsEvaluateForHovers" : True,
            "supportsExceptionFilterOptions" : False,
            "supportsSteppingGranularity" : True,
            "supportsBreakpointLocationsRequest" : False,
            "supportsReadMemoryRequest" : True,
            "supportsDataBreakpoints" : False,
            "supportsDisassembleRequest" : True,
            "supportsLogPoints" : False,
            "supportsExceptionInfoRequest" : False,
            "supportsExceptionOptions" : False,
            "supportsExceptionFilterOptions" : False,
        }


        self.server.send_msg(command.response(capabilities))

    def get_line_column2(self,block):
        locations = block.get_current_instruction()

        if locations == None:
            return 0,0

        start,end = locations

        line = self.text[:start].count('\n')

        idx = start
        c = ''
        while c != '\n' and idx >= 0:
            idx -= 1
            c = self.text[idx]

        idx += 1

        column = start - idx

        return line,column

    def to_address(self,frame, ip):
        return frame << 16 | ip

    def from_address(self, address):
        frame = (address & 0xFF0000) >> 16
        ip =    (address & 0x00FFFF)
        return frame,ip

    def collect_stack_frames(self, start, number):
        frames = []

        for i,block in enumerate(self.interpreter.call_stack):

            frame = {
                "id" : i+1,
                "name" : str(block),
                "source" : {
                    "name" : self.filename,
                    "path" : self.source
                },
                "instructionPointerReference" : "0x{:06x}".format(self.to_address(i,block.get_ip()))
            }

            line,column = self.get_line_column2(block)

            frame["line"] = line+1
            frame["column"] = column+1
            #frame["endColumn"] = column[1]+1
            #frame["endLine"] = line
            frames.append(frame)

        return list(reversed(frames))




    


if __name__ == "__main__":
    server = Server(HOST,PORT)
    server.start()
    debugger = Debugger(server)
    debugger.run()
    server.stop()
