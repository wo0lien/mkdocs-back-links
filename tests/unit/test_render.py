import json
import re

from mkdocs_back_links.render import render_backlinks_section, render_local_graph_data


def test_backlinks_section_with_entries():
    html = render_backlinks_section(
        heading="Backlinks",
        entries=[
            {"title": "Install", "url": "/guides/install/"},
            {"title": "Architecture", "url": "/concepts/architecture/"},
        ],
    )
    assert 'class="mbl-backlinks"' in html
    assert "<h2" in html and ">Backlinks</h2>" in html
    assert '<a href="/guides/install/">Install</a>' in html
    assert '<a href="/concepts/architecture/">Architecture</a>' in html


def test_backlinks_section_empty_returns_empty_string():
    assert render_backlinks_section(heading="Backlinks", entries=[]) == ""


def test_backlinks_escapes_html_in_titles():
    html = render_backlinks_section(
        heading="Backlinks",
        entries=[{"title": "<script>x</script>", "url": "/p/"}],
    )
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_local_graph_data_emits_json_script_tag():
    html = render_local_graph_data(
        {"nodes": [{"id": "a", "title": "A", "url": "/a/"}], "edges": []}
    )
    m = re.search(
        r'<script id="mbl-local-graph" type="application/json">(.+?)</script>',
        html,
        re.DOTALL,
    )
    assert m
    parsed = json.loads(m.group(1))
    assert parsed["nodes"][0]["id"] == "a"


def test_local_graph_data_escapes_closing_script():
    # Defensive: a title containing </script> must not break out of the tag
    html = render_local_graph_data(
        {"nodes": [{"id": "a", "title": "evil </script><b>", "url": "/a/"}], "edges": []}
    )
    assert "</script><b>" not in html.split('<script', 1)[1].split("</script>", 1)[0]
