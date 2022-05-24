import code
from decimal import Clamped
import socket
import json
import re
import threading
import os
import copy
from gs_codeblock import CodeBlock

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
        self.condition = threading.Condition()


    def send_msg(self, obj):
        #self.message_queue.append(obj)
        self.send(obj)

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
                    raise OSError
                self.command_queue.append(self.process_message(data))
                self.condition.acquire()
                self.condition.notify_all()
                self.condition.release()
                
            except OSError:
                self.wait_for_client()
            except Exception as e:
                print(e)

    def send(self, obj):
        if not self.conn:
            return

        try:
            msg = json.dumps(obj)
            msg = "Content-Length: {}\r\n\r\n{}".format(len(msg), msg)
            self.conn.send(msg.encode('utf8'))
        except Exception as e:
            print(e)
        
        
    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(10.0)
        self.socket.bind((self.host,self.port))
        self.socket.listen()
        self.wait_for_client()
        self.receive_thread = threading.Thread(target=self.receive)
        self.receive_thread.start()

    def wait_for_client(self):

        if self.quit:
            return

        try:
            self.conn,self.client_addr = self.socket.accept()
            print("Connected by {}".format(self.client_addr))
        except socket.timeout:
            self.quit = True
            self.condition.acquire()
            self.condition.notify_all()
            self.condition.release()


    def stop(self):
        self.quit = True
        self.socket.close()
        self.receive_thread.join()



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
            "next" : self.next,
            "variables" : self.variables,
            "setVariable" : self.set_variable
        }

        self.fetch_variables_map = {
            "::built-ins" : self.fetch_built_ins,
            "::stack" : self.fetch_stack,
            "::loop_registers" : self.fetch_loop_registers,
            "::variables" : self.fetch_variables
        }

        self.set_variables_map = {
            "::variables" : self.set_variables
        }

        #Use :: because : is a unsignable character
        self.displayed_variables = ["undefined"]

    def wait(self):
        self.server.condition.acquire()
        result = self.server.condition.wait(10) #wait 10 seconds in case we missing something?
        #print("Notified {}".format(result))

    def run(self):
        while not self.quit and not self.server.quit:
            command = self.server.get_command()

            while command != None:
                if command["command"] in self.command_map:
                    self.command_map[command["command"]](command)
                    if self.quit:
                        return

                command = self.server.get_command()

            if self.interpreter:
                if self.running:
                    self.interpreter.execute_instruction()
                else:
                    self.wait()

                if self.interpreter.done():
                    self.running = False
                    self.finish()
                    #self.quit = True

            else:
                self.wait()


    def has_children(self, obj):
        instance_map = {
            list : True,
            gs_interpreter.CodeBlock : False,
        }

        if type(obj) in instance_map:
            return instance_map[type(obj)]

        return False

    def add_display_variable(self,name):
        if name in self.displayed_variables:
            return self.displayed_variables.index(name)

        idx = len(self.displayed_variables)
        self.displayed_variables.append(name)
        return idx

    def set_variable(self, command):
        reference = command["arguments"]["variablesReference"]
        value = "undefined"
        if reference <= len(self.displayed_variables):
            category_name = self.displayed_variables[reference]   
            if category_name in self.set_variables_map:
                value = self.set_variables_map[category_name](command)

        if isinstance(value, str):
            value = "'" + value + "'"

        self.server.send_msg(command.response({
            "value" : str(value)
        }))

    def set_variables(self, command):
        name = command["arguments"]["name"]
        value = command["arguments"]["value"]
        old = "undefined"
        try:
            old = self.interpreter.symbols[name]
            value = value.replace("\'","\"")
            value = "{ \"result\" : " + value + "}"
            value = json.loads(value)["result"]
            self.interpreter.symbols[name] = value
            return value
        except Exception as e:
            print(e)
        
        return old
        

    def fetch_variables(self):
        variables = []
        for name,value in sorted(self.interpreter.symbols.items()):

            if name in self.interpreter.default_symbols and value == self.interpreter.default_symbols[name]:
                continue 

            if isinstance(value, str):
                value = "'" + value + "'"

            variables.append({
                "name" : name,
                "value" : str(value),
                "variablesReference": 0
            })

        return variables
        

    def fetch_loop_registers(self):
        variables = []

        current_frame = self.interpreter.stack_frame()

        for name,value in current_frame.get_registers():
            variables.append({
                "name" : name,
                "value" : str(value),
                "variablesReference" : 0
            })
        return variables

    def fetch_stack(self):
        variables = []

        sp = max(0,self.interpreter.sp+1)

        for i,item in enumerate(self.interpreter.stack[:sp]):
            variables.append({
                "name" : str(i),
                "value" : str(item),
                "variablesReference" : 0
            })

        return list(reversed(variables))
    
    def fetch_built_ins(self):
        variables = [
            {
                "name" : "stack",
                "value" : str(self.interpreter.stack[:self.interpreter.sp+1]),
                "variablesReference" : self.add_display_variable("::stack")
            },
            {
                "name" : "variables",
                "value" : "<variable table>",
                "variablesReference" : self.add_display_variable("::variables")
            }
        ]

        current_frame = self.interpreter.stack_frame()

        if type(current_frame) != gs_interpreter.CodeBlock:
            variables.append({
                "name" : "Loop Registers",
                "value" : str(current_frame),
                "variablesReference" : self.add_display_variable("::loop_registers")
            })

        return variables

    def create_variables(self,reference):
        if reference >= len(self.displayed_variables):
            return []

        name = self.displayed_variables[reference]

        if name in self.fetch_variables_map:
            return self.fetch_variables_map[name]()
        elif name in self.interpreter.symbols:
            variables = [{
                "name" : name,
                "value" : str(self.interpreter.symbols[name]),
                "variablesReference" : 0
            }]

            return variables

        return []

    def variables(self, command):
        reference = command["arguments"]["variablesReference"]

        self.server.send_msg(command.response({
            "variables" : self.create_variables(reference)
        }))



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
                "variablesReference" : self.add_display_variable("::built-ins"),
                "indexedVariables" : 10,
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

    def finish(self):
        event = dap_events.Event("terminated")
        self.server.send_msg(event.event())

    def disconnect(self,command):
        self.quit = True
        self.server.send_msg(command.response())
        event = dap_events.Event("exited")
        event.set_body({"exitCode" : 0})
        self.server.send_msg(event.event())

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

            #

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
                "instructionPointerReference" : "0x{:06x}".format(self.to_address(i,block.get_ip()))
            }

            if type(block) == gs_interpreter.CodeBlock:
                frame["source"] = {
                        "name" : self.filename,
                        "path" : self.source
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
    print(debugger.interpreter.stack[:debugger.interpreter.sp+1])
    server.stop()
