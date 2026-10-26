#!/usr/bin/env python3
"""
Swan — a graceful little programming language.

    swan program.swan         run a program
    swan test program.swan    run the tests inside a program
    swan docs program.swan    write the program's documentation
    swan lake [folder]        open Lake, the Swan editor, in your browser
    swan                      open the playground
"""
import sys, os, math, time, difflib, inspect, threading, functools, contextlib
import random as _random

VERSION = "0.3"
MAX_DEPTH = 2500

# ───────────────────────────── errors ─────────────────────────────

class SwanError(Exception):
    def __init__(self, message, line=0, col=0, hint=None, incomplete=False):
        super().__init__(message)
        self.message, self.line, self.col = message, line, col
        self.hint, self.incomplete = hint, incomplete

class ExpectFailed(SwanError):
    pass

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

class StopSignal(Exception):
    def __init__(self, node):
        self.node = node

class SkipSignal(Exception):
    def __init__(self, node):
        self.node = node

USE_COLOR = False

def paint(text, code, color=None):
    use = USE_COLOR if color is None else color
    return f"\033[{code}m{text}\033[0m" if use else str(text)

def report(err, source, filename):
    lines = source.split("\n")
    out = [paint("✗ ", "31;1") + paint(err.message, "1")]
    if err.line:
        out.append(paint(f"  in {filename}, line {err.line}", "90"))
        if 1 <= err.line <= len(lines):
            gutter = f"  {err.line} │ "
            out.append(paint(gutter, "90") + lines[err.line - 1].rstrip())
            if err.col:
                out.append(" " * (len(gutter) + err.col - 1) + paint("^", "31;1"))
    if err.hint:
        out.append(paint("  hint: ", "36") + err.hint)
    print("\n".join(out), file=sys.stderr, flush=True)

# ───────────────────────────── lexer ─────────────────────────────

KEYWORDS = {
    "let", "var", "fn", "return", "if", "elif", "else", "then", "while", "for",
    "in", "match", "shape", "say", "true", "false", "yes", "no", "nothing",
    "and", "or", "not", "ref", "try", "otherwise", "fail", "stop", "skip",
    "test", "expect", "repeat", "by", "is", "ability", "glide", "flock",
    "spawn", "await", "choice", "hidden",
}

OPS = sorted([
    "...", "..<", "..", "**", "//", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=",
    "|>", "=>", "->", "??", "?.", "?", "+", "-", "*", "/", "%", "<", ">", "=", "(", ")",
    "[", "]", "{", "}", ",", ".", ":", "@",
], key=len, reverse=True)
OPEN, CLOSE = {"(", "[", "{"}, {")", "]", "}"}

STRANGERS = {
    ";": ("Swan doesn't need semicolons.", "Just start a new line."),
    "!": ("Swan uses the word 'not' instead of !", "Write: not ready   (and != for 'is not equal')"),
    "&": ("Swan uses the word 'and' instead of &&", "Write: a and b"),
    "|": ("Swan uses the word 'or' instead of ||", "Write: a or b   (|> is the pipe)"),
    "#": ("Comments in Swan start with --", "Write: -- this is a note"),
}

class Token:
    __slots__ = ("kind", "value", "line", "col")
    def __init__(self, kind, value, line, col):
        self.kind, self.value, self.line, self.col = kind, value, line, col
    def __repr__(self):
        return f"{self.kind}:{self.value!r}@{self.line}:{self.col}"

ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'", "{": "{", "}": "}", "0": "\0"}

def lex_string(text, i, ln):
    quote, j, parts, buf = text[i], i + 1, [], []
    while j < len(text):
        c = text[j]
        if c == "\\" and j + 1 < len(text):
            buf.append(ESCAPES.get(text[j + 1], "\\" + text[j + 1]))
            j += 2
            continue
        if c == quote:
            if buf or not parts:
                parts.append("".join(buf))
            return parts, j + 1
        if c == "{":
            k, depth = j + 1, 1
            while k < len(text) and depth:
                if text[k] == "{": depth += 1
                elif text[k] == "}": depth -= 1
                k += 1
            if depth:
                raise SwanError("This { inside the text is never closed.", ln, j + 1,
                                "Add a } after the value, or write \\{ for a plain brace.")
            if buf:
                parts.append("".join(buf))
                buf = []
            parts.append((text[j + 1:k - 1], ln, j + 2))
            j = k
            continue
        buf.append(c)
        j += 1
    raise SwanError("This text is missing its closing quote.", ln, i + 1, f"Add a {quote} at the end of the text.")

def lex(src, docs=None):
    src = src.replace("\ufeff", "")
    toks, indents, depth = [], [0], 0
    last_line = 1
    for ln, raw in enumerate(src.split("\n"), 1):
        text = raw.rstrip("\r")
        i, width = 0, 0
        while i < len(text) and text[i] in " \t":
            width += 4 if text[i] == "\t" else 1
            i += 1
        if text.startswith("---", i):
            if docs is not None:
                docs[ln] = text[i + 3:].strip()
            continue
        if i >= len(text) or text.startswith("--", i):
            continue
        last_line = ln
        continues = (text.startswith("|>", i) or text.startswith("?.", i) or
                     (text.startswith(".", i) and not text.startswith("..", i)))
        if depth == 0 and continues and toks and toks[-1].kind == "NEWLINE":
            toks.pop()
        elif depth == 0:
            if width > indents[-1]:
                indents.append(width)
                toks.append(Token("INDENT", None, ln, i + 1))
            else:
                while width < indents[-1]:
                    indents.pop()
                    toks.append(Token("DEDENT", None, ln, i + 1))
                if width != indents[-1]:
                    raise SwanError("This line's indentation doesn't line up with the lines above it.", ln, i + 1,
                                    "Use the same number of spaces as the block it belongs to (4 is standard).")
        while i < len(text):
            c, col = text[i], i + 1
            if c in " \t":
                i += 1
                continue
            if text.startswith("--", i):
                break
            if c.isdigit():
                j = i
                while j < len(text) and (text[j].isdigit() or text[j] == "_"):
                    j += 1
                if j + 1 < len(text) and text[j] == "." and text[j + 1].isdigit():
                    j += 1
                    while j < len(text) and (text[j].isdigit() or text[j] == "_"):
                        j += 1
                    value = float(text[i:j].replace("_", ""))
                else:
                    value = int(text[i:j].replace("_", ""))
                toks.append(Token("NUM", value, ln, col))
                i = j
                continue
            if c.isalpha() or c == "_":
                j = i
                while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                word = text[i:j]
                toks.append(Token("KW" if word in KEYWORDS else "NAME", word, ln, col))
                i = j
                continue
            if c in "\"'":
                parts, i = lex_string(text, i, ln)
                toks.append(Token("STR", parts, ln, col))
                continue
            for op in OPS:
                if text.startswith(op, i):
                    if op in OPEN: depth += 1
                    elif op in CLOSE: depth = max(0, depth - 1)
                    toks.append(Token("OP", op, ln, col))
                    i += len(op)
                    break
            else:
                msg, hint = STRANGERS.get(c, (f"I don't understand the character '{c}'.", None))
                raise SwanError(msg, ln, col, hint)
        if depth == 0:
            toks.append(Token("NEWLINE", None, ln, len(text) + 1))
    while len(indents) > 1:
        indents.pop()
        toks.append(Token("DEDENT", None, last_line + 1, 1))
    toks.append(Token("EOF", None, last_line, 1))
    return toks

# ───────────────────────────── parser ─────────────────────────────

class Node:
    def __init__(self, kind, tok, **fields):
        self.kind = kind
        self.line = tok.line if tok else 0
        self.col = tok.col if tok else 0
        self.__dict__.update(fields)

class Param:
    def __init__(self, name, default=None, rest=False, type=None, default_src=None, hidden=False):
        self.name, self.default, self.rest = name, default, rest
        self.type, self.default_src, self.hidden = type, default_src, hidden

def show_token(tok):
    if tok.kind == "NEWLINE": return "the end of the line"
    if tok.kind == "INDENT": return "an indented line"
    if tok.kind == "DEDENT": return "the end of a block"
    if tok.kind == "EOF": return "the end of the code"
    if tok.kind == "STR": return "some text"
    return f"'{tok.value}'"

GLIDE_STEPS = ("keep", "drop", "pick", "sort", "first", "last", "unique", "reverse", "group")

