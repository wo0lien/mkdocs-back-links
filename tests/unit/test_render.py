import json
import re

from mkdocs_back_links.render import (
    render_backlinks_section,
    render_local_graph_data,
    render_section_backlinks,
    render_settings_data,
)


def test_backlinks_section_with_entries():
    html = render_backlinks_section(
        heading='Backlinks',
        entries=[
            {'title': 'Install', 'url': '/guides/install/'},
            {'title': 'Architecture', 'url': '/concepts/architecture/'},
        ],
    )
    assert 'class="mbl-backlinks"' in html
    assert '<h2' in html and '>Backlinks</h2>' in html
    assert '<a href="/guides/install/">Install</a>' in html
    assert '<a href="/concepts/architecture/">Architecture</a>' in html


def test_backlinks_section_empty_returns_empty_string():
    assert render_backlinks_section(heading='Backlinks', entries=[]) == ''


def test_backlinks_escapes_html_in_titles():
    html = render_backlinks_section(
        heading='Backlinks',
        entries=[{'title': '<script>x</script>', 'url': '/p/'}],
    )
    assert '<script>x</script>' not in html
    assert '&lt;script&gt;' in html


def test_local_graph_data_emits_json_script_tag():
    html = render_local_graph_data(
        {'nodes': [{'id': 'a', 'title': 'A', 'url': '/a/'}], 'edges': []}
    )
    m = re.search(
        r'<script id="mbl-local-graph" type="application/json">(.+?)</script>',
        html,
        re.DOTALL,
    )
    assert m
    parsed = json.loads(m.group(1))
    assert parsed['nodes'][0]['id'] == 'a'


def test_local_graph_data_escapes_closing_script():
    # Defensive: a title containing </script> must not break out of the tag
    html = render_local_graph_data(
        {
            'nodes': [{'id': 'a', 'title': 'evil </script><b>', 'url': '/a/'}],
            'edges': [],
        }
    )
    assert '</script><b>' not in html.split('<script', 1)[1].split('</script>', 1)[0]


def test_settings_data_emits_json():
    html = render_settings_data({'max_nodes': 500})
    assert 'id="mbl-settings"' in html
    m = re.search(r'>(.*)</script>', html, re.DOTALL)
    parsed = json.loads(m.group(1))
    assert parsed['max_nodes'] == 500


def test_section_backlinks_basic_cross_page():
    html = render_section_backlinks(
        section_title='Deep dive',
        section_slug='deep-dive',
        target_page='b.md',
        entries=[
            {
                'source_page': 'a.md',
                'source_section': None,
                'page_title': 'A',
                'page_url': '/a/',
                'section_title_lookup': None,
            },
        ],
        collapse_threshold=3,
    )
    assert 'class="mbl-section-backlinks"' in html
    assert 'data-section="deep-dive"' in html
    assert (
        '>Backlinks to &quot;Deep dive&quot;</h3>' in html
        or '>Backlinks to "Deep dive"</h3>' in html
    )
    assert '<a href="/a/">A</a>' in html
    assert '<details' not in html  # below threshold


def test_section_backlinks_same_page_uses_source_heading():
    html = render_section_backlinks(
        section_title='Deep dive',
        section_slug='deep-dive',
        target_page='b.md',
        entries=[
            {
                'source_page': 'b.md',
                'source_section': 'overview',
                'page_title': 'B',
                'page_url': '/b/',
                'section_title_lookup': 'Overview',
            },
        ],
        collapse_threshold=3,
    )
    assert '<a href="#overview"># Overview</a>' in html


def test_section_backlinks_collapses_when_over_threshold():
    entries = [
        {
            'source_page': f'p{i}.md',
            'source_section': None,
            'page_title': f'P{i}',
            'page_url': f'/p{i}/',
            'section_title_lookup': None,
        }
        for i in range(4)
    ]
    html = render_section_backlinks(
        section_title='Hot',
        section_slug='hot',
        target_page='b.md',
        entries=entries,
        collapse_threshold=3,
    )
    assert '<details' in html
    assert '<summary' in html
    assert '4 backlinks' in html


def test_section_backlinks_threshold_zero_disables_collapse():
    entries = [
        {
            'source_page': f'p{i}.md',
            'source_section': None,
            'page_title': f'P{i}',
            'page_url': f'/p{i}/',
            'section_title_lookup': None,
        }
        for i in range(10)
    ]
    html = render_section_backlinks(
        section_title='Hot',
        section_slug='hot',
        target_page='b.md',
        entries=entries,
        collapse_threshold=0,
    )
    assert '<details' not in html


def test_section_backlinks_sorted_alphabetically_by_label():
    entries = [
        {
            'source_page': 'z.md',
            'source_section': None,
            'page_title': 'Zebra',
            'page_url': '/z/',
            'section_title_lookup': None,
        },
        {
            'source_page': 'a.md',
            'source_section': None,
            'page_title': 'Apple',
            'page_url': '/a/',
            'section_title_lookup': None,
        },
    ]
    html = render_section_backlinks(
        section_title='X',
        section_slug='x',
        target_page='t.md',
        entries=entries,
        collapse_threshold=3,
    )
    assert html.index('Apple') < html.index('Zebra')


def test_section_backlinks_escapes_titles():
    entries = [
        {
            'source_page': 'x.md',
            'source_section': None,
            'page_title': '<bad>',
            'page_url': '/x/',
            'section_title_lookup': None,
        },
    ]
    html = render_section_backlinks(
        section_title='<b>Section</b>',
        section_slug='s',
        target_page='t.md',
        entries=entries,
        collapse_threshold=3,
    )
    assert '<bad>' not in html
    assert '&lt;bad&gt;' in html
    assert '<b>Section</b>' not in html
    assert '&lt;b&gt;Section&lt;/b&gt;' in html
