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

