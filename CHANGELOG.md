# Changelog

## Unreleased

- **Libraries:** bring in extra tools with `use maths`, `use maths as m` or `use gcd, lcm from maths`.
  Errors inside a library point at the line in your code that called it, and `hidden fn` keeps a library's helpers private.
- **maths library:** `gcd`, `lcm`, primes and factors, `factorial`, `fibonacci`, `clamp`, `percent`, and
  statistics (`median`, `mode`, `spread`, `deviation`).
- **draw library:** text pictures for the terminal: `box`, `table`, `bars`, `progress`, `pad` and `divider`.
- Libraries work in Lake on your computer and in the browser; there's a new [libraries.swan](examples/libraries.swan) example.

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
