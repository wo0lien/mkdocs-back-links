# Internals

Implementation details.

## Parsing

The parser walks each page line-by-line, tracking the current section.

## Rendering

Backlinks blocks are inserted by the [data flow](architecture.md#data-flow)
step right before the next heading boundary.
