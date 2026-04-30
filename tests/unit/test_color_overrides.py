from mkdocs_back_links.plugin import BackLinksPlugin


def _plugin_with_colors(**color_overrides):
    p = BackLinksPlugin()
    p.load_config(
        {
            'graph': {'colors': color_overrides},
        }
    )
    return p


def test_no_overrides_emits_nothing():
    p = _plugin_with_colors()
    assert p._build_color_style() == ''


def test_single_override_emits_root_var():
    p = _plugin_with_colors(current_label='#222')
    style = p._build_color_style()
    assert style.startswith('<style>') and style.endswith('</style>')
    assert '--mbl-graph-current-label: #222;' in style


def test_multiple_overrides_each_mapped_to_correct_var():
    p = _plugin_with_colors(
        node='red',
        section='blue',
        current_fill='#fff',
        current_stroke='#000',
        link='gray',
        highlight='tomato',
        label='hsl(0 0% 50%)',
        current_label='var(--my-color)',
    )
    style = p._build_color_style()
    expected = [
        '--mbl-graph-node-fill: red;',
        '--mbl-graph-section-fill: blue;',
        '--mbl-graph-current-fill: #fff;',
        '--mbl-graph-current-stroke: #000;',
        '--mbl-graph-link: gray;',
        '--mbl-graph-highlight: tomato;',
        '--mbl-graph-label: hsl(0 0% 50%);',
        '--mbl-graph-current-label: var(--my-color);',
    ]
    for rule in expected:
        assert rule in style


def test_empty_string_value_skipped():
    p = _plugin_with_colors(current_label='', highlight='tomato')
    style = p._build_color_style()
    assert '--mbl-graph-current-label' not in style
    assert '--mbl-graph-highlight: tomato;' in style
