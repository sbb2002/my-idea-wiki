"""
HTML 뷰어 빌더 단위 테스트.
"""
import json
from src.viewer.builder import build_viewer_html, build_viewer_html_from_file
from src.pipeline.wiki_store import empty_wiki, dump_wiki, make_item, make_version


def _sample_wiki_json() -> str:
    wiki = empty_wiki()
    version = make_version("2026-05-25", "테스트 내용", ["note_001"])
    item = make_item("테스트 아이템", ["태그1"], "요약 내용", version)
    wiki["items"].append(item)
    return dump_wiki(wiki)


class TestBuildViewerHtml:
    def test_returns_html_string(self):
        html = build_viewer_html(_sample_wiki_json())
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")

    def test_contains_wiki_data_variable(self):
        html = build_viewer_html(_sample_wiki_json())
        assert "const WIKI_DATA =" in html

    def test_wiki_data_is_valid_json_embedded(self):
        wiki_json = _sample_wiki_json()
        html = build_viewer_html(wiki_json)
        # WIKI_DATA = {...}; 부분 추출
        start = html.index("const WIKI_DATA = ") + len("const WIKI_DATA = ")
        # 세미콜론 + 줄바꿈 직전까지
        end = html.index(";\n", start)
        embedded = html[start:end]
        parsed = json.loads(embedded)
        assert "items" in parsed
        assert parsed["items"][0]["title"] == "테스트 아이템"

    def test_script_tag_injection_in_head(self):
        html = build_viewer_html(_sample_wiki_json())
        # 주입된 스크립트가 </head> 직전에 있어야 함
        inject_pos = html.index("const WIKI_DATA")
        head_close_pos = html.index("</head>")
        assert inject_pos < head_close_pos

    def test_xss_script_tag_escaped(self):
        """wiki 데이터 안에 </script>가 있어도 안전하게 이스케이프."""
        wiki = empty_wiki()
        version = make_version("2026-05-25", "</script><script>alert(1)</script>", [])
        item = make_item("악성 아이템", [], "요약", version)
        wiki["items"].append(item)
        wiki_json = dump_wiki(wiki)
        html = build_viewer_html(wiki_json)
        # 원시 </script>가 WIKI_DATA 블록 안에 존재하면 안 됨
        wiki_data_section = html[html.index("const WIKI_DATA"):html.index(";\n", html.index("const WIKI_DATA"))]
        assert "</script>" not in wiki_data_section

    def test_empty_wiki(self):
        wiki_json = dump_wiki(empty_wiki())
        html = build_viewer_html(wiki_json)
        assert "const WIKI_DATA =" in html
        embedded_start = html.index("const WIKI_DATA = ") + len("const WIKI_DATA = ")
        embedded_end = html.index(";\n", embedded_start)
        parsed = json.loads(html[embedded_start:embedded_end])
        assert parsed["items"] == []

    def test_template_structure_preserved(self):
        html = build_viewer_html(_sample_wiki_json())
        assert "아이디어 위키" in html
        assert "id=\"sidebar\"" in html
        assert "id=\"wiki-doc\"" in html
        assert "id=\"item-list\"" in html

    def test_graph_view_elements_present(self):
        """그래프 뷰 DOM 요소들이 포함되어 있어야 함."""
        html = build_viewer_html(_sample_wiki_json())
        assert "id=\"graph-view\"" in html
        assert "id=\"graph-canvas\"" in html
        assert "id=\"graph-legend\"" in html
        assert "id=\"graph-tooltip\"" in html

    def test_graph_js_functions_present(self):
        """그래프 핵심 함수들이 포함되어 있어야 함."""
        html = build_viewer_html(_sample_wiki_json())
        assert "function renderGraph" in html
        assert "function switchView" in html

    def test_view_toggle_buttons_present(self):
        """뷰 전환 버튼이 헤더에 포함되어 있어야 함."""
        html = build_viewer_html(_sample_wiki_json())
        assert "btn-wiki" in html
        assert "btn-graph" in html

    def test_build_from_file(self, tmp_path):
        wiki_json = _sample_wiki_json()
        wiki_file = tmp_path / "wiki.json"
        wiki_file.write_text(wiki_json, encoding="utf-8")
        html = build_viewer_html_from_file(str(wiki_file))
        assert "const WIKI_DATA =" in html

