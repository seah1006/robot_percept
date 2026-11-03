// Robot Percept UI 스크립트
// 모션: Motion (motiondivision/motion, vanilla build) — Magic UI / Motion Primitives 의 효과를 참고해 재구성
const $ = s => document.querySelector(s);
const M = window.Motion;                       // 없으면 CSS 만으로 동작
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
if (M && !reduce) document.documentElement.classList.add('js-motion');
const video = $('#video'), wrap = $('#video-wrap');

// ---------- 등장 애니메이션 (Magic UI "Blur Fade" 느낌) ----------
if (M && !reduce) {
  M.animate('.reveal', { opacity: [0, 1], y: [14, 0], filter: ['blur(6px)', 'blur(0px)'] },
            { duration: .6, delay: M.stagger(.07), ease: [.2, .8, .2, 1] });
}

// ---------- 배경 격자 셀 반짝임 (Magic UI "Animated Grid Pattern") ----------
(function gridCells () {
  const grid = document.querySelector('.bg-grid'); if (!grid || reduce) return;
  for (let i = 0; i < 14; i++) {
    const c = document.createElement('span'); c.className = 'cell'; grid.appendChild(c);
    const relocate = () => { c.style.left = (Math.floor(Math.random() * 40) * 44 + 1) + 'px'; c.style.top = (Math.floor(Math.random() * 22) * 44 + 1) + 'px'; };
    const loop = () => {
      relocate();
      if (M) M.animate(c, { opacity: [0, .9, 0] }, { duration: 3 + Math.random() * 3, ease: 'easeInOut' }).then(loop);
      else { c.style.opacity = .5; setTimeout(loop, 4000); }
    };
    setTimeout(loop, i * 500);
  }
})();

// ---------- 토스트 (alert 대체) ----------
function toast (msg, kind = 'info') {
  const t = document.createElement('div'); t.className = 'toast ' + kind; t.textContent = msg; $('#toasts').appendChild(t);
  if (M) M.animate(t, { opacity: [0, 1], x: [30, 0], scale: [.96, 1] }, { type: 'spring', stiffness: 400, damping: 28 });
  setTimeout(() => {
    if (M) M.animate(t, { opacity: 0, x: 30 }, { duration: .25 }).then(() => t.remove()); else t.remove();
  }, kind === 'err' ? 5000 : 3000);
}

async function post (url, body) {
  const opt = { method: 'POST' };
  if (body !== undefined) { opt.headers = { 'Content-Type': 'application/json' }; opt.body = JSON.stringify(body); }
  const r = await fetch(url, opt), j = await r.json();
  if (!r.ok || j.ok === false) throw new Error(j.error || r.statusText);
  return j;
}

// 버튼 누름 반응 (spring)
document.querySelectorAll('.btn').forEach(b => b.addEventListener('pointerdown', () => {
  if (M && !reduce) M.animate(b, { scale: [.95, 1] }, { type: 'spring', stiffness: 500, damping: 15 });
}));

function busy (on, text = '처리 중') { $('#busy').classList.toggle('show', on); $('#busy-text').textContent = text; }

// ---------- 클릭: 물체 선택 / 놓기 위치 ----------
let placeMode = false;
function setPlaceMode (on) {
  placeMode = on;
  wrap.classList.toggle('place-mode', on);
  $('#place-click').classList.toggle('active', on);
  $('#place-click span').textContent = on ? '취소' : '놓기 위치 클릭';
}
$('#place-click').onclick = () => setPlaceMode(!placeMode);

function ripple (px, py, place) {
  const r = document.createElement('span'); r.className = 'ripple' + (place ? ' place' : '');
  r.style.left = px + 'px'; r.style.top = py + 'px'; wrap.appendChild(r);
  if (M) M.animate(r, { scale: [1, 6], opacity: [1, 0] }, { duration: .7, ease: 'easeOut' }).then(() => r.remove());
  else setTimeout(() => r.remove(), 600);
}

