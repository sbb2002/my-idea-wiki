const SAMPLE_WIKI = {
  "schema_version": "1",
  "updated_at": "2026-05-26T09:00:00+00:00",
  "last_processed_at": "2026-05-26T09:00:00+00:00",
  "items": [
    {
      "id": "item_demo01",
      "title": "AI 기반 루틴 코치 앱",
      "tags": ["앱", "AI", "헬스"],
      "summary": "사용자의 일일 루틴을 분석해 AI가 맞춤형 피드백과 개선 제안을 제공하는 모바일 앱. 수면, 운동, 식사 패턴을 종합적으로 파악해 최적의 루틴을 설계해준다.",
      "versions": [
        { "week": "2026-05-25", "content": "수면 트래킹과 운동 데이터를 연동해 상관관계를 분석하는 기능 추가 구상. 수면 질이 좋을수록 다음날 운동 퍼포먼스가 높다는 패턴을 자동으로 감지하고 시각화.", "source_note_ids": [] },
        { "week": "2026-05-18", "content": "기본 아이디어 정리. 사용자가 매일 간단한 체크인만 하면 AI가 패턴을 학습해 점진적으로 더 나은 루틴을 제안.", "source_note_ids": [] }
      ],
      "related": ["item_demo02"],
      "comments": [{ "date": "2026-05-27", "text": "수면 트래킹은 워치 연동으로 자동화하는 게 더 좋을 것 같다.", "attachments": [] }]
    },
    {
      "id": "item_demo02",
      "title": "구독 관리 서비스",
      "tags": ["앱", "핀테크"],
      "summary": "사용자가 가입한 모든 구독 서비스를 한눈에 보여주고, 사용하지 않는 구독을 탐지해 해지를 도와주는 서비스.",
      "versions": [
        { "week": "2026-05-25", "content": "은행 API 연동으로 구독 결제 내역을 자동 감지하는 방식 검토.", "source_note_ids": [] }
      ],
      "related": ["item_demo01"],
      "comments": []
    }
  ]
};

let wiki = null;
let activeId = null;
let tocItems = [];

async function loadWiki() {
  if (typeof WIKI_DATA !== 'undefined') return WIKI_DATA;
  const token = typeof getGhToken === 'function' ? getGhToken() : (localStorage.getItem('github_token') || '');
  if (!token) {
    throw new Error('🔑 GitHub Token이 필요합니다. 킥오프 섹션의 🔑 버튼으로 토큰을 입력해주세요.');
  }
  const resp = await fetch(
    'https://api.github.com/repos/sbb2002/my-idea-wiki/contents/wiki.json?ref=gh-pages',
    { headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' } }
  );
  if (resp.status === 401 || resp.status === 403) {
    throw new Error('🔒 인증 실패: Token이 올바르지 않거나 권한이 부족합니다. 🔑 버튼으로 다시 입력해주세요.');
  }
  if (!resp.ok) {
    throw new Error(`wiki.json 로드 실패: HTTP ${resp.status}`);
  }
  const meta = await resp.json();
  return JSON.parse(atob(meta.content.replace(/\n/g, '')));
}

function esc(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

