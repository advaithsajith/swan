# Changelog

## Unreleased

- **Libraries:** bring in extra tools with `use maths`, `use maths as m` or `use gcd, lcm from maths`.
  Errors inside a library point at the line in your code that called it, and `hidden fn` keeps a library's helpers private.
- **maths library:** `gcd`, `lcm`, primes and factors, `factorial`, `fibonacci`, `clamp`, `percent`, and
  statistics (`median`, `mode`, `spread`, `deviation`).
- **draw library:** text pictures for the terminal: `box`, `table`, `bars`, `progress`, `pad` and `divider`.
- Libraries work in Lake on your computer and in the browser; there's a new [libraries.swan](examples/libraries.swan) example.
- **Five more libraries**, shown off in [toolbox.swan](examples/toolbox.swan):
  - **lists:** `take`, `rest`, `chunk`, `windows`, `flatten`, `rotate`, `transpose`, `tally`, `group_by`, `partition`, `max_by` and more.
  - **prose:** text tools like `title_case`, `slug`, `wrap`, `plural`, `ordinal`, `with_commas`, plus `pig_latin` and the `caesar` cipher.
  - **chance:** `coin`, `dice`, `roll`, `maybe`, `shuffle`, `pick_many`, `weighted` and random `code`s.
  - **clock:** `date`, `timestamp`, `date_text`, `weekday`, `days_between`, `duration`, a `Stopwatch` shape, and constants like `clock.day`.
  - **units:** `temperature`, `distance`, `weight`, `speed` and `file_size`.
- **Fifty more libraries**, so there are 57 in all, grouped in the README:
  - *Numbers and maths:* trig, geometry, fractions, vectors, matrix, stats, sequences, combos, solve, physics, roman, bases, finance, money.
  - *Text:* spell, wordplay, cipher, morse, diff, template, markdown, emoji.
  - *Lists and data:* sets, search, sorting, collections, graph, grid, csv, json (a full JSON reader and writer).
  - *Time, measures and the world:* calendar, birthday, planets, music, colors.
  - *Pictures made of text:* plot, canvas, maze, life.
  - *Games and chance:* cards, tictactoe, hangman, wordle, quiz.
  - *Building programs:* validate, memo, log, machine, prompt, todo.
- Two new examples, [arcade.swan](examples/arcade.swan) and [notebook.swan](examples/notebook.swan), and 58 new checks.
- A library that itself says `use maths` no longer lists `maths` among its own tools, and browser Lake loads
  library files in parallel, so the bigger set doesn't slow it down.

## 0.3 · preview

The first public release.

- **Language:** values, functions, pipelines, ranges, `match`, maps and lists, and kind error messages with hints.
- **Shapes:** fields and functions, `from` for inheritance, `parent.`, `hidden` for encapsulation,
  outline shapes and abilities for abstraction, and `is` for polymorphism.
- **`glide`:** step-by-step data processing (`keep`, `sort`, `pick`, `group` and more).
- **`flock`, `spawn` and `await`:** run jobs at the same time, safely.
- **`choice`:** options that carry data, with a check that every `match` handles every option.
- **Types and nothing:** optional types, `number?`, `?.` and `??`.
- **Refs:** safe pointers with `ref` and `@`.
- **Tests and docs:** `test` and `expect` blocks, `---` notes, `swan test` and `swan docs`.
- **Lake:** the editor, on your computer (`swan lake`) or [in your browser](https://advaithsajith.github.io/swan/lake/).
- **Learning:** [GUIDE.md](GUIDE.md), with fifteen lessons and exercises.
- **Editors:** VS Code colours with the Black Swan and Swan Lake themes.