let clickBusy = false;
video.addEventListener('click', async e => {
  if (clickBusy) { toast('이전 클릭을 처리하는 중이에요. 잠시만 기다려 주세요'); return; }
  const rect = video.getBoundingClientRect();
  const x = (e.clientX - rect.left) * video.naturalWidth / rect.width;
  const y = (e.clientY - rect.top) * video.naturalHeight / rect.height;
  ripple(e.clientX - wrap.getBoundingClientRect().left, e.clientY - wrap.getBoundingClientRect().top, placeMode);
  const mode = placeMode ? 'place' : 'select';
  clickBusy = true;
  busy(true, mode === 'place' ? '놓을 위치로 이동 중' : 'SAM2 분할 · FoundationPose 등록 중');
  try {
    const j = await post('/click', { x, y, mode });
    if (mode === 'place') toast('놓기 명령을 보냈어요', 'ok');
    else toast(`${j.object} 선택 · 오차 ${j.error_mm.toFixed(1)}mm / ${j.error_deg.toFixed(1)}°`, 'ok');
    setPlaceMode(false);
  } catch (err) { toast(err.message, 'err'); }
  finally { busy(false); clickBusy = false; }
});

$('#pick').onclick = () => post('/robot/pick', {}).then(() => toast('집기 시작', 'ok')).catch(e => toast(e.message, 'err'));
$('#place').onclick = () => post('/robot/place', {}).then(() => toast('놓기 시작', 'ok')).catch(e => toast(e.message, 'err'));
$('#reset').onclick = () => post('/reset').then(() => toast('리셋했어요')).catch(e => toast(e.message, 'err'));
$('#randomize').onclick = () => post('/scene/randomize').then(() => toast('장면을 랜덤 배치했어요')).catch(e => toast(e.message, 'err'));
$('#cad').onchange = async e => {
  const file = e.target.files[0]; if (!file) return;
  const f = new FormData(); f.append('file', file); busy(true, `${file.name} 변환 중`);
  try {
    const r = await fetch('/cad/upload', { method: 'POST', body: f }), j = await r.json();
    if (!r.ok) throw new Error(j.error); toast(`${j.name} 추가 완료`, 'ok');
  } catch (err) { toast(err.message, 'err'); }
  finally { busy(false); e.target.value = ''; }
};

// ---------- 숫자 티커 (Magic UI "Number Ticker") ----------
function ticker (el, value, digits = 1) {
  if (value == null || !isFinite(value)) { el.textContent = '-'; el.dataset.v = 0; el.className = ''; return; }
  const from = parseFloat(el.dataset.v) || 0; el.dataset.v = value;
  if (M && !reduce && Math.abs(from - value) > 1e-6)
    M.animate(from, value, { duration: .5, ease: 'easeOut', onUpdate: v => { el.textContent = v.toFixed(digits); } });
  else el.textContent = value.toFixed(digits);
}
const grade = (el, v, good, mid) => { el.className = v == null ? '' : v <= good ? 'good' : v <= mid ? 'mid' : 'bad'; };

// ---------- 단계 표시 ----------
const ORDER = ['select', 'register', 'track', 'pick', 'place'];
function stepFrom (s) {
  const ph = s.phase || 'idle';
  if (ph.startsWith('pick')) return 'pick';
  if (ph.startsWith('place')) return 'place';
  if (s.held_object) return 'place';
  if (s.selected_object && s.tracking_state === 'tracking') return 'track';
  if (s.selected_object) return 'register';
  return 'select';
}
function renderSteps (cur) {
  const idx = ORDER.indexOf(cur);
  document.querySelectorAll('.step').forEach((el, i) => { el.classList.toggle('active', i === idx); el.classList.toggle('done', i < idx); });
  document.querySelectorAll('.bar').forEach((el, i) => el.classList.toggle('done', i < idx));
}

// ---------- 로그 (새 항목 슬라이드 인) ----------
let lastLogKey = '';
function renderLogs (logs) {
  const key = logs.map(l => l.time + l.message).join('|'); if (key === lastLogKey) return;
  const prevTop = lastLogKey.split('|')[0]; lastLogKey = key;
  $('#logs').innerHTML = logs.map(l => `<div class="log"><span class="time">${l.time}</span><span>${l.message}</span></div>`).join('');
  const first = $('#logs .log');
  if (first && (logs[0].time + logs[0].message) !== prevTop) {
    first.classList.add('new');
    if (M && !reduce) M.animate(first, { opacity: [0, 1], x: [-12, 0] }, { duration: .35 });
    setTimeout(() => first.classList.remove('new'), 1500);
  }
}

