from mkdocs_back_links.linkgraph import extract_links


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


from mkdocs_back_links.linkgraph import resolve_link


def test_resolve_relative_in_same_dir():
    assert resolve_link("guides/install.md", "configure.md") == "guides/configure.md"


def test_resolve_parent_dir():
    assert resolve_link("guides/install.md", "../concepts/architecture.md") == "concepts/architecture.md"


def test_resolve_strips_anchor():
    assert resolve_link("guides/install.md", "configure.md#prereqs") == "guides/configure.md"


def test_resolve_strips_query():
    assert resolve_link("guides/install.md", "configure.md?x=1") == "guides/configure.md"


def test_resolve_root_relative_path():
    # paths starting with / are treated as docs-root-relative
    assert resolve_link("guides/install.md", "/concepts/architecture.md") == "concepts/architecture.md"


def test_resolve_returns_none_for_non_md():
    assert resolve_link("page.md", "image.png") is None
    assert resolve_link("page.md", "file.txt") is None


def test_resolve_returns_none_for_escape_above_root():
    assert resolve_link("page.md", "../../../etc/passwd.md") is None


from mkdocs_back_links.linkgraph import build_edges, inverse_index


def test_build_edges_simple():
    pages = {
        "a.md": "[to b](b.md)",
        "b.md": "[to c](c.md) and back to [a](a.md)",
        "c.md": "no links",
    }
    edges = build_edges(pages)
    assert sorted(edges) == [("a.md", "b.md"), ("b.md", "a.md"), ("b.md", "c.md")]


def test_build_edges_drops_unknown_targets():
    pages = {
        "a.md": "[ghost](does-not-exist.md)",
        "b.md": "",
    }
    assert build_edges(pages) == []


def test_build_edges_dedupes():
    pages = {"a.md": "[1](b.md) and [2](b.md)", "b.md": ""}
    assert build_edges(pages) == [("a.md", "b.md")]


def test_build_edges_skips_self_links():
    pages = {"a.md": "[self](a.md)", "b.md": ""}
    assert build_edges(pages) == []


def test_inverse_index():
    edges = [("a.md", "b.md"), ("c.md", "b.md"), ("a.md", "c.md")]
    assert inverse_index(edges) == {
        "b.md": ["a.md", "c.md"],
        "c.md": ["a.md"],
    }


from mkdocs_back_links.linkgraph import local_subgraph


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
