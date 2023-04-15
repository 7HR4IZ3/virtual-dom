# Copyright 2020 Thiago Teixeira
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
jsbuild -- write JavaScript in Python
==================================

Just annotate a Python function with `@js` and then call `str()` on it to get
a fully-working JavaScript version of that function.

Example
-------

>>> from jsbuild import js
>>>
>>> @js
... def js_code():
...     bleed = 100
...     width = 960
...     height = 760
...
...     pack = (d3.layout.pack()
...         .sort(None)
...         .size([width, height + bleed * 2])
...         .padding(2))
...
...     svg = (d3.select("body").append("svg")
...         .attr("width", width)
...         .attr("height", height)
...         .append("g")
...         .attr("transform", "translate(0," + (-bleed) + ")"))
...
...     def json_read(js, error, json):
...         if error:
...             raise error
...
...         node = (svg.selectAll(".node")
...             .data(pack.nodes(flatten(json)))
...             .filter(lambda d: not d.children)
...             .enter()
...                 .append("g")
...                 .attr("class", "node")
...                 .attr("transform", lambda d: "translate(" + d.x + "," + d.y + ")"))
...
...         (node.append("circle")
...             .attr("r", lambda d: d.r))
...
...         (node.append("text")
...             .text(lambda d: d.name)
...             .style("font-size", lambda d: Math.min(2 * d.r, (2 * d.r - 8) / getComputedTextLength() * 24) + "px")
...             .attr("dy", ".35em"))
...
...     d3.json("README.json", json_read)
...
>>>
>>> str(js_code)
'bleed = 100;\nwidth = 960;\nheight = 760;\npack = d3.layout.pack().sort(null).size([width, (height + (bleed * 2))]).padding(2);\nsvg = d3.select("body").append("svg").attr("width", width).attr("height", height).append("g").attr("transform", (("translate(0," + (-bleed)) + ")"));\nfunction json_read(js, error, json) {\nif (error) {\nthrow new Error(\'error\')\n} else {\n\n};\nnode = svg.selectAll(".node").data(pack.nodes(flatten(json))).filter(((d) => ((!d.children)))).enter().append("g").attr("class", "node").attr("transform", ((d) => ((((("translate(" + d.x) + ",") + d.y) + ")"))));\nnode.append("circle").attr("r", ((d) => (d.r)));\nnode.append("text").text(((d) => (d.name))).style("font-size", ((d) => ((Math.min((2 * d.r), ((((2 * d.r) - 8) / getComputedTextLength()) * 24)) + "px")))).attr("dy", ".35em")\n};\nd3.json("README.json", json_read)'
>>>
>>> print(js_code)
bleed = "100";
width = "960";
height = "760";
pack = "d3.layout.pack().sort(null).size([width, (height + (bleed * 2))])".padding("2");
svg = "d3.select("body").append("svg").attr("width", width).attr("height", height).append("g")".attr(""transform"", ("("translate(0," + (-bleed))" "+" "")""));
function json_read("js, error, json") {
"if (error) {
throw new Error('error')
} else {
};
node = svg.selectAll(".node").data(pack.nodes(flatten(json))).filter(((d) => ((!d.children)))).enter().append("g").attr("class", "node").attr("transform", ((d) => ((((("translate(" + d.x) + ",") + d.y) + ")"))));
node.append("circle").attr("r", ((d) => (d.r)));
node.append("text").text(((d) => (d.name))).style("font-size", ((d) => ((Math.min((2 * d.r), ((((2 * d.r) - 8) / getComputedTextLength()) * 24)) + "px")))).attr("dy", ".35em")"
};
"d3.json("README.json", json_read)"

