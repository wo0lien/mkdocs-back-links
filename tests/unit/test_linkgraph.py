from markdown.extensions.toc import slugify as _md_slugify

from mkdocs_back_links.linkgraph import (
    Section,
    build_edges,
    extract_links,
    extract_links_in_sections,
    extract_sections,
    inverse_page_index,
    inverse_section_index,
    local_subgraph,
    resolve_link,
)


def test_extracts_simple_link():
    md = "See [the install guide](install.md)."
    assert extract_links(md) == ["install.md"]


def test_extracts_multiple_links():
    md = "[a](one.md) and [b](two.md) and [c](sub/three.md)"
    assert extract_links(md) == ["one.md", "two.md", "sub/three.md"]


def test_strips_link_title():
    md = '[hi](page.md "Title text")'
    assert extract_links(md) == ["page.md"]


def test_skips_external_links():
    md = "[ext](https://example.com) [other](http://x.org) [local](page.md)"
    assert extract_links(md) == ["page.md"]


def test_skips_anchor_only_links():
    md = "[top](#section) [page](page.md#section)"
    assert extract_links(md) == ["page.md#section"]


def test_skips_links_inside_fenced_code():
    md = "Before [a](one.md)\n\n```\n[fake](nope.md)\n```\n\nAfter [b](two.md)"
    assert extract_links(md) == ["one.md", "two.md"]


def test_skips_links_inside_inline_code():
    md = "Use `[link](nope.md)` then [real](real.md)"
    assert extract_links(md) == ["real.md"]


def test_skips_image_links():
    md = "![alt](img.png) [page](page.md)"
    assert extract_links(md) == ["page.md"]


def test_resolve_relative_in_same_dir():
    assert resolve_link("guides/install.md", "configure.md") == ("guides/configure.md", None)


def test_resolve_parent_dir():
    assert resolve_link("guides/install.md", "../concepts/architecture.md") == ("concepts/architecture.md", None)


def test_resolve_keeps_anchor():
    assert resolve_link("guides/install.md", "configure.md#prereqs") == ("guides/configure.md", "prereqs")


def test_resolve_strips_query_keeps_anchor():
    assert resolve_link("guides/install.md", "configure.md?x=1#sec") == ("guides/configure.md", "sec")


def test_resolve_root_relative_path():
    assert resolve_link("guides/install.md", "/concepts/architecture.md") == ("concepts/architecture.md", None)


def test_resolve_returns_none_for_non_md():
    assert resolve_link("page.md", "image.png") is None
    assert resolve_link("page.md", "file.txt") is None


def test_resolve_returns_none_for_escape_above_root():
    assert resolve_link("page.md", "../../../etc/passwd.md") is None


def test_resolve_empty_fragment_is_none():
    assert resolve_link("a.md", "b.md#") == ("b.md", None)


def test_build_edges_simple():
    pages = {
        "a.md": "[to b](b.md)",
        "b.md": "[to c](c.md) and back to [a](a.md)",
        "c.md": "no links",
    }
    edges = build_edges(pages, section_levels=[])
    assert sorted(edges) == [
        ("a.md", None, "b.md", None),
        ("b.md", None, "a.md", None),
        ("b.md", None, "c.md", None),
    ]


def test_build_edges_drops_unknown_targets():
    pages = {
        "a.md": "[ghost](does-not-exist.md)",
        "b.md": "",
    }
    assert build_edges(pages, section_levels=[]) == []


def test_build_edges_dedupes():
    pages = {"a.md": "[1](b.md) and [2](b.md)", "b.md": ""}
    assert build_edges(pages, section_levels=[]) == [("a.md", None, "b.md", None)]


def test_build_edges_skips_self_links():
    # Whole-page self-link dropped; anchor self-link to a different section is allowed
    pages = {"a.md": "[self](a.md) [to-foo](a.md#foo)", "b.md": ""}
    edges = build_edges(pages, section_levels=[])
    assert edges == [("a.md", None, "a.md", "foo")]


def test_build_edges_records_target_section():
    pages = {
        "a.md": "[deep](b.md#deep-dive)",
        "b.md": "## Deep dive\n\nbody",
    }
    edges = build_edges(pages, section_levels=[])
    assert edges == [("a.md", None, "b.md", "deep-dive")]


def test_build_edges_records_source_section():
    pages = {
        "a.md": "## Intro\n\n[ext](b.md)\n\n## Details\n\n[ext2](b.md#x)",
        "b.md": "",
    }
    edges = build_edges(pages, section_levels=[2])
    assert sorted(edges) == [
        ("a.md", "details", "b.md", "x"),
        ("a.md", "intro", "b.md", None),
    ]


