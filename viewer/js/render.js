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

