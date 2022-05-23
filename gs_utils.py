import gs_codeblock

#Same as 'str1'.join(['1','2','3']) but for lists
def list_join(list_a, list_b):
    new_list = []

    for i,x in enumerate(list_b):

        if isinstance(x, list):
            new_list += x
        else:
            new_list.append(x)

        if (i+1) < len(list_b):
            new_list += list_a

    return new_list

def convert_str_list(s):
    new_list = []
    for c in s:
        new_list.append(ord(c))
    return new_list

def to_string(v : list):

    if isinstance(v, list):
        s = ""
        for x in v:
            s += to_string(x)

        return s

    else:
        return str(v)

def list_div(l : list, i : int):
    result = []
    arr = []
    for index,entry in enumerate(l):
        if index % i == 0:
            if arr != []:
                result.append(arr)
                arr = []
        arr.append(entry)

    if arr != []:
        result.append(arr)

    return result
