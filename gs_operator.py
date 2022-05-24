from gs import *
from gs_codeblock import *
import gs_utils
import operator as op
import copy
import random

coersion_priority = {
            int : 0,
            list : 1,
            str : 2,
            CodeBlock : 4 
}

def convert_int(other_type : type, x : int):
    if other_type == list:
        return [x]
    else:
        return other_type(x)


convert_map = {
    int : convert_int
}

not_assignable = {
    ":" : True,
    "{" : True,
    "}" : True,
    "#" : True,
}

def convert(other_type,value):
    if type(value) in convert_map:
        return convert_map[type(value)](other_type, value)
    else:
        return other_type(value)

def coerce(first,second):
    first_priority = coersion_priority[type(first)]
    second_priority = coersion_priority[type(second)]

    if first_priority > second_priority:
        second = convert(type(first),second)
    elif second_priority > first_priority:
        first = convert(type(second),first)
    return first,second

def check_type(self,top,second):
    return isinstance(self.stack[self.sp], top) and isinstance(self.stack[self.sp-1], second)

def sets(self):
    return set(self.stack[self.sp]), set(self.stack[self.sp-1])

# Operate on two
def oper2(self,fnc,should_coerce=True):
    first = self.stack[self.sp-1]
    second = self.stack[self.sp]

    if should_coerce:
        first,second = coerce(first,second)

    result = fnc(first,second)
    self.sp -= 1
    self.stack[self.sp] = result

def cmp(self, fnc):
    oper2(self,fnc)
    self.stack[self.sp] = int(self.stack[self.sp])

def op_bit_not(self):
 
    if isinstance(self.top(), str):
        self.call(self.top())
        self.sp -= 1
    elif isinstance(self.top(), CodeBlock):
        self.call(self.top())
        self.sp -= 1
    elif isinstance(self.top(), list):
        popped_list = self.top()
        for i,x in enumerate(popped_list):
            self.stack[self.sp+i] = x
        self.sp += i
    else:
        self.stack[self.sp] = ~self.top()

def op_str(self):

    if isinstance(self.top(), list):
        s = []
        for i in self.stack[self.sp]:
            if isinstance(i,str):
                s.append("\'{}\'".format(i))
            else:
                s.append(str(i))
        self.stack[self.sp] = '[' + ' '.join(s) + ']'
    elif isinstance(self.top(), str):
        self.stack[self.sp] = '\"' + str(self.stack[self.sp]) + '\"'
    else:
        self.stack[self.sp] = str(self.stack[self.sp])



def op_not(self):
    if self.top() == "" or self.top() == [] or self.top() == 0:
        self.stack[self.sp] = 1
    else:
        self.stack[self.sp] = 0
    

def op_rot(self):
    i0 = self.stack[self.sp]
    i1 = self.stack[self.sp - 1]
    i2 = self.stack[self.sp - 2]

    self.stack[self.sp] = i2
    self.stack[self.sp-1] = i0
    self.stack[self.sp-2] = i1

def op_cmv(self):
    if isinstance(self.top(), int):
        idx = self.top()
        result = self.stack[self.sp - 1 - idx]
        self.stack[self.sp] = result
    elif isinstance(self.top(), CodeBlock):
        raise NotImplementedError   
    elif isinstance(self.top(), str):
        result = sorted(self.top())
        self.stack[self.sp] = ''.join(result)
    else:
        result = sorted(self.top())
        self.stack[self.sp] = result

def op_add(self):
    oper2(self,op.__add__)

def op_sub(self):

    if check_type(self,list,list):
        new_list = list(filter(lambda x: x not in self.top(), self.stack[self.sp-1]))
        self.sp -= 1
        self.stack[self.sp] = new_list
    else:
        oper2(self,op.__sub__)

