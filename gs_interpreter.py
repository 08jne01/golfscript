import collections
from gs_codeblock import *
from gs_operator import *
import copy

class Interpreter:
    def __init__(self, txt):
        code = CodeBlock(txt)
        self.call_stack = [code]

        self.stack = [None]*500
        self.sp = -1
        self.bracket_stack = []

        self.symbols = {
            "~" : op_bit_not,
            "`" : op_str,
            "!" : op_not,
            "@" : op_rot,
            "$" : op_cmv, #partial
            "+" : op_add,
            "-" : op_sub,
            "*" : op_mul,
            "/" : op_div,
            "%" : op_mod,
            "|" : op_bit_or,
            "&" : op_bit_and,
            "^" : op_bit_xor,
            "[" : op_opb,
            "]" : op_clb,
            "\\": op_swp,
            ":" : op_asn,
            ";" : op_pop,
            "<" : op_lt,
            ">" : op_gt,
            "=" : op_eq,
            "," : op_arr, #partial
            "." : op_dup,
            "?" : op_pow, #partial
            "(" : op_dec,
            ")" : op_inc,
            "and" : CodeBlock("1$if"),
            "or"  : CodeBlock("1$\\if"),
            "xor" : CodeBlock("\\!!{!}*"),
            "print" : op_print,
            "p" : CodeBlock("`puts"),
            "n" : "\n",
            "puts" : CodeBlock("print n print"),
            "rand" : op_rand,
            "do" : op_do,
            "while" : op_while,
            "until" : op_until,
            "if"    : op_if,
            "abs"   : op_abs,
            "zip"   : op_zip,
            "base"  : op_base, #partial
        }

        self.default_symbols = copy.deepcopy(self.symbols)

    def stack_frame(self):
        return self.call_stack[-1]

    def call(self,block):
        new_block = copy.deepcopy(block)

        if isinstance(new_block, CodeBlock):
            self.call_stack.append(new_block)
        else:
            self.call_stack.append(CodeBlock(str(new_block)))

    def top(self):
        return self.stack[self.sp]

    def push(self, item):
        self.sp += 1
        self.stack[self.sp] = copy.deepcopy(item)

    def push_value(self, item):
        if not isinstance(item, str):
            self.push(item)
        elif str.isnumeric(item.lstrip('-')):
            self.push(int(item))
        elif item[0] == '\'' or item[0] == '\"':
            self.push(item.strip('\'\"'))
        else:
            pass

    def pop(self):
        self.sp -= 1


    def execute_instruction(self):
        if not self.call_stack:
            return False

        item = self.stack_frame().get_next_item(self.top())

        if item == None:
            self.call_stack.pop()
        else:
            if isinstance(item,CodeBlock):
                if item.immediate:
                    self.call(item)
                else:
                    self.push(item)
            elif isinstance(item, collections.abc.Hashable) and item in self.symbols:
                translation = self.symbols[item]

                if callable(translation):
                    translation(self)
                elif isinstance(translation, CodeBlock):
                    self.call(translation)
                else:
                    self.push(translation)

            else:
                self.push_value(item)

        return True

    def execute(self):
        while self.call_stack:
            self.execute_instruction()
        return self.stack[:self.sp+1]

    def done(self):
        return len(self.call_stack) == 0

    def get_current_instruction(self):

        if not self.call_stack:
            return None

        current_block = self.stack_frame()
        return current_block.get_current_instruction()