class Parser:
    def __init__(self, tokens, lines, docs=None):
        self.t, self.p, self.lines = tokens, 0, lines
        self.docs = docs or {}
        self.no_lambda = False

    # ── token helpers ──
    def peek(self, o=0):
        return self.t[min(self.p + o, len(self.t) - 1)]

    def next(self):
        tok = self.t[self.p]
        if tok.kind != "EOF":
            self.p += 1
        return tok

    def at(self, kind, value=None, o=0):
        tok = self.peek(o)
        return tok.kind == kind and (value is None or tok.value == value)

    def at_op(self, v, o=0): return self.at("OP", v, o)
    def at_kw(self, v, o=0): return self.at("KW", v, o)

    def accept(self, kind, value=None):
        return self.next() if self.at(kind, value) else None

    def fail(self, msg, tok=None, hint=None):
        tok = tok or self.peek()
        raise SwanError(msg, tok.line, tok.col, hint, incomplete=tok.kind == "EOF")

    def expect(self, kind, value=None, msg=None, hint=None):
        if self.at(kind, value):
            return self.next()
        want = f"'{value}'" if value else {"NAME": "a name", "STR": "some text", "NUM": "a number"}.get(kind, kind)
        self.fail(msg or f"I expected {want} here, but found {show_token(self.peek())}.", hint=hint)

    def at_line_end(self):
        return self.at("NEWLINE") or self.at("EOF") or self.at("DEDENT")

    def end_line(self):
        if self.p > 0 and self.t[self.p - 1].kind == "DEDENT":
            return
        if self.accept("NEWLINE") or self.at("EOF") or self.at("DEDENT"):
            return
        tok = self.peek()
        hint = "Each statement goes on its own line."
        before = self.t[self.p - 1] if self.p else None
        if tok.kind == "OP" and tok.value == "+" and self.at_op("+", 1):
            hint = "To add one, write: count += 1"
        elif before is not None and before.kind == "NAME" and before.value in FAMILIAR:
            hint = FAMILIAR[before.value]
        self.fail(f"I didn't expect {show_token(tok)} here.", hint=hint)

    def doc_for(self, line):
        found, ln = [], line - 1
        while ln in self.docs:
            found.append(self.docs[ln])
            ln -= 1
        return "\n".join(reversed(found))

    # ── program structure ──
    def program(self):
        body = []
        while not self.at("EOF"):
            if self.accept("NEWLINE") or self.accept("DEDENT"):
                continue
            body.append(self.statement())
        return body

    def block(self, what):
        if self.accept("KW", "then"):
            return [self.simple_statement_line()]
        if self.at_op(":"):
            self.fail("Swan doesn't need a colon here.", hint="Just end the line and indent the lines underneath.")
        if self.at_op("{"):
            self.fail("Swan doesn't use curly braces for blocks.", hint="End the line and indent the lines underneath instead.")
        if self.at_op("="):
            self.fail("A single = gives a value; it can't be used to compare.", hint="To compare, use == (two equals signs).")
        if not self.at("NEWLINE"):
            self.fail(f"I expected the end of the line here, but found {show_token(self.peek())}.")
        self.next()
        if not self.at("INDENT"):
            self.fail(f"This {what} needs some indented lines underneath it.",
                      hint="Indent the next line by 4 spaces.  (Or keep it on one line with: then ...)")
        self.next()
        body = []
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            body.append(self.statement())
        self.accept("DEDENT")
        return body

    # ── statements ──
    def statement(self):
        tok = self.peek()
        if tok.kind == "KW":
            v = tok.value
            if v in ("let", "var"): return self.let_statement()
            if v == "fn" and (self.at("NAME", o=1) or (self.at("KW", o=1) and self.at_op("(", 2))):
                return self.fn_declaration()
            if v == "shape": return self.shape_declaration()
            if v == "ability": return self.ability_declaration()
            if v == "choice": return self.choice_declaration()
            if v == "if": return self.if_statement()
            if v == "while":
                self.next()
                cond = self.expression()
                return Node("While", tok, cond=cond, body=self.block("while loop"))
            if v == "for": return self.for_statement()
            if v == "repeat":
                self.next()
                times = self.expression()
                return Node("Repeat", tok, times=times, body=self.block("repeat"))
            if v == "match" or (v == "glide" and not self.at_op("(", 1)):
                e = self.expression()
                self.end_line()
                return Node("ExprStmt", tok, expr=e)
            if v == "flock": return self.flock_statement()
            if v == "hidden":
                self.fail("'hidden' only works inside a shape.",
                          hint="Use it for a shape's private fields and functions, like: shape Account(owner, hidden balance)")
            if v == "try":
                self.next()
                body = self.block("try")
                self.expect("KW", "otherwise", msg="A try block needs an 'otherwise' part after it.",
                            hint="Write: otherwise problem   — then indent what to do if something goes wrong.")
                name = self.accept("NAME")
                handler = self.block("otherwise")
                return Node("Try", tok, body=body, name=name.value if name else None, handler=handler)
            if v == "test":
                self.next()
                name_tok = self.expect("STR", msg='A test needs a name in quotes, like: test "adding numbers"')
                name = "".join(p for p in name_tok.value if isinstance(p, str))
                return Node("Test", tok, name=name, body=self.block("test"))
        return self.simple_statement_line()

    def simple_statement_line(self):
        s = self.simple_statement()
        self.end_line()
        return s

    def simple_statement(self):
        tok = self.peek()
        if tok.kind == "KW":
            v = tok.value
            if v == "say":
                self.next()
                args = []
                if not self.at_line_end():
                    args.append(self.expression())
                    while self.accept("OP", ","):
                        args.append(self.expression())
                return Node("Say", tok, args=args)
            if v == "return":
                self.next()
                value = None if self.at_line_end() else self.expression()
                return Node("Return", tok, value=value)
            if v == "stop":
                self.next()
                return Node("Stop", tok)
            if v == "skip":
                self.next()
                return Node("Skip", tok)
            if v == "fail":
                self.next()
                return Node("Fail", tok, value=self.expression())
            if v == "expect":
                self.next()
                line = self.lines[tok.line - 1] if tok.line - 1 < len(self.lines) else ""
                source = line[tok.col - 1 + len("expect"):].split(" --")[0].strip()
                return Node("Expect", tok, expr=self.expression(), source=source)
            if v in ("let", "var"):
                return self.let_statement(end=False)
        expr = self.expression()
        if self.at_op(","):
            targets = [expr]
            while self.accept("OP", ","):
                targets.append(self.expression())
            eq = self.expect("OP", "=", msg="I expected = after these names.", hint="To swap two values, write: a, b = b, a")
            values = [self.expression()]
            while self.accept("OP", ","):
                values.append(self.expression())
            if len(values) != len(targets):
                self.fail(f"There are {len(targets)} names on the left but {len(values)} values on the right.", eq)
            return Node("MultiAssign", tok, targets=targets, values=values)
        for op in ("=", "+=", "-=", "*=", "/="):
            if self.at_op(op):
                self.next()
                value = self.expression()
                return Node("Assign", tok, target=expr, op=op, value=value)
        return Node("ExprStmt", tok, expr=expr)

    def type_annotation(self):
        tok = self.peek()
        options, optional = [], False
        while True:
            t = self.peek()
            if t.kind == "NAME" or (t.kind == "KW" and t.value == "nothing"):
                self.next()
                options.append(t.value)
            else:
                self.fail(f"I expected a type here, but found {show_token(t)}.",
                          hint="Types are words like number, text, bool, list, map, or a shape's name.")
            if self.accept("OP", "?"):
                optional = True
            if not self.accept("KW", "or"):
                break
        return Node("Type", tok, options=options, optional=optional)

    def let_statement(self, end=True):
        kw = self.next()
        if self.at("KW"):
            word = self.peek().value
            self.fail(f"'{word}' is one of Swan's special words, so it can't be used as a name.",
                      hint=f"Try another name, like: {kw.value} my_{word} = ...")
        name = self.expect("NAME", msg=f"I expected a name after '{kw.value}'.", hint=f"Write it like: {kw.value} score = 0")
        names = [name.value]
        while self.accept("OP", ","):
            names.append(self.expect("NAME").value)
        typ = self.type_annotation() if len(names) == 1 and self.accept("OP", ":") else None
        self.expect("OP", "=", msg=f"'{names[0]}' needs a starting value.", hint=f"Write it like: {kw.value} {names[0]} = 0")
        value = self.expression()
        if len(names) > 1 and self.at_op(","):
            items = [(False, value)]
            while self.accept("OP", ","):
                items.append((False, self.expression()))
            value = Node("List", kw, items=items)
        if end:
            self.end_line()
        return Node("Let", kw, names=names, mutable=kw.value == "var", value=value, type=typ)

    def params(self):
        self.expect("OP", "(", hint="List the inputs in brackets, like: fn greet(name)")
        params = []
        while not self.at_op(")"):
            hidden = bool(self.accept("KW", "hidden"))
            rest = bool(self.accept("OP", "..."))
            name = self.expect("NAME", msg="I expected a name for this input.").value
            typ = self.type_annotation() if self.accept("OP", ":") else None
            default, default_src = None, None
            if self.accept("OP", "="):
                start = self.peek()
                default = self.expression()
                end = self.peek()
                if start.line == end.line and start.line - 1 < len(self.lines):
                    default_src = self.lines[start.line - 1][start.col - 1:end.col - 1].strip()
                else:
                    default_src = "…"
            params.append(Param(name, default, rest, typ, default_src, hidden))
            if not self.accept("OP", ","):
                break
        self.expect("OP", ")", msg="This list of inputs is missing its closing ).")
        return params

    def fn_declaration(self):
        tok = self.next()
        name = self.next().value
        params = self.params()
        returns = self.type_annotation() if self.accept("OP", "->") else None
        if self.accept("OP", "=>"):
            value = self.expression()
            self.end_line()
            body = [Node("Return", tok, value=value)]
        else:
            body = self.block("function")
        return Node("Fn", tok, name=name, params=params, body=body, returns=returns, doc=self.doc_for(tok.line))

    def shape_declaration(self):
        tok = self.next()
        name = self.expect("NAME", msg="A shape needs a name.", hint="Write it like: shape Point(x, y)").value
        params = self.params() if self.at_op("(") else None
        parent, abilities = None, []
        if self.at("NAME", "from"):
            self.next()
            parent = self.expect("NAME", msg="I expected the name of a shape after 'from'.").value
        if self.at("NAME", "can"):
            self.next()
            abilities.append(self.expect("NAME", msg="I expected an ability name after 'can'.").value)
            while self.accept("OP", ","):
                abilities.append(self.expect("NAME").value)
        methods = {}
        if self.at("NEWLINE") and self.at("INDENT", o=1):
            self.next(); self.next()
            while not self.at("DEDENT") and not self.at("EOF"):
                if self.accept("NEWLINE"):
                    continue
                hidden = bool(self.accept("KW", "hidden"))
                if not self.at_kw("fn"):
                    self.fail("Inside a shape you can only write fn definitions.", hint="Move other code outside the shape.")
                m = self.method_declaration()
                m.hidden = hidden
                methods[m.name] = m
            self.accept("DEDENT")
        else:
            self.end_line()
        return Node("Shape", tok, name=name, params=params, parent=parent, abilities=abilities,
                    methods=methods, doc=self.doc_for(tok.line))

    def method_declaration(self):
        """A fn inside a shape or ability. With no body, it's left for others to fill in."""
        fn_tok = self.next()
        if not (self.at("NAME") or self.at("KW")):
            self.fail("I expected the function's name here.")
        fn_name = self.next().value
        params = self.params()
        returns = self.type_annotation() if self.accept("OP", "->") else None
        if self.accept("OP", "=>"):
            value = self.expression()
            self.end_line()
            body = [Node("Return", fn_tok, value=value)]
        elif self.at("NEWLINE") and self.at("INDENT", o=1):
            body = self.block("function")
        else:
            self.end_line()
            body = None
        return Node("Fn", fn_tok, name=fn_name, params=params, body=body, returns=returns,
                    doc=self.doc_for(fn_tok.line), hidden=False)

    def ability_declaration(self):
        tok = self.next()
        name = self.expect("NAME", msg="An ability needs a name.", hint="Write it like: ability Glide").value
        required, defaults = {}, {}
        if not self.accept("NEWLINE"):
            self.fail("After the ability's name, list its fn lines underneath, indented.")
        self.expect("INDENT", msg="An ability needs some indented fn lines underneath it.",
                    hint="Write lines like:   fn glide()")
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            if not self.at_kw("fn"):
                self.fail("Inside an ability you can only write fn lines.")
            m = self.method_declaration()
            (required if m.body is None else defaults)[m.name] = m
        self.accept("DEDENT")
        return Node("Ability", tok, name=name, required=required, defaults=defaults, doc=self.doc_for(tok.line))

    def choice_declaration(self):
        tok = self.next()
        name = self.expect("NAME", msg="A choice needs a name.", hint="Write it like: choice Weather").value
        if not self.accept("NEWLINE"):
            self.fail("After the choice's name, list the options underneath, one per line, indented.")
        self.expect("INDENT", msg="A choice needs its options listed underneath it.",
                    hint="Write lines like:   Sunny   or   Rain(millimetres)")
        variants = []
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            vt = self.expect("NAME", msg="I expected the name of an option here, like: Sunny")
            if not vt.value[0].isupper():
                raise SwanError(f"Options in a choice start with a capital letter, like {vt.value.capitalize()}.",
                                vt.line, vt.col)
            params = self.params() if self.at_op("(") else None
            variants.append(Node("Variant", vt, name=vt.value, params=params, doc=self.doc_for(vt.line)))
            self.end_line()
        self.accept("DEDENT")
        return Node("Choice", tok, name=name, variants=variants, doc=self.doc_for(tok.line))

    def flock_statement(self):
        tok = self.next()
        body = self.block("flock")
        for st in body:
            fine = (st.kind == "Assign" and st.op == "=" and st.target.kind == "Name" and st.value.kind == "Call") or \
                   (st.kind == "ExprStmt" and st.expr.kind == "Call")
            if not fine:
                raise SwanError("Each line in a flock should be a function call.", st.line, st.col,
                                "Write lines like:   weather = fetch_weather(\"Oslo\")")
        return Node("Flock", tok, body=body)

    def if_statement(self):
        tok = self.next()
        branches = [(self.expression(), self.block("if"))]
        else_body = None
        while True:
            if self.accept("KW", "elif"):
                branches.append((self.expression(), self.block("elif")))
            elif self.accept("KW", "else"):
                if self.accept("KW", "if"):
                    branches.append((self.expression(), self.block("else if")))
                    continue
                else_body = self.block("else")
                break
            else:
                break
        return Node("If", tok, branches=branches, else_body=else_body)

    def for_statement(self):
        tok = self.next()
        names = [self.expect("NAME", hint="Write it like: for item in list").value]
        if self.accept("OP", ","):
            names.append(self.expect("NAME").value)
        self.expect("KW", "in", hint="Write it like: for item in list")
        it = self.expression()
        return Node("For", tok, names=names, iter=it, body=self.block("for loop"))

    def match_expression(self):
        tok = self.next()
        subject = self.expression()
        if not self.accept("NEWLINE"):
            self.fail("After match, put each pattern on its own indented line.")
        self.expect("INDENT", msg="A match needs some indented patterns underneath it.",
                    hint='Write lines like:   0 => say "zero"')
        arms = []
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            pattern = self.pattern()
            guard = None
            if self.accept("KW", "if"):
                self.no_lambda = True
                guard = self.expression()
                self.no_lambda = False
            self.expect("OP", "=>", msg="I expected => after this pattern.", hint='Write it like:   1 => say "one"')
            if self.at("NEWLINE"):
                body = self.block("match arm")
            else:
                body = [self.simple_statement_line()]
            arms.append((pattern, guard, body))
        self.accept("DEDENT")
        return Node("Match", tok, subject=subject, arms=arms)

    def glide_expression(self):
        tok = self.next()
        source = self.expression()
        if not self.accept("NEWLINE"):
            self.fail("After glide, put each step on its own indented line.")
        self.expect("INDENT", msg="A glide needs some indented steps underneath it.",
                    hint="Write steps like:   keep age > 18")
        steps = []
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.accept("NEWLINE"):
                continue
            st = self.peek()
            if st.kind not in ("NAME", "KW") or st.value not in GLIDE_STEPS:
                close = difflib.get_close_matches(str(st.value), GLIDE_STEPS, 1, 0.6)
                self.fail(f"I don't know the glide step {show_token(st)}.",
                          hint=f"Did you mean '{close[0]}'?" if close else f"Steps are: {', '.join(GLIDE_STEPS)}")
            self.next()
            word, expr, extra = st.value, None, None
            if word in ("keep", "drop", "pick", "group", "first", "last"):
                if self.at_line_end():
                    self.fail(f"The '{word}' step needs something after it.",
                              hint={"keep": "keep age > 18", "drop": "drop name == \"\"", "pick": "pick name",
                                    "group": "group city", "first": "first 3", "last": "last 3"}[word])
                expr = self.expression()
            elif word == "sort":
                if not self.at_line_end() and not self.at("NAME", "descending"):
                    expr = self.expression()
                extra = bool(self.accept("NAME", "descending"))
            steps.append(Node("Step", st, word=word, expr=expr, descending=extra))
            self.end_line()
        self.accept("DEDENT")
        return Node("Glide", tok, source=source, steps=steps)

    # ── patterns ──
    def pattern(self):
        first = self.single_pattern()
        options = [first]
        while self.accept("KW", "or"):
            options.append(self.single_pattern())
        return first if len(options) == 1 else Node("POr", first, options=options)

    def literal_value(self):
        tok = self.peek()
        if tok.kind == "OP" and tok.value == "-" and self.at("NUM", o=1):
            self.next()
            return -self.next().value
        if tok.kind == "NUM":
            return self.next().value
        if tok.kind == "STR":
            if any(not isinstance(p, str) for p in tok.value):
                self.fail("Patterns can't contain {…} values.")
            self.next()
            return "".join(tok.value)
        if tok.kind == "KW" and tok.value in ("true", "yes"):
            self.next()
            return True
        if tok.kind == "KW" and tok.value in ("false", "no"):
            self.next()
            return False
        if tok.kind == "KW" and tok.value == "nothing":
            self.next()
            return None
        self.fail(f"I expected a pattern here, but found {show_token(tok)}.",
                  hint="Patterns can be values (3, \"hi\"), ranges (1..9), names, lists [a, b] or _")

    def single_pattern(self):
        tok = self.peek()
        if tok.kind == "NAME":
            self.next()
            if tok.value == "_":
                return Node("PAny", tok)
            if self.at_op("("):
                self.next()
                subs = []
                while not self.at_op(")"):
                    subs.append(self.pattern())
                    if not self.accept("OP", ","):
                        break
                self.expect("OP", ")")
                return Node("PShape", tok, name=tok.value, subs=subs)
            if tok.value[0].isupper():
                return Node("PShape", tok, name=tok.value, subs=[])
            return Node("PBind", tok, name=tok.value)
        if tok.kind == "OP" and tok.value == "[":
            self.next()
            items, rest = [], None
            while not self.at_op("]"):
                if self.accept("OP", "..."):
                    rest = self.expect("NAME", msg="After ... write a name for the rest, like ...others").value
                    break
                items.append(self.pattern())
                if not self.accept("OP", ","):
                    break
            self.expect("OP", "]")
            return Node("PList", tok, items=items, rest=rest)
        value = self.literal_value()
        if self.at_op("..") or self.at_op("..<"):
            inclusive = self.next().value == ".."
            return Node("PRange", tok, start=value, end=self.literal_value(), inclusive=inclusive)
        return Node("PLit", tok, value=value)

    # ── expressions ──
    def expression(self):
        if self.is_lambda():
            return self.lambda_expression()
        if self.at_kw("if"):
            tok = self.next()
            cond = self.pipe()
            self.expect("KW", "then", hint="Write it like: if score > 10 then \"high\" else \"low\"")
            yes = self.expression()
            self.expect("KW", "else", hint="An inline if needs an else part, like: if a then b else c")
            return Node("IfExpr", tok, cond=cond, yes=yes, no=self.expression())
        if self.at_kw("match"):
            return self.match_expression()
        if self.at_kw("glide") and not self.at_op("(", 1):
            return self.glide_expression()
        return self.pipe()

    def is_lambda(self):
        if self.no_lambda:
            return False
        if self.at("NAME") and self.at_op("=>", 1):
            return True
        if self.at_op("("):
            depth, i = 0, self.p
            while i < len(self.t):
                tk = self.t[i]
                if tk.kind == "OP" and tk.value in OPEN:
                    depth += 1
                elif tk.kind == "OP" and tk.value in CLOSE:
                    depth -= 1
                    if depth == 0:
                        nxt = self.t[i + 1] if i + 1 < len(self.t) else None
                        return nxt is not None and nxt.kind == "OP" and nxt.value == "=>"
                elif tk.kind in ("NEWLINE", "EOF"):
                    return False
                i += 1
        return False

    def lambda_expression(self):
        tok = self.peek()
        params = [Param(self.next().value)] if self.at("NAME") else self.params()
        self.expect("OP", "=>")
        body = self.expression()
        return Node("Lambda", tok, name="fn", params=params, body=[Node("Return", tok, value=body)])

    def pipe(self):
        left = self.nullish()
        while self.at_op("|>"):
            tok = self.next()
            right = self.nullish()
            if right.kind == "Call":
                left = Node("Call", tok, callee=right.callee, args=[("pos", None, left)] + right.args)
            else:
                left = Node("Call", tok, callee=right, args=[("pos", None, left)])
        return left

    def nullish(self):
        left = self.or_expression()
        while self.at_op("??"):
            tok = self.next()
            left = Node("Nullish", tok, left=left, right=self.or_expression())
        return left

    def or_expression(self):
        left = self.and_expression()
        while self.at_kw("or"):
            tok = self.next()
            left = Node("Or", tok, left=left, right=self.and_expression())
        return left

    def and_expression(self):
        left = self.not_expression()
        while self.at_kw("and"):
            tok = self.next()
            left = Node("And", tok, left=left, right=self.not_expression())
        return left

    def not_expression(self):
        if self.at_kw("not"):
            tok = self.next()
            return Node("Not", tok, operand=self.not_expression())
        return self.comparison()

    def comparison(self):
        tok = self.peek()
        operands, ops = [self.range_expression()], []
        if self.at_kw("is"):
            is_tok = self.next()
            negate = bool(self.accept("KW", "not"))
            return Node("Is", is_tok, value=operands[0], type=self.type_annotation(), negate=negate)
        while True:
            if self.peek().kind == "OP" and self.peek().value in ("==", "!=", "<", "<=", ">", ">="):
                ops.append(self.next().value)
            elif self.at_kw("in"):
                self.next()
                ops.append("in")
            elif self.at_kw("not") and self.at_kw("in", 1):
                self.next(); self.next()
                ops.append("not in")
            else:
                break
            operands.append(self.range_expression())
        if not ops:
            return operands[0]
        return Node("Compare", tok, ops=ops, operands=operands)

    def range_expression(self):
        start = self.additive()
        if self.at_op("..") or self.at_op("..<"):
            tok = self.next()
            end = self.additive()
            step = self.additive() if self.accept("KW", "by") else None
            return Node("Range", tok, start=start, end=end, inclusive=tok.value == "..", step=step)
        return start

    def additive(self):
        left = self.multiplicative()
        while self.at_op("+") or self.at_op("-"):
            tok = self.next()
            left = Node("Binary", tok, op=tok.value, left=left, right=self.multiplicative())
        return left

    def multiplicative(self):
        left = self.unary()
        while self.peek().kind == "OP" and self.peek().value in ("*", "/", "//", "%"):
            tok = self.next()
            left = Node("Binary", tok, op=tok.value, left=left, right=self.unary())
        return left

    def unary(self):
        tok = self.peek()
        if self.at_op("-"):
            self.next()
            return Node("Neg", tok, operand=self.unary())
        if self.at_op("@"):
            self.next()
            return Node("Deref", tok, target=self.unary())
        if self.at_kw("ref"):
            self.next()
            return Node("RefOf", tok, target=self.unary())
        if self.at_kw("spawn"):
            self.next()
            call = self.unary()
            if call.kind != "Call":
                self.fail("spawn needs a function call after it.", tok, hint="Write it like: spawn download(url)")
            return Node("Spawn", tok, call=call)
        if self.at_kw("await"):
            self.next()
            return Node("Await", tok, value=self.unary())
        base = self.postfix()
        if self.at_op("**"):
            op = self.next()
            return Node("Binary", op, op="**", left=base, right=self.unary())
        return base

    def call_args(self):
        self.next()
        args = []
        while not self.at_op(")"):
            if (self.at("NAME") or self.at("KW")) and self.at_op(":", 1):
                name = self.next().value
                self.next()
                args.append(("named", name, self.expression()))
            elif self.accept("OP", "..."):
                args.append(("spread", None, self.expression()))
            else:
                args.append(("pos", None, self.expression()))
            if not self.accept("OP", ","):
                break
        self.expect("OP", ")", msg="This call is missing its closing ).")
        return args

    def postfix(self):
        e = self.primary()
        while True:
            tok = self.peek()
            if self.at_op("("):
                e = Node("Call", tok, callee=e, args=self.call_args())
            elif self.at_op("["):
                self.next()
                index = self.expression()
                self.expect("OP", "]", msg="I expected ] to close this [.")
                e = Node("Index", tok, obj=e, index=index)
            elif self.at_op(".") or self.at_op("?."):
                safe = self.next().value == "?."
                name = self.peek()
                if name.kind not in ("NAME", "KW"):
                    self.fail("I expected a name after the dot.")
                self.next()
                e = Node("Member", name, obj=e, name=name.value, safe=safe)
            else:
                return e

    def string_node(self, tok):
        parts = []
        for part in tok.value:
            if isinstance(part, str):
                parts.append(part)
                continue
            src, ln, col = part
            stripped = src.lstrip()
            col += len(src) - len(stripped)
            if not stripped.strip():
                raise SwanError("There's an empty {} inside this text.", ln, col - 1,
                                "Put a value inside, like {name}, or write \\{ for a plain brace.")
            toks = lex(stripped)
            for t in toks:
                t.line, t.col = ln, t.col + col - 1
            sub = Parser(toks, self.lines)
            expr = sub.expression()
            if not (sub.at("NEWLINE") or sub.at("EOF")):
                sub.fail("I couldn't make sense of the value inside these braces.")
            parts.append(expr)
        if all(isinstance(p, str) for p in parts):
            return Node("Lit", tok, value="".join(parts))
        return Node("Interp", tok, parts=parts)

    def primary(self):
        tok = self.peek()
        k, v = tok.kind, tok.value
        if k == "NUM":
            self.next()
            return Node("Lit", tok, value=v)
        if k == "STR":
            self.next()
            return self.string_node(tok)
        if k == "NAME":
            self.next()
            return Node("Name", tok, name=v)
        if k == "KW":
            if v in ("true", "yes"):
                self.next()
                return Node("Lit", tok, value=True)
            if v in ("false", "no"):
                self.next()
                return Node("Lit", tok, value=False)
            if v == "nothing":
                self.next()
                return Node("Lit", tok, value=None)
            if v == "say":
                self.next()
                return Node("Name", tok, name="say")
            if v == "fn":
                self.next()
                params = self.params()
                self.expect("OP", "=>", hint="Write it like: fn(x) => x * 2")
                body = self.expression()
                return Node("Lambda", tok, name="fn", params=params, body=[Node("Return", tok, value=body)])
            if v == "match":
                return self.match_expression()
            if self.at_op("(", 1):
                # a function that happens to share a name with a special word, like glide()
                self.next()
                return Node("Name", tok, name=v)
            if v == "glide":
                return self.glide_expression()
        if k == "OP":
            if v == "(":
                self.next()
                e = self.expression()
                self.expect("OP", ")", msg="I expected ) to close this (.")
                return e
            if v == "[":
                return self.list_literal()
            if v == "{":
                return self.map_literal()
        hint = None
        if k == "OP" and v == "+" and self.p > 0 and self.t[self.p - 1].value == "+":
            hint = "To add one, write: count += 1"
        self.fail(f"I expected a value here, but found {show_token(tok)}.", hint=hint)

    def list_literal(self):
        tok = self.next()
        items = []
        while not self.at_op("]"):
            spread = bool(self.accept("OP", "..."))
            item = self.expression()
            if not items and not spread and self.at_kw("for"):
                self.next()
                names = [self.expect("NAME").value]
                if self.accept("OP", ","):
                    names.append(self.expect("NAME").value)
                self.expect("KW", "in")
                source = self.pipe()
                cond = self.expression() if self.accept("KW", "if") else None
                self.expect("OP", "]")
                return Node("Comp", tok, expr=item, names=names, iter=source, cond=cond)
            items.append((spread, item))
            if not self.accept("OP", ","):
                break
        self.expect("OP", "]", msg="This list is missing its closing ].")
        return Node("List", tok, items=items)

    def map_literal(self):
        tok = self.next()
        entries = []
        while not self.at_op("}"):
            key_tok = self.peek()
            if key_tok.kind in ("NAME", "KW"):
                self.next()
                key = Node("Lit", key_tok, value=key_tok.value)
            elif key_tok.kind == "STR":
                self.next()
                key = self.string_node(key_tok)
            elif key_tok.kind == "NUM":
                self.next()
                key = Node("Lit", key_tok, value=key_tok.value)
            else:
                self.fail("I expected a key here, like: {name: \"Odette\"}")
            self.expect("OP", ":", hint="Keys and values are joined with a colon, like: {age: 3}")
            entries.append((key, self.expression()))
            if not self.accept("OP", ","):
                break
        self.expect("OP", "}", msg="This map is missing its closing }.")
        return Node("Map", tok, entries=entries)

