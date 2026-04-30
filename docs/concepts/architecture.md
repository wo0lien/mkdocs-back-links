# Architecture

High-level design overview.

## Components

The plugin has a small, focused Python core and a separate JS rendering layer.
The runtime layer also drives UI features like the
[scroll-spy indicator](../walkthrough.md#scroll-spy-behavior).

## Data flow

Markdown is parsed at build time. See [internals](internals.md#parsing) for
how the parser walks each page line by line. The same data feeds the
[scroll-spy indicator](../walkthrough.md#scroll-spy-behavior) at runtime.
