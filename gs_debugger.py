from curses import wrapper
import curses
import gs_interpreter
import textwrap


def main(screen, txt):
    dbg = Debugger(screen,txt)
    dbg.main()

class Debugger:
    def __init__(self, screen, txt):
        self.screen = screen
        
        self.interpreter = gs_interpreter.Interpreter(txt)
        self.txt = txt

        self.running = False

        self.call_stack = []

        self.create_windows()

        self.update_windows()


    def create_windows(self):

        h,w = self.screen.getmaxyx()

        call_stack_width = int(w * 0.3)

        self.call_stack_win = curses.newwin(h, call_stack_width, 0, 0)

        text_width = 50
        self.text_win = curses.newwin(h,text_width,0,call_stack_width)

        stack_width = w - (call_stack_width+text_width) -1
        self.stack_win = curses.newwin(h,stack_width,0,call_stack_width+text_width)

    def update_windows(self):
        self.update_call_stack_win()
        self.update_text_win()
        self.update_stack_win()

    def update_stack_win(self):
        self.stack_win.clear()
        h,w = self.stack_win.getmaxyx()

        y = 0
        for item in self.interpreter.stack[:self.interpreter.sp+1]:

            self.stack_win.addstr(h-1-y, 0, "-"*(w-1))
            y+=1

            lines = textwrap.wrap(str(item), w)
            for line in reversed(lines):
                self.stack_win.addstr(h-1-y, 0, line)
                y += 1

            

        self.stack_win.refresh()

    def update_call_stack_win(self):
        self.call_stack_win.clear()
        h,w = self.call_stack_win.getmaxyx()

        y = 0
        for fnc in self.interpreter.call_stack:

            self.call_stack_win.addstr(h-1-y, 0, "-"*(w-1))
            y+=1

            lines = textwrap.wrap(str(fnc), w)
            for line in reversed(lines):
                self.call_stack_win.addstr(h-1-y, 0, line)
                y += 1

            

        self.call_stack_win.refresh()

    def update_text_win(self):
        self.text_win.clear()

        pos = self.interpreter.get_current_instruction()

        self.text_win.move(0,0)

        for i,c in enumerate(self.txt):

            if pos != None and i >= pos[0] and i < pos[1]:
                self.text_win.addch(c, curses.A_UNDERLINE)
            else:
                self.text_win.addch(c)
        
        self.text_win.refresh()
        
    def main(self):
        while self.interpreter.call_stack:
            key = self.text_win.getkey()
            self.interpreter.execute_instruction()
            self.update_windows()


        