# ───────────────────────────── values ─────────────────────────────

class Function:
    def __init__(self, name, params, body, env, returns=None, doc="", owner=None, hidden=False):
        self.name, self.params, self.body, self.env = name, params, body, env
        self.returns, self.doc, self.owner, self.hidden = returns, doc, owner, hidden

class Builtin:
    def __init__(self, name, fn, usage):
        self.name, self.fn, self.usage = name, fn, usage
        self.sig = inspect.signature(fn)
        self.doc = fn.__doc__ or ""

class ShapeType:
    def __init__(self, name, params, methods, env, parent=None, abilities=(), doc=""):
        self.name, self.params, self.methods, self.env = name, params, methods, env
        self.parent, self.abilities, self.doc = parent, list(abilities), doc
        self.field_types = {p.name: p.type for p in params if p.type is not None}
        self.variants = None   # for a choice: the names of its options
        self.hidden_fields = {p.name for p in params if p.hidden}
        self.required = []     # functions left for the shapes that come from this one

    def is_a(self, other):
        s = self
        while s is not None:
            if s is other:
                return True
            s = s.parent
        return False

    def lineage(self):
        s, names = self, []
        while s is not None:
            names.append(s.name)
            s = s.parent
        return names

class Ability:
    def __init__(self, name, required, defaults, env, doc=""):
        self.name, self.required, self.defaults, self.env, self.doc = name, required, defaults, env, doc

class Instance:
    def __init__(self, shape):
        self.shape, self.fields = shape, {}

class ParentView:
    """What 'parent' means inside a method: the same thing, seen as its parent shape."""
    def __init__(self, me, shape):
        self.me, self.shape = me, shape

class BoundMethod:
    def __init__(self, fn, me):
        self.fn, self.me = fn, me

class Task:
    def __init__(self, name):
        self.name = name
        self.done = threading.Event()
        self.value, self.error, self.seen = None, None, False

class Ref:
    def __init__(self, get, set_, label):
        self.get, self._set, self.label = get, set_, label
    def set(self, value, node):
        self._set(value, node)

class Range:
    def __init__(self, start, end, inclusive, step=None):
        self.start, self.end, self.inclusive = start, end, inclusive
        direction = 1 if end >= start else -1
        self.step = direction * abs(step) if step is not None else direction
        self.explicit_step = step is not None

    def items(self):
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in (self.start, self.end, self.step)):
            raise SwanError("Only ranges of whole numbers can be counted through.",
                            hint="Use whole numbers, like 1..10")
        stop = self.end + (1 if self.step > 0 else -1) if self.inclusive else self.end
        return range(self.start, stop, self.step)

    def contains(self, x):
        lo, hi = min(self.start, self.end), max(self.start, self.end)
        if not (lo <= x <= hi):
            return False
        if not self.inclusive and x == self.end:
            return False
        if self.explicit_step:
            return (x - self.start) % self.step == 0
        return True

def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)

def is_callable(x):
    return isinstance(x, (Function, Builtin, ShapeType, BoundMethod))

