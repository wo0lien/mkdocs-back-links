# FAQ

## Does this work with non-Material themes?

The backlinks block itself is theme-agnostic. The graph pane assumes the
Material sidebar layout, so on other themes the graph will render but may
not be positioned identically.

## Does it slow down the build?

The parser is single-pass and cheap. On a 500-page site the build cost is
typically under a second.

## Can I disable the graph?

Yes — set `graph.enabled: false` in the plugin config.
