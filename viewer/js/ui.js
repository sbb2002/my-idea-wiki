// ── 사이드바 드로어 (모바일) ────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const isOpen = sidebar.classList.contains('open');
  if (isOpen) closeSidebar();
  else openSidebar();
}

function openSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  sidebar.classList.add('open');
  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  sidebar.classList.remove('open');
  overlay.classList.remove('open');
  document.body.style.overflow = '';
}

// ── 하단 탭바 — #37: 목록/그래프 ON-OFF 토글 ──────────────
function bbTab(tab) {
  if (tab === 'list') {
    const sidebar = document.getElementById('sidebar');
    const isOpen = sidebar.classList.contains('open');
    if (isOpen) {
      closeSidebar();
      document.getElementById('bb-list').classList.remove('active');
    } else {
      openSidebar();
      document.getElementById('bb-list').classList.add('active');
      document.getElementById('bb-graph').classList.remove('active');
    }
  } else if (tab === 'graph') {
    const isGraph = currentView === 'graph';
    if (isGraph) {
      switchView('wiki');
      document.getElementById('bb-graph').classList.remove('active');
    } else {
      closeSidebar();
      document.getElementById('bb-list').classList.remove('active');
      switchView('graph');
      document.getElementById('bb-graph').classList.add('active');
    }
  }
}

// ── TOC 스크롤: 접힌 섹션 자동 펼침 (#29) ──────────────────
function scrollToSection(id) {
  const target = document.getElementById(id);
  if (!target) return;
  // 해당 섹션이 h2인 경우 본인은 괜찮고, h2의 다음 형제(wiki-section-body)가 접혔으면 펼침
  // 또는 target 자체가 section-body 내부에 있을 수 있음
  // → target 앞의 가장 가까운 wiki-h2를 찾아 펼침
  let el = target;
  // target이 wiki-h2 자신이면 그 body를 펼침
  if (el.classList.contains('wiki-h2')) {
    const body = el.nextElementSibling;
    if (body?.classList.contains('wiki-section-body') && body.classList.contains('collapsed')) {
      el.classList.remove('collapsed');
      body.classList.remove('collapsed');
    }
  } else {
    // target이 section-body 안에 있으면 부모 section-body 펼침
    const sectionBody = el.closest('.wiki-section-body');
    if (sectionBody?.classList.contains('collapsed')) {
      sectionBody.classList.remove('collapsed');
      const h2 = sectionBody.previousElementSibling;
      if (h2?.classList.contains('wiki-h2')) h2.classList.remove('collapsed');
    }
  }
  target.scrollIntoView({ behavior: 'smooth' });
}

// ── 모바일 TOC 접힘 ─────────────────────────────────────────
function toggleMobileToc() {
  const list = document.getElementById('toc-mobile-list');
  const arrow = document.getElementById('toc-mobile-arrow');
  const isOpen = list.classList.contains('open');
  list.classList.toggle('open', !isOpen);
  arrow.style.transform = isOpen ? '' : 'rotate(180deg)';
}