BASIC_TYPES = ("number", "text", "bool", "list", "map", "nothing", "range", "ref", "function", "task", "any")

def type_name(v):
    if v is None: return "nothing"
    if isinstance(v, bool): return "bool"
    if is_num(v): return "number"
    if isinstance(v, str): return "text"
    if isinstance(v, list): return "list"
    if isinstance(v, dict): return "map"
    if isinstance(v, Range): return "range"
    if isinstance(v, Instance): return v.shape.name
    if isinstance(v, ShapeType): return "shape"
    if isinstance(v, Ability): return "ability"
    if isinstance(v, Ref): return "ref"
    if isinstance(v, Task): return "task"
    if isinstance(v, ParentView): return v.shape.name
    return "function"

def type_phrase(name):
    return {"number": "a number", "text": "text", "bool": "true or false", "list": "a list", "map": "a map",
            "nothing": "nothing", "range": "a range", "ref": "a ref", "function": "a function", "task": "a task",
            "any": "anything", "shape": "a shape", "ability": "an ability"}.get(name, f"a {name}")

def type_text(t):
    return " or ".join(t.options) + ("?" if t.optional else "")

def quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'

def is_plain_name(s):
    return isinstance(s, str) and s.isidentifier()

class Env:
    __slots__ = ("vars", "consts", "types", "parent", "inst", "redefine")
    def __init__(self, parent=None, inst=None):
        self.vars = inst.fields if inst is not None else {}
        self.consts = set()
        self.types = {}
        self.parent, self.inst = parent, inst
        self.redefine = False

    def define(self, name, value, mutable, node, typ=None):
        if name in self.vars and not self.redefine:
            raise SwanError(f"'{name}' already exists here.", node.line, node.col,
                            f"To change it, write: {name} = ...   (it must have been made with var)")
        self.vars[name] = value
        if mutable:
            self.consts.discard(name)
        else:
            self.consts.add(name)
        if typ is not None:
            self.types[name] = typ
        else:
            self.types.pop(name, None)

    def owner(self, name):
        e = self
        while e is not None:
            if name in e.vars:
                return e
            e = e.parent
        return None

    def lookup(self, name):
        e = self
        while e is not None:
            if name in e.vars:
                return True, e.vars[name]
            if e.inst is not None and name in e.inst.shape.methods:
                return True, BoundMethod(e.inst.shape.methods[name], e.inst)
            e = e.parent
        return False, None

    def all_names(self):
        names, e = set(), self
        while e is not None:
            names.update(e.vars)
            if e.inst is not None:
                names.update(e.inst.shape.methods)
            e = e.parent
        return names

FAMILIAR = {
    "print": "Swan uses say, like: say \"hello\"",
    "console": "Swan uses say, like: say \"hello\"",
    "len": "Swan uses length(list) or list.length",
    "filter": "Swan calls it keep, like: keep(nums, n => n > 2)",
    "reduce": "Swan calls it fold, like: fold(nums, 0, (total, n) => total + n)",
    "null": "Swan calls it nothing",
    "None": "Swan calls it nothing",
    "nil": "Swan calls it nothing",
    "True": "Swan writes it as true (lowercase)",
    "False": "Swan writes it as false (lowercase)",
    "self": "Inside a shape, use me (or just the field name)",
    "this": "Inside a shape, use me (or just the field name)",
    "super": "Inside a shape, use parent, like: parent.speak()",
    "def": "Swan makes functions with fn, like: fn greet(name)",
    "function": "Swan makes functions with fn, like: fn greet(name)",
    "class": "Swan calls them shapes, like: shape Swan(name, color)",
    "struct": "Swan calls them shapes, like: shape Swan(name, color)",
    "interface": "Swan calls them abilities, like: ability Glide",
    "trait": "Swan calls them abilities, like: ability Glide",
    "extends": "A shape can come from another, like: shape Cygnet from Swan",
    "async": "Run things at the same time with spawn, or a flock block",
    "input": "Swan uses ask, like: let name = ask(\"Your name? \")",
    "str": "Swan uses text(value)",
    "int": "Swan uses number(value)",
    "append": "Swan uses push, like: push(list, item) or list.push(item)",
}

NO_CALL = object()

# ───────────────────────────── interpreter ─────────────────────────────

