import gs_interpreter
import gs_debugger

import sys

from curses import wrapper

def run_debugger(txt):
    wrapper(gs_debugger.main, txt)

def run(txt):
    interpreter = gs_interpreter.Interpreter(txt)
    result = interpreter.execute()
    print(result)


if __name__ == "__main__":
    with open("test.gs","r") as f:
        txt = f.read()
        run_debugger(txt)

        