"""

import inspect
import ast
import textwrap


def js(func=None, **kwargs):
    if kwargs:
        def wrapped_js(func):
            return JSFunc(func, kwargs)
        return wrapped_js

    elif func:
        return JSFunc(func)

    else:
        raise ValueError("@js requires at least a function")

class JSFunc(object):
    def __init__(self, func, initial_scope={}):
        self._orig = func
        self._initial_scope = initial_scope

        source_code = inspect.getsource(func)
        code_ast = ast.parse(textwrap.dedent(source_code))
        self._code = code_ast.body[0].body

        empty_scope = _Scope()
        initial_code_py = '\n'.join(
            "%s = %s" % (k, _to_str(v, empty_scope))
            for (k, v) in self._initial_scope.items()
        )

        if initial_code_py:
            initial_code_ast = ast.parse(textwrap.dedent(initial_code_py))
            self._initial_code_js = _to_str(
                initial_code_ast.body, empty_scope) + ";"
        else:
            self._initial_code_js = ""


    def __str__(self):
        return self._initial_code_js + _to_str(
            self._code,
            _Scope(self._initial_scope)
        )

    def __call__(self, *args, **kwargs):
        return self._orig(*args, **kwargs)


def _parse_assign(node, scope):
    value = _to_str(node.value, scope)
    target_iter = _to_str_iter(node.targets, scope)

    assignments = []


    for t in target_iter:
        is_in_scope = t in scope
        is_in_class_scope = scope._type == "class"
        is_field_assignment = '.' in t
        is_arr_assignment = '[' in t

        if is_in_scope or is_field_assignment or is_arr_assignment or is_in_class_scope:
            # if is_field_assignment:
            #     if scope.in_class():
            #         if t.startswith("self."):
            #             t = "this." + t.lstrip("self.")
            assignments.append(f"{t} = {value}")
        else:
            scope.add(t)
            assignments.append(f"let {t} = {value}")

    return ";".join(assignments)

def _parse_bool_op(node, scope):
    op = _to_str(node.op, scope)
    return op.join(_to_str_iter(node.values, scope))

def _parse_compare(node, scope):
    ops = _to_str_iter(node.ops, scope)
    comparators = _to_str_iter(node.comparators, scope)
    ops_comps = zip(ops, comparators)
    return "%s %s" % (
        _to_str(node.left, scope),
        " ".join("%s %s" % oc for oc in ops_comps),
    )

def _parse_call(node, scope):
    func = _to_str(node.func, scope)
    # args = list(_to_str_iter(node.args, scope))

    args = ", ".join([_to_str(x, scope) for x in node.args])
    kwargs = ", ".join([f"{kw.arg}={_to_str(kw.value, scope)}" for kw in node.keywords])

    # print("Call:", func, args, kwargs)

    if func in _PyToJS:
        return _PyToJS[func](args, node, scope)

    if func == "super" and scope.in_class():
        return func

    # if scope.is_class(func):
    #     return "new %s(%s)" % (
    #         func,
    #         ", ".join(args),
    #     )
    # else:
    return "%s(%s)" % (
        func,
        ", ".join([args, kwargs]).strip().strip(",").strip()
    )


def _parse_dict(node, scope):
    keys = _to_str_iter(node.keys, scope)
    values = _to_str_iter(node.values, scope)
    kvs = zip(keys, values)
    return "{%s}" % ", ".join("%s: %s" % kv for kv in kvs)


def _parse_function_def(node, scope):
    new_scope = scope.enter_new()

    def main():
        if scope._type == "class":
            new_scope.add(x.arg for x in node.args.args[1:])

            return "%(name)s(%(args)s) {\n%(body)s\n}", {
                "name": node.name,
                "args": _to_str(ast.arguments(
                    node.args.posonlyargs,
                    node.args.args[1:],
                    node.args.vararg,
                    node.args.kwonlyargs,
                    node.args.kw_defaults,
                    node.args.kwarg,
                    node.args.defaults
                ), new_scope),
                "body": _to_str(node.body, new_scope),
            }
        else:
            new_scope.add(x.arg for x in node.args.args)

            return "function %(name)s(%(args)s) {\n%(body)s\n}", {
                "name": node.name,
                "args": _to_str(node.args, new_scope),
                "body": _to_str(node.body, new_scope),
            }
    
    if node.decorator_list:
        ret, kw = main()
        name = kw["name"]
        kw["name"] = ""

        if scope._type == "class":
            ret = "function(%(args)s) {\n%(body)s\n}"
        ret = (ret%kw).strip()

        for item in node.decorator_list:
            ret = _to_str(item, scope) + "(" + ret + ")"
        
        if scope._type == "class":
            ret = f"{name} = " + ret
        else:
            is_in_scope = name in scope
            is_field_assignment = '.' in name
            is_arr_assignment = '[' in name

            if is_in_scope or is_field_assignment or is_arr_assignment:
                ret = f"{name} = " + ret
            else:
                ret = f"let {name} = " + ret
        return ret
    else:
        ret, kw = main()
        return ret%kw

def _parse_class_def(node, scope):
    new_scope = scope.enter_new(type="class")

    scope.add_class(node.name)
    new_scope.add_class(node.name)

    def main():
        return "class %(name)s {\n%(body)s\n}", {
            "name": node.name,
            "body": _to_str(node.body, new_scope),
        }
    
    if node.decorator_list:
        ret, kw = main()
        name = kw["name"]
        kw["name"] = ""

        ret = (ret%kw).strip()

        for item in node.decorator_list:
            ret = _to_str(item, scope) + "(" + ret + ")"

        is_in_scope = name in scope
        is_field_assignment = '.' in name
        is_arr_assignment = '[' in name

        if is_in_scope or is_field_assignment or is_arr_assignment:
            ret = f"{name} = " + ret
        else:
            ret = f"let {name} = " + ret

        
        return ret
    else:
        ret, kw = main()
        return ret%kw


def _parse_lambda(node, scope):
    new_scope = scope.enter_new()
    new_scope.add(x.arg for x in node.args.args)

    return "((%(args)s) => (%(body)s))" % {
        "args": _to_str(node.args, new_scope),
        "body": _to_str(node.body, new_scope),
    }


def _parse_list(node, scope):
    return "[%s]" % ", ".join(_to_str(x, scope) for x in node.elts)

def _arguments_defaults(args, scope):
    ret = {}

    for arg, default in zip(args.args[::-1][:len(args.defaults)], args.defaults):
        ret[arg.arg] = _to_str(default, scope)
    return ret

def _parse_arguments(node, scope):
    args = ", ".join([x.arg for x in node.args[len(node.defaults):]])
    kwargs = ", ".join([f"{k}={v}" for k, v in _arguments_defaults(node, scope).items()])
    return (", ".join([args, kwargs])).strip().strip(",").strip()

def _parse_attribute(node, scope):
    target = _to_str(node.value, scope)
    attr = node.attr

    # print("Attribute:", target, attr)

    # if scope.in_class():
    #     if target == "self":
    #         target = "this"
    
    if attr in _JsKwds:
        return _JsKwds[attr](target, attr, node, scope)
    
    # if target == "new":
    #     return _JsKwds["new"](attr, target, node,scope)

    return "%(target)s.%(attr)s"%{
        "target": target,
        "attr": attr
    }

def _parse_name(node, scope):
    name = node.id
    if name == "self" and scope.in_class():
        name = "this"

    return "%(id)s"%{
        "id": name
    }

def _convert_isinstance(args, node, scope):
    return f"{args[0]} instanceof {args[1]}"

def _convert_issubclass(args, node, scope):
    ret = f"typeof {args[0]}"
    if len(args) > 1:
        ret = ret + f" == {args[1]}"
    return ret

def _convert_new_keyword(target, attr, node, scope):
    return "new %s"%target

_PyToJS = {
    "isinstance": _convert_isinstance,
    "issubclass": _convert_issubclass,
    "instanceof": _convert_isinstance,
    "typeof": _convert_issubclass,
    "new": lambda args, *a: _convert_new_keyword(args, None, *a)
}

_JsKwds = {
    "new": _convert_new_keyword
}

# See:
# - https://docs.python.org/3/library/ast.html
# - https://greentreesnakes.readthedocs.io/en/latest/nodes.html
_PARSERS = {
    #"Module":
    "FunctionDef": _parse_function_def,
    "AsyncFunctionDef": (lambda *a: "async " + _parse_function_def(*a)),
    "ClassDef": _parse_class_def,  # TODO: Need to figure out "new" JS keyword.
    "Return": "return %(value)s",
    "Delete": "delete %(targets)s",
    "Assign": _parse_assign,
    "AugAssign": "%(target)s %(op)s= %(value)s",
    #"AnnAssign":
    "For": "%(iter)s.forEach((%(target)s, _i) => {\n%(body)s\n})",
    #"AsyncFor":
    "While": "while (%(test)s) {\n%(body)s\n}",
    "If": "if (%(test)s) {\n%(body)s\n} else {\n%(orelse)s\n}",
    #"With":
    #"AsyncWith":
    "Raise": "throw new Error(%(exc)s)",
    #"Try": TODO _parse_try,
    #"TryFinally": TODO _parse_try_finally,
    #"TryExcept": TODO _parse_try_except,
    #"Assert":
    #"Import":
    #"ImportFrom":
    #"Global":
    #"Nonlocal":
    "Expr": "%(value)s",
    "Pass": "",
    "BoolOp": _parse_bool_op,
    #"NamedExpr":
    "BinOp": "(%(left)s %(op)s %(right)s)",
    "UnaryOp": "(%(op)s%(operand)s)",
    "Lambda": _parse_lambda,
    "IfExp": "(%(test)s) ? (%(body)s) : (%(orelse)s)",
    "Dict": _parse_dict,
    #"Set":
    #"ListComp":
    #"SetComp":
    #"DictComp":
    #"GeneratorExp":
    #"Await":
    #"Yield":
    #"YieldFrom":
    "Compare": _parse_compare,
    "Call": _parse_call,
    #"FormattedValue":
    #"JoinedStr":
    "Constant": "%(value)s",
    "Attribute": _parse_attribute,
    "Subscript": "%(value)s[%(slice)s]",
    #"Starred":
    "Name": _parse_name,
    "List": _parse_list,
    "Tuple": _parse_list,#TODO
    #"AugLoad":
    #"AugStore":
    #"Param":
    #"Slice":
    #"ExtSlice":
    "Index": "%(value)s",
    "And": "&&",
    "Or": "||",
    "Add": "+",
    "Sub": "-",
    "Mult": "*",
    #"MatMult":
    "Div": "/",
    "Mod": "%%",  # Escape the "%" as "%%" since we call "%" on this string later.
    #"Pow":
    "LShift": "<<",
    "RShift": ">>",
    "BitOr": "|",
    "BitXor": "^",
    "BitAnd": "&",
    #"FloorDiv": ,
    "Invert": "~",
    "Not": "!",
    "UAdd": "+",
    "USub": "-",
    "Eq": "===",
    "NotEq": "!==",
    "Lt": "<",
    "LtE": "<=",
    "Gt": ">",
    "GtE": ">=",
    #"Is":
    #"IsNot":
    #"In":
    #"NotIn":
    #"ExceptHandler": _parse_except_handler,
    "Break": "break",
    "Continue": "continue",
    "arguments": _parse_arguments,

    # For Python < 3.8
    "Num": "%(n)s",
    "Str": '%(s)s',
    "Bytes": '"%(s)s"',
    #"Ellipsis
    "NameConstant": "%(value)s",
}


def _to_str(node, scope):
    node_type = type(node)

    if node_type is list:
        return ";\n".join(_to_str(x, scope) for x in node)

    if node is None:
        return "null"

    if node_type is str:
        return '"%s"' % node

    if node_type in (int, float):
        return str(node)

    if node_type is bool:
        return "true" if node else "false"

    if node_type.__name__ not in _PARSERS:
        raise Exception("Unsupported operation in JS: %s" % node_type)

    parser = _PARSERS[node_type.__name__]

    if type(parser) is str:
        return parser % _DictWrapper(node.__dict__, scope)

    return parser(node, scope)

def _to_js(name, node, scope):
    if name in _PyToJS:
        return _PyToJS[name](node, scope)

class _DictWrapper(dict):
    def __init__(self, dikt, scope):
        self._dict = dikt
        self._parsed_keys = set()
        self._scope = scope

    def __getitem__(self, k):
        raw = False

        if k.startswith("raw_"):
            k = k[4:]
            raw = True

        if k not in self._parsed_keys:
            if raw:
                self._dict[k] = self._dict[k]
            else:
                self._dict[k] = _to_str(self._dict[k], self._scope)
            self._parsed_keys.add(k)

        return self._dict[k]


def _to_str_iter(arg, scope):
    return (_to_str(x, scope) for x in arg)


class _Scope(object):
    def __init__(self, parent=None, type="normal"):
        self._parent = parent
        self._type = type
        self._class_list = []
        self._identifiers = set()

    def enter_new(self, type="normal"):
        return _Scope(self, type=type)

    def add(self, identifiers):
        for x in identifiers:
            self._identifiers.add(x)
    
    def add_class(self, name):
        self._class_list.append(name)
    
    def is_class(self, name):
        parent = self
        is_class = False

        while not is_class:
            if not parent:
                break
            is_class = (name in parent._class_list)
            parent = parent._parent
        return is_class
    
    def in_class(self):
        parent = self
        in_class = False

        while not in_class:
            if not parent:
                break
            in_class = (parent._type == "class")
            parent = parent._parent
        return in_class

    def __contains__(self, x):
        if x in self._identifiers:
            return True

        if self._parent is not None and x in self._parent:
            return True

        return False

@js
def test(console, Number, new):
    name =  "Thraize"
    console.log(name)

    class Age:
        name = "Ian"

        def constructor(self, name):
            self.name = name
            super().constructor(name)

        @classmethod
        def SayName(self, age=7):
            self.age = 19
            console.log(self)
            console.log(isinstance(age, Number))
            console.log(issubclass(age))
            return age# instanceof Number
    
    @property
    def hello(age, name):
        # new.Age(name="Thraize")
        new(Age)("Demian", name="Thraize")
        Age.new(name="Thraize")
        return age, name
    
    print(Age.new(name="Thraize"))

print(str(test))