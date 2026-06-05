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
  try {
    const resp = await fetch('./wiki.json');
    if (resp.ok) return await resp.json();
  } catch(e) {}
  return null;
}

function esc(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderMarkdown(md, attachments) {
  // 이미지 참조 변환: ![alt](pic_drive_id) 또는 ![alt](attachment:filename)
  const atts = attachments || [];
  const attByFilename = {};
  atts.forEach(a => { if (a.filename) attByFilename[a.filename] = a; });

  // 1단계: 이스케이프 (일반 텍스트 전용 — HTML 삽입 전에 처리)
  let escaped = String(md||'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

  // 2단계: 마크다운 → HTML 변환 (이스케이프된 텍스트 위에서 패턴 매칭)
  escaped = escaped
    .replace(/^### (.+)$/gm, '<h4 class="body-h4">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="body-h3">$1</h3>')
    .replace(/^# (.+)$/gm, '<h3 class="body-h3">$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="body-code">$1</code>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[^]*?<\/li>\n?)+/g, m => `<ul class="body-ul">${m}</ul>`);

  // 3단계: 파이프 테이블 파싱 (라인 단위 처리)
  const lines = escaped.split('\n');
  const out = [];
  let tableLines = [];

  function flushTable() {
    if (!tableLines.length) return;
    let theadHtml = '', tbodyHtml = '';
    let headerDone = false;
    tableLines.forEach(row => {
      // 구분선 스킵
      if (/^\|?[\s\-:|]+\|/.test(row)) return;
      const cells = row.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      if (!headerDone) {
        theadHtml = `<thead><tr>${cells.map(c=>`<th>${c}</th>`).join('')}</tr></thead>`;
        headerDone = true;
      } else {
        tbodyHtml += `<tr>${cells.map(c=>`<td>${c}</td>`).join('')}</tr>`;
      }
    });
    out.push(`<table class="body-table">${theadHtml}<tbody>${tbodyHtml}</tbody></table>`);
    tableLines = [];
  }

  lines.forEach(line => {
    if (/^\|.+\|/.test(line)) {
      tableLines.push(line);
    } else {
      flushTable();
      out.push(line);
    }
  });
  flushTable();

  // 4단계: 이미지 참조 치환 (HTML 안전 상태에서 삽입)
  const withImgs = out.join('\n').replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, ref) => {
    const safeAlt = alt.replace(/"/g,'&quot;');
    if (ref.startsWith('attachment:')) {
      const fname = ref.slice('attachment:'.length);
      const att = attByFilename[fname];
      if (att?.pic_drive_id) {
        return `<img src="https://lh3.googleusercontent.com/d/${att.pic_drive_id}" alt="${safeAlt}" class="body-inline-img">`;
      }
      return match;
    }
    if (/^[A-Za-z0-9_-]{10,}$/.test(ref)) {
      return `<img src="https://lh3.googleusercontent.com/d/${ref}" alt="${safeAlt}" class="body-inline-img">`;
    }
    return match;
  });

  // 5단계: 빈 줄 기준 블록 분리 → <p> 래핑
  const html = withImgs
    .split(/\n\n+/)
    .map(block => {
      if (/^<[hultib]/.test(block.trim())) return block;
      return `<p class="body-p">${block.replace(/\n/g,'<br>')}</p>`;
    })
    .join('\n');

  return html;
}

function fmtDate(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString('ko-KR', { year:'numeric', month:'long', day:'numeric' }); }
  catch { return iso; }
}

function fmtWeek(w) {
  if (!w) return '';
  try { return new Date(w).toLocaleDateString('ko-KR', { year:'numeric', month:'short', day:'numeric' }); }
  catch { return w; }
}

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

function renderSidebar(items) {
  const list = document.getElementById('item-list');
  document.getElementById('item-count').textContent = items.length;
  if (!items.length) {
    list.innerHTML = '<div style="padding:14px;font-size:13px;color:var(--text-dim);font-style:italic">결과 없음</div>';
    return;
  }
  list.innerHTML = items.map(item => {
    const week = item.versions?.[0]?.week || '';
    return `<div class="item-entry${item.id === activeId ? ' active' : ''}" data-id="${esc(item.id)}">
      <div class="entry-title">${esc(item.title)}</div>
      ${week ? `<div class="entry-week">${fmtWeek(week)}</div>` : ''}
    </div>`;
  }).join('');
  list.querySelectorAll('.item-entry').forEach(el =>
    el.addEventListener('click', () => {
      selectItem(el.dataset.id);
      // 모바일에서 아이템 선택 시 드로어 닫기 + 위키 뷰로 전환 (#37)
      if (window.innerWidth <= 640) {
        closeSidebar();
        if (currentView !== 'wiki') switchView('wiki');
        document.getElementById('bb-list')?.classList.remove('active');
        document.getElementById('bb-graph')?.classList.remove('active');
      }
    })
  );
}

function buildAttachHtml(item) {
  if (!item.attachments?.length) return '';
  return `
    <h2 class="wiki-h2" id="sec-attachments">이미지 첨부</h2>
    ${item.attachments.map(att => {
      const picUrl = att.pic_drive_id
        ? `https://lh3.googleusercontent.com/d/${att.pic_drive_id}`
        : null;
      const thumbHtml = picUrl
        ? `<img class="attach-thumb" src="${picUrl}"
              alt="${esc(att.description || att.summary || '')}"
              onclick="window.open('https://drive.google.com/file/d/${att.pic_drive_id}/view','_blank')"
              onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"
           /><div class="attach-thumb-placeholder" style="display:none">🖼️</div>`
        : `<div class="attach-thumb-placeholder">🖼️</div>`;
      return `
      <div class="attach-card">
        ${thumbHtml}
        <div class="attach-meta">
          <div class="attach-filename">${esc(att.filename||'')}</div>
          <div class="attach-summary">${esc(att.summary||'')}</div>
          ${att.description ? `<div class="attach-desc">${esc(att.description)}</div>` : ''}
          ${att.ocr_text ? `<div class="attach-ocr">${esc(att.ocr_text)}</div>` : ''}
        </div>
      </div>`;
    }).join('')}`;
}

function selectItem(id) {
  activeId = id;
  document.querySelectorAll('.item-entry').forEach(el =>
    el.classList.toggle('active', el.dataset.id === id)
  );

  const item = wiki.items.find(i => i.id === id);
  if (!item) return;

  document.getElementById('empty-state').style.display = 'none';
  const doc = document.getElementById('wiki-doc');
  doc.classList.add('visible');

  const latestWeek = item.versions?.[0]?.week;
  const tagsHtml = (item.tags||[]).map(t => `<span class="doc-tag">${esc(t)}</span>`).join(' ');
  const relatedItems = (item.related||[]).map(rid => wiki.items.find(i=>i.id===rid)).filter(Boolean);

  const versionsHtml = !item.versions?.length
    ? '<p class="no-content">버전 기록 없음</p>'
    : item.versions.map((v, i) => `
        <div class="tl-item">
          <div class="tl-gutter"><div class="tl-date">${v.week||''}</div></div>
          <div class="tl-connector"><div class="tl-dot"></div></div>
          <div class="tl-body">
            <div class="tl-badge">${i===0 ? '최신' : fmtWeek(v.week)}</div>
            <div class="tl-content">${esc(v.content||'')}</div>
            ${v.source_note_ids?.length ? `<div class="tl-sources">노트 ${v.source_note_ids.length}개 기반</div>` : ''}
          </div>
        </div>`).join('');

  const relatedHtml = !relatedItems.length
    ? '<p class="no-content">연관 아이템 없음</p>'
    : `<div class="related-list">${relatedItems.map(r =>
        `<span class="related-link" data-id="${r.id}">${esc(r.title)}</span>`
      ).join('<span style="color:var(--border);margin:0 2px"> · </span>')}</div>`;

  const comments = (item.comments||[]).slice().sort((a,b)=>b.date.localeCompare(a.date));
  const commentsHtml = !comments.length ? '' : `
    <h2 class="wiki-h2" id="sec-comments">코멘트</h2>
    ${comments.map(c => `
      <div class="comment-item">
        <div class="comment-date">${esc(c.date)}</div>
        <div class="comment-text">${esc(c.text||'')}</div>
      </div>`).join('')}`;

  const attachmentsHtml = buildAttachHtml(item);
  const hasAttachments = !!item.attachments?.length;

  // TOC 구성
  tocItems = [
    { id: 'sec-summary', label: '개요' },
    ...(item.body ? [{ id: 'sec-body', label: '상세 내용' }] : []),
    { id: 'sec-history', label: '버전 히스토리' },
    ...(hasAttachments ? [{ id: 'sec-attachments', label: '이미지 첨부' }] : []),
    ...(comments.length ? [{ id: 'sec-comments', label: '코멘트' }] : []),
    ...((item.see_also?.length) ? [{ id: 'sec-see-also', label: '같이 보기' }] : []),
    { id: 'sec-related', label: '연관 아이템' },
  ];

  const tocHtml = tocItems.map(t =>
    `<li class="toc-item" onclick="scrollToSection('${t.id}')">${t.label}</li>`
  ).join('');

  // 데스크탑 TOC
  document.getElementById('toc-list').innerHTML = tocHtml;
  document.getElementById('toc').classList.add('visible');

  // 모바일 TOC
  const mobileTocList = document.getElementById('toc-mobile-list');
  mobileTocList.innerHTML = tocItems.map(t =>
    `<li onclick="scrollToSection('${t.id}');toggleMobileToc()">${t.label}</li>`
  ).join('');
  document.getElementById('toc-mobile').classList.add('visible');

  document.getElementById('doc-content').innerHTML = `
    <h1 class="doc-title">${esc(item.title)}</h1>
    <div class="infobox">
      <div class="infobox-header">아이디어 요약<i class="infobox-toggle-icon">▼</i></div>
      <div class="infobox-body">
        <div class="infobox-row">
          <div class="infobox-label">분류</div>
          <div class="infobox-val infobox-tags">${(item.tags||[]).map(t=>`<span class="doc-tag">${esc(t)}</span>`).join(' ')}</div>
        </div>
        <div class="infobox-row">
          <div class="infobox-label">버전 수</div>
          <div class="infobox-val">${item.versions?.length||0}개</div>
        </div>
        ${latestWeek ? `<div class="infobox-row">
          <div class="infobox-label">최신</div>
          <div class="infobox-val">${fmtWeek(latestWeek)}</div>
        </div>` : ''}
        ${relatedItems.length ? `<div class="infobox-row">
          <div class="infobox-label">연관</div>
          <div class="infobox-val">${relatedItems.map(r=>`<span class="related-link" data-id="${r.id}" style="font-size:12px">${esc(r.title)}</span>`).join(', ')}</div>
        </div>` : ''}
      </div>
    </div>

    <h2 class="wiki-h2" id="sec-summary">개요</h2>
    <p class="summary-text">${esc(item.summary||'개요 없음')}</p>

    ${item.body ? `
    <h2 class="wiki-h2" id="sec-body">상세 내용</h2>
    <div class="wiki-body">${renderMarkdown(item.body, item.attachments||[])}</div>` : ''}

    ${item.see_also?.length ? `
    <h2 class="wiki-h2" id="sec-see-also">같이 보기</h2>
    <ul class="see-also-list">
      ${item.see_also.map(s => `
      <li class="see-also-item">
        <span class="see-also-name">${esc(s.name||'')}</span>
        ${s.url ? `<a href="${esc(s.url)}" target="_blank" class="see-also-link">↗</a>` : ''}
        ${s.description ? `<span class="see-also-desc"> — ${esc(s.description)}</span>` : ''}
      </li>`).join('')}
    </ul>` : ''}

    <h2 class="wiki-h2" id="sec-history">버전 히스토리</h2>
    <div class="timeline">${versionsHtml}</div>

    ${attachmentsHtml}
    ${commentsHtml}

    <h2 class="wiki-h2" id="sec-related">연관 아이템</h2>
    ${relatedHtml}
  `;

  doc.querySelectorAll('.related-link').forEach(el =>
    el.addEventListener('click', () => {
      selectItem(el.dataset.id);
      document.querySelector(`.item-entry[data-id="${el.dataset.id}"]`)?.scrollIntoView({ block:'nearest' });
    })
  );

  // 인포박스 헤더 클릭/터치 토글 (모바일/데스크탑 공통, 기본 펼침 #수정제안)
  const infobox = doc.querySelector('.infobox');
  if (infobox) {
    const header = infobox.querySelector('.infobox-header');
    if (header) {
      let _infoLastTouch = 0;
      header.addEventListener('touchend', e => {
        e.preventDefault();
        _infoLastTouch = Date.now();
        infobox.classList.toggle('collapsed');
      });
      header.addEventListener('click', () => {
        if (Date.now() - _infoLastTouch < 350) return;
        infobox.classList.toggle('collapsed');
      });
    }
  }

  // wiki-h2 섹션 래핑 및 접기/펼치기
  const content = document.getElementById('doc-content');
  const h2els = content.querySelectorAll('.wiki-h2');
  h2els.forEach(h2 => {
    // h2 다음 형제 요소들을 wiki-section-body로 래핑
    const body = document.createElement('div');
    body.className = 'wiki-section-body';
    let sibling = h2.nextElementSibling;
    while (sibling && !sibling.classList.contains('wiki-h2')) {
      const next = sibling.nextElementSibling;
      body.appendChild(sibling);
      sibling = next;
    }
    h2.insertAdjacentElement('afterend', body);
    // 이미지 첨부 섹션은 기본 접힘 (#수정제안)
    if (h2.id === 'sec-attachments') {
      h2.classList.add('collapsed');
      body.classList.add('collapsed');
    }
    let _lastTouch = 0;
    const toggleSection = () => {
      h2.classList.toggle('collapsed');
      body.classList.toggle('collapsed');
    };
    h2.addEventListener('touchend', e => {
      e.preventDefault();
      _lastTouch = Date.now();
      toggleSection();
    });
    h2.addEventListener('click', () => {
      // touchend 후 300ms 이내 발화되는 합성 click 이벤트 무시
      if (Date.now() - _lastTouch < 350) return;
      toggleSection();
    });
  });

  // PRD 다운로드 버튼 상태 업데이트
  _updatePrdBtn(item);

  document.getElementById('main').scrollTo({ top: 0, behavior: 'smooth' });
}

// ── PRD 다운로드 ────────────────────────────────────────────
let _currentPrdItem = null;

function _updatePrdBtn(item) {
  _currentPrdItem = item;
  const hasPrd = !!item?.prd;

  // 데스크탑 버튼
  const btn = document.getElementById('prd-download-btn');
  if (btn) {
    btn.classList.add('visible');
    btn.classList.toggle('no-prd', !hasPrd);
    btn.title = hasPrd ? 'PRD 다운로드 (.md)' : 'PRD가 아직 생성되지 않았습니다 (다음 파이프라인 실행 시 생성)';
  }

  // 모바일 버튼
  const mBtn = document.getElementById('prd-download-btn-mobile');
  if (mBtn) {
    mBtn.style.opacity = hasPrd ? '1' : '0.4';
    mBtn.title = btn?.title || '';
  }
}

function downloadPrd() {
  if (!_currentPrdItem?.prd) return;

  // 리플 애니메이션
  const btn = document.getElementById('prd-download-btn');
  if (btn) {
    const ripple = document.createElement('span');
    ripple.className = 'prd-ripple';
    ripple.style.cssText = 'width:60px;height:60px;left:calc(50% - 30px);top:calc(50% - 30px)';
    btn.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);
  }

  const title = (_currentPrdItem.title || 'prd')
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/\s+/g, '_');
  const filename = `PRD_${title}.md`;
  const blob = new Blob([_currentPrdItem.prd], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function filterItems(q) {
  if (!wiki) return;
  const query = q.toLowerCase().trim();
  if (!query) { renderSidebar(wiki.items); return; }
  renderSidebar(wiki.items.filter(item =>
    item.title.toLowerCase().includes(query) ||
    (item.tags||[]).some(t => t.toLowerCase().includes(query)) ||
    (item.summary||'').toLowerCase().includes(query)
  ));
}

function showError(msg) {
  const el = document.getElementById('error-banner');
  el.innerHTML = msg;
  el.classList.add('visible');
}

let currentView = 'wiki';
let graphState = null;

function switchView(view) {
  currentView = view;
  const graphPanel = document.getElementById('graph-view');
  const mainPanel = document.getElementById('main');
  const btnWiki = document.getElementById('btn-wiki');
  const btnGraph = document.getElementById('btn-graph');

  if (view === 'graph') {
    mainPanel.style.display = 'none';
    graphPanel.classList.add('visible');
    btnGraph?.classList.add('active');
    btnWiki?.classList.remove('active');
    if (wiki) renderGraph(wiki.items||[]);
  } else {
    mainPanel.style.display = '';
    graphPanel.classList.remove('visible');
    btnWiki?.classList.add('active');
    btnGraph?.classList.remove('active');
  }
}

// ── 그래프 렌더링 (터치 지원 포함) ──────────────────────────
const TAG_COLORS = ['#3366cc','#cc3333','#339933','#cc6600','#663399','#006666','#993366','#336699'];

function renderGraph(items) {
  const canvas = document.getElementById('graph-canvas');
  const tooltip = document.getElementById('graph-tooltip');
  const parent = document.getElementById('graph-view');
  const ctx = canvas.getContext('2d');

  const dpr = window.devicePixelRatio||1;
  const W = parent.clientWidth;
  const H = parent.clientHeight;
  canvas.width = W*dpr; canvas.height = H*dpr;
  ctx.scale(dpr, dpr);

  const allTags = [...new Set(items.flatMap(i=>i.tags||[]))];
  const tagColor = {};
  allTags.forEach((t,i) => { tagColor[t] = TAG_COLORS[i%TAG_COLORS.length]; });

  const nodeMap = {};
  items.forEach(item => { nodeMap[item.id] = item; });

  const nodes = items.map((item, i) => {
    const angle = 2*Math.PI*i/items.length;
    const r = Math.min(W,H)*0.3;
    return {
      id: item.id, title: item.title, tags: item.tags||[],
      color: tagColor[(item.tags||[])[0]]||'#3366cc',
      x: W/2+r*Math.cos(angle)+(Math.random()-.5)*30,
      y: H/2+r*Math.sin(angle)+(Math.random()-.5)*30,
      vx:0, vy:0, radius:10
    };
  });

  const edges = [], seen = new Set();
  items.forEach(item => {
    (item.related||[]).forEach(rid => {
      const key = [item.id,rid].sort().join('--');
      if (seen.has(key)||!nodeMap[rid]) return;
      seen.add(key);
      const explicit = (item.explicit_related||[]).includes(rid);
      edges.push({ from:item.id, to:rid, explicit });
    });
  });

  const nodeIdx = {};
  nodes.forEach((n,i) => { nodeIdx[n.id]=i; });

  let transform = {x:0,y:0,scale:1};
  let dragging=null, panning=null, hoveredNode=null;
  let simRunning=true, frameCnt=0, animFrame=null;

  function tick() {
    const repulse=4000, linkDist=130, linkStr=0.04, alpha=0.08, centerStr=0.012;
    for(let i=0;i<nodes.length;i++) for(let j=i+1;j<nodes.length;j++) {
      const a=nodes[i],b=nodes[j];
      let dx=b.x-a.x, dy=b.y-a.y;
      const d2=dx*dx+dy*dy+.01, f=repulse/d2, d=Math.sqrt(d2);
      a.vx-=f*dx/d; a.vy-=f*dy/d; b.vx+=f*dx/d; b.vy+=f*dy/d;
    }
    edges.forEach(e => {
      const a=nodes[nodeIdx[e.from]], b=nodes[nodeIdx[e.to]];
      if(!a||!b) return;
      let dx=b.x-a.x, dy=b.y-a.y, d=Math.sqrt(dx*dx+dy*dy)||1;
      const f=(d-linkDist)*linkStr;
      a.vx+=f*dx/d; a.vy+=f*dy/d; b.vx-=f*dx/d; b.vy-=f*dy/d;
    });
    nodes.forEach(n => { n.vx+=(W/2-n.x)*centerStr; n.vy+=(H/2-n.y)*centerStr; });
    nodes.forEach(n => {
      if(dragging&&dragging.node===n) return;
      n.vx*=(1-alpha); n.vy*=(1-alpha);
      n.x+=n.vx; n.y+=n.vy;
    });
  }

  function draw() {
    ctx.clearRect(0,0,W,H);
    ctx.save();
    ctx.translate(transform.x,transform.y);
    ctx.scale(transform.scale,transform.scale);

    edges.forEach(e => {
      const a=nodes[nodeIdx[e.from]], b=nodes[nodeIdx[e.to]];
      if(!a||!b) return;
      ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y);
      ctx.strokeStyle = e.explicit ? 'rgba(51,102,204,0.6)' : 'rgba(162,169,177,0.5)';
      ctx.lineWidth = e.explicit ? 2.5 : 1.5;
      ctx.stroke();
    });

    nodes.forEach(n => {
      const isHov = hoveredNode===n;
      const r = isHov ? n.radius+3 : n.radius;
      ctx.beginPath(); ctx.arc(n.x,n.y,r,0,2*Math.PI);
      ctx.fillStyle = isHov ? n.color : n.color+'cc';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.font = `${isHov?12:11}px "Noto Sans KR", sans-serif`;
      ctx.fillStyle = isHov
        ? getComputedStyle(document.documentElement).getPropertyValue('--graph-node-label-hover').trim()
        : getComputedStyle(document.documentElement).getPropertyValue('--graph-node-label').trim();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      let label = n.title;
      const maxW = 85;
      if(ctx.measureText(label).width>maxW) {
        while(label.length>2&&ctx.measureText(label+'…').width>maxW) label=label.slice(0,-1);
        label+='…';
      }
      ctx.fillText(label, n.x, n.y+r+4);
    });
    ctx.restore();
  }

  function loop() {
    if(simRunning){tick();frameCnt++;if(frameCnt>300)simRunning=false;}
    draw();
    animFrame=requestAnimationFrame(loop);
  }

  if(graphState?.animFrame) cancelAnimationFrame(graphState.animFrame);
  graphState = {animFrame:null};

  function canvasPos(clientX, clientY) {
    const rect=canvas.getBoundingClientRect();
    return {
      x:(clientX-rect.left-transform.x)/transform.scale,
      y:(clientY-rect.top-transform.y)/transform.scale
    };
  }

  function hitNode(cx,cy) {
    for(let i=nodes.length-1;i>=0;i--) {
      const n=nodes[i], dx=cx-n.x, dy=cy-n.y;
      if(dx*dx+dy*dy<=(n.radius+8)**2) return n;
    }
    return null;
  }

  // ── 마우스 이벤트 ──
  canvas.onmousedown = e => {
    const {x,y}=canvasPos(e.clientX, e.clientY), hit=hitNode(x,y);
    if(hit) { dragging={node:hit,ox:x-hit.x,oy:y-hit.y}; simRunning=true; frameCnt=0; }
    else panning={sx:e.clientX,sy:e.clientY,tx:transform.x,ty:transform.y};
  };

  canvas.onmousemove = e => {
    if(dragging){const{x,y}=canvasPos(e.clientX,e.clientY);dragging.node.x=x-dragging.ox;dragging.node.y=y-dragging.oy;return;}
    if(panning){transform.x=panning.tx+(e.clientX-panning.sx);transform.y=panning.ty+(e.clientY-panning.sy);return;}
    const{x,y}=canvasPos(e.clientX,e.clientY),hit=hitNode(x,y),prev=hoveredNode;
    hoveredNode=hit;
    if(hit!==prev){simRunning=true;frameCnt=0;}
    if(hit){
      const rect=canvas.getBoundingClientRect();
      tooltip.style.left=(e.clientX-rect.left+14)+'px';
      tooltip.style.top=(e.clientY-rect.top-10)+'px';
      tooltip.innerHTML=`<b>${esc(hit.title)}</b>${hit.tags.length?'<br><span style="color:#3366cc;font-size:10px">'+hit.tags.map(t=>'#'+esc(t)).join(' ')+'</span>':''}`;
      tooltip.classList.add('visible');
      canvas.style.cursor='pointer';
    } else { tooltip.classList.remove('visible'); canvas.style.cursor='grab'; }
  };

  canvas.onmouseup = () => { dragging=null; panning=null; };

  canvas.onclick = e => {
    const{x,y}=canvasPos(e.clientX,e.clientY),hit=hitNode(x,y);
    if(hit){switchView('wiki');selectItem(hit.id);document.querySelector(`.item-entry[data-id="${hit.id}"]`)?.scrollIntoView({block:'nearest'});}
  };

  canvas.onwheel = e => {
    e.preventDefault();
    const rect=canvas.getBoundingClientRect(), mx=e.clientX-rect.left, my=e.clientY-rect.top;
    const delta=e.deltaY>0?.85:1.18, ns=Math.max(.2,Math.min(4,transform.scale*delta));
    transform.x=mx-(mx-transform.x)*(ns/transform.scale);
    transform.y=my-(my-transform.y)*(ns/transform.scale);
    transform.scale=ns;
  };

  // ── 터치 이벤트 (핀치줌 + 드래그) ──
  let lastTouches = null;
  let touchDragging = null;
  let touchPanning = null;
  let pinchStartDist = null;
  let pinchStartScale = null;
  let pinchStartCenter = null;
  let pinchStartTx = null, pinchStartTy = null;
  let tapTimeout = null;
  let tapCandidate = null;

  canvas.addEventListener('touchstart', e => {
    e.preventDefault();
    simRunning = true; frameCnt = 0;

    if (e.touches.length === 1) {
      const t = e.touches[0];
      const {x,y} = canvasPos(t.clientX, t.clientY);
      const hit = hitNode(x, y);

      tapCandidate = hit;
      if (tapTimeout) clearTimeout(tapTimeout);
      tapTimeout = setTimeout(() => { tapCandidate = null; }, 300);

      if (hit) {
        touchDragging = { node: hit, ox: x - hit.x, oy: y - hit.y };
      } else {
        touchPanning = { sx: t.clientX, sy: t.clientY, tx: transform.x, ty: transform.y };
      }
    } else if (e.touches.length === 2) {
      touchDragging = null; touchPanning = null;
      const t1 = e.touches[0], t2 = e.touches[1];
      const cx = (t1.clientX + t2.clientX) / 2;
      const cy = (t1.clientY + t2.clientY) / 2;
      const rect = canvas.getBoundingClientRect();
      pinchStartCenter = { x: cx - rect.left, y: cy - rect.top };
      pinchStartDist = Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY);
      pinchStartScale = transform.scale;
      pinchStartTx = transform.x;
      pinchStartTy = transform.y;
    }
  }, { passive: false });

  canvas.addEventListener('touchmove', e => {
    e.preventDefault();

    if (e.touches.length === 1) {
      const t = e.touches[0];
      if (touchDragging) {
        const {x,y} = canvasPos(t.clientX, t.clientY);
        touchDragging.node.x = x - touchDragging.ox;
        touchDragging.node.y = y - touchDragging.oy;
      } else if (touchPanning) {
        transform.x = touchPanning.tx + (t.clientX - touchPanning.sx);
        transform.y = touchPanning.ty + (t.clientY - touchPanning.sy);
      }
    } else if (e.touches.length === 2 && pinchStartDist !== null) {
      const t1 = e.touches[0], t2 = e.touches[1];
      const dist = Math.hypot(t1.clientX - t2.clientX, t1.clientY - t2.clientY);
      const ratio = dist / pinchStartDist;
      const ns = Math.max(.2, Math.min(4, pinchStartScale * ratio));
      const cx = pinchStartCenter.x;
      const cy = pinchStartCenter.y;
      transform.scale = ns;
      transform.x = cx - (cx - pinchStartTx) * (ns / pinchStartScale);
      transform.y = cy - (cy - pinchStartTy) * (ns / pinchStartScale);
    }
  }, { passive: false });

  canvas.addEventListener('touchend', e => {
    e.preventDefault();
    if (e.touches.length === 0) {
      // 탭으로 노드 클릭
      if (tapCandidate && touchDragging?.node === tapCandidate) {
        const hit = tapCandidate;
        switchView('wiki');
        selectItem(hit.id);
        document.querySelector(`.item-entry[data-id="${hit.id}"]`)?.scrollIntoView({block:'nearest'});
        // 모바일 하단탭 업데이트 (#37)
        document.getElementById('bb-list')?.classList.remove('active');
        document.getElementById('bb-graph')?.classList.remove('active');
      }
      touchDragging = null; touchPanning = null;
      pinchStartDist = null;
    } else if (e.touches.length === 1) {
      // 핀치 종료 후 한 손가락만 남은 경우
      const t = e.touches[0];
      touchPanning = { sx: t.clientX, sy: t.clientY, tx: transform.x, ty: transform.y };
      pinchStartDist = null;
    }
  }, { passive: false });

  document.getElementById('gc-zoom-in').onclick=()=>{transform.scale=Math.min(4,transform.scale*1.25);simRunning=true;frameCnt=0;};
  document.getElementById('gc-zoom-out').onclick=()=>{transform.scale=Math.max(.2,transform.scale*.8);simRunning=true;frameCnt=0;};
  document.getElementById('gc-reset').onclick=()=>{transform={x:0,y:0,scale:1};simRunning=true;frameCnt=0;};

  // ── 그래프 범례 초기화 (최초 1회만 실행 — 리스너 중복 방지) ──
  if (!renderGraph._legendInited) {
    renderGraph._legendInited = true;
    _initGraphLegend(allTags, tagColor);
  } else {
    // 태그 색상만 재주입 (새 아이템 추가 대응)
    const tagRows = document.getElementById('legend-tag-rows');
    if (tagRows) {
      tagRows.innerHTML = allTags.length
        ? allTags.map(t =>
            `<div class="legend-row">
              <span class="legend-dot" style="background:${tagColor[t]||'#3366cc'}"></span>
              <span>${esc(t)}</span>
            </div>`
          ).join('')
        : `<div class="legend-row" style="color:var(--text-muted);font-size:11px">태그 없음</div>`;
    }
  }

  animFrame=requestAnimationFrame(loop);
  graphState.animFrame=animFrame;
}

function _initGraphLegend(allTags, tagColor) {
  // 태그 색상 행 주입
  const tagRows = document.getElementById('legend-tag-rows');
  if (tagRows) {
    tagRows.innerHTML = allTags.length
      ? allTags.map(t =>
          `<div class="legend-row">
            <span class="legend-dot" style="background:${tagColor[t]||'#3366cc'}"></span>
            <span>${esc(t)}</span>
          </div>`
        ).join('')
      : `<div class="legend-row" style="color:var(--text-muted);font-size:11px">태그 없음</div>`;
  }

  // 토글 버튼
  const legend = document.getElementById('graph-legend');
  const toggleBtn = document.getElementById('graph-legend-toggle');
  const body = document.getElementById('graph-legend-body');
  if (!legend || !toggleBtn || !body) return;

  toggleBtn.addEventListener('click', e => {
    e.stopPropagation();
    const collapsed = legend.classList.toggle('collapsed');
    toggleBtn.textContent = collapsed ? '+' : '−';
  });

  // 드래그 이동
  const header = document.getElementById('graph-legend-header');
  if (!header) return;
  let dragging = false, ox = 0, oy = 0;
  // position 초기값: CSS bottom/right 기반 → absolute 좌표로 전환
  const initLegendPos = () => {
    const parent = legend.offsetParent || legend.parentElement;
    if (!parent) return;
    const pr = parent.getBoundingClientRect();
    const lr = legend.getBoundingClientRect();
    // bottom/right → top/left 로 변환 (드래그 전 초기화)
    legend.style.bottom = '';
    legend.style.right  = '';
    legend.style.top  = (lr.top  - pr.top)  + 'px';
    legend.style.left = (lr.left - pr.left) + 'px';
  };

  const onMove = e => {
    if (!dragging) return;
    const cx = e.touches ? e.touches[0].clientX : e.clientX;
    const cy = e.touches ? e.touches[0].clientY : e.clientY;
    legend.style.left = (cx - ox) + 'px';
    legend.style.top  = (cy - oy) + 'px';
  };
  const onUp = () => { dragging = false; };

  header.addEventListener('mousedown', e => {
    if (e.target === toggleBtn) return;
    initLegendPos();
    dragging = true;
    ox = e.clientX - legend.getBoundingClientRect().left;
    oy = e.clientY - legend.getBoundingClientRect().top;
    e.preventDefault();
  });
  header.addEventListener('touchstart', e => {
    if (e.target === toggleBtn) return;
    initLegendPos();
    dragging = true;
    ox = e.touches[0].clientX - legend.getBoundingClientRect().left;
    oy = e.touches[0].clientY - legend.getBoundingClientRect().top;
    e.preventDefault();
  }, { passive: false });

  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup',   onUp);
  document.addEventListener('touchmove', onMove, { passive: false });
  document.addEventListener('touchend',  onUp);
}

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