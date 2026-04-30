# Customizing

There are two ways to change how the plugin's blocks look. Use whichever
fits your need.

## Plugin config — colors only

The eight most common color slots are exposed as plugin options. Any value
left empty keeps the [Material](https://squidfunk.github.io/mkdocs-material/)
default.

```yaml
plugins:
  - back-links:
      graph:
        colors:
          current_label: "#222"
          highlight: "tomato"
```

Each option maps to a `--mbl-graph-*` CSS custom property emitted at
`:root` for every page:

| Option | Variable | Default |
|---|---|---|
| `node` | `--mbl-graph-node-fill` | Material Blue Grey 800 / 100 |
| `section` | `--mbl-graph-section-fill` | Material Blue Grey 200 / 400 |
| `current_fill` | `--mbl-graph-current-fill` | `var(--md-accent-fg-color)` |
| `current_stroke` | `--mbl-graph-current-stroke` | `var(--md-primary-fg-color)` |
| `link` | `--mbl-graph-link` | `var(--md-default-fg-color--lighter)` |
| `highlight` | `--mbl-graph-highlight` | `var(--md-accent-fg-color)` |
| `label` | `--mbl-graph-label` | `var(--md-default-fg-color--light)` |
| `current_label` | `--mbl-graph-current-label` | `var(--md-primary-fg-color)` |

## extra_css — everything else

For anything beyond the eight color slots — typography, spacing, borders,
hover behavior, per-mode overrides, layout tweaks — drop a stylesheet next
to your docs and reference it from `mkdocs.yml`.

```yaml
extra_css:
  - assets/back-links-custom.css
```

```css
/* docs/assets/back-links-custom.css */

/* Override a CSS var directly — equivalent to the plugin config above. */
:root {
  --mbl-graph-current-label: #222;
}

/* Per-mode override — the plugin config can't do this. */
[data-md-color-scheme="slate"] {
  --mbl-graph-node-fill: #455a64;
}

/* Restyle the bottom-of-page backlinks block. */
.md-typeset .mbl-backlinks {
  margin-top: 1.5rem;
  font-size: 0.7em;
}

/* Bring back the blockquote-style aside on per-section backlinks. */
.md-typeset .mbl-section-backlinks {
  background: var(--md-code-bg-color);
  border-left: 3px solid var(--md-accent-fg-color);
  border-top: 0;
  padding: 0.6em 0.8em;
}

/* Tweak graph rendering. */
.mbl-graph-svg { border-radius: 0; }
.mbl-graph-link--contains { stroke-dasharray: 6 2; }
```

## Class reference

The class names below are stable and intended for theming.

| Block / element | Class |
|---|---|
| Bottom-of-page backlinks block | `.mbl-backlinks` |
| Per-section backlinks aside | `.mbl-section-backlinks` (with `data-section="<slug>"`) |
| Graph pane (sidebar) | `.mbl-graph-pane` — also `.mbl-graph-pane--header-only` for orphan pages |
| Pane header / expand button | `.mbl-graph-header`, `.mbl-graph-expand` |
| Modal overlay | `.mbl-graph-modal`, `.mbl-graph-modal__inner`, `.mbl-graph-close` |
| Graph SVG | `.mbl-graph-svg` |
| Nodes | `.mbl-graph-node` (+ `--section`, `--current`, `--clustered`, `--scrolled`, `--faded`) |
| Edges | `.mbl-graph-link` (+ `--contains`, `--clustered`, `--active`, `--scrolled`, `--faded`) |
| Labels | `.mbl-graph-label` (+ `--current`, `--clustered`, `--scrolled`, `--hover`, `--faded`) |

## CSS variables

All `--mbl-graph-*` variables are read-write — override them via plugin
config or directly in CSS. `--mbl-pane-height` is set by the runtime to
the current pane height; the bottom-of-page backlinks block reads it to
keep the two top borders aligned.
