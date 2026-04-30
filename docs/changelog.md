# Changelog

A running list of notable changes.

## 0.4.0

- `graph.colors` config section: eight color slots exposed as
  `--mbl-graph-*` CSS custom properties, with Material defaults that
  every site already gets for free
- Bottom-of-article backlinks block locks to the graph pane's height,
  and the pane tracks the block's bottom y when in viewport — both
  top-borders now align across the article and sidebar columns
- Material icons on the pane buttons (`arrow-expand`, `window-close`)
  in place of the previous hand-rolled SVG and unicode multiplication
  sign
- New customizing guide in the demo (`Guides → Customizing`) with
  copy-pasteable recipes for restyling the section-backlinks aside,
  the graph, and per-mode color overrides
- New unit tests for the color-override style emission

## 0.3.0

Pane anchored to the bottom of the viewport with content-driven height and
footer-aware lift. Section clustering with scroll-spy reveal, elliptical
collide for height-distributed layouts, hover highlight ignores structural
section edges, simplified section-backlinks aside.

## 0.2.0

Section-aware backlinks and the graph view landed.

## 0.1.0

Initial release with whole-page backlinks.
