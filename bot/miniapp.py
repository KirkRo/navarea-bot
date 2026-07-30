"""
Telegram Mini App -- одностраничное приложение, которое открывается
кнопкой рядом с полем ввода в чате с ботом.

Всё в одном файле специально: Mini App отдаётся тем же скромным
HTTP-сервером, что и остальное (bot/webapp.py), без сборки, без
node_modules и без отдельного хостинга фронтенда. Единственная внешняя
зависимость -- Leaflet с CDN для карты.

Данные берутся из /api/* того же сервера. Последний успешный ответ
кладётся в localStorage, поэтому при пропадании связи (обычное дело в
рейсе) приложение открывается и показывает последние известные данные
с пометкой, что они не свежие.
"""

MINI_APP_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>NAVAREA Monitor</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
:root{
  --bg: var(--tg-theme-bg-color, #0c1c2e);
  --card: var(--tg-theme-secondary-bg-color, #14293f);
  --text: var(--tg-theme-text-color, #f2f6fa);
  --muted: var(--tg-theme-hint-color, #8fa6bd);
  --accent: var(--tg-theme-button-color, #e8a33e);
  --accent-text: var(--tg-theme-button-text-color, #10243a);
  --link: var(--tg-theme-link-color, #6fb3f0);
  --border: rgba(143,166,189,.22);
  --danger: #e8664a;
  --ok: #43c47f;
  --radius: 14px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{
  margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  font-size:15px;line-height:1.45;padding-bottom:76px;
}
h1,h2,h3{margin:0;font-weight:650}
a{color:var(--link)}
.wrap{padding:14px;max-width:900px;margin:0 auto}

/* Шапка */
.top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px}
.top h1{font-size:17px;letter-spacing:.2px}
.sync{font-size:11px;color:var(--muted);display:flex;align-items:center;gap:6px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--ok);flex:none}
.dot.stale{background:var(--danger)}
.iconbtn{
  background:var(--card);border:1px solid var(--border);color:var(--text);
  border-radius:10px;padding:7px 10px;font-size:14px;cursor:pointer;
}
.iconbtn:active{transform:scale(.95)}

/* Статистика */
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:16px}
@media(min-width:560px){.stats{grid-template-columns:repeat(4,1fr)}}
.stat{
  background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:13px 14px;position:relative;overflow:hidden;
}
.stat .num{font-size:26px;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}
.stat .lbl{font-size:11px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:.6px}
.stat.hl .num{color:var(--accent)}
.stat::after{content:'';position:absolute;right:-14px;top:-14px;width:52px;height:52px;
  border-radius:50%;background:var(--accent);opacity:.06}

/* Панель сервера */
.server{
  background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:12px 14px;margin-bottom:16px;font-size:13px;
}
.server .row{display:flex;justify-content:space-between;padding:3px 0;color:var(--muted)}
.server .row b{color:var(--text);font-weight:600}

/* Поиск и фильтры */
.search{
  width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);
  border-radius:12px;padding:11px 13px;font-size:15px;margin-bottom:10px;outline:none;
}
.search:focus{border-color:var(--accent)}
.chips{display:flex;gap:7px;overflow-x:auto;padding-bottom:8px;margin-bottom:6px;scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chip{
  background:var(--card);border:1px solid var(--border);color:var(--muted);
  border-radius:20px;padding:6px 12px;font-size:12.5px;white-space:nowrap;cursor:pointer;flex:none;
}
.chip.on{background:var(--accent);color:var(--accent-text);border-color:var(--accent);font-weight:600}

/* Карточки районов */
.cards{display:grid;gap:9px}
@media(min-width:640px){.cards{grid-template-columns:repeat(2,1fr)}}
.card{
  background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:12px 13px;display:flex;align-items:center;gap:11px;cursor:pointer;
  transition:border-color .15s;
}
.card:active{border-color:var(--accent)}
.card .code{
  background:rgba(232,163,62,.14);color:var(--accent);font-weight:700;font-size:13px;
  border-radius:9px;padding:8px 9px;min-width:56px;text-align:center;flex:none;
}
.card .mid{flex:1;min-width:0}
.card .nm{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card .sub{font-size:11.5px;color:var(--muted);margin-top:2px}
.card .cnt{font-size:19px;font-weight:700;font-variant-numeric:tabular-nums;flex:none}
.star{background:none;border:none;font-size:17px;cursor:pointer;padding:2px 4px;opacity:.35;flex:none}
.star.on{opacity:1}
.badge{
  background:var(--danger);color:#fff;font-size:9.5px;font-weight:700;border-radius:20px;
  padding:2px 6px;margin-left:6px;vertical-align:middle;letter-spacing:.4px;
}

/* Список предупреждений */
.warn{
  background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:12px 13px;margin-bottom:9px;
}
.warn .hd{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap}
.warn .tag{background:rgba(232,163,62,.14);color:var(--accent);font-size:11px;font-weight:700;
  border-radius:6px;padding:2px 7px}
.warn .reg{font-size:11.5px;color:var(--muted)}
.warn .txt{font-size:13px;white-space:pre-wrap;word-break:break-word;color:var(--text);opacity:.92}
.warn .txt.clip{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.warn .acts{display:flex;gap:8px;margin-top:9px}
.btn{
  background:var(--accent);color:var(--accent-text);border:none;border-radius:9px;
  padding:7px 13px;font-size:12.5px;font-weight:600;cursor:pointer;
}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}
.dist{font-size:11px;color:var(--accent);font-weight:600}

/* Карта */
#map{height:64vh;border-radius:var(--radius);border:1px solid var(--border);margin-bottom:12px}
#vmap{height:38vh;border-radius:var(--radius);border:1px solid var(--border);margin:12px 0}

/* Рейс */
.field{margin-bottom:11px;position:relative}
.field label{display:block;font-size:11.5px;color:var(--muted);margin-bottom:5px;
  text-transform:uppercase;letter-spacing:.5px}
.sugg{
  position:absolute;top:100%;left:0;right:0;background:var(--card);border:1px solid var(--border);
  border-radius:11px;margin-top:4px;z-index:900;max-height:210px;overflow-y:auto;display:none;
}
.sugg.on{display:block}
.sugg div{padding:10px 13px;font-size:13.5px;cursor:pointer;border-bottom:1px solid var(--border)}
.sugg div:last-child{border-bottom:none}
.sugg div:active{background:rgba(232,163,62,.12)}
.voyhead{
  background:linear-gradient(135deg,rgba(232,163,62,.16),rgba(232,163,62,.04));
  border:1px solid rgba(232,163,62,.3);border-radius:var(--radius);padding:14px;margin:12px 0;
}
.voyhead .big{font-size:16px;font-weight:650;margin-bottom:3px}
.voyhead .sm{font-size:12px;color:var(--muted)}

/* Табы */
.tabs{
  position:fixed;bottom:0;left:0;right:0;background:var(--card);
  border-top:1px solid var(--border);display:flex;z-index:1000;
  padding-bottom:env(safe-area-inset-bottom);
}
.tab{
  flex:1;padding:9px 4px 8px;text-align:center;color:var(--muted);
  font-size:10.5px;cursor:pointer;border:none;background:none;
}
.tab .ic{display:block;font-size:19px;margin-bottom:2px}
.tab.on{color:var(--accent)}

/* Скелетоны и пустые состояния */
.sk{background:var(--card);border-radius:var(--radius);position:relative;overflow:hidden;
  border:1px solid var(--border)}
.sk::after{content:'';position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent);
  animation:sh 1.4s infinite}
@keyframes sh{100%{transform:translateX(100%)}}
.sk.stat{height:76px}.sk.card{height:64px;margin-bottom:9px}
.empty{text-align:center;padding:34px 18px;color:var(--muted);font-size:13.5px}
.empty .ic{font-size:34px;display:block;margin-bottom:9px;opacity:.55}
.offline{
  background:rgba(232,102,74,.14);border:1px solid rgba(232,102,74,.4);color:var(--text);
  border-radius:11px;padding:9px 12px;font-size:12.5px;margin-bottom:12px;display:none;
}
.offline.on{display:block}
.hidden{display:none!important}
.fade{animation:fi .25s ease}
@keyframes fi{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
</style>
</head>
<body>

<div class="wrap">
  <div class="top">
    <h1>🛰 NAVAREA Monitor</h1>
    <div style="display:flex;align-items:center;gap:9px">
      <span class="sync" id="sync"><span class="dot" id="dot"></span><span id="synctxt">…</span></span>
      <button class="iconbtn" id="refresh">↻</button>
    </div>
  </div>

  <div class="offline" id="offline">📡 Нет связи. Показаны последние сохранённые данные.</div>

  <!-- ПАНЕЛЬ -->
  <section id="v-dash">
    <div class="stats" id="stats">
      <div class="sk stat"></div><div class="sk stat"></div>
      <div class="sk stat"></div><div class="sk stat"></div>
    </div>
    <div class="server" id="server"></div>
    <h3 style="font-size:13px;color:var(--muted);margin:0 0 9px;text-transform:uppercase;letter-spacing:.6px">Избранные районы</h3>
    <div class="cards" id="favcards"></div>
  </section>

  <!-- РАЙОНЫ -->
  <section id="v-areas" class="hidden">
    <input class="search" id="q" placeholder="Поиск: номер, координаты, текст…">
    <div class="chips" id="chips">
      <button class="chip on" data-f="all">Все районы</button>
      <button class="chip" data-f="fav">⭐ Избранные</button>
      <button class="chip" data-f="active">С предупреждениями</button>
      <button class="chip" data-f="new">🔔 Новые сегодня</button>
    </div>
    <div class="chips">
      <button class="chip on" data-s="count">По количеству</button>
      <button class="chip" data-s="new">По новизне</button>
      <button class="chip" data-s="code">По номеру</button>
    </div>
    <div id="arealist"><div class="sk card"></div><div class="sk card"></div><div class="sk card"></div></div>
  </section>

  <!-- КАРТА -->
  <section id="v-map" class="hidden">
    <div class="chips" id="mapchips"></div>
    <div id="map"></div>
    <div class="empty" id="maphint" style="padding:12px">Нажми на область, чтобы увидеть текст предупреждения.</div>
  </section>

  <!-- РЕЙС -->
  <section id="v-voy" class="hidden">
    <div class="field">
      <label>Порт отправления</label>
      <input class="search" id="pfrom" placeholder="Например Constanta" autocomplete="off" style="margin:0">
      <div class="sugg" id="sfrom"></div>
    </div>
    <div class="field">
      <label>Порт прибытия</label>
      <input class="search" id="pto" placeholder="Например Santos" autocomplete="off" style="margin:0">
      <div class="sugg" id="sto"></div>
    </div>
    <div class="field">
      <label>Ширина коридора</label>
      <div class="chips" id="corr">
        <button class="chip" data-c="50">50 миль</button>
        <button class="chip on" data-c="150">150 миль</button>
        <button class="chip" data-c="300">300 миль</button>
        <button class="chip" data-c="500">500 миль</button>
      </div>
    </div>
    <button class="btn" id="govoy" style="width:100%;padding:12px;font-size:14px">Проложить и проверить</button>
    <div id="voyout"></div>
  </section>
</div>

<nav class="tabs">
  <button class="tab on" data-v="dash"><span class="ic">📊</span>Панель</button>
  <button class="tab" data-v="areas"><span class="ic">🌍</span>Районы</button>
  <button class="tab" data-v="map"><span class="ic">🗺</span>Карта</button>
  <button class="tab" data-v="voy"><span class="ic">🚢</span>Рейс</button>
</nav>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const TG = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
if (TG) { TG.ready(); TG.expand(); }
const INIT = TG ? (TG.initData || '') : '';
const CACHE_KEY = 'navarea_cache_v1';

let S = { stats:null, favs:[], warnings:[], filter:'all', sort:'count', q:'', corridor:150, view:'dash', offline:false };
let map=null, vmap=null, mapLayers=[], mapArea='all';

/* ---------- вспомогательное ---------- */
const $ = s => document.querySelector(s);
const esc = s => String(s==null?'':s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const haptic = t => { try{ TG && TG.HapticFeedback.impactOccurred(t||'light'); }catch(e){} };

function saveCache(){
  try{ localStorage.setItem(CACHE_KEY, JSON.stringify({stats:S.stats, warnings:S.warnings, favs:S.favs, at:Date.now()})); }catch(e){}
}
function loadCache(){
  try{
    const c = JSON.parse(localStorage.getItem(CACHE_KEY)||'null');
    if(c && c.stats){ S.stats=c.stats; S.warnings=c.warnings||[]; S.favs=c.favs||[]; return c.at; }
  }catch(e){}
  return null;
}
async function api(path){
  const sep = path.includes('?') ? '&' : '?';
  const r = await fetch(path + sep + 'initData=' + encodeURIComponent(INIT));
  if(!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}
function ago(iso){
  if(!iso) return 'нет данных';
  const d = (Date.now() - new Date(iso).getTime())/1000;
  if(d<60) return 'только что';
  if(d<3600) return Math.floor(d/60)+' мин назад';
  if(d<86400) return Math.floor(d/3600)+' ч назад';
  return Math.floor(d/86400)+' дн назад';
}

/* ---------- загрузка ---------- */
async function load(showSpinner){
  if(showSpinner) $('#refresh').textContent='⏳';
  try{
    const [st, wr] = await Promise.all([ api('/api/stats'), api('/api/warnings?limit=500') ]);
    S.stats = st; S.warnings = wr.results||[]; S.offline=false;
    try{ const f = await api('/api/favorites'); if(!f.error) S.favs = f.favorites||[]; }catch(e){}
    saveCache();
  }catch(e){
    S.offline = true;
  }
  $('#offline').classList.toggle('on', S.offline);
  $('#refresh').textContent='↻';
  render();
}

/* ---------- отрисовка ---------- */
function render(){ renderDash(); renderAreas(); renderMapChips(); }

function renderDash(){
  if(!S.stats) return;
  const t = S.stats.totals;
  $('#stats').innerHTML = `
    <div class="stat hl fade"><div class="num">${t.in_force}</div><div class="lbl">Действует</div></div>
    <div class="stat fade"><div class="num">${t.added_today}</div><div class="lbl">Новых сегодня</div></div>
    <div class="stat fade"><div class="num">${t.added_week}</div><div class="lbl">За 7 дней</div></div>
    <div class="stat fade"><div class="num">${t.archived}</div><div class="lbl">В архиве</div></div>`;

  const sv = S.stats.server||{};
  const h = Math.floor((sv.uptime_seconds||0)/3600), m = Math.floor(((sv.uptime_seconds||0)%3600)/60);
  $('#server').innerHTML = `
    <div class="row"><span>Статус сервера</span><b style="color:var(--ok)">${S.offline?'нет связи':'● работает'}</b></div>
    <div class="row"><span>Последнее предупреждение</span><b>${ago(S.stats.last_update)}</b></div>
    <div class="row"><span>Синхронизация</span><b>${S.offline?'—':'только что'}</b></div>
    <div class="row"><span>Аптайм</span><b>${h} ч ${m} мин</b></div>
    <div class="row"><span>Районов на связи</span><b>${t.areas_count}</b></div>`;

  $('#dot').className = 'dot' + (S.offline?' stale':'');
  $('#synctxt').textContent = S.offline ? 'офлайн' : 'на связи';

  const favAreas = (S.stats.areas||[]).filter(a=>S.favs.includes(a.code));
  $('#favcards').innerHTML = favAreas.length
    ? favAreas.map(cardHtml).join('')
    : '<div class="empty"><span class="ic">⭐</span>Отметь районы звёздочкой во вкладке «Районы», чтобы они были здесь.</div>';
  bindCards();
}

function cardHtml(a){
  const fav = S.favs.includes(a.code);
  const isNew = a.added_today>0;
  return `<div class="card fade" data-code="${a.code}">
    <div class="code">${esc(a.code)}</div>
    <div class="mid">
      <div class="nm">${esc(a.name)}${isNew?`<span class="badge">NEW ${a.added_today}</span>`:''}</div>
      <div class="sub">${a.added_week} за неделю · обновлён ${ago(a.last_update)}</div>
    </div>
    <div class="cnt">${a.in_force}</div>
    <button class="star ${fav?'on':''}" data-fav="${a.code}">${fav?'★':'☆'}</button>
  </div>`;
}

function renderAreas(){
  if(!S.stats) return;
  let list = (S.stats.areas||[]).slice();

  if(S.filter==='fav') list = list.filter(a=>S.favs.includes(a.code));
  if(S.filter==='active') list = list.filter(a=>a.in_force>0);
  if(S.filter==='new') list = list.filter(a=>a.added_today>0);

  if(S.q){
    const q = S.q.toLowerCase();
    const hits = S.warnings.filter(w =>
      (w.text||'').toLowerCase().includes(q) ||
      (w.msg_number||'').toLowerCase().includes(q) ||
      (w.region||'').toLowerCase().includes(q));
    $('#arealist').innerHTML = hits.length
      ? hits.slice(0,60).map(warnHtml).join('')
      : '<div class="empty"><span class="ic">🔍</span>Ничего не нашлось. Попробуй номер, часть текста или координаты.</div>';
    bindWarns();
    return;
  }

  if(S.sort==='count') list.sort((a,b)=>b.in_force-a.in_force);
  if(S.sort==='new') list.sort((a,b)=>b.added_today-a.added_today || b.added_week-a.added_week);
  if(S.sort==='code') list.sort((a,b)=>a.code.localeCompare(b.code,undefined,{numeric:true}));

  $('#arealist').innerHTML = list.length
    ? `<div class="cards">${list.map(cardHtml).join('')}</div>`
    : '<div class="empty"><span class="ic">🌍</span>Под этот фильтр районов нет.</div>';
  bindCards();
}

function warnHtml(w){
  const mapBtn = (w.coords&&w.coords.length)
    ? `<button class="btn" data-map="${w.id}">🗺 На карте (${w.coords.length})</button>` : '';
  return `<div class="warn fade" data-wid="${w.id}">
    <div class="hd">
      <span class="tag">${esc(w.area_code)} №${esc(w.msg_number||'—')}</span>
      ${w.region?`<span class="reg">${esc(w.region)}</span>`:''}
      ${w.distance_nm!==undefined?`<span class="dist">${w.distance_nm} миль от курса</span>`:''}
    </div>
    <div class="txt clip" data-txt>${esc(w.text)}</div>
    <div class="acts">${mapBtn}<button class="btn ghost" data-more>Показать целиком</button></div>
  </div>`;
}

function bindCards(){
  document.querySelectorAll('[data-fav]').forEach(b=>b.onclick=async ev=>{
    ev.stopPropagation(); haptic();
    const code = b.dataset.fav;
    S.favs = S.favs.includes(code) ? S.favs.filter(c=>c!==code) : S.favs.concat([code]);
    render(); saveCache();
    try{ await api('/api/favorites?toggle='+encodeURIComponent(code)); }catch(e){}
  });
  document.querySelectorAll('.card[data-code]').forEach(c=>c.onclick=()=>{
    haptic(); S.q=''; $('#q').value='';
    switchView('areas');
    const code = c.dataset.code;
    const hits = S.warnings.filter(w=>w.area_code===code);
    $('#arealist').innerHTML = hits.length
      ? `<button class="chip on" style="margin-bottom:10px" onclick="renderAreas()">← Все районы</button>` + hits.map(warnHtml).join('')
      : '<div class="empty"><span class="ic">✅</span>По этому району сейчас нет действующих предупреждений.</div>';
    bindWarns();
  });
}

function bindWarns(){
  document.querySelectorAll('[data-more]').forEach(b=>b.onclick=()=>{
    const t = b.closest('.warn').querySelector('[data-txt]');
    t.classList.toggle('clip');
    b.textContent = t.classList.contains('clip') ? 'Показать целиком' : 'Свернуть';
  });
  document.querySelectorAll('[data-map]').forEach(b=>b.onclick=()=>{
    haptic(); const w = S.warnings.find(x=>String(x.id)===b.dataset.map);
    if(w) { switchView('map'); setTimeout(()=>focusWarning(w), 60); }
  });
}

/* ---------- карта ---------- */
function initMap(){
  if(map) return;
  map = L.map('map').setView([30,0],2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap'}).addTo(map);
  drawMap();
}
function renderMapChips(){
  if(!S.stats) return;
  const codes = (S.stats.areas||[]).filter(a=>a.in_force>0).map(a=>a.code);
  $('#mapchips').innerHTML = ['all'].concat(codes).map(c=>
    `<button class="chip ${mapArea===c?'on':''}" data-m="${c}">${c==='all'?'Все':c}</button>`).join('');
  document.querySelectorAll('[data-m]').forEach(b=>b.onclick=()=>{
    mapArea=b.dataset.m; renderMapChips(); drawMap(); haptic();
  });
}
function drawMap(){
  if(!map) return;
  mapLayers.forEach(l=>map.removeLayer(l)); mapLayers=[];
  const list = S.warnings.filter(w=>w.coords&&w.coords.length&&(mapArea==='all'||w.area_code===mapArea));
  list.forEach(w=>{
    const pts = w.coords;
    const popup = `<b>${esc(w.area_code)} №${esc(w.msg_number||'—')}</b><br>${esc((w.text||'').slice(0,260))}…`;
    let layer;
    if(pts.length===1) layer = L.circleMarker(pts[0],{radius:7,color:'#e8a33e',fillOpacity:.85});
    else if(pts.length===2) layer = L.polyline(pts,{color:'#e8a33e',weight:3});
    else layer = L.polygon(pts,{color:'#e8a33e',weight:2,fillOpacity:.13});
    layer.bindPopup(popup).addTo(map); mapLayers.push(layer);
  });
  $('#maphint').textContent = list.length
    ? `На карте ${list.length} предупреждений с координатами. Нажми на область, чтобы прочитать текст.`
    : 'Нет предупреждений с координатами для этого выбора.';
}
function focusWarning(w){
  initMap(); mapArea='all'; renderMapChips(); drawMap();
  const pts=w.coords;
  if(pts.length===1) map.setView(pts[0],8);
  else map.fitBounds(L.latLngBounds(pts),{padding:[40,40]});
}

/* ---------- рейс ---------- */
function setupPortInput(inputId, suggId){
  const inp=$(inputId), sug=$(suggId); let timer=null;
  inp.oninput=()=>{
    clearTimeout(timer);
    const v=inp.value.trim();
    if(v.length<2){ sug.classList.remove('on'); return; }
    timer=setTimeout(async()=>{
      try{
        const r=await api('/api/ports?q='+encodeURIComponent(v));
        sug.innerHTML=(r.results||[]).map(p=>`<div data-p="${esc(p.name)}">${esc(p.label)}</div>`).join('');
        sug.classList.toggle('on',(r.results||[]).length>0);
        sug.querySelectorAll('[data-p]').forEach(d=>d.onclick=()=>{
          inp.value=d.dataset.p; sug.classList.remove('on'); haptic();
        });
      }catch(e){ sug.classList.remove('on'); }
    },220);
  };
  inp.onblur=()=>setTimeout(()=>sug.classList.remove('on'),180);
}

async function runVoyage(){
  const from=$('#pfrom').value.trim(), to=$('#pto').value.trim();
  if(!from||!to){ $('#voyout').innerHTML='<div class="empty">Укажи оба порта.</div>'; return; }
  $('#voyout').innerHTML='<div class="sk card"></div><div class="sk card"></div>';
  haptic('medium');
  try{
    const r=await api(`/api/voyage?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&corridor=${S.corridor}`);
    if(r.error){ $('#voyout').innerHTML=`<div class="empty"><span class="ic">⚠️</span>${esc(r.error)}</div>`; return; }
    const word = r.count===1?'предупреждение':(r.count>=2&&r.count<=4?'предупреждения':'предупреждений');
    $('#voyout').innerHTML=`
      <div class="voyhead fade">
        <div class="big">🚢 На вашем маршруте найдено ${r.count} активных ${word}.</div>
        <div class="sm">${esc(r.from.label)} → ${esc(r.to.label)} · ${r.distance_nm} миль · коридор ±${r.corridor_nm} миль</div>
      </div>
      <div id="vmap"></div>
      ${r.results.length ? r.results.map(warnHtml).join('') :
        '<div class="empty"><span class="ic">✅</span>По этому маршруту действующих предупреждений с координатами нет.</div>'}`;
    bindWarns();
    setTimeout(()=>drawVoyMap(r),60);
  }catch(e){
    $('#voyout').innerHTML='<div class="empty"><span class="ic">📡</span>Нет связи с сервером. Попробуй позже.</div>';
  }
}
function drawVoyMap(r){
  if(vmap){ vmap.remove(); vmap=null; }
  vmap=L.map('vmap');
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OSM'}).addTo(vmap);
  const line=L.polyline(r.route,{color:'#6fb3f0',weight:3,dashArray:'6 6'}).addTo(vmap);
  L.marker([r.from.lat,r.from.lon]).bindPopup(esc(r.from.label)).addTo(vmap);
  L.marker([r.to.lat,r.to.lon]).bindPopup(esc(r.to.label)).addTo(vmap);
  r.results.forEach(w=>{
    const pts=w.coords; if(!pts||!pts.length) return;
    const l = pts.length<3 ? L.circleMarker(pts[0],{radius:6,color:'#e8a33e',fillOpacity:.85})
                           : L.polygon(pts,{color:'#e8a33e',weight:2,fillOpacity:.15});
    l.bindPopup(`<b>${esc(w.area_code)} №${esc(w.msg_number||'—')}</b><br>${w.distance_nm} миль от курса`).addTo(vmap);
  });
  vmap.fitBounds(line.getBounds(),{padding:[25,25]});
}

/* ---------- навигация ---------- */
function switchView(v){
  S.view=v;
  ['dash','areas','map','voy'].forEach(x=>$('#v-'+x).classList.toggle('hidden',x!==v));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.v===v));
  if(v==='map'){ setTimeout(()=>{ initMap(); map.invalidateSize(); drawMap(); },50); }
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{ haptic(); switchView(t.dataset.v); });
document.querySelectorAll('#chips .chip').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('#chips .chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); S.filter=c.dataset.f; renderAreas(); haptic();
});
document.querySelectorAll('[data-s]').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('[data-s]').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); S.sort=c.dataset.s; renderAreas(); haptic();
});
document.querySelectorAll('#corr .chip').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('#corr .chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); S.corridor=+c.dataset.c; haptic();
});
let qt=null;
$('#q').oninput=e=>{ clearTimeout(qt); qt=setTimeout(()=>{ S.q=e.target.value.trim(); renderAreas(); },230); };
$('#refresh').onclick=()=>{ haptic(); load(true); };
$('#govoy').onclick=runVoyage;
setupPortInput('#pfrom','#sfrom');
setupPortInput('#pto','#sto');

/* ---------- старт ---------- */
const cachedAt = loadCache();
if(cachedAt){ render(); }
load(false);
setInterval(()=>{ if(S.view==='dash'||S.view==='areas') load(false); }, 120000);
</script>
</body>
</html>
"""
