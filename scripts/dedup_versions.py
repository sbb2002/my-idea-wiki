"""
#35: 기존 중복 week 버전 데이터 일회성 정리 스크립트

실행 방법:
  python scripts/dedup_versions.py --dry-run   # 변경 내용 미리 확인
  python scripts/dedup_versions.py             # 실제 적용 (Drive 업로드 포함)

동작:
  wiki.json의 각 아이템에서 동일 week 버전이 여러 개인 경우
  가장 마지막(최신) 항목 하나만 남기고 나머지를 제거한다.
  source_note_ids는 합산(union)한다.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.drive.client import read_wiki_json, upload_wiki_json

DRY_RUN = "--dry-run" in sys.argv


def dedup_versions(versions: list[dict]) -> tuple[list[dict], int]:
    """
    동일 week 버전 중복 제거.
    - 순서 보존 (최신순)
    - 동일 week 항목들의 source_note_ids 합산
    Returns: (deduped_versions, removed_count)
    """
    seen: dict[str, dict] = {}  # week -> merged version
    order: list[str] = []       # week 순서 보존

    for v in versions:
        week = v.get("week", "")
        if week not in seen:
            seen[week] = {
                "week": week,
                "content": v.get("content", ""),
                "source_note_ids": list(v.get("source_note_ids", [])),
            }
            order.append(week)
        else:
            # 동일 week: content는 마지막(= 덮어쓰기), note_ids 합산
            seen[week]["content"] = v.get("content", seen[week]["content"])
            existing_ids = set(seen[week]["source_note_ids"])
            new_ids = v.get("source_note_ids", [])
            seen[week]["source_note_ids"] = list(existing_ids | set(new_ids))

    deduped = [seen[w] for w in order]
    removed = len(versions) - len(deduped)
    return deduped, removed


def main():
    print("📥 wiki.json 로드 중...")
    raw = read_wiki_json()
    if not raw:
        print("❌ wiki.json을 불러올 수 없습니다.")
        return

    wiki = json.loads(raw)
    items = wiki.get("items", [])
    total_removed = 0
    affected_items = []

    for item in items:
        versions = item.get("versions", [])
        deduped, removed = dedup_versions(versions)
        if removed > 0:
            affected_items.append((item["title"], len(versions), removed))
            total_removed += removed
            if not DRY_RUN:
                item["versions"] = deduped

    if not affected_items:
        print("✅ 중복 버전 없음. 정리할 내용이 없습니다.")
        return

    print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}중복 버전 발견:")
    for title, before, removed in affected_items:
        print(f"  - {title}: {before}개 → {before - removed}개 (제거: {removed}개)")
    print(f"\n총 제거 버전 수: {total_removed}개 / 영향 아이템: {len(affected_items)}개")

    if DRY_RUN:
        print("\n(--dry-run 모드: 실제 변경 없음. 적용하려면 --dry-run 없이 실행)")
        return

    from src.pipeline.wiki_store import dump_wiki
    updated_json = dump_wiki(wiki)
    upload_wiki_json(updated_json)
    print("\n✅ wiki.json 업데이트 완료 (Drive 업로드됨)")


if __name__ == "__main__":
    main()