class Interpreter:
    def __init__(self, filename, testing=False, out=None, color=None):
        self.filename = filename
        self.globals = Env()
        self.testing, self.tests = testing, []
        self.local = threading.local()
        self.baton = threading.Lock()
        self.tasks = []
        self.cancelled = False
        self.input_lines = None
        self.color = USE_COLOR if color is None else color
        self.out = out or (lambda text: (sys.stdout.write(text), sys.stdout.flush()))
        self.builtins = make_builtins(self)

    # per-thread state, so tasks running side by side don't trip over each other
    @property
    def depth(self): return getattr(self.local, "depth", 0)
    @depth.setter
    def depth(self, value): self.local.depth = value
    @property
    def current_node(self): return getattr(self.local, "node", None)
    @current_node.setter
    def current_node(self, value): self.local.node = value

    def write(self, text):
        self.out(text + "\n")

    def check_cancelled(self):
        if self.cancelled:
            raise SwanError("Stopped.")

    @contextlib.contextmanager
    def released(self):
        """Lets other tasks run while this one waits."""
        self.baton.release()
        try:
            yield
        finally:
            self.baton.acquire()

    # ── running ──
    def run_program(self, program):
        """Runs top-level code, turning stray signals into friendly errors."""
        with self.baton:
            try:
                result = self.exec_block(program, self.globals)
                self.finish_tasks()
                return result
            except ReturnSignal as r:
                self.finish_tasks()
                return r.value
            except (StopSignal, SkipSignal) as sig:
                word = "stop" if isinstance(sig, StopSignal) else "skip"
                raise SwanError(f"'{word}' only works inside a loop.", sig.node.line, sig.node.col)
            except RecursionError:
                raise SwanError("The program went too deep (a function kept calling itself).", 0, 0,
                                "Make sure every repeating function has a case where it stops.")

    def finish_tasks(self):
        i = 0
        while i < len(self.tasks):
            task = self.tasks[i]
            if not task.seen:
                self.await_value(task, None)
            i += 1

    # ── blocks & statements ──
    def exec_block(self, stmts, env):
        shapes = []
        for s in stmts:
            if s.kind == "Fn":
                env.define(s.name, Function(s.name, s.params, s.body, env, s.returns, s.doc), False, s)
            elif s.kind == "Ability":
                env.define(s.name, Ability(s.name, s.required, s.defaults, env, s.doc), False, s)
            elif s.kind == "Shape":
                shapes.append(s)
            elif s.kind == "Choice":
                self.build_choice(s, env)
        while shapes:
            waiting = {s.name for s in shapes}
            ready = [s for s in shapes if s.parent is None or s.parent not in waiting]
            if not ready:
                s = shapes[0]
                raise SwanError(f"{s.name} comes from {s.parent}, which comes back around to {s.name}.", s.line, s.col)
            for s in ready:
                env.define(s.name, self.build_shape(s, env), False, s)
                shapes.remove(s)
        last = None
        for s in stmts:
            if s.kind in ("Fn", "Shape", "Ability", "Choice"):
                last = None
            elif s.kind == "Test":
                if self.testing:
                    self.tests.append((s, env))
                last = None
            else:
                last = getattr(self, "s_" + s.kind)(s, env)
        return last

    def build_choice(self, s, env):
        whole = ShapeType(s.name, [], {}, env, doc=s.doc)
        whole.variants = [v.name for v in s.variants]
        env.define(s.name, whole, False, s)
        for v in s.variants:
            option = ShapeType(v.name, v.params or [], {}, env, parent=whole, doc=v.doc)
            # an option with no fields is a ready-made value, like Sunny
            env.define(v.name, option if v.params is not None else Instance(option), False, v)

    def check_every_option(self, n, choice):
        """A match on a choice must handle every option, so no case is ever forgotten."""
        checked = n.__dict__.setdefault("checked", set())
        if id(choice) in checked:
            return
        covered = set()
        for pattern, guard, _ in n.arms:
            if guard is not None:
                continue
            for p in (pattern.options if pattern.kind == "POr" else [pattern]):
                if p.kind in ("PAny", "PBind"):
                    checked.add(id(choice))
                    return
                if p.kind == "PShape" and all(sub.kind in ("PAny", "PBind") for sub in p.subs):
                    covered.add(p.name)
        missing = [name for name in choice.variants if name not in covered and choice.name not in covered]
        if missing:
            raise SwanError(f"This match doesn't handle every kind of {choice.name}: {', '.join(missing)} "
                            f"{'is' if len(missing) == 1 else 'are'} missing.", n.line, n.col,
                            f"Add a line for {missing[0]}, or a catch-all:   _ => ...")
        checked.add(id(choice))

    def build_shape(self, s, env):
        parent = None
        if s.parent is not None:
            found, parent = env.lookup(s.parent)
            if not found or not isinstance(parent, ShapeType):
                close = difflib.get_close_matches(s.parent, env.all_names(), 1, 0.7)
                raise SwanError(f"{s.name} comes from '{s.parent}', but I don't know a shape called that.",
                                s.line, s.col, f"Did you mean '{close[0]}'?" if close else None)
        abilities = list(parent.abilities) if parent else []
        for name in s.abilities:
            found, ab = env.lookup(name)
            if not found or not isinstance(ab, Ability):
                raise SwanError(f"{s.name} says it can '{name}', but I don't know an ability called that.",
                                s.line, s.col, f"Make one first:  ability {name}")
            abilities.append(ab)
        params = s.params if s.params is not None else (parent.params if parent else [])
        shape = ShapeType(s.name, params, {}, env, parent, abilities, s.doc)
        methods = {}
        for ab in abilities:
            for name, f in ab.defaults.items():
                methods[name] = Function(f"{ab.name}.{name}", f.params, f.body, ab.env, f.returns, f.doc)
        if parent:
            methods.update(parent.methods)
        for name, m in s.methods.items():
            methods[name] = Function(f"{s.name}.{name}", m.params, m.body, env, m.returns, m.doc,
                                     owner=shape, hidden=m.hidden)
        for ab in abilities:
            for name in ab.required:
                if name not in methods:
                    raise SwanError(f"{s.name} says it can {ab.name}, but it has no {name}().", s.line, s.col,
                                    f"Add it inside the shape:   fn {name}(...)")
        shape.methods = methods
        shape.required = [name for name, f in methods.items() if f.body is None]
        return shape

    # ── what's hidden beneath the surface ──
    def can_see_inside(self, shape):
        inside = getattr(self.local, "inside", None)
        return inside is not None and (inside.is_a(shape) or shape.is_a(inside))

    def is_hidden(self, obj, name):
        hidden = name in obj.shape.hidden_fields or (name in obj.shape.methods and obj.shape.methods[name].hidden)
        return hidden and not self.can_see_inside(obj.shape)

    def hidden_error(self, obj, name, node):
        what = f"{name}()" if name in obj.shape.methods else f"'{name}'"
        return SwanError(f"{what} is hidden inside {obj.shape.name}.", node.line, node.col,
                         f"Only {obj.shape.name}'s own functions can use it. "
                         f"Add a function to {obj.shape.name} that does what you need.")

    def public_fields(self, obj):
        if self.can_see_inside(obj.shape):
            return obj.fields
        return {k: v for k, v in obj.fields.items() if k not in obj.shape.hidden_fields}

    def s_ExprStmt(self, s, env):
        return self.eval(s.expr, env)

    def s_Say(self, s, env):
        self.write(" ".join(self.show(self.eval(a, env)) for a in s.args))

    def s_Let(self, s, env):
        value = self.eval(s.value, env)
        if len(s.names) == 1:
            if s.type is not None:
                self.require_type(value, s.type, env, f"'{s.names[0]}'", s.value)
            env.define(s.names[0], value, s.mutable, s, s.type)
            return
        items = self.to_list(value, s)
        if len(items) != len(s.names):
            raise SwanError(f"I need exactly {len(s.names)} values to fill {', '.join(s.names)}, but got {len(items)}.",
                            s.line, s.col)
        for name, item in zip(s.names, items):
            env.define(name, item, s.mutable, s)

    def s_Assign(self, s, env):
        value = self.eval(s.value, env)
        if s.op != "=":
            value = self.binop(s.op[0], self.eval(s.target, env), value, s)
        self.assign(s.target, value, env)

    def s_MultiAssign(self, s, env):
        values = [self.eval(v, env) for v in s.values]
        for target, value in zip(s.targets, values):
            self.assign(target, value, env)

    def set_variable(self, owner, name, value, node):
        if name in owner.consts:
            raise SwanError(f"'{name}' was made with let, so it can't change.", node.line, node.col,
                            f"If it needs to change, create it with: var {name} = ...")
        typ = owner.types.get(name)
        if typ is not None:
            self.require_type(value, typ, owner, f"'{name}'", node)
        owner.vars[name] = value

    def assign(self, t, value, env):
        if t.kind == "Name":
            owner = env.owner(t.name)
            if owner is None:
                if t.name in self.builtins:
                    raise SwanError(f"'{t.name}' is one of Swan's built-in tools, so it can't be changed.",
                                    t.line, t.col, f"Pick another name, like: var my_{t.name} = ...")
                raise SwanError(f"There's no '{t.name}' to change yet.", t.line, t.col,
                                f"Create it first with: var {t.name} = ...")
            self.set_variable(owner, t.name, value, t)
        elif t.kind == "Index":
            self.set_index(self.eval(t.obj, env), self.eval(t.index, env), value, t)
        elif t.kind == "Member":
            self.set_member(self.eval(t.obj, env), t.name, value, t)
        elif t.kind == "Deref":
            r = self.eval(t.target, env)
            if not isinstance(r, Ref):
                raise SwanError(f"@ writes through a ref, but this is {self.a(r)}.", t.line, t.col,
                                "Make a ref first with: let r = ref something")
            r.set(value, t)
        else:
            raise SwanError("I can't put a value into this.", t.line, t.col,
                            "The left side of = should be a name, like: total = 5")

    def s_If(self, s, env):
        for cond, body in s.branches:
            if self.truthy(self.eval(cond, env)):
                self.exec_block(body, Env(env))
                return
        if s.else_body is not None:
            self.exec_block(s.else_body, Env(env))

    def loop_body(self, body, env):
        if self.cancelled:
            self.check_cancelled()
        try:
            self.exec_block(body, env)
        except SkipSignal:
            pass

    def s_While(self, s, env):
        try:
            while self.truthy(self.eval(s.cond, env)):
                self.loop_body(s.body, Env(env))
        except StopSignal:
            pass

    def s_Repeat(self, s, env):
        n = self.eval(s.times, env)
        if not (isinstance(n, int) and not isinstance(n, bool)) or n < 0:
            raise SwanError(f"repeat needs a whole number of times, but got {self.show(n, True)}.", s.line, s.col)
        try:
            for _ in range(n):
                self.loop_body(s.body, Env(env))
        except StopSignal:
            pass

    def s_For(self, s, env):
        try:
            for values in self.iterate(self.eval(s.iter, env), len(s.names), s.iter):
                scope = Env(env)
                for name, value in zip(s.names, values):
                    scope.define(name, value, False, s)
                self.loop_body(s.body, scope)
        except StopSignal:
            pass

    def iterate(self, it, count, node):
        if isinstance(it, Ref):
            it = it.get()
        if isinstance(it, dict):
            items = list(it.items())
            return [(k, v) for k, v in items] if count == 2 else [(k,) for k, _ in items]
        if isinstance(it, (list, str, Range)):
            seq = list(it.items()) if isinstance(it, Range) else list(it)
            return list(enumerate(seq)) if count == 2 else [(x,) for x in seq]
        hint = None
        if is_num(it):
            hint = f"To repeat {self.show(it)} times, write: repeat {self.show(it)} — or count with: for i in 1..{self.show(it)}"
        raise SwanError(f"I can't loop over {self.a(it)}.", node.line, node.col, hint)

    def s_Try(self, s, env):
        try:
            self.exec_block(s.body, Env(env))
        except SwanError as e:
            if self.cancelled:
                raise
            scope = Env(env)
            if s.name:
                scope.define(s.name, e.message, False, s)
            self.exec_block(s.handler, scope)

    def s_Fail(self, s, env):
        raise SwanError(self.show(self.eval(s.value, env)), s.line, s.col)

    def s_Expect(self, s, env):
        e = s.expr
        if e.kind == "Compare" and len(e.ops) == 1:
            left, right = self.eval(e.operands[0], env), self.eval(e.operands[1], env)
            if not self.compare(e.ops[0], left, right, e):
                raise ExpectFailed(f"Expected {s.source}", s.line, s.col,
                                   f"left side was {self.show(left, True)}, right side was {self.show(right, True)}")
        else:
            value = self.eval(e, env)
            if not self.truthy(value):
                raise ExpectFailed(f"Expected {s.source}", s.line, s.col, f"but it was {self.show(value, True)}")

    def s_Return(self, s, env):
        raise ReturnSignal(None if s.value is None else self.eval(s.value, env))

    def s_Stop(self, s, env):
        raise StopSignal(s)

    def s_Skip(self, s, env):
        raise SkipSignal(s)

    def s_Flock(self, s, env):
        started = []
        for st in s.body:
            if st.kind == "Assign":
                started.append((st.target.name, self.spawn(st.value, env), st))
            else:
                started.append((None, self.spawn(st.expr, env), st))
        results = [(name, self.await_value(task, st), st) for name, task, st in started]
        for name, value, st in results:
            if name is not None:
                env.define(name, value, False, st)

    # ── expressions ──
    def eval(self, node, env):
        return getattr(self, "e_" + node.kind)(node, env)

    def e_Lit(self, n, env):
        return n.value

    def e_Interp(self, n, env):
        return "".join(p if isinstance(p, str) else self.show(self.eval(p, env)) for p in n.parts)

    def e_Name(self, n, env):
        found, value = env.lookup(n.name)
        if found:
            return value
        if n.name in self.builtins:
            return self.builtins[n.name]
        raise self.unknown(n, env)

    def unknown(self, n, env):
        if n.name in FAMILIAR:
            hint = FAMILIAR[n.name]
        else:
            close = difflib.get_close_matches(n.name, env.all_names() | set(self.builtins), 1, 0.7)
            hint = f"Did you mean '{close[0]}'?" if close else f"Create it first, like: let {n.name} = ..."
        return SwanError(f"I don't know anything called '{n.name}'.", n.line, n.col, hint)

    def e_List(self, n, env):
        out = []
        for spread, item in n.items:
            value = self.eval(item, env)
            if spread:
                out.extend(self.to_list(value, item))
            else:
                out.append(value)
        return out

    def e_Comp(self, n, env):
        out = []
        for values in self.iterate(self.eval(n.iter, env), len(n.names), n.iter):
            scope = Env(env)
            for name, value in zip(n.names, values):
                scope.define(name, value, False, n)
            if n.cond is None or self.truthy(self.eval(n.cond, scope)):
                out.append(self.eval(n.expr, scope))
        return out

    def e_Map(self, n, env):
        return {self.eval(k, env): self.eval(v, env) for k, v in n.entries}

    def e_Neg(self, n, env):
        v = self.eval(n.operand, env)
        if not is_num(v):
            raise SwanError(f"I can't make {self.a(v)} negative.", n.line, n.col)
        return -v

    def e_Not(self, n, env):
        return not self.truthy(self.eval(n.operand, env))

    def e_And(self, n, env):
        left = self.eval(n.left, env)
        return self.eval(n.right, env) if self.truthy(left) else left

    def e_Or(self, n, env):
        left = self.eval(n.left, env)
        return left if self.truthy(left) else self.eval(n.right, env)

    def e_Nullish(self, n, env):
        left = self.eval(n.left, env)
        return self.eval(n.right, env) if left is None else left

    def e_IfExpr(self, n, env):
        return self.eval(n.yes if self.truthy(self.eval(n.cond, env)) else n.no, env)

    def e_Binary(self, n, env):
        return self.binop(n.op, self.eval(n.left, env), self.eval(n.right, env), n)

    def e_Compare(self, n, env):
        left = self.eval(n.operands[0], env)
        for op, right_node in zip(n.ops, n.operands[1:]):
            right = self.eval(right_node, env)
            if not self.compare(op, left, right, n):
                return False
            left = right
        return True

    def e_Is(self, n, env):
        return self.fits(self.eval(n.value, env), n.type, env) != n.negate

    def e_Range(self, n, env):
        start, end = self.eval(n.start, env), self.eval(n.end, env)
        step = self.eval(n.step, env) if n.step is not None else None
        for v in (start, end) + ((step,) if step is not None else ()):
            if not is_num(v):
                raise SwanError(f"Ranges are made of numbers, but this has {self.a(v)}.", n.line, n.col)
        if step == 0:
            raise SwanError("A range can't step by 0 — it would never move.", n.line, n.col)
        return Range(start, end, n.inclusive, step)

    def e_Lambda(self, n, env):
        return Function(n.name, n.params, n.body, env)

    def e_Deref(self, n, env):
        r = self.eval(n.target, env)
        if not isinstance(r, Ref):
            raise SwanError(f"@ reads what a ref points to, but this is {self.a(r)}.", n.line, n.col,
                            "Make a ref with: let r = ref something")
        return r.get()

    def e_RefOf(self, n, env):
        t = n.target
        if t.kind == "Name":
            owner = env.owner(t.name)
            if owner is None:
                raise self.unknown(t, env)
            name = t.name
            def set_name(value, node):
                if name in owner.consts:
                    raise SwanError(f"Can't change '{name}' through this ref — it was made with let.",
                                    node.line, node.col, f"Make it with var {name} = ... if it should change.")
                self.set_variable(owner, name, value, node)
            return Ref(lambda: owner.vars[name], set_name, name)
        if t.kind == "Index":
            obj, index = self.eval(t.obj, env), self.eval(t.index, env)
            self.get_index(obj, index, t)
            return Ref(lambda: self.get_index(obj, index, t),
                       lambda value, node: self.set_index(obj, index, value, node), "item")
        if t.kind == "Member":
            obj = self.eval(t.obj, env)
            self.get_member(obj, t.name, t)
            return Ref(lambda: self.get_member(obj, t.name, t),
                       lambda value, node: self.set_member(obj, t.name, value, node), t.name)
        box = [self.eval(t, env)]
        return Ref(lambda: box[0], lambda value, node: box.__setitem__(0, value), "box")

    def e_Index(self, n, env):
        return self.get_index(self.eval(n.obj, env), self.eval(n.index, env), n)

    def e_Member(self, n, env):
        return self.get_member(self.eval(n.obj, env), n.name, n, n.safe)

    def prepare_call(self, n, env):
        c = n.callee
        prefix = []
        if c.kind == "Member":
            obj = self.eval(c.obj, env)
            while isinstance(obj, Ref):
                obj = obj.get()
            if obj is None and c.safe:
                return NO_CALL, [], {}
            f = self.method(obj, c.name, env, c)
            if isinstance(f, tuple):
                fn, prefix = f[0], [obj]
            else:
                fn = f
        else:
            fn = self.eval(c, env)
        args, kwargs = [], {}
        for kind, name, e in n.args:
            value = self.eval(e, env)
            if kind == "pos":
                args.append(value)
            elif kind == "spread":
                args.extend(self.to_list(value, e))
            else:
                kwargs[name] = value
        return fn, prefix + args, kwargs

    def e_Call(self, n, env):
        fn, args, kwargs = self.prepare_call(n, env)
        if fn is NO_CALL:
            return None
        return self.call(fn, args, kwargs, n)

    def method(self, obj, name, env, node):
        if isinstance(obj, ParentView):
            if name in obj.shape.methods:
                return BoundMethod(obj.shape.methods[name], obj.me)
            raise SwanError(f"{obj.shape.name} has no '{name}' to call.", node.line, node.col)
        if isinstance(obj, Instance):
            if (name in obj.fields or name in obj.shape.methods) and self.is_hidden(obj, name):
                raise self.hidden_error(obj, name, node)
            if name in obj.fields:
                return obj.fields[name]
            if name in obj.shape.methods:
                return BoundMethod(obj.shape.methods[name], obj)
        if isinstance(obj, dict) and name in obj and is_callable(obj[name]):
            return obj[name]
        found, fn = env.lookup(name)
        if not found and name in self.builtins:
            found, fn = True, self.builtins[name]
        if found and is_callable(fn):
            return (fn,)
        options = set(self.builtins)
        if isinstance(obj, Instance):
            options = set(obj.fields) | set(obj.shape.methods)
        close = difflib.get_close_matches(name, options, 1, 0.7)
        raise SwanError(f"{self.a(obj).capitalize()} has no '{name}'.", node.line, node.col,
                        f"Did you mean '{close[0]}'?" if close else None)

    def call(self, fn, args, kwargs, node):
        if isinstance(fn, Function):
            return self.call_function(fn, args, kwargs, node)
        if isinstance(fn, BoundMethod):
            return self.call_function(fn.fn, args, kwargs, node, fn.me)
        if isinstance(fn, Builtin):
            return self.call_builtin(fn, args, kwargs, node)
        if isinstance(fn, ShapeType):
            if fn.required:
                left = fn.required[0]
                raise SwanError(f"{fn.name} is an outline, so it can't be made directly.", node.line, node.col,
                                f"It leaves {left}() for the shapes that come from it. "
                                f"Make one of those, or write {left}() inside {fn.name}.")
            inst = Instance(fn)
            scope = Env(fn.env)
            self.bind(fn.name, fn.params, args, kwargs, scope, node)
            inst.fields.update(scope.vars)
            if "setup" in fn.methods:
                self.call_function(fn.methods["setup"], [], {}, node, inst)
            return inst
        if isinstance(fn, Ability):
            raise SwanError(f"{fn.name} is an ability, so it can't be made directly.", node.line, node.col,
                            f"Make a shape that can {fn.name}, like:  shape Thing can {fn.name}")
        raise SwanError(f"{self.a(fn).capitalize()} isn't something you can call.", node.line, node.col)

    def bind(self, name, params, args, kwargs, scope, node):
        args, kwargs = list(args), dict(kwargs)
        plain = [p.name for p in params if not p.rest]
        for extra in kwargs:
            if extra not in plain:
                close = difflib.get_close_matches(extra, plain, 1, 0.6)
                raise SwanError(f"{name} has no input called '{extra}'.", node.line, node.col,
                                f"Did you mean '{close[0]}'?" if close else f"Its inputs are: {', '.join(plain) or 'none'}")
        for p in params:
            if p.rest:
                scope.vars[p.name] = args
                args = []
                continue
            if args:
                if p.name in kwargs:
                    raise SwanError(f"'{p.name}' was given twice when calling {name}.", node.line, node.col)
                value = args.pop(0)
            elif p.name in kwargs:
                value = kwargs.pop(p.name)
            elif p.default is not None:
                value = self.eval(p.default, scope)
            else:
                raise SwanError(f"{name} needs a value for '{p.name}'.", node.line, node.col,
                                f"Call it like: {name}({', '.join(plain)})")
            if p.type is not None:
                self.require_type(value, p.type, scope, f"{name}'s '{p.name}'", node)
                scope.types[p.name] = p.type
            scope.vars[p.name] = value
        if args:
            raise SwanError(f"{name} takes {len(plain)} value{'s' if len(plain) != 1 else ''}, "
                            f"but was given {len(plain) + len(args)}.", node.line, node.col,
                            f"Call it like: {name}({', '.join(plain)})")

    def call_function(self, fn, args, kwargs, node, me=None):
        self.depth += 1
        outside = getattr(self.local, "inside", None)
        if me is not None:
            self.local.inside = fn.owner or me.shape
        try:
            if self.cancelled:
                self.check_cancelled()
            if self.depth > MAX_DEPTH:
                raise SwanError(f"Too many calls inside calls (while running {fn.name}).", node.line, node.col,
                                "This usually means a function keeps calling itself forever. "
                                "Make sure it has a case where it stops.")
            if me is not None:
                scope = Env(Env(fn.env, inst=me))
                scope.vars["me"] = me
                scope.consts.add("me")
                if fn.owner is not None and fn.owner.parent is not None:
                    scope.vars["parent"] = ParentView(me, fn.owner.parent)
                    scope.consts.add("parent")
            else:
                scope = Env(fn.env)
            self.bind(fn.name, fn.params, args, kwargs, scope, node)
            try:
                result = self.exec_block(fn.body, scope)
            except ReturnSignal as r:
                result = r.value
            except (StopSignal, SkipSignal) as sig:
                word = "stop" if isinstance(sig, StopSignal) else "skip"
                raise SwanError(f"'{word}' only works inside a loop.", sig.node.line, sig.node.col)
            if fn.returns is not None and not self.fits(result, fn.returns, fn.env):
                raise SwanError(f"{fn.name} should give back {self.phrase(fn.returns)}, but gave back "
                                f"{self.a(result)}{self.peek_value(result)}.", node.line, node.col,
                                f"Check what {fn.name} returns, or change its -> type.")
            return result
        except RecursionError:
            raise SwanError(f"Too many calls inside calls (while running {fn.name}).", node.line, node.col,
                            "This usually means a function keeps calling itself forever. "
                            "Make sure it has a case where it stops.")
        finally:
            self.depth -= 1
            self.local.inside = outside

    def call_builtin(self, b, args, kwargs, node):
        try:
            b.sig.bind(*args, **kwargs)
        except TypeError:
            raise SwanError(f"{b.name} wasn't given the right values.", node.line, node.col, f"Use it like: {b.usage}")
        saved, self.current_node = self.current_node, node
        try:
            return b.fn(*args, **kwargs)
        except SwanError as e:
            if not e.line:
                e.line, e.col = node.line, node.col
            if not e.hint and e.message != "Stopped.":
                e.hint = f"Use it like: {b.usage}"
            raise
        finally:
            self.current_node = saved

    # ── types ──
    def phrase(self, typ):
        text = " or ".join(type_phrase(name) for name in typ.options)
        return text + (" (or nothing)" if typ.optional else "")

    def peek_value(self, value):
        shown = self.show(value, True)
        return f" ({shown})" if len(shown) <= 30 and not isinstance(value, Instance) else ""

    def fits(self, value, typ, env):
        if value is None and typ.optional:
            return True
        return any(self.fits_name(value, name, env, typ) for name in typ.options)

    def fits_name(self, value, name, env, typ):
        if name == "any":
            return True
        if name in BASIC_TYPES:
            if name == "function":
                return is_callable(value)
            return type_name(value) == name
        found, t = env.lookup(name)
        if found and isinstance(t, ShapeType):
            return isinstance(value, Instance) and value.shape.is_a(t)
        if found and isinstance(t, Ability):
            return isinstance(value, Instance) and t in value.shape.abilities
        close = difflib.get_close_matches(name, list(BASIC_TYPES) + list(env.all_names()), 1, 0.6)
        raise SwanError(f"I don't know a type called '{name}'.", typ.line, typ.col,
                        f"Did you mean '{close[0]}'?" if close else
                        "Types are number, text, bool, list, map, function, any — or a shape or ability name.")

    def require_type(self, value, typ, env, what, node):
        if not self.fits(value, typ, env):
            hint = None
            if "number" in typ.options and isinstance(value, str):
                hint = "To turn text into a number, use number(value)."
            elif "text" in typ.options and is_num(value):
                hint = "To turn a number into text, use text(value)."
            raise SwanError(f"{what} should be {self.phrase(typ)}, but got {self.a(value)}{self.peek_value(value)}.",
                            node.line, node.col, hint)

    # ── tasks ──
    def spawn(self, call_node, env):
        fn, args, kwargs = self.prepare_call(call_node, env)
        if fn is NO_CALL:
            fn = self.builtins["first"]
            args = [[None]]
        name = getattr(fn, "name", "task")
        task = Task(name)
        def work():
            with self.baton:
                self.local.task = task
                try:
                    task.value = self.call(fn, args, kwargs, call_node)
                except SwanError as e:
                    task.error = e
                except RecursionError:
                    task.error = SwanError(f"{name} went too deep (a function kept calling itself).",
                                           call_node.line, call_node.col)
                except Exception as e:
                    task.error = SwanError(f"Something went wrong inside {name}: {e}", call_node.line, call_node.col)
                finally:
                    task.done.set()
        self.tasks.append(task)
        threading.Thread(target=work, daemon=True).start()
        return task

    def e_Spawn(self, n, env):
        return self.spawn(n.call, env)

    def e_Await(self, n, env):
        return self.await_value(self.eval(n.value, env), n)

    def await_value(self, value, node):
        if isinstance(value, list):
            return [self.await_value(v, node) for v in value]
        if not isinstance(value, Task):
            return value
        if value is getattr(self.local, "task", None):
            raise SwanError("A task can't wait for itself.", node.line if node else 0, node.col if node else 0)
        value.seen = True
        if not value.done.is_set():
            with self.released():
                while not value.done.wait(0.05):
                    if self.cancelled:
                        break
            self.check_cancelled()
        if value.error is not None:
            e = value.error
            raise SwanError(e.message if e.message.startswith("Stopped") else f"{value.name} failed: {e.message}",
                            e.line, e.col, e.hint)
        return value.value

    # ── glide ──
    def item_scope(self, env, item):
        if isinstance(item, Instance) and self.can_see_inside(item.shape):
            scope = Env(Env(env, inst=item))
        else:
            scope = Env(env)
            fields = self.public_fields(item) if isinstance(item, Instance) else item
            if isinstance(fields, dict):
                scope.vars.update({k: v for k, v in fields.items() if is_plain_name(k)})
        scope.vars["it"] = item
        return scope

    def e_Glide(self, n, env):
        items = list(self.to_list(self.eval(n.source, env), n.source))
        for step in n.steps:
            word, expr = step.word, step.expr
            each = lambda x: self.eval(expr, self.item_scope(env, x))
            if word == "keep":
                items = [x for x in items if self.truthy(each(x))]
            elif word == "drop":
                items = [x for x in items if not self.truthy(each(x))]
            elif word == "pick":
                items = [each(x) for x in items]
            elif word == "sort":
                keys = [each(x) if expr is not None else x for x in items]
                saved, self.current_node = self.current_node, step
                try:
                    order = sorted(range(len(items)), key=lambda i: self.ordering(keys[i]))
                finally:
                    self.current_node = saved
                items = [items[i] for i in order]
                if step.descending:
                    items.reverse()
            elif word in ("first", "last"):
                count = self.eval(expr, env)
                if not (isinstance(count, int) and not isinstance(count, bool)) or count < 0:
                    raise SwanError(f"'{word}' needs a whole number, like: {word} 3", step.line, step.col)
                items = items[:count] if word == "first" else (items[-count:] if count else [])
            elif word == "unique":
                kept = []
                for x in items:
                    if not any(self.equal(x, y) for y in kept):
                        kept.append(x)
                items = kept
            elif word == "reverse":
                items = items[::-1]
            elif word == "group":
                groups = []
                for x in items:
                    key = each(x)
                    for g in groups:
                        if self.equal(g["key"], key):
                            g["items"].append(x)
                            break
                    else:
                        groups.append({"key": key, "items": [x]})
                items = groups
        return items

    def ordering(self, value):
        node = self.current_node
        @functools.total_ordering
        class Key:
            def __init__(s, v): s.v = v
            def __eq__(s, o): return self.equal(s.v, o.v)
            def __lt__(s, o): return self.compare("<", s.v, o.v, node)
        return Key(value)

    def e_Match(self, n, env):
        value = self.eval(n.subject, env)
        if isinstance(value, Instance) and value.shape.parent is not None and value.shape.parent.variants:
            self.check_every_option(n, value.shape.parent)
        for pattern, guard, body in n.arms:
            bound = {}
            if self.matches(pattern, value, bound, env):
                scope = Env(env)
                for name, v in bound.items():
                    scope.define(name, v, False, pattern)
                if guard is not None and not self.truthy(self.eval(guard, scope)):
                    continue
                return self.exec_block(body, scope)
        raise SwanError(f"Nothing in this match fits {self.show(value, True)}.", n.line, n.col,
                        "Add a catch-all line at the end:   _ => ...")

    def matches(self, p, value, bound, env):
        k = p.kind
        if k == "PAny": return True
        if k == "PBind":
            bound[p.name] = value
            return True
        if k == "PLit": return self.equal(p.value, value)
        if k == "PRange":
            return is_num(value) and Range(p.start, p.end, p.inclusive).contains(value)
        if k == "POr":
            return any(self.matches(o, value, bound, env) for o in p.options)
        if k == "PList":
            if not isinstance(value, list): return False
            if len(value) < len(p.items) or (p.rest is None and len(value) != len(p.items)): return False
            if not all(self.matches(sub, v, bound, env) for sub, v in zip(p.items, value)): return False
            if p.rest is not None:
                bound[p.rest] = value[len(p.items):]
            return True
        if k == "PShape":
            if not isinstance(value, Instance):
                return False
            if p.name not in value.shape.lineage():
                found, t = env.lookup(p.name)
                if not (found and isinstance(t, Ability) and t in value.shape.abilities):
                    return False
            fields = list(self.public_fields(value).values())
            return len(p.subs) <= len(fields) and all(self.matches(s, v, bound, env) for s, v in zip(p.subs, fields))
        return False

    # ── operations ──
    def truthy(self, v):
        if isinstance(v, Ref):
            v = v.get()
        if v is None or v is False: return False
        if is_num(v): return v != 0
        if isinstance(v, (str, list, dict)): return len(v) > 0
        return True

    def a(self, v):
        if isinstance(v, Instance): return f"a {v.shape.name}"
        return type_phrase(type_name(v))

    def binop(self, op, a, b, node):
        if op == "+":
            if is_num(a) and is_num(b): return a + b
            if isinstance(a, str) and isinstance(b, str): return a + b
            if isinstance(a, list) and isinstance(b, list): return a + b
            if isinstance(a, dict) and isinstance(b, dict): return {**a, **b}
            hint = None
            if isinstance(a, str) or isinstance(b, str):
                hint = 'To put a value inside text, use braces: "Score: {score}"'
            raise SwanError(f"I can't add {self.a(a)} and {self.a(b)} together.", node.line, node.col, hint)
        if op == "*":
            if is_num(a) and is_num(b): return a * b
            if isinstance(a, (str, list)) and isinstance(b, int) and not isinstance(b, bool): return a * b
            if isinstance(b, (str, list)) and isinstance(a, int) and not isinstance(a, bool): return b * a
            raise SwanError(f"I can't multiply {self.a(a)} by {self.a(b)}.", node.line, node.col)
        if not (is_num(a) and is_num(b)):
            names = {"-": "subtract", "/": "divide", "//": "divide", "%": "find the remainder of", "**": "raise"}
            raise SwanError(f"I can only {names[op]} numbers, but got {self.a(a)} and {self.a(b)}.", node.line, node.col)
        if op == "-": return a - b
        if op == "**": return a ** b
        if b == 0:
            raise SwanError("Dividing by zero has no answer.", node.line, node.col,
                            "Check that the number you divide by isn't 0 first.")
        if op == "/":
            if isinstance(a, int) and isinstance(b, int) and a % b == 0:
                return a // b
            return a / b
        if op == "//": return math.floor(a / b) if isinstance(a, float) or isinstance(b, float) else a // b
        if op == "%": return a % b

    def equal(self, a, b):
        if isinstance(a, bool) != isinstance(b, bool): return False
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(self.equal(x, y) for x, y in zip(a, b))
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(self.equal(a[k], b[k]) for k in a)
        if isinstance(a, Instance) and isinstance(b, Instance):
            return a.shape is b.shape and self.equal(list(a.fields.values()), list(b.fields.values()))
        if isinstance(a, Range) and isinstance(b, Range):
            return (a.start, a.end, a.inclusive, a.step) == (b.start, b.end, b.inclusive, b.step)
        if type_name(a) != type_name(b): return False
        return a == b

    def compare(self, op, a, b, node):
        if op == "==": return self.equal(a, b)
        if op == "!=": return not self.equal(a, b)
        if op == "in": return self.contains(b, a, node)
        if op == "not in": return not self.contains(b, a, node)
        if (is_num(a) and is_num(b)) or (isinstance(a, str) and isinstance(b, str)):
            return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
        line, col = (node.line, node.col) if node else (0, 0)
        raise SwanError(f"I can't compare {self.a(a)} with {self.a(b)} using {op}.", line, col,
                        "Only numbers with numbers, or text with text, can be compared this way.")

    def contains(self, container, item, node):
        if isinstance(container, Ref): container = container.get()
        if isinstance(container, list): return any(self.equal(x, item) for x in container)
        if isinstance(container, str):
            if not isinstance(item, str):
                raise SwanError(f"I can only look for text inside text, not {self.a(item)}.", node.line, node.col)
            return item in container
        if isinstance(container, dict): return item in container
        if isinstance(container, Range): return is_num(item) and container.contains(item)
        raise SwanError(f"I can't look inside {self.a(container)}.", node.line, node.col,
                        "'in' works with lists, text, maps and ranges.")

    def position(self, seq, index, node):
        if not (isinstance(index, int) and not isinstance(index, bool)):
            raise SwanError(f"Positions must be whole numbers, not {self.a(index)}.", node.line, node.col)
        n = len(seq)
        i = index + n if index < 0 else index
        if not 0 <= i < n:
            what = "text" if isinstance(seq, str) else "list"
            hint = (f"Positions start at 0, so the last one is {n - 1} (or use -1)." if n
                    else f"This {what} is empty. first() and last() safely give nothing for empty lists.")
            raise SwanError(f"Position {index} is outside this {what}, which has {n} item{'s' if n != 1 else ''}.",
                            node.line, node.col, hint)
        return i

    def get_index(self, obj, index, node):
        while isinstance(obj, Ref):
            obj = obj.get()
        if isinstance(obj, Range):
            obj = list(obj.items())
        if isinstance(obj, (list, str)):
            if isinstance(index, Range):
                start, end = index.start, index.end
                if index.inclusive:
                    end = None if end == -1 else end + 1
                return obj[start:end]
            return obj[self.position(obj, index, node)]
        if isinstance(obj, dict):
            if index in obj:
                return obj[index]
            close = difflib.get_close_matches(str(index), [str(k) for k in obj], 1, 0.7)
            raise SwanError(f"This map has no key {self.show(index, True)}.", node.line, node.col,
                            f"Did you mean '{close[0]}'?" if close else "Use get(map, key, fallback) to give a backup value.")
        raise SwanError(f"I can't look inside {self.a(obj)} with [ ].", node.line, node.col)

    def set_index(self, obj, index, value, node):
        while isinstance(obj, Ref):
            obj = obj.get()
        if isinstance(obj, list):
            obj[self.position(obj, index, node)] = value
        elif isinstance(obj, dict):
            obj[index] = value
        elif isinstance(obj, str):
            raise SwanError("Text can't be changed one letter at a time.", node.line, node.col,
                            "Build new text instead, for example with replace(text, old, new).")
        else:
            raise SwanError(f"I can't put things inside {self.a(obj)} with [ ].", node.line, node.col)

    def get_member(self, obj, name, node, safe=False):
        while isinstance(obj, Ref):
            obj = obj.get()
        if obj is None and safe:
            return None
        if isinstance(obj, ParentView):
            obj = obj.me
        if isinstance(obj, Instance):
            if (name in obj.fields or name in obj.shape.methods) and self.is_hidden(obj, name):
                raise self.hidden_error(obj, name, node)
            if name in obj.fields: return obj.fields[name]
            if name in obj.shape.methods: return BoundMethod(obj.shape.methods[name], obj)
            visible = list(self.public_fields(obj))
            close = difflib.get_close_matches(name, visible + list(obj.shape.methods), 1, 0.6)
            raise SwanError(f"A {obj.shape.name} has no '{name}'.", node.line, node.col,
                            f"Did you mean '{close[0]}'?" if close else f"It has: {', '.join(visible) or 'no fields'}")
        if isinstance(obj, dict):
            if name in obj: return obj[name]
            if safe: return None
            close = difflib.get_close_matches(name, [str(k) for k in obj], 1, 0.6)
            raise SwanError(f"This map has no '{name}'.", node.line, node.col,
                            f"Did you mean '{close[0]}'?" if close else f"Use map?.{name} to get nothing instead of an error.")
        if isinstance(obj, (ShapeType, Ability)) and name == "name":
            return obj.name
        if name in ("length", "size") and isinstance(obj, (list, str, dict)):
            return len(obj)
        if isinstance(obj, Task) and name == "done":
            return obj.done.is_set()
        if obj is None:
            raise SwanError(f"Can't get '{name}' from nothing.", node.line, node.col,
                            f"Use ?. to safely skip nothing, like: thing?.{name}")
        hint = f"Did you mean to call it? .{name}()" if name in self.builtins else None
        raise SwanError(f"{self.a(obj).capitalize()} has no '{name}'.", node.line, node.col, hint)

    def set_member(self, obj, name, value, node):
        while isinstance(obj, Ref):
            obj = obj.get()
        if isinstance(obj, ParentView):
            obj = obj.me
        if isinstance(obj, Instance):
            if name in obj.fields and self.is_hidden(obj, name):
                raise self.hidden_error(obj, name, node)
            if name not in obj.fields:
                close = difflib.get_close_matches(name, list(obj.fields), 1, 0.6)
                raise SwanError(f"A {obj.shape.name} has no '{name}' to change.", node.line, node.col,
                                f"Did you mean '{close[0]}'?" if close else f"It has: {', '.join(obj.fields) or 'no fields'}")
            typ = obj.shape.field_types.get(name)
            if typ is not None:
                self.require_type(value, typ, obj.shape.env, f"{obj.shape.name}'s '{name}'", node)
            obj.fields[name] = value
        elif isinstance(obj, dict):
            obj[name] = value
        else:
            raise SwanError(f"I can't set '{name}' on {self.a(obj)}.", node.line, node.col)

    def to_list(self, v, node=None):
        if isinstance(v, Ref): v = v.get()
        if isinstance(v, list): return v
        if isinstance(v, Range): return list(v.items())
        if isinstance(v, str): return list(v)
        if isinstance(v, dict): return list(v.keys())
        line, col = (node.line, node.col) if node else (0, 0)
        raise SwanError(f"I expected a list here, but got {self.a(v)}.", line, col)

    def show(self, v, nested=False, seen=None):
        if v is None: return "nothing"
        if v is True: return "true"
        if v is False: return "false"
        if isinstance(v, int): return str(v)
        if isinstance(v, float):
            if v != v: return "not a number"
            if v in (math.inf, -math.inf): return "infinity" if v > 0 else "-infinity"
            return format(v, ".12g")
        if isinstance(v, str): return quote(v) if nested else v
        seen = seen or set()
        if id(v) in seen: return "[…]"
        if isinstance(v, list):
            seen = seen | {id(v)}
            return "[" + ", ".join(self.show(x, True, seen) for x in v) + "]"
        if isinstance(v, dict):
            seen = seen | {id(v)}
            return "{" + ", ".join(f"{k if is_plain_name(k) else self.show(k, True)}: {self.show(x, True, seen)}"
                                   for k, x in v.items()) + "}"
        if isinstance(v, Range):
            text = f"{self.show(v.start)}{'..' if v.inclusive else '..<'}{self.show(v.end)}"
            return text + (f" by {abs(v.step)}" if v.explicit_step else "")
        if isinstance(v, Instance):
            if "show" in v.shape.methods:
                return self.show(self.call_function(v.shape.methods["show"], [], {}, self.current_node or Node("x", None), v))
            if not v.fields and v.shape.parent is not None and v.shape.parent.variants:
                return v.shape.name
            seen = seen | {id(v)}
            return f"{v.shape.name}(" + ", ".join(f"{k}: {self.show(x, True, seen)}"
                                                  for k, x in self.public_fields(v).items()) + ")"
        if isinstance(v, Ref): return f"ref → {self.show(v.get(), True, seen)}"
        if isinstance(v, ShapeType): return f"<shape {v.name}>"
        if isinstance(v, Ability): return f"<ability {v.name}>"
        if isinstance(v, Task): return f"<task {v.name}, {'done' if v.done.is_set() else 'still running'}>"
        if isinstance(v, ParentView): return f"<parent {v.shape.name}>"
        if isinstance(v, BoundMethod): return f"<fn {v.fn.name}>"
        return f"<fn {v.name}>"

    # ── tests ──
    def run_tests(self):
        c = self.color
        if not self.tests:
            self.write("No tests found. Write one like this:\n\n  test \"adding\"\n      expect 1 + 1 == 2")
            return 0
        self.write(paint(f"Running {len(self.tests)} test{'s' if len(self.tests) != 1 else ''} from {self.filename}\n", "1", c))
        passed = failed = 0
        with self.baton:
            for node, env in self.tests:
                try:
                    try:
                        self.exec_block(node.body, Env(env))
                    except ReturnSignal:
                        pass
                    passed += 1
                    self.write("  " + paint("✓", "32", c) + " " + node.name)
                except SwanError as e:
                    if self.cancelled:
                        raise
                    failed += 1
                    self.write("  " + paint("✗", "31", c) + " " + paint(node.name, "1", c))
                    self.write("      " + e.message)
                    if e.hint:
                        self.write("      " + paint(e.hint, "90", c))
                    self.write(paint(f"      line {e.line}", "90", c))
        summary = paint(f"{passed} passed", "32", c)
        if failed:
            summary += ", " + paint(f"{failed} failed", "31", c)
        self.write("\n" + summary)
        return 1 if failed else 0

