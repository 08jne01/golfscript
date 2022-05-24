import unittest
import gs_interpreter
from gs_codeblock import CodeBlock



class TestInterpreter(unittest.TestCase):
    def check(self, text, result):
        interpreter = gs_interpreter.Interpreter(text)
        test_result =  interpreter.execute()

        if len(test_result) == 1:
            test_result = test_result[0]

        if isinstance(test_result, CodeBlock):
            self.assertEqual(test_result.tokens, result.tokens)
        else:
            self.assertEqual(test_result, result)

    def test_op_bit_not(self):
        self.check("5~", -6)
        self.check("\"1 2+\"~", 3)
        self.check("{1 2+}~", 3)

    def test_op_str(self):
        self.check("1`", "1")
        self.check("[1 [2] 'asdf']`", "[1 [2] 'asdf']")
        self.check("\"1\"`", "\"1\"")
        self.check("{1}`", "{1}")

    def test_op_not(self):
        self.check("1!", 0)
        self.check("{asdf}!", 0)
        self.check("\"\"!", 1)

    def test_op_rot(self):
        self.check("1 2 3 4 @", [1,3,4,2])

    def test_op_cmv(self):
        self.check("1 2 3 4 5 1$", [1,2,3,4,5,4])
        self.check("\'asdf\'$", "adfs")
        self.check("[12 3 5 1]$", [1,3,5,12])
        #self.check("[5 4 3 1 2]{-1*}$", [5, 4, 3, 2, 1])

    def test_op_add(self):
        self.check("5 7+", 12)

        block = CodeBlock("asdf 1234")
        block.tokens.remove(' ')
        self.check("\'asdf\'{1234}+", block)
        self.check("[1 2 3][4 5]+", [1,2,3,4,5])

    def test_op_sub(self):
        self.check("1 2-3+", [1,-1])
        self.check("1 2 -3+", [1,-1])
        self.check("1 2- 3+", 2)

        self.check("[5 2 5 4 1 1][1 2]-", [5, 5, 4])

    def test_op_mul(self):
        self.check("5 7*", 35)
        self.check("2 {2*} 5*", 64)

        self.check("[1 2 3]2*", [1,2,3,1,2,3])
        self.check("3\'asdf\'*", "asdfasdfasdf")

        self.check("[1 2 3]\',\'*","1,2,3")
        self.check("[1 2 3][4]*", [1,4,2,4,3])
        self.check("\'asdf\'\' \'*", "a s d f")
        self.check("[1 [2] [3 [4 [5]]]]\'-\'*", "1-2-345")
        self.check("[1 [2] [3 [4 [5]]]][6 7]*",[1,6,7,2,6,7,3,[4,[5]]])

        self.check("[1 2 3 4]{+}*", 10)

    def test_op_div(self):
        self.check("7 3 /", 2)
        self.check("\'a s d f\' \' \'/", ["a", "s", "d", "f"])
        self.check("\'assdfs\' \'s\'/", ["a","","df",""])
        self.check("[1 2 3 4 5] 2/", [[1,2],[3,4],[5]])
        self.check("[1 2 3]{1+}/", [2,3,4])

    def test_op_mod(self):
        self.check("7 3 %", 1)
        self.check("\'assdfs\' \'s\'%", ["a", "df"])
        self.check("[1 2 3 4 5] 2%", [1,3,5])
        self.check("[1 2 3 4 5] -1%", [5,4,3,2,1])
        self.check("[1 2 3]{.}%", [1,1,2,2,3,3])

    def test_op_bit_or(self):
        self.check("5 3|", 7)

    def test_op_bit_and(self):
        self.check("2 1&", 0)
        self.check("[1 1 2 2][1 3]&", [1])

    def test_op_bit_xor(self):
        self.check("2 1^", 3)
        self.check("[1 1 2 2][1 3]^", [2,3])

    def test_op_bracket(self):
        self.check("[ 1 2 3 4 ] [ 1 2 ]", [[1,2,3,4],[1,2]])
        self.check("1 2 [\\]", [2,1])

    def test_op_swp(self):
        self.check("1 2 3 \\", [1, 3, 2])

    def test_op_asn(self):
        self.check("1:a a", [1,1])
        self.check("{1 1+}:x; x", 2)

    def test_op_pop(self):
        self.check("1 2 3;", [1, 2])

    def test_op_lt(self):
        self.check("3 4 <", 1)
        self.check("\"asdf\" \"asdg\" <", 1)
        self.check("[1 2 3] 2 <", [1, 2])
        self.check("{asdf} -1 <", CodeBlock("asd"))

    def test_op_gt(self):
        self.check("3 4 >", 0)
        self.check("\"asdf\" \"asdg\" >", 0)
        self.check("[1 2 3] 2 >", [3])
        self.check("{asdf} -1 >", CodeBlock("f"))

    def test_op_eq(self):
        self.check("3 4 =", 0)
        self.check("\"asdf\" \"asdg\" =", 0)
        self.check("[1 2 3] 2 =", 3)
        self.check("{asdf} -1 =", 102)

    def test_op_arr(self):
        self.check("10,", [0,1,2,3,4,5,6,7,8,9])
        self.check("10,,", 10)
        self.check("10,{3%},", [1,2,4,5,7,8])

    def test_op_dup(self):
        self.check("1 2 3.", [1,2,3,3])

    def test_op_do(self):
        self.check("5{1-..}do", [4,3,2,1,0,0])

    def test_op_while(self):
        self.check("5{.}{1-.}while", [4,3,2,1,0,0])

    def test_op_until(self):
        self.check("5{.}{1-.}until", 5)

    def test_op_if(self):
        self.check("1 2 3 if", 2)

    def test_op_zip(self):
        self.check("[[1 2 3][4 5 6][7 8 9]]zip", [[1,4,7],[2,5,8],[3,6,9]])
        self.check("[\'asdf\'\'1234\']zip", ["a1", "s2", "d3", "f4"])


    def test_op_base(self):
        self.check("[1 1 0] 2 base", 6)
        #self.check("6 2 base", [1 1 0])

if __name__ == '__main__':
    unittest.main(verbosity=2)