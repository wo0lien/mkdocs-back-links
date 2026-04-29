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
