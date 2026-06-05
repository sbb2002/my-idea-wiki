"""
HTML 뷰어 생성 유틸리티.

viewer/_template.html + viewer/style.css + viewer/app.js 세 파일을
빌드 시 합쳐 단일 HTML을 생성하고, wiki.json 데이터를 인라인으로 삽입한다.

소스 구조 (개발용):
  viewer/_template.html  — HTML 뼈대 ({{CSS}}, {{JS}} 플레이스홀더 포함)
  viewer/style.css        — 전체 CSS
  viewer/app.js           — 전체 JS

빌드 결과 (배포용):
  단일 index.html — CSS/JS 인라인 포함, WIKI_DATA 주입

사용법:
  from src.viewer.builder import build_viewer_html
  html = build_viewer_html(wiki_json_str)
"""
from pathlib import Path

_VIEWER_DIR   = Path(__file__).parent.parent.parent / "viewer"
_TEMPLATE     = _VIEWER_DIR / "_template.html"
_CSS          = _VIEWER_DIR / "style.css"
_JS           = _VIEWER_DIR / "app.js"

# 분리된 소스 파일이 없는 경우 fallback (기존 index.html 직접 사용)
_LEGACY_INDEX = _VIEWER_DIR / "index.html"


def _build_html() -> str:
    """
    _template.html의 {{CSS}}, {{JS}} 플레이스홀더에
    style.css, app.js 내용을 주입해 단일 HTML 문자열을 반환한다.

    소스 파일이 없으면 index.html을 그대로 반환한다(레거시 폴백).
    """
    if not _TEMPLATE.exists() or not _CSS.exists() or not _JS.exists():
        # 레거시 폴백: 분리 전 index.html 사용
        return _LEGACY_INDEX.read_text(encoding="utf-8")

    template = _TEMPLATE.read_text(encoding="utf-8")
    css      = _CSS.read_text(encoding="utf-8")
    js       = _JS.read_text(encoding="utf-8")
    return template.replace("{{CSS}}", css).replace("{{JS}}", js)


def build_viewer_html(wiki_json_str: str) -> str:
    """
    wiki.json 문자열을 받아 데이터가 인라인으로 삽입된 HTML을 반환한다.

    viewer/_template.html + style.css + app.js 를 합친 뒤
    </head> 직전에 WIKI_DATA 스크립트를 주입한다.
    """
    html = _build_html()
    wiki_json_safe = wiki_json_str.replace("</script>", "<\\/script>")
    inject_script = (
        "<script>\n"
        "// AUTO-GENERATED: wiki.json 인라인 데이터\n"
        f"const WIKI_DATA = {wiki_json_safe};\n"
        "</script>\n"
    )
    return html.replace("</head>", inject_script + "</head>", 1)


def build_viewer_html_from_file(wiki_json_path: str) -> str:
    """wiki.json 파일 경로를 받아 인라인 뷰어 HTML을 반환한다."""
    json_str = Path(wiki_json_path).read_text(encoding="utf-8")
    return build_viewer_html(json_str)
