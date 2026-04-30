# Architecture

High-level design overview.

## Components

The plugin has a small, focused Python core and a separate JS rendering layer.

## Data flow

Markdown is parsed at build time. See [internals](internals.md#parsing) for
how the parser walks each page line by line.
