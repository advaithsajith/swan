# Learning Swan

A gentle course in fifteen short lessons. You don't need any programming experience.
Each lesson takes about ten minutes and ends with a small **Try it** exercise. The answers are at the end.

**Before you start:** open Lake, the Swan editor.

```bash
python swan.py lake
```

Click **+** next to *Files* to make a new file. Type the examples in yourself rather than copying them;
your fingers learn faster than your eyes. Press **Ctrl+Enter** to run.

---

## Lesson 1 · First ripple

```swan
say "Hello, lake!"
```

`say` shows something in the **Reflection** panel. Text goes inside quotes.

Lines that start with `--` are notes for people. Swan ignores them:

```swan
-- This is a note. It doesn't do anything.
say "But this line does."
```

> **Try it 1:** Make Swan say your name, then say your favourite animal on a second line.

---

## Lesson 2 · Remembering things

A program remembers things with names.

```swan
let name = "Odette"       -- let: this will never change
var swans = 12            -- var: this is allowed to change

swans = swans + 3
swans += 1                -- a shorter way to add

say "{name} counts {swans} swans."
```

Anything inside `{ }` in text is worked out and dropped into place.

Swan has a few kinds of values:

| Kind | Looks like |
|---|---|
| number | `12`, `3.5`, `-4` |
| text | `"Odette"` or `'Odette'` |
| bool | `true`, `false` |
| nothing | `nothing`, meaning "no value here" |

Maths works the way you'd hope: `+ - * /`, plus `**` for powers and `%` for remainders.

**Why `let` and `var`?** If you write `let` and later try to change the value, Swan stops you. Lots of bugs
come from changing something by accident. With `let`, that can't happen.

> **Try it 2:** Make `let price = 4` and `var tickets = 3`. Add 2 to `tickets`, then say
> `"Total: ..."` with the price times the tickets.

---

## Lesson 3 · Making decisions

```swan
let temperature = 18

if temperature > 25
    say "Warm water."
elif temperature >= 10
    say "Perfect for gliding."
else
    say "Too cold. Stay in the reeds."
```

The indented lines (four spaces) belong to the line above them. Lake indents for you when you press Enter.

To compare things, use `==` (equal), `!=` (not equal), `<`, `<=`, `>` and `>=`.
Combine comparisons with `and`, `or` and `not`. They can also chain: `10 <= temperature <= 25`.

For a short decision, use `then`:

```swan
if temperature < 0 then say "The lake is frozen!"
let mood = if temperature > 15 then "happy" else "sleepy"
```

> **Try it 3:** Make `let age = 15`. Say `"child"` if age is under 13, `"teen"` if under 20, and `"adult"` otherwise.

---

## Lesson 4 · Repeating

```swan
for n in 1..5            -- 1, 2, 3, 4, 5
    say n

for n in 5..1            -- counts down by itself
    say n
say "Curtain up!"

repeat 3
    say "~ ripple ~"
```

Some more ranges: `0..<5` stops before 5, and `0..100 by 10` jumps in tens.

`while` keeps going as long as something is true:

```swan
var energy = 3
while energy > 0
    say "Swimming… energy {energy}"
    energy -= 1
```

Inside a loop, `stop` leaves it early, and `skip` jumps straight to the next round.

> **Try it 4:** Say every number from 1 to 20 that divides evenly by 3. (Hint: `n % 3 == 0`.)

---

## Lesson 5 · Lists and maps

A **list** holds things in order:

```swan
var birds = ["Odette", "Odile", "Pip"]

say birds[0]          -- the first one (positions start at 0)
say birds[-1]         -- the last one
say birds.length      -- 3

birds.push("Benno")   -- add one to the end
for bird in birds
    say bird
```

A **map** holds things by name:

```swan
let ballet = {title: "Swan Lake", year: 1877}
say ballet.title
for key, value in ballet
    say "{key}: {value}"
```