# ───────────────────────────── built-in tools ─────────────────────────────

def make_builtins(I):
    B = {}

    def tool(name, usage):
        def register(fn):
            B[name] = Builtin(name, fn, usage)
            return fn
        return register

    def need(ok, message, hint=None):
        if not ok:
            raise SwanError(message, hint=hint)

    def run(f, *args):
        need(is_callable(f), f"I expected a function here, but got {I.a(f)}.",
             "Pass a little function, like: n => n * 2")
        return I.call(f, list(args), {}, I.current_node)

    def items(x):
        return I.to_list(x)

    def text_arg(x, name):
        need(isinstance(x, str), f"{name} works on text, but got {I.a(x)}.")
        return x

    def num_arg(x, name):
        need(is_num(x), f"{name} works on numbers, but got {I.a(x)}.")
        return x

    @tool("say", "say(value, ...)")
    def say(*values):
        """Shows values on the screen."""
        I.write(" ".join(I.show(v) for v in values))
        return values[0] if len(values) == 1 else None

    @tool("ask", 'ask("Your name? ")')
    def ask(prompt=""):
        """Asks the person running the program to type something."""
        if I.input_lines is not None:
            answer = I.input_lines.pop(0) if I.input_lines else ""
            I.write(f"{I.show(prompt)}{answer}")
            return answer
        try:
            with I.released():
                return input(I.show(prompt))
        except EOFError:
            return ""

    @tool("length", "length(list)")
    def length(x):
        """How many items are in a list, letters in text, or keys in a map."""
        if isinstance(x, Range): return len(x.items())
        need(isinstance(x, (list, str, dict)), f"I can't measure the length of {I.a(x)}.")
        return len(x)

    @tool("text", "text(value)")
    def text(x):
        """Turns any value into text."""
        return I.show(x)

    @tool("number", 'number("42")')
    def number(x):
        """Turns text like "42" into a number."""
        if is_num(x): return x
        need(isinstance(x, str), f"I can't turn {I.a(x)} into a number.")
        s = x.strip().replace("_", "")
        for convert in (int, float):
            try:
                return convert(s)
            except ValueError:
                pass
        raise SwanError(f"I can't turn {quote(x)} into a number.", hint="Use try / otherwise if the text might not be a number.")

    @tool("type", "type(value)")
    def type_(x):
        """The name of a value's type, like "number" or "Swan"."""
        return type_name(x)

    @tool("help", "help(fn_or_shape)")
    def help_(x):
        """The notes written above a function, shape or ability with ---"""
        doc = getattr(x, "doc", None) or (x.fn.doc if isinstance(x, BoundMethod) else "")
        return doc or f"No notes for {I.show(x)}. Add some with --- just above it."

    @tool("round", "round(number, digits: 0)")
    def round_(x, digits=0):
        num_arg(x, "round")
        factor = 10 ** digits
        result = math.floor(abs(x) * factor + 0.5) / factor * (1 if x >= 0 else -1)
        return int(result) if digits == 0 else result

    @tool("floor", "floor(number)")
    def floor(x): return math.floor(num_arg(x, "floor"))

    @tool("ceil", "ceil(number)")
    def ceil(x): return math.ceil(num_arg(x, "ceil"))

    @tool("abs", "abs(number)")
    def abs_(x): return abs(num_arg(x, "abs"))

    @tool("sqrt", "sqrt(number)")
    def sqrt(x):
        num_arg(x, "sqrt")
        need(x >= 0, "Negative numbers don't have a square root.")
        root = math.sqrt(x)
        return int(root) if root.is_integer() and isinstance(x, int) else root

    @tool("min", "min(list) or min(a, b, ...)")
    def min_(*values):
        xs = items(values[0]) if len(values) == 1 else list(values)
        need(xs, "min needs at least one value.")
        return min(xs, key=I.ordering)

    @tool("max", "max(list) or max(a, b, ...)")
    def max_(*values):
        xs = items(values[0]) if len(values) == 1 else list(values)
        need(xs, "max needs at least one value.")
        return max(xs, key=I.ordering)

    @tool("sum", "sum(list)")
    def sum_(xs):
        total = 0
        for x in items(xs):
            need(is_num(x), f"sum can only add numbers, but the list has {I.a(x)}.")
            total += x
        return total

    @tool("average", "average(list)")
    def average(xs):
        xs = items(xs)
        need(xs, "average needs at least one number.")
        return I.binop("/", sum_(xs), len(xs), I.current_node)

    @tool("sort", "sort(list, by: item => item.age)")
    def sort(xs, by=None):
        xs = items(xs)
        keys = [run(by, x) for x in xs] if by is not None else xs
        order = sorted(range(len(xs)), key=lambda i: I.ordering(keys[i]))
        return [xs[i] for i in order]

    @tool("reverse", "reverse(list)")
    def reverse(x):
        return x[::-1] if isinstance(x, str) else items(x)[::-1]

    @tool("map", "map(list, n => n * 2)")
    def map_(xs, f): return [run(f, x) for x in items(xs)]

    @tool("keep", "keep(list, n => n > 2)")
    def keep(xs, f): return [x for x in items(xs) if I.truthy(run(f, x))]

    @tool("drop", "drop(list, n => n > 2)")
    def drop(xs, f): return [x for x in items(xs) if not I.truthy(run(f, x))]

    @tool("fold", "fold(list, start, (total, n) => total + n)")
    def fold(xs, start, f):
        acc = start
        for x in items(xs):
            acc = run(f, acc, x)
        return acc

    @tool("find", "find(list, n => n > 2)")
    def find(xs, f):
        for x in items(xs):
            if I.truthy(run(f, x)):
                return x
        return None

    @tool("any", "any(list, n => n > 2)")
    def any_(xs, f=None): return any(I.truthy(run(f, x) if f else x) for x in items(xs))

    @tool("all", "all(list, n => n > 2)")
    def all_(xs, f=None): return all(I.truthy(run(f, x) if f else x) for x in items(xs))

    @tool("count", "count(list, n => n > 2)")
    def count(xs, f=None):
        return sum(1 for x in items(xs) if I.truthy(run(f, x) if f else x))

    @tool("first", "first(list)")
    def first(xs):
        xs = items(xs)
        return xs[0] if xs else None

    @tool("last", "last(list)")
    def last(xs):
        xs = items(xs)
        return xs[-1] if xs else None

    @tool("push", "push(list, item)")
    def push(xs, *new):
        need(isinstance(xs, list), f"push adds to a list, but got {I.a(xs)}.")
        xs.extend(new)
        return xs

    @tool("pop", "pop(list)")
    def pop(xs):
        need(isinstance(xs, list), f"pop takes from a list, but got {I.a(xs)}.")
        need(xs, "Can't pop from an empty list.", "Check length(list) > 0 first.")
        return xs.pop()

    @tool("insert", "insert(list, position, item)")
    def insert(xs, pos, item):
        need(isinstance(xs, list), f"insert puts into a list, but got {I.a(xs)}.")
        xs.insert(pos, item)
        return xs

    @tool("remove", "remove(list, item)")
    def remove(xs, item):
        need(isinstance(xs, list), f"remove takes from a list, but got {I.a(xs)}.")
        for i, x in enumerate(xs):
            if I.equal(x, item):
                del xs[i]
                return True
        return False

    @tool("unique", "unique(list)")
    def unique(xs):
        out = []
        for x in items(xs):
            if not any(I.equal(x, y) for y in out):
                out.append(x)
        return out

    @tool("zip", "zip(list_a, list_b)")
    def zip_(a, b): return [[x, y] for x, y in zip(items(a), items(b))]

    @tool("join", 'join(list, ", ")')
    def join(xs, between=""):
        return text_arg(between, "join").join(I.show(x) for x in items(xs))

    @tool("split", 'split(text, ",")')
    def split(s, by=None):
        text_arg(s, "split")
        need(by != "", "split can't split by empty text.", "Use chars(text) to get each letter.")
        return s.split(by) if by is not None else s.split()

    @tool("chars", "chars(text)")
    def chars(s): return list(text_arg(s, "chars"))

    @tool("words", "words(text)")
    def words(s): return text_arg(s, "words").split()

    @tool("lines", "lines(text)")
    def lines(s): return text_arg(s, "lines").splitlines()

    @tool("upper", "upper(text)")
    def upper(s): return text_arg(s, "upper").upper()

    @tool("lower", "lower(text)")
    def lower(s): return text_arg(s, "lower").lower()

    @tool("trim", "trim(text)")
    def trim(s): return text_arg(s, "trim").strip()

    @tool("replace", 'replace(text, "old", "new")')
    def replace(s, old, new): return text_arg(s, "replace").replace(old, new)

    @tool("starts_with", 'starts_with(text, "Sw")')
    def starts_with(s, start): return text_arg(s, "starts_with").startswith(start)

    @tool("ends_with", 'ends_with(text, "an")')
    def ends_with(s, end): return text_arg(s, "ends_with").endswith(end)

    @tool("contains", "contains(list_or_text, item)")
    def contains(x, item): return I.contains(x, item, I.current_node)

    @tool("keys", "keys(map)")
    def keys(m):
        need(isinstance(m, dict), f"keys works on maps, but got {I.a(m)}.")
        return list(m.keys())

    @tool("values", "values(map)")
    def values(m):
        need(isinstance(m, dict), f"values works on maps, but got {I.a(m)}.")
        return list(m.values())

    @tool("has", "has(map, key)")
    def has(m, key):
        if isinstance(m, Instance): return key in m.fields or key in m.shape.methods
        need(isinstance(m, dict), f"has works on maps, but got {I.a(m)}.")
        return key in m

    @tool("get", "get(map, key, fallback)")
    def get(m, key, fallback=None):
        if isinstance(m, list):
            return m[key] if isinstance(key, int) and -len(m) <= key < len(m) else fallback
        need(isinstance(m, dict), f"get works on maps and lists, but got {I.a(m)}.")
        return m.get(key, fallback)

    @tool("copy", "copy(value)")
    def copy(x):
        if isinstance(x, list): return [copy(v) for v in x]
        if isinstance(x, dict): return {k: copy(v) for k, v in x.items()}
        if isinstance(x, Instance):
            new = Instance(x.shape)
            new.fields = {k: copy(v) for k, v in x.fields.items()}
            return new
        return x

    @tool("random", "random(1, 6) or random(list)")
    def random(a=None, b=None):
        if a is None: return _random.random()
        if b is None:
            xs = items(a)
            need(xs, "Can't pick from an empty list.")
            return _random.choice(xs)
        need(isinstance(a, int) and isinstance(b, int), "random(a, b) needs two whole numbers.")
        return _random.randint(min(a, b), max(a, b))

    @tool("now", "now()")
    def now(): return time.time()

    @tool("wait", "wait(seconds)")
    def wait(seconds):
        """Pauses for some seconds. Other tasks keep running meanwhile."""
        num_arg(seconds, "wait")
        end = time.time() + seconds
        with I.released():
            while time.time() < end and not I.cancelled:
                time.sleep(min(0.05, max(0, end - time.time())))
        I.check_cancelled()

    @tool("read_file", 'read_file("notes.txt")')
    def read_file(path):
        try:
            with open(text_arg(path, "read_file"), encoding="utf-8") as f:
                return f.read()
        except OSError:
            raise SwanError(f"I couldn't open the file {quote(path)}.", hint="Check the name and that the file exists.")

    @tool("write_file", 'write_file("notes.txt", text)')
    def write_file(path, content):
        try:
            with open(text_arg(path, "write_file"), "w", encoding="utf-8") as f:
                f.write(I.show(content))
        except OSError:
            raise SwanError(f"I couldn't write to the file {quote(path)}.")

    B["pi"] = math.pi
    return B

