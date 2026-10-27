"""Throws good and broken programs at Swan. Every one must give the right output
or a friendly Swan error — never a Python crash."""
import io, os, sys, contextlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import swan

def run(source):
    out = io.StringIO()
    interp = swan.Interpreter("check")
    with contextlib.redirect_stdout(out):
        try:
            interp.run_program(swan.parse(source))
        except swan.SwanError as e:
            return out.getvalue(), e
    return out.getvalue(), None

WORKS = [
    ('say 1 + 2', "3"),
    ('say 7 / 2', "3.5"),
    ('say 7 // 2', "3"),
    ('say 2 ** 10', "1024"),
    ('say -2 ** 2', "-4"),
    ('say "a" * 3', "aaa"),
    ('say [1, 2] + [3]', "[1, 2, 3]"),
    ('say 1 < 2 < 3', "true"),
    ('say 3 > 2 > 5', "false"),
    ('say "lake" in "swan lake"', "true"),
    ('say 4 not in [1, 2]', "true"),
    ('say 1 == 1.0', "true"),
    ('say 1 == true', "false"),
    ('say nothing ?? 5', "5"),
    ('say 0..<3 |> map(n => n * 2)', "[0, 2, 4]"),
    ('say (1..10 by 3) |> map(n => n)', "[1, 4, 7, 10]"),
    ('say 3 in 1..5', "true"),
    ('say [1,2,3,4][1..2]', "[2, 3]"),
    ('say "swan"[-1]', "n"),
    ('say "swan"[1..-1]', "wan"),
    ('say sort([3, 1, 2])', "[1, 2, 3]"),
    ('say sort(["bb", "a", "ccc"], by: length)', '["a", "bb", "ccc"]'),
    ('say [3, 1].sort()', "[1, 3]"),
    ('say "Swan".upper().lower()', "swan"),
    ('say "a,b".split(",")', '["a", "b"]'),
    ('say [1, 2, 3].length', "3"),
    ('say fold([1, 2, 3], 0, (t, n) => t + n)', "6"),
    ('say round(2.5)', "3"),
    ('say round(3.14159, 2)', "3.14"),
    ('say sqrt(16)', "4"),
    ('say max([4, 9, 2])', "9"),
    ('say min(5, 3)', "3"),
    ('say average([1, 2])', "1.5"),
    ('say unique([1, 1, 2])', "[1, 2]"),
    ('say first([])', "nothing"),
    ('say number("42") + 1', "43"),
    ('say type(1)', "number"),
    ('say type({})', "map"),
    ('say {a: 1} + {b: 2}', "{a: 1, b: 2}"),
    ('say "{1 + 1} and {"x"}"', "2 and x"),
    ('say "braces: \\{ok\\}"', "braces: {ok}"),
    ('say "tab:\\tdone"', "tab:\tdone"),
    ('var x = 1\nx += 2\nsay x', "3"),
    ('let a, b = 1, 2\nsay a + b', "3"),
    ('let [x] = 5', None),
    ('fn f(...all) => length(all)\nsay f(1, 2, 3)', "3"),
    ('fn f(a, b = a * 2) => a + b\nsay f(1)', "3"),
    ('fn f(n)\n    if n == 0 then return "done"\n    return f(n - 1)\nsay f(500)', "done"),
    ('let add = fn(a, b) => a + b\nsay add(2, 3)', "5"),
    ('let nums = [1, 2, 3]\nsay [n * 2 for n in nums]', "[2, 4, 6]"),
    ('for i, c in "ab"\n    say i, c', "0 a\n1 b"),
    ('var n = 0\nwhile true\n    n += 1\n    if n == 3 then stop\nsay n', "3"),
    ('for n in 1..5\n    if n % 2 == 0 then skip\n    say n', "1\n3\n5"),
    ('var r = ref 0\n@r += 1\nsay @r', "1"),
    ('let r = ref [1, 2]\nsay r.length', "2"),
    ('shape P(x, y)\nvar p = P(1, 2)\np.x = 5\nsay p', "P(x: 5, y: 2)"),
    ('shape P(x)\nsay P(1) == P(1)', "true"),
    ('shape C(n = 0)\n    fn bump()\n        n += 1\n        me\nsay C().bump().bump().n', "2"),
    ('shape A(v)\n    fn setup()\n        v = v * 10\nsay A(2).v', "20"),
    ('let m = {}\nm.x = 1\nm["y"] = 2\nsay m', "{x: 1, y: 2}"),
    ('let size = match 5\n    1..3 => "small"\n    _ => "big"\nsay size', "big"),
    ('if 1 > 2\n    say "no"\nelse if 2 > 1\n    say "yes"', "yes"),
    ('let x = [1,\n    2,\n    3]\nsay x', "[1, 2, 3]"),
    ('say 1 -- a comment', "1"),
    ('let l = [3]\nl.push(4)\nsay l', "[3, 4]"),
    ('say 5 |> say', "5\n5"),
    ('let a = [1]\na.push(a)\nsay a', "[1, […]]"),
    ('say 10 / 4 * 4', "10"),
    # shapes from shapes, abilities, parent
    ('shape A(x)\n    fn hi() => "A{x}"\nshape B from A\n    fn hi() => "B" + parent.hi()\nsay B(1).hi()', "BA1"),
    ('shape A(x)\nshape B from A\nsay B(1) is A, A(1) is B', "true false"),
    ('ability Talk\n    fn talk()\n    fn twice() => talk() + talk()\nshape D can Talk\n    fn talk() => "w"\nsay D().twice()', "ww"),
    ('ability Talk\n    fn talk()\nshape D can Talk\n    fn talk() => 1\nsay D() is Talk, 5 is Talk', "true false"),
    ('shape B from A\nshape A(x)\nsay B(2).x', "2"),
    ('shape S(n)\n    fn glide() => n\nsay S(3).glide()', "3"),
    # glide
    ('say glide [3, 1, 2]\n    sort', "[1, 2, 3]"),
    ('let p = [{n: "b", a: 2}, {n: "a", a: 9}]\nsay glide p\n    keep a > 1\n    sort n\n    pick n', '["a", "b"]'),
    ('say glide [1, 2, 3, 4]\n    group it % 2\n    pick key', "[1, 0]"),
    ('say glide 1..10\n    keep it > 3\n    first 2', "[4, 5]"),
    ('say glide [1, 2, 2]\n    unique\n    reverse', "[2, 1]"),
    # choices
    ('choice C\n    A\n    B(v)\nfn f(c)\n    match c\n        A => "a"\n        B(v) => "b{v}"\nsay f(A), f(B(2))', "a b2"),
    ('choice C\n    A\n    B(v)\nsay A, B(1), A is C', "A B(v: 1) true"),
    # types
    ('let x: number = 3\nsay x', "3"),
    ('fn f(x: number?) => x ?? 0\nsay f(nothing)', "0"),
    ('fn f(x: number or text) => x\nsay f("a"), f(1)', "a 1"),
    ('say 3 is number, "a" is not number', "true true"),
    # tasks
    ('fn f(n) => n * 2\nflock\n    a = f(1)\n    b = f(2)\nsay a + b', "6"),
    ('fn f(n)\n    wait(0.01)\n    n\nsay await [spawn f(1), spawn f(2)]', "[1, 2]"),
    ('fn f(n) => n\nlet t = spawn f(5)\nsay await t, await t', "5 5"),
    # docs
    ('--- adds\nfn add(a, b) => a + b\nsay help(add)', "adds"),
    # hidden (encapsulation) and outlines (abstraction)
    ('shape A(hidden v)\n    fn get() => v\nsay A(3).get()', "3"),
    ('shape A(n, hidden v)\nsay A(1, 2)', "A(n: 1)"),
    ('shape A(hidden v)\n    fn same(o) => v == o.v\nsay A(1).same(A(1))', "true"),
    ('shape A(hidden v)\nshape B from A\n    fn get() => v * 2\nsay B(2).get()', "4"),
    ('shape A(n)\n    hidden fn secret() => n * 10\n    fn reveal() => secret()\nsay A(2).reveal()', "20"),
    ('shape A(hidden v)\n    fn bump()\n        v += 1\n        v\nsay A(1).bump()', "2"),
    ('shape Animal(name)\n    fn sound()\n    fn speak() => "{name}: {sound()}"\nshape Dog from Animal\n    fn sound() => "woof"\nsay Dog("Rex").speak()', "Rex: woof"),
]

