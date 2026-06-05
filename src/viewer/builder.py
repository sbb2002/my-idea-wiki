"""
HTML 뷰어 생성 유틸리티.

소스 파일 구조 (개발용):
  viewer/_template.html          — HTML 뼈대
  viewer/css/variables.css       — CSS 변수 + 테마 (라이트/다크)
  viewer/css/layout.css          — 헤더, 사이드바, 메인 레이아웃
  viewer/css/wiki.css            — 위키 문서 본문 스타일
  viewer/css/graph.css           — 그래프 뷰 + PRD 버튼
  viewer/css/layout_shell.css    — 로딩 오버레이, 하단 탭바, 첨부 카드
  viewer/css/responsive.css      — @media 반응형 오버라이드
  viewer/js/data.js              — SAMPLE_WIKI, 전역 상태, loadWiki, esc
  viewer/js/render.js            — renderMarkdown, fmtDate, fmtWeek
  viewer/js/ui.js                — 사이드바 드로어, 탭바, TOC 네비
  viewer/js/wiki.js              — renderSidebar, selectItem, PRD, filterItems
  viewer/js/graph.js             — switchView, renderGraph, _initGraphLegend
  viewer/js/init.js              — THEMES, applyTheme, toggleTheme, init()

빌드 산출물 (배포용):
  viewer/index.html — CSS/JS 인라인 포함, WIKI_DATA 주입 (git 추적 제외)

사용법:
  from src.viewer.builder import build_viewer_html
  html = build_viewer_html(wiki_json_str)
"""
from pathlib import Path

_VIEWER_DIR = Path(__file__).parent.parent.parent / "viewer"

# CSS 합치는 순서 (원본 style.css 순서와 동일해야 함)
_CSS_FILES = [
    "css/variables.css",
    "css/layout.css",
    "css/wiki.css",
    "css/graph.css",
    "css/layout_shell.css",
    "css/responsive.css",
]

# JS 합치는 순서 (원본 app.js 순서와 동일해야 함)
_JS_FILES = [
    "js/data.js",
    "js/render.js",
    "js/ui.js",
    "js/wiki.js",
    "js/graph.js",
    "js/init.js",
]

_TEMPLATE     = _VIEWER_DIR / "_template.html"
_LEGACY_INDEX = _VIEWER_DIR / "index.html"


def _read_all(file_list: list[str]) -> str:
    return "".join((_VIEWER_DIR / f).read_text(encoding="utf-8") for f in file_list)


def _build_html() -> str:
    """
    _template.html의 {{CSS}}, {{JS}} 플레이스홀더에
    분리된 소스 파일들을 순서대로 합쳐 주입한다.

    소스 파일이 없으면 index.html을 그대로 반환한다(레거시 폴백).
    """
    if not _TEMPLATE.exists() or not (_VIEWER_DIR / _CSS_FILES[0]).exists():
        return _LEGACY_INDEX.read_text(encoding="utf-8")

    css = _read_all(_CSS_FILES)
    js  = _read_all(_JS_FILES)
    return _TEMPLATE.read_text(encoding="utf-8") \
                    .replace("{{CSS}}", css) \
                    .replace("{{JS}}",  js)


def build_viewer_html(wiki_json_str: str) -> str:
    """
    wiki.json 문자열을 받아 WIKI_DATA가 인라인 주입된 단일 HTML을 반환한다.
    """
    html = _build_html()
    wiki_json_safe = wiki_json_str.replace("</script>", "<\\/script>")
    inject = (
        "<script>\n"
        "// AUTO-GENERATED: wiki.json 인라인 데이터\n"
        f"const WIKI_DATA = {wiki_json_safe};\n"
        "</script>\n"
    )
    return html.replace("</head>", inject + "</head>", 1)


def build_viewer_html_from_file(wiki_json_path: str) -> str:
    """wiki.json 파일 경로를 받아 인라인 뷰어 HTML을 반환한다."""
    return build_viewer_html(Path(wiki_json_path).read_text(encoding="utf-8"))
