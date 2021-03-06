import copy

def tokenise(txt,dbg=0):
    import re
    pattern = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*|'(?:\\.|[^'])*'?|\"(?:\\.|[^\"])*\"?|-?[0-9]+|#[^\n\r]*|.")

    tokens = []
    tokens_index = []
    for m in re.finditer(pattern,txt):
        start = m.start(0)
        end = m.end(0)
        tokens.append(txt[start:end])
        tokens_index.append((start,end))

    result = []
    txt_index = []

    for index,token in enumerate(tokens):
        if token[0] != '#':
            result.append(token)
            txt_index.append(tokens_index[index])

    return (result,txt_index)

class CodeBlock:
    def __init__(self,tokens, immediate=False):
        
        self.immediate = immediate
        if isinstance(tokens, str):
            self.tokens,self.txt_index = tokenise(tokens)
        else:
            self.tokens,self.txt_index = tokens


        self.ip = 0

    def __eq__(self, other):
        if isinstance(other,CodeBlock):
            return self.tokens == other.tokens
        else:
            return False

    def __add__(self, other):
        return CodeBlock((self.tokens + other.tokens, self.txt_index + other.txt_index))

    def get_next_item(self, top):

        if self.ip >= len(self.tokens):
            return None

        current_token = self.tokens[self.ip]

        if current_token == '{':
            return self.find_block()
        else:
            self.ip += 1
            return current_token

    def find_block(self):
        bracket_count = 0

        for i,v in enumerate(self.tokens[self.ip:]):
            if v == '{':
                bracket_count += 1
            elif v == '}':
                bracket_count -= 1
            
            if bracket_count == 0:
                min_idx = self.ip+1
                max_idx = self.ip+i
                tokens = (self.tokens[min_idx:max_idx], self.txt_index[min_idx:max_idx])
                block = CodeBlock(tokens)
                self.ip += i + 1
                return block

        raise Exception("Missing Bracket")

    def get_ip(self):
        return self.ip

    def set_ip(self,ip):
        self.ip = ip

    def get_current_instruction(self):
        if self.ip >= len(self.tokens):
            return None
        return self.txt_index[self.ip]

    def __str__(self):
        return '{' + ''.join(self.tokens) + '}'

    def __repr__(self):
        #return str(self.tokens[self.ip:])
        return self.__str__()

    def get_registers(self):
        obj = [
            ("code", self.__str__()),
            ("instruction_pointer", self.ip)
        ]
        return obj

class For(CodeBlock):
    def __init__(self, code : CodeBlock, number : int):
        self.max = number
        self.number = number
        self.code = copy.deepcopy(code)

        self.code.immediate = True

    def get_next_item(self,top):
        if self.number > 0:
            self.number -= 1
            return self.code
        else:
            return None

    def get_ip(self):
        return self.max - self.number

    def set_ip(self,ip):
        pass

    def __str__(self):
        return "ForBlock: {}".format(self.number)

    def get_current_instruction(self):
        return None

    def get_registers(self):
        obj = [
            ("code", self.code),
            ("count", self.number)
        ]
        return obj


class ForEach(CodeBlock):
    def __init__(self, code : CodeBlock, item : list, pop = 1):
        self.item = item
        self.max = len(item)
        self.code = copy.deepcopy(code)
        self.code.immediate = True
        
        self.fold = False
        self.push_code = False
        self.popped = 0
        self.pop = pop

    def get_ip(self):
        return self.max - len(self.item)

    def set_ip(self,ip):
        pass

    def get_next_item(self,top):
        if self.push_code:
            self.push_code = False
            return self.code
        elif len(self.item) > 0:
            if self.popped >= self.pop:
                self.push_code = True
            self.popped += 1
            return self.item.pop(0)
        else:
            return None

    def __str__(self):
        return "ForEachBlock: {}".format(self.item)

    def get_current_instruction(self):
        return None

    def get_registers(self):
        obj = [
            ("code", self.code),
            ("items", self.item),
            ("pushing_code", self.push_code),
            ("fold",self.fold)
        ]
        return obj

