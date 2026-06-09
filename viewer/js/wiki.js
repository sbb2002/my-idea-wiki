// ── 킥오프 섹션 ─────────────────────────────────────────────

const KICKOFF_FIELDS = [
  { key: 'core_value',     label: '1. 핵심 가치',          hint: '이걸 왜 만드는가? 한 문장으로.' },
  { key: 'mvp_scope',      label: '2. MVP 범위',            hint: '딱 이것만. 그 외는 명시적으로 제외.' },
  { key: 'ui_anchor',      label: '3. UI 앵커',             hint: '화면/인터페이스가 어떻게 생겼는지.' },
  { key: 'tech_rationale', label: '4. 기술 선택 근거',      hint: '익숙해서인가, 적합해서인가.' },
  { key: 'weak_points',    label: '5. 가장 먼저 무너질 것', hint: '구조적 약점 2개.' },
  { key: 'kill_condition', label: '6. Kill Condition',      hint: '이 조건이 충족되면 미련 없이 중단한다.' },
];

function buildKickoffHtml(item) {
  const ko = item.kickoff || {};
  const rows = KICKOFF_FIELDS.map(f => {
    const val = ko[f.key] || '';
    const isEmpty = !val.trim();
    return `
      <div class="kickoff-row" data-item-id="${esc(item.id)}" data-field="${f.key}">
        <div class="kickoff-label">${f.label}</div>
        <div class="kickoff-value${isEmpty ? ' kickoff-empty' : ''}"
             data-placeholder="${esc(f.hint)}"
             contenteditable="true"
             spellcheck="false"
        >${isEmpty ? '' : esc(val)}</div>
      </div>`;
  }).join('');

  const logs = (ko.decision_log || []);
  const logRows = logs.length === 0
    ? `<div class="kickoff-log-empty">아직 기록 없음</div>`
    : logs.map((l, i) => `
        <div class="kickoff-log-item">
          <div class="kickoff-log-meta">
            <span class="kickoff-log-date">${esc(l.date||'')}</span>
            <button class="kickoff-log-del" data-log-idx="${i}" title="삭제">✕</button>
          </div>
          <div class="kickoff-log-decision"><strong>결정:</strong> ${esc(l.decision||'')}</div>
          ${l.reason ? `<div class="kickoff-log-reason"><strong>이유:</strong> ${esc(l.reason)}</div>` : ''}
          ${l.rejected_alternative ? `<div class="kickoff-log-alt"><strong>포기한 대안:</strong> ${esc(l.rejected_alternative)}</div>` : ''}
        </div>`).join('');

  return `
    <div class="kickoff-block" data-item-id="${esc(item.id)}">
      <div class="kickoff-save-bar">
        <span class="kickoff-save-msg" id="kickoff-save-msg-${esc(item.id)}"></span>
        <button class="kickoff-save-btn" onclick="saveKickoff('${esc(item.id)}')">저장</button>
        <button class="kickoff-token-btn" onclick="openTokenModal()" title="GitHub Token 설정">🔑</button>
      </div>
      ${rows}
      <div class="kickoff-row kickoff-log-section">
        <div class="kickoff-label">7. 의사결정 로그</div>
        <div class="kickoff-log-body">
          <div id="kickoff-log-list-${esc(item.id)}">${logRows}</div>
          <button class="kickoff-log-add-btn" onclick="openLogForm('${esc(item.id)}')">+ 추가</button>
          <div class="kickoff-log-form" id="kickoff-log-form-${esc(item.id)}" style="display:none">
            <input class="kickoff-log-input" id="log-date-${esc(item.id)}" type="date" value="${new Date().toISOString().slice(0,10)}">
            <textarea class="kickoff-log-input" id="log-decision-${esc(item.id)}" placeholder="결정 내용" rows="2"></textarea>
            <textarea class="kickoff-log-input" id="log-reason-${esc(item.id)}" placeholder="이유" rows="2"></textarea>
            <textarea class="kickoff-log-input" id="log-alt-${esc(item.id)}" placeholder="포기한 대안" rows="2"></textarea>
            <div class="kickoff-log-form-btns">
              <button class="kickoff-save-btn" onclick="submitLogEntry('${esc(item.id)}')">추가</button>
              <button class="kickoff-cancel-btn" onclick="closeLogForm('${esc(item.id)}')">취소</button>
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

// ── 킥오프 편집 이벤트 위임 ──────────────────────────────────
document.addEventListener('focusout', e => {
  const val = e.target;
  if (!val.classList.contains('kickoff-value')) return;
  val.classList.toggle('kickoff-empty', !val.textContent.trim());
});

// ── 의사결정 로그 폼 ──────────────────────────────────────────
function openLogForm(itemId) {
  document.getElementById(`kickoff-log-form-${itemId}`).style.display = 'block';
}
function closeLogForm(itemId) {
  document.getElementById(`kickoff-log-form-${itemId}`).style.display = 'none';
}

function submitLogEntry(itemId) {
  const date     = document.getElementById(`log-date-${itemId}`)?.value || '';
  const decision = document.getElementById(`log-decision-${itemId}`)?.value.trim() || '';
  const reason   = document.getElementById(`log-reason-${itemId}`)?.value.trim() || '';
  const alt      = document.getElementById(`log-alt-${itemId}`)?.value.trim() || '';
  if (!decision) { alert('결정 내용을 입력하세요.'); return; }
  saveKickoff(itemId, { date, decision, reason, rejected_alternative: alt });
  closeLogForm(itemId);
}

// ── GitHub API 저장 ───────────────────────────────────────────
const GH_REPO  = 'sbb2002/my-idea-wiki';
const GH_BRANCH = 'gh-pages';

function getGhToken() {
  return localStorage.getItem('github_token') || '';
}

function openTokenModal(callback) {
  const existing = getGhToken();
  const token = prompt(
    'GitHub Personal Access Token을 입력하세요.\n(repo 또는 contents 권한 필요)\n입력값은 이 브라우저에만 저장됩니다.',
    existing || ''
  );
  if (token === null) return;           // 취소
  if (token.trim()) {
    localStorage.setItem('github_token', token.trim());
    if (callback) callback();
  } else {
    localStorage.removeItem('github_token');
  }
}

async function pushKickoffToGithub(itemId, updatedKickoff) {
  const token = getGhToken();
  if (!token) {
    return new Promise((resolve, reject) => {
      openTokenModal(() => pushKickoffToGithub(itemId, updatedKickoff).then(resolve).catch(reject));
    });
  }

  const apiBase = `https://api.github.com/repos/${GH_REPO}/contents/wiki.json`;

  // 1) 현재 wiki.json SHA + 내용 조회
  const getResp = await fetch(`${apiBase}?ref=${GH_BRANCH}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' }
  });
  if (!getResp.ok) throw new Error(`GitHub GET 실패: ${getResp.status}`);
  const getMeta = await getResp.json();
  const sha = getMeta.sha;
  const currentJson = JSON.parse(atob(getMeta.content.replace(/\n/g, '')));

  // 2) 해당 아이템 kickoff만 업데이트
  const targetItem = currentJson.items.find(i => i.id === itemId);
  if (!targetItem) throw new Error(`아이템 ID ${itemId}를 찾을 수 없습니다.`);
  targetItem.kickoff = updatedKickoff;
  currentJson.updated_at = new Date().toISOString();

  // 3) PUT
  const newContent = btoa(unescape(encodeURIComponent(JSON.stringify(currentJson, null, 2))));
  const putResp = await fetch(apiBase, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: `chore: update kickoff for "${targetItem.title}"`,
      content: newContent,
      sha,
      branch: GH_BRANCH,
    }),
  });
  if (!putResp.ok) {
    const err = await putResp.json().catch(() => ({}));
    throw new Error(`GitHub PUT 실패: ${putResp.status} — ${err.message || ''}`);
  }

  // 4) 로컬 wiki 데이터도 동기화
  const localItem = wiki.items.find(i => i.id === itemId);
  if (localItem) localItem.kickoff = updatedKickoff;
}

async function saveKickoff(itemId, newLogEntry) {
  const item = wiki.items.find(i => i.id === itemId);
  if (!item) return;

  // 현재 DOM에서 1~6번 값 수집
  const block = document.querySelector(`.kickoff-block[data-item-id="${itemId}"]`);
  if (!block) return;

  const updatedKickoff = Object.assign({}, item.kickoff || {});
  // decision_log 보존
  if (!Array.isArray(updatedKickoff.decision_log)) updatedKickoff.decision_log = [];

  KICKOFF_FIELDS.forEach(f => {
    const el = block.querySelector(`.kickoff-row[data-field="${f.key}"] .kickoff-value`);
    if (el) updatedKickoff[f.key] = el.textContent.trim();
  });

  // 의사결정 로그 신규 항목 추가
  if (newLogEntry) {
    updatedKickoff.decision_log = [newLogEntry, ...updatedKickoff.decision_log];
  }

  const msgEl = document.getElementById(`kickoff-save-msg-${itemId}`);
  if (msgEl) { msgEl.textContent = '저장 중…'; msgEl.className = 'kickoff-save-msg saving'; }

  try {
    await pushKickoffToGithub(itemId, updatedKickoff);
    if (msgEl) { msgEl.textContent = '✓ 저장됨'; msgEl.className = 'kickoff-save-msg saved'; }
    setTimeout(() => { if (msgEl) { msgEl.textContent = ''; msgEl.className = 'kickoff-save-msg'; } }, 2500);

    // 로그 목록 재렌더링
    if (newLogEntry) {
      const logList = document.getElementById(`kickoff-log-list-${itemId}`);
      if (logList) {
        const logs = updatedKickoff.decision_log;
        logList.innerHTML = logs.map((l, i) => `
          <div class="kickoff-log-item">
            <div class="kickoff-log-meta">
              <span class="kickoff-log-date">${esc(l.date||'')}</span>
              <button class="kickoff-log-del" data-item-id="${itemId}" data-log-idx="${i}" title="삭제">✕</button>
            </div>
            <div class="kickoff-log-decision"><strong>결정:</strong> ${esc(l.decision||'')}</div>
            ${l.reason ? `<div class="kickoff-log-reason"><strong>이유:</strong> ${esc(l.reason)}</div>` : ''}
            ${l.rejected_alternative ? `<div class="kickoff-log-alt"><strong>포기한 대안:</strong> ${esc(l.rejected_alternative)}</div>` : ''}
          </div>`).join('');
      }
    }
  } catch (err) {
    console.error('[kickoff save]', err);
    const msg = err.message || '저장 실패';
    if (msgEl) { msgEl.textContent = `✕ ${msg}`; msgEl.className = 'kickoff-save-msg error'; }
  }
}

// 로그 삭제 이벤트 위임
document.addEventListener('click', async e => {
  const btn = e.target.closest('.kickoff-log-del');
  if (!btn) return;
  const itemId = btn.dataset.itemId;
  const idx    = parseInt(btn.dataset.logIdx, 10);
  if (!itemId || isNaN(idx)) return;
  if (!confirm('이 항목을 삭제할까요?')) return;

  const item = wiki.items.find(i => i.id === itemId);
  if (!item?.kickoff?.decision_log) return;
  const updatedKickoff = Object.assign({}, item.kickoff);
  updatedKickoff.decision_log = updatedKickoff.decision_log.filter((_, i) => i !== idx);

  const msgEl = document.getElementById(`kickoff-save-msg-${itemId}`);
  if (msgEl) { msgEl.textContent = '삭제 중…'; msgEl.className = 'kickoff-save-msg saving'; }
  try {
    await pushKickoffToGithub(itemId, updatedKickoff);
    if (msgEl) { msgEl.textContent = '✓ 삭제됨'; msgEl.className = 'kickoff-save-msg saved'; }
    setTimeout(() => { if (msgEl) { msgEl.textContent = ''; msgEl.className = 'kickoff-save-msg'; } }, 2000);
    // 로그 항목 DOM 제거
    btn.closest('.kickoff-log-item')?.remove();
    const logList = document.getElementById(`kickoff-log-list-${itemId}`);
    if (logList && !logList.querySelector('.kickoff-log-item')) {
      logList.innerHTML = `<div class="kickoff-log-empty">아직 기록 없음</div>`;
    }
  } catch (err) {
    if (msgEl) { msgEl.textContent = `✕ ${err.message||'삭제 실패'}`; msgEl.className = 'kickoff-save-msg error'; }
  }
});

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
            ${v.tokens ? `<div class="tl-tokens">🔢 ${v.tokens.toLocaleString()} tokens</div>` : ''}
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
  const hasPrd     = !!item.prd;
  const hasPrdHist = !!(item.prd_history?.length);

  tocItems = [
    { id: 'sec-summary', label: '개요' },
    { id: 'sec-kickoff', label: '킥오프' },
    ...(item.body ? [{ id: 'sec-body', label: '상세 내용' }] : []),
    ...(hasPrd ? [{ id: 'sec-prd', label: 'PRD' }] : []),
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
        ${item.versions?.[0]?.tokens ? `<div class="infobox-row">
          <div class="infobox-label">토큰</div>
          <div class="infobox-val" style="font-size:12px;color:var(--text-dim)">🔢 ${item.versions[0].tokens.toLocaleString()} tokens</div>
        </div>` : ''}
      </div>
    </div>

    <h2 class="wiki-h2" id="sec-summary">개요</h2>
    <p class="summary-text">${esc(item.summary||'개요 없음')}</p>

    <h2 class="wiki-h2" id="sec-kickoff">킥오프</h2>
    ${buildKickoffHtml(item)}

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

    ${hasPrd ? `
    <h2 class="wiki-h2" id="sec-prd">PRD</h2>
    <div class="prd-section">
      <div class="prd-meta">
        <span class="prd-badge">LLM 구현 문서</span>
        ${hasPrdHist ? `<span class="prd-hist-count">이전 버전 ${item.prd_history.length}개 ↓</span>` : ''}
      </div>
      <div class="prd-body">${renderMarkdown(item.prd, [])}</div>
      ${hasPrdHist ? `
      <div class="prd-history">
        <div class="prd-history-title">이전 PRD 버전</div>
        ${item.prd_history.map((h, i) => `
        <div class="prd-hist-item">
          <div class="prd-hist-date">${esc(h.date)} · v${item.prd_history.length - i}</div>
          <div class="prd-hist-body">${renderMarkdown(h.content, [])}</div>
        </div>`).join('')}
      </div>` : ''}
    </div>` : ''}

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
      // touch-action: manipulation 설정으로 300ms 딜레이 없음 → click 단일 리스너로 충분
      header.addEventListener('click', () => {
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
    // touch-action: manipulation 설정으로 300ms 딜레이 없음 → click 단일 리스너로 충분
    h2.addEventListener('click', () => {
      h2.classList.toggle('collapsed');
      body.classList.toggle('collapsed');
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

