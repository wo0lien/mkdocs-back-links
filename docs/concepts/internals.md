# Internals

Implementation details.

## Parsing

The parser walks each page line-by-line, tracking the current section.
This is what makes features like the
[scroll-spy indicator](../walkthrough.md#scroll-spy-behavior) possible.

## Rendering

Backlinks blocks are inserted by the [data flow](architecture.md#data-flow)
step right before the next heading boundary. Client-side JS then wires up
the [scroll-spy indicator](../walkthrough.md#scroll-spy-behavior).
