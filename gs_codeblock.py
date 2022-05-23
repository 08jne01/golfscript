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
        return str(self.tokens[self.ip:])

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

class UntilBlock(WhileBlock):
    def check_condition(self, top):
        return not top

    def __str__(self):
        return "UntilBlock"

    def get_current_instruction(self):
        return None