class ForEachFold(ForEach):
    def get_next_item(self,top):
        if self.push_code:
            self.push_code = False
            return self.code
        elif len(self.item) > 0:
            self.push_code = True
            return self.item.pop(0)
        elif not self.fold:
            self.fold = True
            return CodeBlock(']', True)
        else:
            return None

    def __str__(self):
        return "ForEachFold: {}".format(self.item)

    def get_current_instruction(self):
        return None

class ComplexCodeBlock(CodeBlock):
    def __init__(self, start : list, sequence : list, end : list):
        self.ip = 0
        self.start = start
        self.sequence = sequence
        self.sequence_done = self.sequence == None
        self.end = end

    def get_ip(self):
        return 0

    def set_ip(self,ip):
        pass

    def get_current_instruction(self):
        return None

    def get_next_item(self,top):
        if self.start:
            return self.start.pop(0)(top)
        elif self.sequence and not self.sequence_done:
            
            sequence_result = self.sequence[self.ip](top)
            self.sequence_done = sequence_result == None
            self.ip = (self.ip + 1) % len(self.sequence)

            if sequence_result != None:
                return sequence_result
            elif self.end:
                return self.end.pop(0)(top)
            else:
                return None

        elif self.end:
            return self.end.pop(0)(top)
        else:
            return None

    def get_registers(self):
        obj = [
            ("code", self.code),
            ("items", self.item),
            ("start_code", self.start),
            ("sequence_code", self.sequence),
            ("sequence_ptr",self.ip),
            ("end_code", self.end),
        ]
        return obj

    def __str__(self):
        return "ComplexCodeBlock"

#Map the code onto the list keeping the list
class Map(ComplexCodeBlock):
    def __init__(self, code : CodeBlock,item : list):
        self.code = copy.deepcopy(code)
        self.code.immediate = True
        self.item = copy.deepcopy(item)

        start = [lambda top : CodeBlock('[', True)]
        sequence = [self.pop_list,self.map_code]
        end = [lambda top : CodeBlock(']', True)]
        super().__init__(start,sequence,end)

    def pop_list(self,top):
        if self.item:
            return self.item.pop(0)
        return None

    def map_code(self,top):
        return self.code

    def __str__(self):
        return "MapBlock"

class MapCondition(Map):
    def __init__(self, code : CodeBlock, item : list):
        super().__init__(code, item)
        self.original = copy.deepcopy(item)

        self.end.append(self.examine_conditions)
        self.end.append(self.swap)

    def examine_conditions(self,top):
        self.new_arr = []
        for i,v in enumerate(top):
            if v:
                self.new_arr.append(self.original[i])

        #Pop the old array
        return CodeBlock(';', True)

    def swap(self, top):
        return self.new_arr

    def __str__(self):
        return "MapBlockConditional"



class Do(CodeBlock):
    def __init__(self,code : CodeBlock):
        self.code = copy.deepcopy(code)
        self.code.tokens += ';' #add pop
        self.code.immediate = True

    def get_next_item(self,top):
        if top:
            return self.code
        else:
            return None

    def get_ip(self):
        return 0

    def set_ip(self,ip):
        pass

    def get_registers(self):
        obj = [
            ("condition", self.code)
        ]
        return obj

    def __str__(self):
        return "Do"

    def get_current_instruction(self):
        return None

class WhileBlock(CodeBlock):
    def __init__(self,condition : CodeBlock,code : CodeBlock):
        self.condition = copy.deepcopy(condition)
        self.code = copy.deepcopy(code)
        self.is_condition = True

        self.condition.tokens += ';' #add pop

        self.code.immediate = True
        self.condition.immediate = True

    def get_ip(self):
        return 0

    def set_ip(self,ip):
        pass

    def check_condition(self, top):
        return not not top

    def get_next_item(self, top):
        if self.is_condition:
            self.is_condition = False
            return self.condition
        elif self.check_condition(top):
            self.is_condition = True
            return self.code
        else:
            return None

    def __str__(self):
        return "WhileBlock"

    def get_current_instruction(self):
        return None

    def get_registers(self):
        obj = [
            ("code", self.code),
            ("condition", self.condition),
            ("processing_condition", self.is_condition)
        ]
        return obj

class UntilBlock(WhileBlock):
    def check_condition(self, top):
        return not top

    def __str__(self):
        return "UntilBlock"

    def get_current_instruction(self):
        return None