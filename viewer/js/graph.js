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

