"""
HTML 뷰어 생성 유틸리티.

viewer/index.html 템플릿에 wiki.json 데이터를 인라인으로 삽입해
file:// 프로토콜에서도 fetch 없이 동작하는 독립 HTML을 생성한다.

사용법:
  from src.viewer.builder import build_viewer_html
  html = build_viewer_html(wiki_json_str)
"""
from pathlib import Path

_TEMPLATE_PATH = Path(__file__).parent.parent.parent / "viewer" / "index.html"


def build_viewer_html(wiki_json_str: str) -> str:
    """
    wiki.json 문자열을 받아 데이터가 인라인으로 삽입된 HTML을 반환한다.

    viewer/index.html의 loadWiki()가 WIKI_DATA 전역 변수를
    먼저 확인하므로, </head> 직전에 주입한다.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    wiki_json_safe = wiki_json_str.replace("</script>", "<\\/script>")
    inject_script = (
        "<script>\n"
        "// AUTO-GENERATED: wiki.json 인라인 데이터\n"
        f"const WIKI_DATA = {wiki_json_safe};\n"
        "</script>\n"
    )
    return template.replace("</head>", inject_script + "</head>", 1)


def build_viewer_html_from_file(wiki_json_path: str) -> str:
    """wiki.json 파일 경로를 받아 인라인 뷰어 HTML을 반환한다."""
    json_str = Path(wiki_json_path).read_text(encoding="utf-8")
    return build_viewer_html(json_str)