# ───────────────────────────── documentation ─────────────────────────────

def param_text(params):
    parts = []
    for p in params:
        text = ("hidden " if p.hidden else "") + ("..." if p.rest else "") + p.name
        if p.type is not None:
            text += f": {type_text(p.type)}"
        if p.default is not None:
            text += f" = {p.default_src}"
        parts.append(text)
    return ", ".join(parts)

def signature(node, prefix="fn"):
    text = f"{prefix} {node.name}({param_text(node.params)})"
    return text + (f" -> {type_text(node.returns)}" if node.returns is not None else "")

def collect_docs(program):
    """Everything worth documenting at the top level of a program."""
    entries = []
    for s in program:
        if s.kind == "Fn":
            entries.append({"kind": "fn", "name": s.name, "signature": signature(s), "doc": s.doc,
                            "line": s.line, "members": []})
        elif s.kind == "Shape":
            sig = f"shape {s.name}" + (f"({param_text(s.params)})" if s.params is not None else "")
            if s.parent: sig += f" from {s.parent}"
            if s.abilities: sig += " can " + ", ".join(s.abilities)
            members = [{"name": m.name, "doc": m.doc, "line": m.line,
                        "signature": ("hidden " if m.hidden else "") + signature(m) +
                                     ("   (left for the shapes that come from it)" if m.body is None else "")}
                       for m in s.methods.values()]
            entries.append({"kind": "shape", "name": s.name, "signature": sig, "doc": s.doc,
                            "line": s.line, "members": members})
        elif s.kind == "Ability":
            members = [{"name": m.name, "signature": signature(m) + "   (required)", "doc": m.doc, "line": m.line}
                       for m in s.required.values()]
            members += [{"name": m.name, "signature": signature(m), "doc": m.doc, "line": m.line}
                        for m in s.defaults.values()]
            entries.append({"kind": "ability", "name": s.name, "signature": f"ability {s.name}", "doc": s.doc,
                            "line": s.line, "members": members})
        elif s.kind == "Choice":
            members = [{"name": v.name, "doc": v.doc, "line": v.line,
                        "signature": v.name + (f"({param_text(v.params)})" if v.params is not None else "")}
                       for v in s.variants]
            entries.append({"kind": "choice", "name": s.name, "signature": f"choice {s.name}", "doc": s.doc,
                            "line": s.line, "members": members})
    return entries