def op_mul(self):
    if check_type(self,CodeBlock,int):
        pass
    elif check_type(self,int,CodeBlock):
        loop = For(self.stack[self.sp-1], self.top())
        self.call(loop)
        self.sp -= 2
    elif check_type(self,CodeBlock,list):
        loop = ForEach(self.top(), self.stack[self.sp-1])
        self.call(loop)
        self.sp -= 2
    elif check_type(self,CodeBlock,str):
        loop = ForEach(self.top(), gs_utils.convert_str_list(self.stack[self.sp-1]))
        self.call(loop)
        self.sp -= 2
    elif check_type(self,list,list):
        result = gs_utils.list_join(self.top(), self.stack[self.sp-1])
        self.sp -= 1
        self.stack[self.sp] = result
    elif check_type(self,str,str):
        result = self.top().join(self.stack[self.sp-1])
        self.sp -= 1
        self.stack[self.sp] = result
    elif check_type(self,str,list):
        result = self.top().join([gs_utils.to_string(e) for e in self.stack[self.sp-1]])
        self.sp -= 1
        self.stack[self.sp] = result
    else:
        oper2(self,op.__mul__,False)

def op_div(self):

    if isinstance(self.top(), CodeBlock):
        #loop = ForEach(self.frame(), self.stack[self.sp-1], self.top())
        #self.push_loop(loop)
        loop = ForEachFold(self.top(), self.stack[self.sp-1])
        self.call(loop)
        self.sp -= 2
        op_opb(self)
    elif check_type(self, int, list):
        result = gs_utils.list_div(self.stack[self.sp-1],self.top())
        self.sp -= 1
        self.stack[self.sp] = result
    elif check_type(self, str, str):
        result = self.stack[self.sp-1].split(self.stack[self.sp])
        self.sp -= 1
        self.stack[self.sp] = result
    else:
        oper2(self,op.__floordiv__,False)

def op_mod(self):
    if check_type(self, int, int):
        result = self.stack[self.sp - 1] % self.top()
        self.sp -= 1
        self.stack[self.sp] = result
    elif check_type(self, str, str):
        result = self.stack[self.sp-1].split(self.stack[self.sp])
        self.sp -= 1
        self.stack[self.sp] = list(filter(lambda x: x != '', result))
    elif check_type(self, int, list):
        result = self.stack[self.sp-1][::self.stack[self.sp]]
        self.sp -= 1
        self.stack[self.sp] = result
    elif check_type(self, CodeBlock, list):
        loop = Map(self.top(), self.stack[self.sp-1])
        self.call(loop)
        self.sp -= 2

def op_bit_or(self):
    if check_type(self,list,list):
        set1,set2 = sets(self)
        self.sp -= 1
        self.stack[self.sp] = list(set1 | set2)
    else:
        result = self.stack[self.sp] | self.stack[self.sp-1]
        self.sp -= 1
        self.stack[self.sp] = result

def op_bit_and(self):
    if check_type(self,list,list):
        set1,set2 = sets(self)
        self.sp -= 1
        self.stack[self.sp] = list(set1 & set2)
    else:
        result = self.stack[self.sp] & self.stack[self.sp-1]
        self.sp -= 1
        self.stack[self.sp] = result

def op_bit_xor(self):
    if check_type(self, list,list):
        set1,set2 = sets(self)
        self.sp -= 1
        self.stack[self.sp] = list(set1 ^ set2)
    else:
        result = self.stack[self.sp] ^ self.stack[self.sp-1]
        self.sp -= 1
        self.stack[self.sp] = result

def op_opb(self):
    self.bracket_stack.append(self.sp + 1)

def op_clb(self):
    start = self.bracket_stack.pop()
    arr = []
    for i in range(start,self.sp+1):
        arr.append(self.stack[i])

    if len(arr) > 0:
        self.sp = start
        self.stack[self.sp] = arr

def op_swp(self):
    tmp = self.stack[self.sp]
    self.stack[self.sp] = self.stack[self.sp - 1]
    self.stack[self.sp - 1] = tmp

def op_asn(self):
    keyword = self.stack_frame().get_next_item(self.top())

    if keyword not in not_assignable:
        self.symbols[keyword] = self.top()

def op_pop(self):
    if self.sp >= 0:
        self.sp -= 1

def op_lt(self):

    if check_type(self, int, list):
        self.stack[self.sp-1] = self.stack[self.sp-1][:self.top():]
        self.sp -= 1
    elif check_type(self, int, CodeBlock):
        s = ''.join(self.stack[self.sp-1].tokens)[:self.top():]
        self.stack[self.sp-1].tokens = tokenise(s)[0]
        self.sp -= 1
    else:
        cmp(self,op.__lt__)

