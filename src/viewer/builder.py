"""
HTML 뷰어 생성 유틸리티.

viewer/index.html 템플릿에 wiki.json의 Drive ID만 심어
브라우저가 실행 시 Drive에서 직접 fetch하도록 한다.

사용자는 index.html을 한 번만 받으면 되고,
이후 /run 결과는 Drive의 wiki.json이 업데이트되면 자동 반영된다.

사용법:
  from src.viewer.builder import build_viewer_html
  html = build_viewer_html(wiki_drive_id)
"""
from pathlib import Path

_TEMPLATE_PATH = Path(__file__).parent.parent.parent / "viewer" / "index.html"


def build_viewer_html(wiki_drive_id: str) -> str:
    """
    wiki.json의 Drive File ID를 받아 WIKI_DRIVE_ID가 심긴 HTML을 반환한다.

    브라우저 실행 시 loadWiki()가 Drive에서 wiki.json을 fetch한다.
    인라인 데이터 주입 없이 index.html은 고정 파일로 유지된다.

    Args:
        wiki_drive_id: Drive의 wiki.json 파일 ID

    Returns:
        WIKI_DRIVE_ID가 <head>에 주입된 HTML 문자열
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    inject_script = (
        "<script>\n"
        "// AUTO-GENERATED: wiki.json Drive File ID\n"
        f"const WIKI_DRIVE_ID = '{wiki_drive_id}';\n"
        "</script>\n"
    )

    return template.replace("</head>", inject_script + "</head>", 1)