FAILS = [
    # (program, words that must appear in the message or hint)
    ('say 1 / 0', "zero"),
    ('say "a" + 1', "braces"),
    ('let x = 1\nx = 2', "made with let"),
    ('y = 5', "var y"),
    ('say nmae\nlet name = 1', "I don't know"),
    ('let name = 1\nsay nmae', "Did you mean 'name'"),
    ('print("hi")', "say"),
    ('say [1, 2][5]', "Positions start at 0"),
    ('say [][0]', "empty"),
    ('say {a: 1}.b', "?."),
    ('say {a: 1}["b"]', "fallback"),
    ('if x > 3:\n    say 1', "colon"),
    ('if 1 = 1\n    say 1', "=="),
    ('if true\nsay 1', "indented"),
    ('say "hello', "closing quote"),
    ('say 1;', "semicolons"),
    ('say 1 && 2', "and"),
    ('say !true', "not"),
    ('# hi', "--"),
    ('fn f(a) => a\nf()', "needs a value for 'a'"),
    ('fn f(a) => a\nf(1, 2)', "takes 1 value"),
    ('fn f(name) => name\nf(nme: 1)', "Did you mean 'name'"),
    ('fn f() => f()\nf()', "calling itself"),
    ('let x = 1\nlet x = 2', "already exists"),
    ('stop', "inside a loop"),
    ('for n in 5\n    say n', "repeat 5"),
    ('match 3\n    1 => say 1', "_ =>"),
    ('shape P(x)\nP(1).y', "has no 'y'"),
    ('shape P(x)\nvar p = P(1)\np.z = 1', "has no 'z'"),
    ('let r = 5\n@r = 1', "ref"),
    ('let x = 1\nlet r = ref x\n@r = 2', "made with let"),
    ('fail "custom problem"', "custom problem"),
    ('say "a" < 1', "compare"),
    ('say length(5)', "length"),
    ('say map([1], 5)', "function"),
    ('say sort([1, "a"])', "compare"),
    ('say number("abc")', "number"),
    ('say sqrt(-1)', "square root"),
    ('let s = "abc"\ns[0] = "x"', "Text can't be changed"),
    ('say 1..2 by 0', "step by 0"),
    ('say "{}"', "empty {}"),
    ('say "{1 +}"', "value"),
    ('say pop([])', "empty list"),
    ('x++', "+="),
    ('say nothing.name', "?."),
    ('say 5()', "can call"),
    ('let = 4', "name"),
    ('fn (', "name"),
    ('say (1', ")"),
    ('    say 1', "indent"),
    ('if true\n    say 1\n  say 2', "line up"),
    ('say 1..2.5 |> map(n => n)', "whole numbers"),
    ('say "x".nope()', "no 'nope'"),
    ('len([1])', "length"),
    # new features, used wrongly
    ('ability Fly\n    fn fly()\nshape S can Fly', "has no fly()"),
    ('shape S can Fly', "ability"),
    ('shape S from Nope', "don't know a shape"),
    ('shape A from B\nshape B from A', "comes back around"),
    ('ability Fly\n    fn fly()\nFly()', "ability"),
    ('choice C\n    A\n    B\nmatch A\n    A => 1', "B is missing"),
    ('choice C\n    a', "capital"),
    ('let x: number = "5"', "number(value)"),
    ('var x: text = "a"\nx = 5', "should be text"),
    ('fn f(x: number) => x\nf("a")', "should be a number"),
    ('fn f() -> number => "a"\nf()', "give back"),
    ('let x: nmber = 1', "Did you mean 'number'"),
    ('shape P(x: number)\nvar p = P(1)\np.x = "a"', "should be a number"),
    ('say glide [1]\n    kep it', "Did you mean 'keep'"),
    ('say glide [1]\n    first', "needs something"),
    ('fn bad()\n    fail "boom"\nawait spawn bad()', "boom"),
    ('fn bad()\n    fail "boom"\nspawn bad()', "boom"),
    ('flock\n    let x = 1', "function call"),
    ('spawn 5', "function call"),
    ('let flock = 1', "special words"),
    ('class Swan', "shapes"),
    ('shape A(x)\n    fn f() => parent.f()\nA(1).f()', "parent"),
    ('shape A(hidden v)\nsay A(1).v', "hidden inside A"),
    ('shape A(hidden v)\nvar a = A(1)\na.v = 2', "hidden inside A"),
    ('shape A(n)\n    hidden fn s() => 1\nA(1).s()', "hidden inside A"),
    ('hidden let x = 1', "inside a shape"),
    ('use mathz', "Did you mean 'maths'"),
    ('use maths\nsay maths.gdc(4, 6)', "Did you mean 'gcd'"),
    ('use maths\nsay maths.whole(1, "x")', "hidden inside the maths"),
    ('use whole from maths', "hidden inside the maths"),
    ('use maths\nsay maths.factorial(2.5)', "whole number"),
    ('use maths\nsay maths.median([])', "maths library"),
    ('use draw\nsay draw.pad("a", 3, align: "up")', "center"),
    ('use maths\nmaths = 1', "maths"),
    ('shape Animal\n    fn sound()\nAnimal()', "outline"),
    ('shape Animal\n    fn sound()\nshape Cat from Animal\nCat()', "outline"),
]

