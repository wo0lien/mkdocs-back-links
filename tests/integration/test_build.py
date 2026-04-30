import subprocess
from pathlib import Path

FIXTURE = Path(__file__).parent.parent / 'fixtures' / 'basic-site'


def _build(tmp_path: Path) -> Path:
    site_dir = tmp_path / 'site'
    subprocess.run(
        [
            'uv',
            'run',
            'mkdocs',
            'build',
            '--strict',
            '-f',
            str(FIXTURE / 'mkdocs.yml'),
            '-d',
            str(site_dir),
        ],
        check=True,
    )
    return site_dir


def test_backlinks_section_rendered(tmp_path):
    site = _build(tmp_path)
    target_html = (site / 'target' / 'index.html').read_text()
    assert 'mbl-backlinks' in target_html
    assert '>Backlinks</h2>' in target_html
    # source.md links to target.md, so target should backlink to source
    assert '/source/' in target_html


def test_local_graph_inlined(tmp_path):
    site = _build(tmp_path)
    target_html = (site / 'target' / 'index.html').read_text()
    assert 'id="mbl-local-graph"' in target_html


def test_global_graph_written(tmp_path):
    site = _build(tmp_path)
    graph_json = site / 'assets' / 'back_links' / 'graph.json'
    assert graph_json.exists()
    content = graph_json.read_text()
    assert '"nodes"' in content and '"edges"' in content


def test_orphan_has_no_backlinks_section(tmp_path):
    site = _build(tmp_path)
    orphan_html = (site / 'orphan' / 'index.html').read_text()
    assert 'mbl-backlinks' not in orphan_html


def test_frontmatter_disables_backlinks(tmp_path):
    site = _build(tmp_path)
    no_back = (site / 'no-backlinks' / 'index.html').read_text()
    assert 'mbl-backlinks' not in no_back


def test_assets_referenced(tmp_path):
    site = _build(tmp_path)
    target_html = (site / 'target' / 'index.html').read_text()
    assert '/assets/back_links/back_links.css' in target_html
    assert '/assets/back_links/back_links.js' in target_html
    assert '/assets/back_links/d3.min.js' in target_html


SECTIONED_FIXTURE = Path(__file__).parent.parent / 'fixtures' / 'sectioned-site'
COLLAPSE_FIXTURE = Path(__file__).parent.parent / 'fixtures' / 'sectioned-collapse'


def _build_at(fixture: Path, tmp_path: Path) -> Path:
    site_dir = tmp_path / 'site'
    subprocess.run(
        [
            'uv',
            'run',
            'mkdocs',
            'build',
            '--strict',
            '-f',
            str(fixture / 'mkdocs.yml'),
            '-d',
            str(site_dir),
        ],
        check=True,
    )
    return site_dir


def test_section_block_rendered_after_section(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    b_html = (site / 'b' / 'index.html').read_text()
    assert 'class="mbl-section-backlinks"' in b_html
    assert 'data-section="deep-dive"' in b_html
    assert '>A</a>' in b_html
    assert '# Overview</a>' in b_html
    assert 'href="#overview"' in b_html


def test_page_bottom_dedupes_to_pages(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    b_html = (site / 'b' / 'index.html').read_text()
    occurrences = b_html.count('>A</a>')
    assert 1 <= occurrences <= 2


def test_local_graph_includes_section_node(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    b_html = (site / 'b' / 'index.html').read_text()
    import json
    import re

    m = re.search(
        r'<script id="mbl-local-graph" type="application/json">(.+?)</script>',
        b_html,
        re.DOTALL,
    )
    assert m
    data = json.loads(m.group(1))
    section_nodes = [n for n in data['nodes'] if n['type'] == 'section']
    assert any(n['id'] == 'b.md#deep-dive' for n in section_nodes)
    contains_edges = [e for e in data['edges'] if e['kind'] == 'contains']
    assert any(
        e['source'] == 'b.md' and e['target'] == 'b.md#deep-dive'
        for e in contains_edges
    )


def test_a_local_graph_has_no_section_nodes_by_default(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    a_html = (site / 'a' / 'index.html').read_text()
    import json
    import re

    m = re.search(
        r'<script id="mbl-local-graph" type="application/json">(.+?)</script>',
        a_html,
        re.DOTALL,
    )
    data = json.loads(m.group(1))
    a_section_nodes = [
        n for n in data['nodes'] if n['type'] == 'section' and n.get('page') == 'a.md'
    ]
    assert a_section_nodes == []


def test_global_graph_has_section_nodes(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    import json

    g = json.loads((site / 'assets' / 'back_links' / 'graph.json').read_text())
    assert any(
        n['type'] == 'section' and n['id'] == 'b.md#deep-dive' for n in g['nodes']
    )
    assert any(e['kind'] == 'contains' and e['source'] == 'b.md' for e in g['edges'])


def test_collapse_threshold_wraps_in_details(tmp_path):
    site = _build_at(COLLAPSE_FIXTURE, tmp_path)
    pop = (site / 'popular' / 'index.html').read_text()
    assert 'data-section="hot-section"' in pop
    aside_start = pop.index('data-section="hot-section"')
    aside_end = pop.index('</aside>', aside_start)
    aside = pop[aside_start:aside_end]
    assert '<details' in aside
    assert '4 backlinks' in aside