If you ask for position 10 of a three-item list, Swan doesn't crash in a confusing way. It tells you
exactly what went wrong and which positions exist.

> **Try it 5:** Make a list of five numbers and say the first, the last, and how many there are.

---

## Lesson 6 · Functions

A function is a recipe you can use again and again.

```swan
fn greet(who, greeting = "Hello")
    say "{greeting}, {who}!"

greet("Odette")
greet("Siegfried", greeting: "Good evening")
```

A function can work something out and give the answer back:

```swan
fn square(n) => n * n          -- one-line function

fn describe(n)
    if n > 100 then return "huge"
    "small"                    -- the last line is the answer

say square(7)                  -- 49
say describe(square(11))       -- huge
```

Tiny unnamed functions are written with an arrow: `n => n * 2`. You'll use them a lot in the next lesson.

> **Try it 6:** Write `fn is_even(n)` that gives back `true` or `false`. Use it to say which numbers from 1 to 6 are even.

---

## Lesson 7 · Pipelines and glide

The pipe `|>` passes a value along to the next step, like water flowing:

```swan
1..10
    |> keep(n => n % 2 == 0)     -- keep the even ones
    |> map(n => n * n)           -- square each
    |> sum                       -- add them up
    |> say                       -- 220
```

When you work with lists of records, `glide` reads like a sentence:

```swan
let dancers = [
    {name: "Odette", age: 24, city: "Paris"},
    {name: "Benno", age: 17, city: "Paris"},
    {name: "Odile", age: 23, city: "Vienna"},
]

let adults = glide dancers
    keep age >= 18
    sort name
    pick name

say adults        -- ["Odette", "Odile"]
```

Inside each step, you can use the fields (`age`, `name`) directly, or `it` for the whole item.
The steps are `keep`, `drop`, `sort` (add `descending` to reverse it), `pick`, `first 3`, `last 3`,
`unique`, `reverse` and `group`.

> **Try it 7:** Using `dancers`, make a list of the cities with nobody repeated. (Hint: `pick city`, then `unique`.)

---

## Lesson 8 · Match

`match` compares a value against several patterns and runs the first one that fits:

```swan
fn describe(x)
    match x
        0 => "zero"
        1..9 => "a small number"
        "swan" or "cygnet" => "a bird"
        [] => "an empty list"
        [first, ...rest] => "a list starting with {first}"
        n if n < 0 => "below zero"
        _ => "something else"        -- _ matches anything
```

`match` gives back a value, so you can write `let size = match n`.

> **Try it 8:** Write FizzBuzz with `match`. For 1 to 15, say "FizzBuzz" if a number divides by 3 and 5,
> "Fizz" for 3, "Buzz" for 5, and otherwise the number itself.
> (Hint: `match [n % 3, n % 5]` and patterns like `[0, 0]`.)

---

## Lesson 9 · Shapes: making your own kinds of things

A **shape** describes a kind of thing: what it has and what it can do.

```swan
shape Swan(name, wingspan, color = "white")
    fn describe() => "{name}, a {color} swan with {wingspan}m wings"

    fn grow(amount)
        wingspan += amount

let odette = Swan("Odette", 2.1)
odette.grow(0.2)
say odette.describe()
say odette            -- Swan(name: "Odette", wingspan: 2.3, color: "white")
```

Inside a shape's functions, you use its fields by name: just `wingspan`, with no `self.` needed.
If you ever need the whole thing, it's called `me`.

> **Try it 9:** Make a `shape Lamp(on = false)` with a `fn switch()` that flips `on`, and a `fn show()`
> that gives back `"lamp: on"` or `"lamp: off"`.

---

## Lesson 10 · The four pillars

Big programs stay tidy thanks to four ideas, known as the **four pillars**. Swan has all four.

### Encapsulation: calm above, paddling below
A swan looks still on the water while its feet do the work out of sight. Mark the inner workings of a
shape `hidden`, and only that shape's own functions can touch them:

```swan
shape BoxOffice(show, hidden seats = 100)
    fn sell(count)
        if count > seats then fail "only {seats} seats left"
        seats -= count
    fn seats_left() => seats

let office = BoxOffice("Swan Lake")
office.sell(2)
say office.seats_left()   -- 98
office.seats = 5000       -- ✗ 'seats' is hidden inside BoxOffice.
```
Nobody outside can break the rules, because the only way in is through `sell`.

### Inheritance: a cygnet comes from a swan
```swan
shape Bird(name)
    fn describe() => "{name} is a bird"

shape Swan from Bird                      -- gets everything Bird has
    fn describe() => parent.describe() + " — a swan!"
```
`parent.` runs the version from the shape it came from.

### Abstraction: an outline
Write a function with no body, and the shape becomes an **outline**. It says *what* must be done
and leaves *how* to the shapes that come from it:

```swan
shape Musician(name)
    fn sound()                                   -- no body: left to others
    fn play() => "{name} plays {sound()}"

shape Harpist from Musician
    fn sound() => "rippling water"
```
`Musician("Lev")` isn't allowed, because an outline can't be made directly. A `Harpist` can.

An **ability** is an outline that any shape can take on, even unrelated ones:

```swan
ability Glide
    fn glide()
    fn perform() => "{name}: {glide()}"        -- free for everyone who can Glide

shape Swan(name) can Glide
    fn glide() => "without a ripple"

shape Boat(name) can Glide
    fn glide() => "with the current"
```

### Polymorphism: one call, many answers
```swan
for thing in [Swan("Odette"), Boat("Lily")]
    say thing.perform()        -- each one glides its own way

if thing is Glide then ...     -- ask what something can do
fn race(a: Glide, b: Glide)    -- accept anything that can Glide
```

> **Try it 10:** Make an outline `shape Shape2D` with `fn area()` left empty. Make `Square(side)`
> and `Circle(radius)` come from it. Loop over a list of both and say each area.

---

## Lesson 11 · Choices, types and nothing

A **choice** is a value that is exactly one of a few options:

```swan
choice Weather
    Sunny
    Rain(mm)
    Storm(wind)

fn advice(today)
    match today
        Sunny => "Go gliding!"
        Rain(mm) => "{mm}mm of rain. Take cover."
        Storm(wind) => "Wind at {wind}. Stay home."
```
If you forget an option in the `match`, Swan tells you, so a forgotten case can never slip through.

**Types are optional.** Swan works them out, but you can add them wherever you want a guard:

```swan
let age: number = 16
fn area(radius: number) -> number => pi * radius ** 2
```

A plain `number` can never secretly be `nothing`. If something might be missing, say so with `?`,
then handle it with `??` ("or else") and `?.` ("only if it's there"):

```swan
fn find_age(name) -> number? => get({Odette: 24}, name)

say find_age("Pip") ?? "unknown"
say person?.address?.city ?? "no city"
```

> **Try it 11:** Make `choice Light` with `Red`, `Amber` and `Green`, and a function that says what a driver should do for each.

---

## Lesson 12 · Refs: pointing at things

A **ref** points at a value somewhere else. Read it with `@`, and change it with `@`:

```swan
var score = 10
let p = ref score
@p += 5
say score              -- 15

fn add_bonus(target, amount)
    @target += amount

add_bonus(ref score, 100)
say score              -- 115
```

Refs are the safe version of C and Rust *pointers*. They can never be empty, never point at something
that has gone, and never change a `let`.

> **Try it 12:** Write `fn double_it(target)` that doubles whatever the ref points at. Try it on a `var`.

---

## Lesson 13 · When things go wrong

Every Swan error says what happened, shows the line, and gives a hint:

```
✗ I can't add text and a number together.
  2 │ say "Score: " + score
                    ^
  hint: To put a value inside text, use braces: "Score: {score}"
```

Raise your own problem with `fail`, and catch problems with `try` / `otherwise`:

```swan
fn divide(a, b)
    if b == 0 then fail "can't divide by zero"
    a / b

try
    say divide(10, 0)
otherwise problem
    say "Caught it: {problem}"
```

> **Try it 13:** Use `number(text)` to turn `"42"` and `"forty"` into numbers, catching the one that fails.

---

## Lesson 14 · Tests and notes

Tests sit right next to your code:

```swan
fn square(n) => n * n

test "squares"
    expect square(3) == 9
    expect square(-2) == 4
```

Press **Test** in Lake (Ctrl+Shift+Enter), or run `swan test file.swan`. A failing test shows both sides,
for example `left side was 8, right side was 9`.

Lines starting with `---` are **notes** about whatever comes next. They appear in Lake's **Docs** tab:

```swan
--- Works out the area of a circle from its radius.
fn area(radius: number) -> number
    pi * radius ** 2
```

> **Try it 14:** Add a test for your `is_even` function from Lesson 6, with one even and one odd number.

---

## Lesson 15 · flock: doing things at the same time

Some jobs mostly *wait*: downloading, timers, slow machines. A `flock` lets them wait together:

```swan
fn slow_hello(name)
    wait(1)
    "hello, {name}"

flock
    a = slow_hello("Odette")
    b = slow_hello("Odile")
    c = slow_hello("Pip")

say a, b, c      -- took about 1 second, not 3
```

For more control, `spawn` starts a task and `await` collects its answer:

```swan
let task = spawn slow_hello("Benno")
say "doing other things…"
say await task
```

Tasks take turns safely, so they can never scramble the same value. If a task fails, the problem
always reaches you.

> **Try it 15:** Make five tasks with `[spawn slow_hello(n) for n in 1..5]` and `await` them all.

---

## Final project · The Swan Lake box office

Put it all together. Build a small program that:

1. Has a `shape Show(title, hidden seats)` with `book(count)` and `seats_left()`.
2. Keeps a list of three shows.
3. Uses `glide` to list the shows that still have seats, sorted by title.
4. Uses `try` / `otherwise` to refuse a booking that's too big.
5. Has at least three `test` blocks.

Then run your tests until every line is green. ✓

---

## Answers

<details><summary>Show the answers</summary>

```swan
-- 1
say "Ada"
say "swan"

-- 2
let price = 4
var tickets = 3
tickets += 2
say "Total: {price * tickets}"

-- 3
let age = 15
if age < 13
    say "child"
elif age < 20
    say "teen"
else
    say "adult"

-- 4
for n in 1..20
    if n % 3 == 0 then say n

-- 5
let nums = [4, 8, 15, 16, 23]
say nums[0], nums[-1], nums.length

-- 6
fn is_even(n) => n % 2 == 0
for n in 1..6
    say n, is_even(n)

-- 7
say glide dancers
    pick city
    unique

-- 8
for n in 1..15
    say match [n % 3, n % 5]
        [0, 0] => "FizzBuzz"
        [0, _] => "Fizz"
        [_, 0] => "Buzz"
        _ => n

-- 9
shape Lamp(on = false)
    fn switch()
        on = not on
    fn show() => if on then "lamp: on" else "lamp: off"

-- 10
shape Shape2D
    fn area()
shape Square(side) from Shape2D
    fn area() => side * side
shape Circle(radius) from Shape2D
    fn area() => round(pi * radius ** 2, 2)
for s in [Square(2), Circle(1)]
    say s.area()

-- 11
choice Light
    Red
    Amber
    Green
fn drive(light)
    match light
        Red => "stop"
        Amber => "get ready"
        Green => "go"

-- 12
fn double_it(target)
    @target *= 2
var x = 21
double_it(ref x)
say x

-- 13
for raw in ["42", "forty"]
    try
        say number(raw)
    otherwise problem
        say "Not a number: {raw}"

-- 14
test "even and odd"
    expect is_even(4)
    expect not is_even(7)

-- 15
say await [spawn slow_hello(n) for n in 1..5]
```

</details>