# libraries: use, maths and draw
WORKS += [
    ('use maths\nsay maths.gcd(12, 18)', "6"),
    ('use maths as m\nsay m.primes(10)', "[2, 3, 5, 7]"),
    ('use lcm, is_prime from maths\nsay lcm(4, 6), is_prime(7)', "12 true"),
    ('use maths\nuse maths\nsay maths.median([3, 1, 2])', "2"),
    ('use maths\nsay maths', "<library maths>"),
    ('use maths\nsay type(maths)', "library"),
    ('fn f() => maths.factorial(4)\nsay f()\nuse maths', "24"),
    ('use maths\nsay [2, 9, 4] |> maths.spread', "7"),
    ('use draw\nsay draw.progress(1, 2, width: 4)', "[██░░] 50%"),
    ('use box from draw\nsay box("hi")', "┌────┐\n│ hi │\n└────┘"),
    ('let use = 3\nsay use', "3"),
    ('fn use(x) => x * 2\nsay use(4)', "8"),
]

def attempt(source):
    try:
        return run(source)
    except Exception as e:
        print(f"CRASH  {source!r}\n       {type(e).__name__}: {e}")
        return None

def check_all():
    failures = 0
    for source, expected in WORKS:
        result = attempt(source)
        if result is None:
            failures += 1
            continue
        out, err = result
        if expected is not None and (err is not None or out.rstrip("\n") != expected):
            failures += 1
            print(f"WRONG  {source!r}\n       wanted {expected!r}, got {out.rstrip()!r} {err.message if err else ''}")

    for source, words in FAILS:
        result = attempt(source)
        if result is None:
            failures += 1
            continue
        out, err = result
        if err is None:
            failures += 1
            print(f"NO ERROR  {source!r}  printed {out!r}")
            continue
        text = f"{err.message} {err.hint or ''}"
        if words.lower() not in text.lower() or not err.line:
            failures += 1
            print(f"UNCLEAR  {source!r}\n       wanted {words!r} in: {text!r} (line {err.line})")

    total = len(WORKS) + len(FAILS)
    print(f"\n{total - failures}/{total} checks passed")
    return failures

outcome = [1]
worker = swan.deep_thread(lambda: outcome.__setitem__(0, check_all()))
worker.start()
worker.join()
sys.exit(1 if outcome[0] else 0)
