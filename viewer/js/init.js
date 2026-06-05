// ── 테마 전환 ────────────────────────────────────────────────
const THEMES = [
  { key: 'wiki', label: '🌙 다크', next: 'dark' },
  { key: 'dark', label: '☀️ 라이트', next: 'wiki' },
];

function applyTheme(key) {
  document.documentElement.setAttribute('data-theme', key);
  const t = THEMES.find(t => t.key === key) || THEMES[0];
  // 데스크탑 테마 버튼: 현재 라이트면 "🌙 다크모드", 현재 다크면 "☀️ 라이트모드"
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = key === 'dark' ? '☀️ 라이트' : '🌙 다크';
  // 모바일 하단 탭 아이콘: 현재 라이트면 🌙(다크로), 현재 다크면 ☀️(라이트로)
  const bbIcon = document.getElementById('bb-theme-icon');
  if (bbIcon) bbIcon.textContent = key === 'dark' ? '☀️' : '🌙';
  try { localStorage.setItem('wiki-theme', key); } catch(e) {}
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'wiki';
  const t = THEMES.find(t => t.key === current) || THEMES[0];
  applyTheme(t.next);
}

async function init() {
  try {
    const saved = localStorage.getItem('wiki-theme');
    if (saved) {
      applyTheme(saved);
    } else if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
      // 저장된 설정 없으면 시스템 다크모드 감지 (#38)
      applyTheme('dark');
    }
  } catch(e) {}

  const overlay = document.getElementById('load-overlay');
  let data = await loadWiki();
  let usingSample = false;

  if (!data) {
    usingSample = true;
    data = SAMPLE_WIKI;
    showError('⚠️ <b>wiki.json을 찾을 수 없습니다.</b> 샘플 데이터로 표시 중입니다.');
  }

  wiki = data;

  const count = wiki.items?.length||0;
  const updatedAt = fmtDate(wiki.updated_at);
  document.getElementById('meta-info').textContent =
    `아이템 ${count}개${updatedAt?' · '+updatedAt:''}${usingSample?' (샘플)':''}`;

  renderSidebar(wiki.items||[]);
  document.getElementById('search').addEventListener('input', e => filterItems(e.target.value));

  if (wiki.items?.length>0) selectItem(wiki.items[0].id);

  overlay.classList.add('hidden');
  setTimeout(()=>overlay.style.display='none', 350);
}

init();