def test_build_edges_drops_self_section_link():
    # Same page, same source and target section -> self loop, dropped
    pages = {"a.md": "## Foo\n\n[loop](a.md#foo)", "b.md": ""}
    edges = build_edges(pages, section_levels=[2])
    assert edges == []


def test_inverse_page_index():
    edges = [
        ("a.md", None, "b.md", None),
        ("c.md", "intro", "b.md", "deep-dive"),
        ("a.md", None, "c.md", None),
    ]
    assert inverse_page_index(edges) == {
        "b.md": ["a.md", "c.md"],
        "c.md": ["a.md"],
    }


def test_inverse_section_index():
    edges = [
        ("a.md", None, "b.md", "deep-dive"),
        ("c.md", "intro", "b.md", "deep-dive"),
        ("d.md", None, "b.md", None),
    ]
    assert inverse_section_index(edges) == {
        ("b.md", "deep-dive"): [("a.md", None), ("c.md", "intro")],
    }


def test_extract_sections_basic():
    md = "# Title\n\n## Intro\n\nbody\n\n## Details\n\nmore"
    sections = extract_sections(md, [1, 2])
    assert sections == [
        Section(level=1, title="Title", slug="title", line_offset=0),
        Section(level=2, title="Intro", slug="intro", line_offset=2),
        Section(level=2, title="Details", slug="details", line_offset=6),
    ]


def test_extract_sections_filters_levels():
    md = "# A\n\n## B\n\n### C\n\n## D"
    sections = extract_sections(md, [2])
    assert [s.title for s in sections] == ["B", "D"]


def test_extract_sections_ignores_fenced_code():
    md = "## Real\n\n```\n## Fake heading inside fence\n```\n\n## Also real"
    sections = extract_sections(md, [2])
    assert [s.title for s in sections] == ["Real", "Also real"]


def test_extract_sections_strips_trailing_hash_chars():
    md = "## Heading ##"
    sections = extract_sections(md, [2])
    assert sections == [Section(level=2, title="Heading", slug="heading", line_offset=0)]


def test_extract_sections_slug_parity_with_mkdocs():
    titles = [
        "Hello World",
        "Edge: Cases & More",
        "  Spaces  Around  ",
        "UPPERCASE / Mixed-Case",
        "non-ascii — em dash",
    ]
    md = "\n\n".join(f"## {t}" for t in titles)
    sections = extract_sections(md, [2])
    expected_slugs = [_md_slugify(t, "-") for t in titles]
    assert [s.slug for s in sections] == expected_slugs


def test_extract_sections_empty_when_no_headings():
    assert extract_sections("just some text\n\nno headings here", [1, 2, 3]) == []


def test_extract_links_in_sections_attributes_source():
    md = (
        "# Title\n\n"
        "Top-level [a](one.md)\n\n"
        "## Intro\n\n"
        "Intro link [b](two.md)\n\n"
        "## Details\n\n"
        "Detail link [c](three.md)\n"
    )
    pairs = extract_links_in_sections(md, [2])
    assert pairs == [
        ("one.md", None),
        ("two.md", "intro"),
        ("three.md", "details"),
    ]


def test_extract_links_in_sections_respects_levels():
    md = "# A\n[1](one.md)\n## B\n[2](two.md)\n### C\n[3](three.md)"
    pairs = extract_links_in_sections(md, [2])
    assert pairs == [("one.md", None), ("two.md", "b"), ("three.md", "b")]


def test_extract_links_in_sections_skips_code_fences_consistent():
    md = "## Real\n\n```\n[fake](nope.md)\n```\n\n[real](real.md)"
    pairs = extract_links_in_sections(md, [2])
    assert pairs == [("real.md", "real")]


def test_extract_links_in_sections_no_levels_returns_none_sources():
    md = "## Heading\n\n[link](page.md)"
    pairs = extract_links_in_sections(md, [])
    assert pairs == [("page.md", None)]


def test_local_subgraph_includes_self_and_neighbors():
    edges = [
        ("a.md", "b.md"),
        ("b.md", "c.md"),
        ("d.md", "b.md"),
        ("e.md", "f.md"),
    ]
    nodes, sub_edges = local_subgraph("b.md", edges)
    assert sorted(nodes) == ["a.md", "b.md", "c.md", "d.md"]
    assert sorted(sub_edges) == [
        ("a.md", "b.md"),
        ("b.md", "c.md"),
        ("d.md", "b.md"),
    ]


def test_local_subgraph_isolated_page():
    edges = [("a.md", "b.md")]
    nodes, sub_edges = local_subgraph("z.md", edges)
    assert nodes == ["z.md"]
    assert sub_edges == []
