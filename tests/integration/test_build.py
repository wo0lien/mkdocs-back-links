from pathlib import Path
import shutil
import subprocess


FIXTURE = Path(__file__).parent.parent / "fixtures" / "basic-site"


def _build(tmp_path: Path) -> Path:
    site_dir = tmp_path / "site"
    subprocess.run(
        ["uv", "run", "mkdocs", "build", "--strict", "-f", str(FIXTURE / "mkdocs.yml"), "-d", str(site_dir)],
        check=True,
    )
    return site_dir


def test_backlinks_section_rendered(tmp_path):
    site = _build(tmp_path)
    target_html = (site / "target" / "index.html").read_text()
    assert "mbl-backlinks" in target_html
    assert ">Backlinks</h2>" in target_html
    # source.md links to target.md, so target should backlink to source
    assert "/source/" in target_html


def test_local_graph_inlined(tmp_path):
    site = _build(tmp_path)
    target_html = (site / "target" / "index.html").read_text()
    assert 'id="mbl-local-graph"' in target_html


def test_global_graph_written(tmp_path):
    site = _build(tmp_path)
    graph_json = site / "assets" / "back_links" / "graph.json"
    assert graph_json.exists()
    content = graph_json.read_text()
    assert '"nodes"' in content and '"edges"' in content


def test_orphan_has_no_backlinks_section(tmp_path):
    site = _build(tmp_path)
    orphan_html = (site / "orphan" / "index.html").read_text()
    assert "mbl-backlinks" not in orphan_html


def test_frontmatter_disables_backlinks(tmp_path):
    site = _build(tmp_path)
    no_back = (site / "no-backlinks" / "index.html").read_text()
    assert "mbl-backlinks" not in no_back