// ---------- 상태 폴링 ----------
async function status () {
  try {
    const s = await fetch('/status').then(r => r.json());
    window.dispatchEvent(new CustomEvent('robot-status', {detail: s}));
    const pill = $('#health-pill'); pill.classList.toggle('ok', !!s.ready); pill.classList.remove('bad');
    $('#health').textContent = s.ready ? (s.state === 'busy' ? '로봇 동작 중' : '연결됨') : '시작 중';
    $('#state').textContent = s.state || '-';
    $('#phase').textContent = s.phase || '-';
    $('#selected').textContent = s.selected_object || '-';
    $('#tracking').innerHTML = !s.selected_object ? '-' : s.tracking_state === 'paused'
      ? '<span class="badge warn">일시정지 (로봇 동작/집은 상태)</span>' : '<span class="badge ok">추적 중</span>';
    $('#fps').textContent = `${(s.fps || 0).toFixed ? (s.fps || 0).toFixed(1) : s.fps} FPS`;
    $('#hud-fps').textContent = `${Number(s.fps || 0).toFixed(1)} FPS`;
    const hp = $('#hud-phase'); hp.textContent = s.phase || 'idle'; hp.classList.toggle('live', (s.phase || 'idle') !== 'idle');
    $('#perception').textContent = (s.perception === 'fp' ? 'SAM2 + FoundationPose' : 'stub') + (s.perception_warning ? ' · ' + s.perception_warning : '');

    const p = s.pose;
    ticker($('#err-mm'), p ? p.error_mm : null, 1); grade($('#err-mm'), p ? p.error_mm : null, 5, 15);
    ticker($('#err-deg'), p ? p.error_deg : null, 1); grade($('#err-deg'), p ? p.error_deg : null, 3, 10);
    const iou = p && p.mask_iou != null ? p.mask_iou * 100 : null;
    ticker($('#iou'), iou, 1);
    const ring = $('#iou-ring'); ring.style.strokeDashoffset = 113.1 * (1 - (iou || 0) / 100);
    ring.style.stroke = iou == null ? 'var(--accent)' : iou > 80 ? 'var(--ok)' : iou > 50 ? 'var(--warn)' : 'var(--bad)';
    ticker($('#track-fps'), p ? (p.tracking_fps || 0) : null, 1);
    const sam = p ? p.sam_ms : null, reg = p ? p.register_ms : null;
    $('#t-sam').style.width = sam ? Math.min(100, sam / 30) + '%' : '0'; $('#t-sam-v').textContent = sam ? `${sam.toFixed(0)} ms` : '-';
    $('#t-reg').style.width = reg ? Math.min(100, reg / 50) + '%' : '0'; $('#t-reg-v').textContent = reg ? `${(reg / 1000).toFixed(2)} s` : '-';

    if (s.gpu) {
      $('#gpu').textContent = `${s.gpu.util}% · ${s.gpu.memory_used_mb}/${s.gpu.memory_total_mb} MB`;
      $('#gpu-mem').style.width = (100 * s.gpu.memory_used_mb / s.gpu.memory_total_mb) + '%';
    } else $('#gpu').textContent = 'N/A';

    const robotBusy = s.state === 'busy';
    ['#pick', '#place', '#place-click', '#reset', '#randomize'].forEach(id => { $(id).disabled = robotBusy; });
    renderSteps(stepFrom(s));
    renderLogs(s.logs || []);
    if (s.error && s.error !== window.__lastErr) { window.__lastErr = s.error; toast(s.error, 'err'); }
  } catch (e) {
    $('#health').textContent = '연결 끊김'; $('#health-pill').classList.add('bad');
  }
}
setInterval(status, 333); status();

// ---- 스트림 자동 재연결: 서버 재시작/일시 끊김 뒤 영상이 깨진 아이콘으로 남지 않게 ----
function reconnectStream (img) {
  if (!img || img.dataset.reconnect) return;
  img.dataset.reconnect = '1';
  img.addEventListener('error', () => {
    const base = (img.getAttribute('src') || '').split('&_r=')[0].split('?_r=')[0];
    if (!base) return;
    setTimeout(() => { img.src = base + (base.includes('?') ? '&' : '?') + '_r=' + Date.now(); }, 1500);
  });
}
document.querySelectorAll('img').forEach(reconnectStream);
new MutationObserver(() => document.querySelectorAll('img').forEach(reconnectStream))
  .observe(document.body, { childList: true, subtree: true });