def docs_markdown(entries, title):
    out = [f"# {title}", ""]
    if not entries:
        out.append("_Nothing to document yet. Write a function, shape or ability, with notes above it starting with `---`._")
    for kind, heading in (("choice", "Choices"), ("ability", "Abilities"), ("shape", "Shapes"), ("fn", "Functions")):
        group = [e for e in entries if e["kind"] == kind]
        if not group:
            continue
        out += [f"## {heading}", ""]
        for e in group:
            out += [f"### {e['name']}", "", "```swan", e["signature"], "```", ""]
            if e["doc"]:
                out += [e["doc"], ""]
            for m in e["members"]:
                out += [f"- `{m['signature']}`" + (f": {m['doc']}" if m["doc"] else "")]
            if e["members"]:
                out.append("")
    return "\n".join(out)

# ───────────────────────────── running ─────────────────────────────

def parse(source, docs=None):
    lines = source.split("\n")
    docs = {} if docs is None else docs
    return Parser(lex(source, docs), lines, docs).program()

def read_source(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        print(paint("✗ ", "31;1") + f"I couldn't find the file '{path}'.", file=sys.stderr)
        return None

def run_file(path, testing=False):
    source = read_source(path)
    if source is None:
        return 1
    interp = Interpreter(os.path.basename(path), testing)
    try:
        interp.run_program(parse(source))
        return interp.run_tests() if testing else 0
    except SwanError as e:
        report(e, source, os.path.basename(path))
    return 1

def docs_file(path):
    source = read_source(path)
    if source is None:
        return 1
    try:
        entries = collect_docs(parse(source))
    except SwanError as e:
        report(e, source, os.path.basename(path))
        return 1
    target = os.path.splitext(path)[0] + ".md"
    with open(target, "w", encoding="utf-8") as f:
        f.write(docs_markdown(entries, os.path.basename(path)))
    print(f"Wrote the documentation to {target}")
    return 0

HELP = """
  let name = "Odette"          a value that stays the same
  var count = 0                a value that can change
  say "Hello, {name}!"         show something
  fn double(n) => n * 2        a one-line function
  for n in 1..5                count (indent the lines underneath)
  nums |> keep(n => n > 2)     send a value through a pipeline
  let r = ref count            point at a value; read it with @r, change it with @r = 5

  bye                          leave the playground
"""

def opens_block(line):
    first = line.strip().split(" ", 1)[0]
    return first in ("if", "for", "while", "repeat", "shape", "try", "test", "match", "ability", "flock", "glide") or \
        (first == "fn" and "=>" not in line) or line.rstrip().endswith(("match", "=>")) or " glide " in line

def playground():
    print(paint(f"Swan {VERSION}", "1") + paint("  ·  type some code, 'help' for a reminder, 'bye' to leave", "90"))
    interp = Interpreter("playground")
    interp.globals.redefine = True
    while True:
        try:
            line = input(paint("swan> ", "36"))
        except EOFError:
            print()
            return 0
        if line.strip() in ("bye", "exit", "quit"):
            return 0
        if line.strip() == "help":
            print(HELP)
            continue
        if not line.strip():
            continue
        buffer = [line]
        while True:
            source = "\n".join(buffer)
            finished = buffer[-1].strip() == "" or (len(buffer) == 1 and not opens_block(line))
            try:
                program = parse(source)
            except SwanError as e:
                if e.incomplete and not finished:
                    program = None
                else:
                    report(e, source, "playground")
                    break
            if program is not None and finished:
                try:
                    value = interp.run_program(program)
                    if value is not None and len(program) == 1 and program[0].kind == "ExprStmt":
                        print(paint(interp.show(value, True), "33"))
                except SwanError as e:
                    report(e, source, "playground")
                break
            try:
                buffer.append(input(paint("  ... ", "90")))
            except EOFError:
                return 0

def prepare_threads():
    """Gives every thread room for deeply nested Swan calls."""
    sys.setrecursionlimit(80000)
    for megabytes in (128, 64, 32):
        try:
            threading.stack_size(megabytes * 1024 * 1024)
            return
        except ValueError:
            pass

def deep_thread(target):
    prepare_threads()
    return threading.Thread(target=target, daemon=True)

def main(argv):
    if argv and argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv and argv[0] in ("-v", "--version", "version"):
        print(f"Swan {VERSION}")
        return 0
    if argv and argv[0] in ("test", "docs"):
        if len(argv) < 2:
            print(f"Tell me which file, like: swan {argv[0]} program.swan")
            return 1
        return run_file(argv[1], testing=True) if argv[0] == "test" else docs_file(argv[1])
    if argv and argv[0] == "lake":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import lake
        return lake.serve(argv[1:])
    if argv:
        return run_file(argv[0])
    return playground()

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if os.name == "nt":
        os.system("")
    USE_COLOR = sys.stderr.isatty() and not os.environ.get("NO_COLOR")
    result = [1]
    worker = deep_thread(lambda: result.__setitem__(0, main(sys.argv[1:])))
    worker.start()
    try:
        while worker.is_alive():
            worker.join(0.2)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        os._exit(130)
    sys.stdout.flush()
    sys.exit(result[0])
