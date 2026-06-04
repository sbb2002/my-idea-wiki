"""
GitHub Pages (gh-pages 브랜치) 파일 업로드 유틸리티.

GitHub Contents API를 사용해 orphan gh-pages 브랜치의
wiki.json 과 index.html 을 갱신한다.

환경변수:
    GITHUB_TOKEN  — Personal Access Token (repo 스코프 필요)
    GITHUB_REPO   — "owner/repo" 형식, 예: "sbb2002/my-idea-wiki"
                    미설정 시 "sbb2002/my-idea-wiki" 하드코딩 기본값 사용
    GITHUB_BRANCH — 대상 브랜치, 기본값 "gh-pages"
"""
import base64
import os
from typing import Optional

import httpx

_GITHUB_API = "https://api.github.com"
_DEFAULT_REPO = "sbb2002/my-idea-wiki"
_DEFAULT_BRANCH = "gh-pages"


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo() -> str:
    return os.getenv("GITHUB_REPO", _DEFAULT_REPO)


def _branch() -> str:
    return os.getenv("GITHUB_BRANCH", _DEFAULT_BRANCH)


def _get_file_sha(path: str) -> Optional[str]:
    """
    gh-pages 브랜치에서 파일의 현재 SHA를 조회한다.
    파일이 없으면 None 반환.
    """
    url = f"{_GITHUB_API}/repos/{_repo()}/contents/{path}"
    resp = httpx.get(url, headers=_headers(), params={"ref": _branch()}, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("sha")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()


def push_file(path: str, content: str | bytes, commit_message: str) -> dict:
    """
    gh-pages 브랜치에 단일 파일을 PUT (신규 생성 또는 갱신)한다.

    Args:
        path:           저장 경로, 예: "wiki.json" 또는 "index.html"
        content:        파일 내용 (str 또는 bytes)
        commit_message: 커밋 메시지

    Returns:
        GitHub API 응답 JSON dict

    Raises:
        httpx.HTTPStatusError: API 호출 실패 시
    """
    if isinstance(content, str):
        content = content.encode("utf-8")

    encoded = base64.b64encode(content).decode("ascii")
    sha = _get_file_sha(path)

    payload: dict = {
        "message": commit_message,
        "content": encoded,
        "branch": _branch(),
    }
    if sha:
        payload["sha"] = sha

    url = f"{_GITHUB_API}/repos/{_repo()}/contents/{path}"
    resp = httpx.put(url, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def push_wiki_to_gh_pages(wiki_json_str: str) -> dict:
    """
    wiki.json 과 WIKI_DATA 인라인 주입된 index.html 을
    gh-pages 브랜치에 동시에 push 한다.

    Args:
        wiki_json_str: dump_wiki() 결과 문자열

    Returns:
        {
            "wiki_json": dict (GitHub API 응답),
            "index_html": dict (GitHub API 응답),
        }

    Raises:
        Exception: 어느 하나라도 실패 시
    """
    from src.viewer.builder import build_viewer_html

    viewer_html = build_viewer_html(wiki_json_str)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    wiki_result = push_file(
        path="wiki.json",
        content=wiki_json_str,
        commit_message=f"chore: update wiki.json [{ts}]",
    )

    html_result = push_file(
        path="index.html",
        content=viewer_html,
        commit_message=f"chore: update index.html [{ts}]",
    )

    return {
        "wiki_json": wiki_result,
        "index_html": html_result,
    }


def gh_pages_url() -> str:
    """GitHub Pages 뷰어 URL을 반환한다."""
    repo = _repo()
    if not repo:
        return ""
    owner, name = repo.split("/", 1)
    return f"https://{owner}.github.io/{name}/"