def op_gt(self):

    if check_type(self, int, list):
        self.stack[self.sp-1] = self.stack[self.sp-1][self.top()::]
        self.sp -= 1
    elif check_type(self, int, CodeBlock):
        s = ''.join(self.stack[self.sp-1].tokens)[self.top()::]
        self.stack[self.sp-1].tokens = tokenise(s)[0]
        self.sp -= 1
    else:
        cmp(self,op.__gt__)

def op_eq(self):
    if check_type(self, int, list):
        size = len(self.stack[self.sp-1])
        if self.top() >= size:
            return

        if self.top() < -size:
            return

        self.stack[self.sp-1] = self.stack[self.sp-1][self.top()]
        self.sp -= 1
    elif check_type(self, int, CodeBlock):
        s = ''.join(self.stack[self.sp-1].tokens)

        size = len(s)
        if self.top() >= size:
            return

        if self.top() < -size:
            return

        self.stack[self.sp-1] = ord(s[self.top()])
        self.sp -= 1
    else:
        cmp(self,op.__eq__)

def op_arr(self):
    if check_type(self,CodeBlock,list):
        loop = MapCondition(self.top(), self.stack[self.sp-1])
        self.call(loop)
        self.sp -= 2
    elif isinstance(self.top(), list):
        self.stack[self.sp] = len(self.top())
    else:
        self.stack[self.sp] = list(range(self.stack[self.sp]))

def op_dup(self):
    cpy = copy.deepcopy(self.stack[self.sp])
    self.sp += 1
    self.stack[self.sp] = cpy

def op_pow(self):
    if check_type(self, int, int):
        oper2(self, op.__ipow__)
    elif check_type(self, list, int):
        self.stack[self.sp].index(self.stack[self.sp-1])
    elif check_type(self, list, CodeBlock):
        raise NotImplementedError

    raise TypeError

def op_dec(self):
    
    if isinstance(self.top(), list):
        x = self.top()[0]
        self.stack[self.sp] = self.top()[1:]
        self.sp += 1
        self.stack[self.sp] = x
    else:
        self.stack[self.sp] -= 1


def op_inc(self):
    if isinstance(self.top(), list):
        x = self.top()[-1]
        self.stack[self.sp] = self.top()[:-1]
        self.sp += 1
        self.stack[self.sp] = x
    else:
        self.stack[self.sp] += 1 

def op_print(self):
    print(str(self.stack[self.sp]), end='')
    self.sp -= 1   

def op_rand(self):
    upto = self.stack[self.sp]
    value = random.randrange(upto)
    self.stack[self.sp] = value

def op_do(self):
    code = self.stack[self.sp]
    self.call(Do(code))
    self.sp -= 1

def op_while(self):
    condition = self.stack[self.sp-1]
    code = self.stack[self.sp]
    self.call(WhileBlock(condition, code))
    self.sp -= 2

def op_until(self):
    condition = self.stack[self.sp-1]
    code = self.stack[self.sp]
    self.call(UntilBlock(condition, code))
    self.sp -= 2


def op_if(self):
    first = self.stack[self.sp-1]
    second = self.stack[self.sp]
    condition = self.stack[self.sp-2]

    if not not condition:
        self.call(first)
    else:
        self.call(second)
    
    self.sp -= 3 

def op_abs(self):
    self.stack[self.sp] = abs(self.stack[self.sp])

def op_zip(self):

    if isinstance(self.top(), list):
        arr = list(zip(*self.stack[self.sp]))

        for i,v in enumerate(arr):
            arr[i] = list(v)
            try:
                arr[i] = ''.join(v)
            except:
                pass

        self.stack[self.sp] = arr

def op_base(self):
    if isinstance(self.stack[self.sp-1], list):
        s = ''.join(str(e) for e in self.stack[self.sp-1])
        result = int(s, self.stack[self.sp])
        self.sp -= 1
        self.stack[self.sp] = result
    else:
        raise NotImplementedError