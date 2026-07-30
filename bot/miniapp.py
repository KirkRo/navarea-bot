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
  --bg: var(--tg-theme-bg-color, #08192b);
  --card: var(--tg-theme-secondary-bg-color, #11293f);
  --text: var(--tg-theme-text-color, #eef4fa);
  --muted: var(--tg-theme-hint-color, #85a0ba);
  --brass: #e8a33e;
  --brass-dim: rgba(232,163,62,.14);
  --accent-text: var(--tg-theme-button-text-color, #0b1e30);
  --link: var(--tg-theme-link-color, #6fb3f0);
  --border: rgba(133,160,186,.2);
  --danger: #e8664a;
  --ok: #43c47f;
  --r: 15px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{overscroll-behavior-y:contain}
body{
  margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  font-size:15px;line-height:1.45;padding-bottom:80px;
  background-image:
    linear-gradient(rgba(133,160,186,.045) 1px,transparent 1px),
    linear-gradient(90deg,rgba(133,160,186,.045) 1px,transparent 1px);
  background-size:44px 44px;
}
h1,h3{margin:0;font-weight:650}
.wrap{padding:14px;max-width:920px;margin:0 auto}
.mono{font-variant-numeric:tabular-nums;font-feature-settings:'tnum'}

/* Шапка */
.top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:15px}
.brand{display:flex;align-items:center;gap:9px;min-width:0}
.beacon{width:26px;height:26px;flex:none;position:relative}
.beacon i{
  position:absolute;inset:0;border-radius:50%;border:2px solid var(--brass);
  opacity:0;animation:ping 2.6s ease-out infinite;
}
.beacon i:nth-child(2){animation-delay:.85s}
.beacon i:nth-child(3){animation-delay:1.7s}
.beacon b{
  position:absolute;inset:8px;border-radius:50%;background:var(--brass);
  box-shadow:0 0 12px rgba(232,163,62,.8);
}
@keyframes ping{0%{transform:scale(.35);opacity:.9}80%{transform:scale(1.15);opacity:0}100%{opacity:0}}
.brand h1{font-size:16.5px;letter-spacing:.3px;white-space:nowrap}
.hd-right{display:flex;align-items:center;gap:8px;flex:none}
.pill{
  display:flex;align-items:center;gap:6px;font-size:10.5px;color:var(--muted);
  background:var(--card);border:1px solid var(--border);border-radius:20px;padding:5px 10px;
  text-transform:uppercase;letter-spacing:.5px;
}
.dot{width:6px;height:6px;border-radius:50%;background:var(--ok);flex:none;
  box-shadow:0 0 0 0 rgba(67,196,127,.6);animation:pulse 2.4s infinite}
.dot.stale{background:var(--danger);animation:none}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(67,196,127,.5)}70%{box-shadow:0 0 0 7px rgba(67,196,127,0)}100%{box-shadow:0 0 0 0 rgba(67,196,127,0)}}
.iconbtn{
  background:var(--card);border:1px solid var(--border);color:var(--text);
  border-radius:11px;width:36px;height:34px;font-size:15px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;transition:transform .18s,border-color .18s;
}
.iconbtn:active{transform:scale(.9);border-color:var(--brass)}
.iconbtn.spin{animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* Статистика */
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:15px}
@media(min-width:600px){.stats{grid-template-columns:repeat(4,1fr)}}
.stat{
  background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:13px 14px;position:relative;overflow:hidden;
}
.stat::before{
  content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--muted);opacity:.4;
}
.stat.hl::before{background:var(--brass);opacity:1}
.stat.new::before{background:var(--danger);opacity:1}
.stat .num{font-size:27px;font-weight:700;line-height:1.05}
.stat.hl .num{color:var(--brass)}
.stat .lbl{font-size:10px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:.7px}

/* Панель сервера */
.panel{
  background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:12px 14px;margin-bottom:15px;font-size:13px;
}
.panel .row{display:flex;justify-content:space-between;align-items:center;padding:4px 0;color:var(--muted)}
.panel .row+.row{border-top:1px solid rgba(133,160,186,.08)}
.panel .row b{color:var(--text);font-weight:600}
.sec{font-size:11px;color:var(--muted);margin:0 0 9px;text-transform:uppercase;letter-spacing:.8px;
  display:flex;align-items:center;gap:8px}
.sec::after{content:'';flex:1;height:1px;background:var(--border)}

/* Поиск, чипы */
.search{
  width:100%;background:var(--card);border:1px solid var(--border);color:var(--text);
  border-radius:12px;padding:11px 13px;font-size:15px;margin-bottom:10px;outline:none;
  transition:border-color .2s,box-shadow .2s;
}
.search:focus{border-color:var(--brass);box-shadow:0 0 0 3px rgba(232,163,62,.12)}
.chips{display:flex;gap:7px;overflow-x:auto;padding-bottom:8px;margin-bottom:4px;scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chip{
  background:var(--card);border:1px solid var(--border);color:var(--muted);
  border-radius:20px;padding:6px 13px;font-size:12.5px;white-space:nowrap;cursor:pointer;flex:none;
  transition:all .18s;
}
.chip:active{transform:scale(.94)}
.chip.on{background:var(--brass);color:var(--accent-text);border-color:var(--brass);font-weight:600}

/* Карточки районов */
.cards{display:grid;gap:9px}
@media(min-width:660px){.cards{grid-template-columns:repeat(2,1fr)}}
.card{
  background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:12px 13px;display:flex;align-items:center;gap:11px;cursor:pointer;
  transition:border-color .18s,transform .18s;position:relative;overflow:hidden;
}
.card:active{transform:scale(.985);border-color:var(--brass)}
.card .code{
  background:var(--brass-dim);color:var(--brass);font-weight:700;font-size:13px;
  border-radius:10px;padding:9px 8px;min-width:58px;text-align:center;flex:none;
  border:1px solid rgba(232,163,62,.22);
}
.card .mid{flex:1;min-width:0}
.card .nm{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card .sub{font-size:11.5px;color:var(--muted);margin-top:2px}
.card .cnt{font-size:20px;font-weight:700;flex:none}
.star{background:none;border:none;font-size:18px;cursor:pointer;padding:2px 3px;opacity:.3;flex:none;
  transition:opacity .2s,transform .2s}
.star.on{opacity:1;color:var(--brass)}
.star:active{transform:scale(1.35)}
.badge{
  background:var(--danger);color:#fff;font-size:9px;font-weight:700;border-radius:20px;
  padding:2px 6px;margin-left:6px;letter-spacing:.4px;vertical-align:1px;
  animation:blink 2.2s ease-in-out infinite;
}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.55}}

/* Предупреждения */
.warn{
  background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:12px 13px;margin-bottom:9px;border-left:3px solid var(--brass);
}
.warn .hd{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap}
.warn .tag{background:var(--brass-dim);color:var(--brass);font-size:11px;font-weight:700;
  border-radius:6px;padding:2px 8px}
.warn .reg{font-size:11.5px;color:var(--muted)}
.warn .txt{font-size:13px;white-space:pre-wrap;word-break:break-word;opacity:.92}
.warn .txt.clip{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.warn .acts{display:flex;gap:8px;margin-top:9px;flex-wrap:wrap}
.btn{
  background:var(--brass);color:var(--accent-text);border:none;border-radius:10px;
  padding:8px 14px;font-size:12.5px;font-weight:650;cursor:pointer;transition:transform .15s,opacity .15s;
}
.btn:active{transform:scale(.95);opacity:.85}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}
.dist{font-size:11px;color:var(--brass);font-weight:650}

/* Карта */
#map{height:60vh;border-radius:var(--r);border:1px solid var(--border);overflow:hidden}
#vmap{height:38vh;border-radius:var(--r);border:1px solid var(--border);margin:12px 0}
.leaflet-container{background:#0a1c2e}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:11px;color:var(--muted);margin:9px 0}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}

/* Переключатели зон */
.sw{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:10px 12px;background:var(--card);border:1px solid var(--border);
  border-radius:12px;margin-bottom:7px;cursor:pointer;
}
.sw .t{font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px}
.sw .t i{width:10px;height:10px;border-radius:3px;flex:none}
.sw .d{font-size:11px;color:var(--muted);margin-top:2px;line-height:1.35}
.toggle{
  width:42px;height:24px;border-radius:20px;background:rgba(133,160,186,.28);
  position:relative;flex:none;transition:background .22s;
}
.toggle::after{
  content:'';position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;
  background:#fff;transition:transform .22s cubic-bezier(.4,1.4,.6,1);
}
.toggle.on{background:var(--brass)}
.toggle.on::after{transform:translateX(18px)}
.hint{font-size:11px;color:var(--muted);line-height:1.4;padding:9px 11px;
  background:rgba(133,160,186,.07);border-radius:10px;margin-bottom:11px}

/* Рейс */
.field{margin-bottom:11px;position:relative}
.field label{display:block;font-size:10.5px;color:var(--muted);margin-bottom:5px;
  text-transform:uppercase;letter-spacing:.7px}
.sugg{
  position:absolute;top:100%;left:0;right:0;background:var(--card);border:1px solid var(--border);
  border-radius:12px;margin-top:5px;z-index:900;max-height:215px;overflow-y:auto;display:none;
  box-shadow:0 10px 26px rgba(0,0,0,.35);
}
.sugg.on{display:block;animation:drop .18s ease}
@keyframes drop{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
.sugg div{padding:10px 13px;font-size:13.5px;cursor:pointer}
.sugg div+div{border-top:1px solid rgba(133,160,186,.1)}
.sugg div:active{background:var(--brass-dim)}
.voyhead{
  background:linear-gradient(135deg,rgba(232,163,62,.17),rgba(232,163,62,.03));
  border:1px solid rgba(232,163,62,.32);border-radius:var(--r);padding:14px;margin:13px 0;
}
.voyhead .big{font-size:16px;font-weight:650;margin-bottom:4px}
.voyhead .sm{font-size:12px;color:var(--muted)}

/* Табы */
.tabs{
  position:fixed;bottom:0;left:0;right:0;background:var(--card);
  border-top:1px solid var(--border);display:flex;z-index:1000;
  padding-bottom:env(safe-area-inset-bottom);backdrop-filter:blur(12px);
}
.tab{
  flex:1;padding:9px 4px 8px;text-align:center;color:var(--muted);
  font-size:10.5px;cursor:pointer;border:none;background:none;position:relative;
  transition:color .2s;
}
.tab .ic{display:block;font-size:19px;margin-bottom:2px;transition:transform .22s}
.tab.on{color:var(--brass)}
.tab.on .ic{transform:translateY(-2px) scale(1.12)}
.tab.on::before{content:'';position:absolute;top:0;left:22%;right:22%;height:2px;
  background:var(--brass);border-radius:0 0 3px 3px}

/* Скелетоны, пустые состояния */
.sk{background:var(--card);border-radius:var(--r);position:relative;overflow:hidden;border:1px solid var(--border)}
.sk::after{content:'';position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.055),transparent);animation:sh 1.4s infinite}
@keyframes sh{100%{transform:translateX(100%)}}
.sk.stat{height:78px}.sk.card{height:66px;margin-bottom:9px}
.empty{text-align:center;padding:36px 18px;color:var(--muted);font-size:13.5px}
.empty .ic{font-size:34px;display:block;margin-bottom:10px;opacity:.5}
.offline{
  background:rgba(232,102,74,.13);border:1px solid rgba(232,102,74,.36);
  border-radius:12px;padding:10px 12px;font-size:12.5px;margin-bottom:12px;display:none;
}
.offline.on{display:block;animation:up .3s ease}
.hidden{display:none!important}
.up{animation:up .32s cubic-bezier(.22,.9,.3,1) backwards}
@keyframes up{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:none}}
</style>
</head>
<body>

<div class="wrap">
  <div class="top">
    <div class="brand">
      <div class="beacon"><i></i><i></i><i></i><b></b></div>
      <h1>NAVAREA Monitor</h1>
    </div>
    <div class="hd-right">
      <span class="pill"><span class="dot" id="dot"></span><span id="synctxt">…</span></span>
      <button class="iconbtn" id="refresh">↻</button>
    </div>
  </div>

  <div class="offline" id="offline">📡 Нет связи. Показаны последние сохранённые данные.</div>

  <section id="v-dash">
    <div class="stats" id="stats">
      <div class="sk stat"></div><div class="sk stat"></div><div class="sk stat"></div><div class="sk stat"></div>
    </div>
    <div class="panel" id="server"></div>
    <h3 class="sec">Избранные районы</h3>
    <div class="cards" id="favcards"></div>
  </section>

  <section id="v-areas" class="hidden">
    <input class="search" id="q" placeholder="Поиск: номер, координаты, текст…">
    <div class="chips" id="chips">
      <button class="chip on" data-f="all">Все</button>
      <button class="chip" data-f="fav">★ Избранные</button>
      <button class="chip" data-f="active">С предупреждениями</button>
      <button class="chip" data-f="new">Новые сегодня</button>
    </div>
    <div class="chips">
      <button class="chip on" data-s="count">По количеству</button>
      <button class="chip" data-s="new">По новизне</button>
      <button class="chip" data-s="code">По номеру</button>
    </div>
    <div id="arealist"><div class="sk card"></div><div class="sk card"></div><div class="sk card"></div></div>
  </section>

  <section id="v-map" class="hidden">
    <div class="chips" id="mapchips"></div>
    <div id="map"></div>
    <div class="legend">
      <span><i style="background:#e8a33e"></i>Предупреждения</span>
      <span><i style="background:#43c47f"></i>MARPOL Прил. V</span>
      <span><i style="background:#6fb3f0"></i>Судовые сообщения</span>
    </div>
    <h3 class="sec">Справочные зоны</h3>
    <div id="zonelist"></div>
  </section>

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
    <button class="btn" id="govoy" style="width:100%;padding:13px;font-size:14px">Проложить и проверить</button>
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
if (TG) { TG.ready(); TG.expand(); try{ TG.setHeaderColor('secondary_bg_color'); }catch(e){} }
const INIT = TG ? (TG.initData || '') : '';
const CK = 'navarea_cache_v2', ZK = 'navarea_zones_v1';

let S = { stats:null, favs:[], warnings:[], zones:null, zoneOn:{},
          filter:'all', sort:'count', q:'', corridor:150, view:'dash', offline:false };
let map=null, vmap=null, wLayers=[], zLayers=[], mapArea='all';

const $ = s => document.querySelector(s);
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const hap = t => { try{ TG && TG.HapticFeedback.impactOccurred(t||'light'); }catch(e){} };

function saveCache(){
  try{
    localStorage.setItem(CK, JSON.stringify({stats:S.stats,warnings:S.warnings,favs:S.favs,at:Date.now()}));
    localStorage.setItem(ZK, JSON.stringify({zones:S.zones,on:S.zoneOn}));
  }catch(e){}
}
function loadCache(){
  try{
    const z = JSON.parse(localStorage.getItem(ZK)||'null');
    if(z){ S.zones=z.zones; S.zoneOn=z.on||{}; }
    const c = JSON.parse(localStorage.getItem(CK)||'null');
    if(c&&c.stats){ S.stats=c.stats; S.warnings=c.warnings||[]; S.favs=c.favs||[]; return c.at; }
  }catch(e){}
  return null;
}
async function api(p){
  const sep = p.includes('?')?'&':'?';
  const r = await fetch(p+sep+'initData='+encodeURIComponent(INIT));
  if(!r.ok) throw new Error('HTTP '+r.status);
  return r.json();
}
function ago(iso){
  if(!iso) return 'нет данных';
  const d=(Date.now()-new Date(iso).getTime())/1000;
  if(d<60) return 'только что';
  if(d<3600) return Math.floor(d/60)+' мин назад';
  if(d<86400) return Math.floor(d/3600)+' ч назад';
  return Math.floor(d/86400)+' дн назад';
}
function countUp(el,to){
  const from=0, dur=520, t0=performance.now();
  (function step(t){
    const k=Math.min(1,(t-t0)/dur), e=1-Math.pow(1-k,3);
    el.textContent=Math.round(from+(to-from)*e);
    if(k<1) requestAnimationFrame(step);
  })(t0);
}

async function load(spin){
  if(spin) $('#refresh').classList.add('spin');
  try{
    const [st,wr] = await Promise.all([api('/api/stats'), api('/api/warnings?limit=500')]);
    S.stats=st; S.warnings=wr.results||[]; S.offline=false;
    try{ const f=await api('/api/favorites'); if(!f.error) S.favs=f.favorites||[]; }catch(e){}
    if(!S.zones){
      try{
        const z=await api('/api/zones'); S.zones=z;
        (z.zones||[]).forEach(x=>{ if(S.zoneOn[x.id]===undefined) S.zoneOn[x.id]=false; });
      }catch(e){}
    }
    saveCache();
  }catch(e){ S.offline=true; }
  $('#offline').classList.toggle('on',S.offline);
  $('#refresh').classList.remove('spin');
  render();
}

function render(){ renderDash(); renderAreas(); renderMapChips(); renderZoneList(); }

function renderDash(){
  if(!S.stats) return;
  const t=S.stats.totals;
  $('#stats').innerHTML=`
    <div class="stat hl up" style="animation-delay:0ms"><div class="num mono" data-n="${t.in_force}">0</div><div class="lbl">Действует</div></div>
    <div class="stat ${t.added_today?'new':''} up" style="animation-delay:60ms"><div class="num mono" data-n="${t.added_today}">0</div><div class="lbl">Новых сегодня</div></div>
    <div class="stat up" style="animation-delay:120ms"><div class="num mono" data-n="${t.added_week}">0</div><div class="lbl">За 7 дней</div></div>
    <div class="stat up" style="animation-delay:180ms"><div class="num mono" data-n="${t.archived}">0</div><div class="lbl">В архиве</div></div>`;
  document.querySelectorAll('.stat .num').forEach(el=>countUp(el,+el.dataset.n));

  const sv=S.stats.server||{}, h=Math.floor((sv.uptime_seconds||0)/3600), m=Math.floor(((sv.uptime_seconds||0)%3600)/60);
  $('#server').innerHTML=`
    <div class="row"><span>Статус сервера</span><b style="color:${S.offline?'var(--danger)':'var(--ok)'}">${S.offline?'нет связи':'● работает'}</b></div>
    <div class="row"><span>Последнее предупреждение</span><b>${ago(S.stats.last_update)}</b></div>
    <div class="row"><span>Синхронизация</span><b>${S.offline?'из кэша':'только что'}</b></div>
    <div class="row"><span>Аптайм</span><b class="mono">${h} ч ${m} мин</b></div>
    <div class="row"><span>Районов на связи</span><b class="mono">${t.areas_count}</b></div>`;

  $('#dot').className='dot'+(S.offline?' stale':'');
  $('#synctxt').textContent=S.offline?'офлайн':'на связи';

  const fav=(S.stats.areas||[]).filter(a=>S.favs.includes(a.code));
  $('#favcards').innerHTML = fav.length ? fav.map(cardHtml).join('')
    : '<div class="empty"><span class="ic">★</span>Отметь районы звёздочкой во вкладке «Районы», чтобы держать их здесь под рукой.</div>';
  bindCards();
}

function cardHtml(a,i){
  const f=S.favs.includes(a.code), n=a.added_today>0;
  return `<div class="card up" style="animation-delay:${Math.min((i||0)*35,300)}ms" data-code="${a.code}">
    <div class="code">${esc(a.code)}</div>
    <div class="mid">
      <div class="nm">${esc(a.name)}${n?`<span class="badge">NEW ${a.added_today}</span>`:''}</div>
      <div class="sub">${a.added_week} за неделю · ${ago(a.last_update)}</div>
    </div>
    <div class="cnt mono">${a.in_force}</div>
    <button class="star ${f?'on':''}" data-fav="${a.code}">${f?'★':'☆'}</button>
  </div>`;
}

function renderAreas(){
  if(!S.stats) return;
  let list=(S.stats.areas||[]).slice();
  if(S.filter==='fav') list=list.filter(a=>S.favs.includes(a.code));
  if(S.filter==='active') list=list.filter(a=>a.in_force>0);
  if(S.filter==='new') list=list.filter(a=>a.added_today>0);

  if(S.q){
    const q=S.q.toLowerCase();
    const hits=S.warnings.filter(w=>(w.text||'').toLowerCase().includes(q)||
      (w.msg_number||'').toLowerCase().includes(q)||(w.region||'').toLowerCase().includes(q));
    $('#arealist').innerHTML = hits.length ? hits.slice(0,60).map(warnHtml).join('')
      : '<div class="empty"><span class="ic">🔍</span>Ничего не нашлось. Попробуй номер, часть текста или координаты.</div>';
    bindWarns(); return;
  }

  if(S.sort==='count') list.sort((a,b)=>b.in_force-a.in_force);
  if(S.sort==='new') list.sort((a,b)=>b.added_today-a.added_today||b.added_week-a.added_week);
  if(S.sort==='code') list.sort((a,b)=>a.code.localeCompare(b.code,undefined,{numeric:true}));

  $('#arealist').innerHTML = list.length ? `<div class="cards">${list.map(cardHtml).join('')}</div>`
    : '<div class="empty"><span class="ic">🌍</span>Под этот фильтр районов нет.</div>';
  bindCards();
}

function warnHtml(w,i){
  const sh=(w.shapes&&w.shapes.length)?w.shapes.length:0;
  const mb = sh ? `<button class="btn" data-map="${w.id}">🗺 На карте${sh>1?' ('+sh+' обл.)':''}</button>` : '';
  return `<div class="warn up" style="animation-delay:${Math.min((i||0)*30,260)}ms" data-wid="${w.id}">
    <div class="hd">
      <span class="tag">${esc(w.area_code)} №${esc(w.msg_number||'—')}</span>
      ${w.region?`<span class="reg">${esc(w.region)}</span>`:''}
      ${w.distance_nm!==undefined?`<span class="dist">${w.distance_nm} миль от курса</span>`:''}
    </div>
    <div class="txt clip" data-txt>${esc(w.text)}</div>
    <div class="acts">${mb}<button class="btn ghost" data-more>Показать целиком</button></div>
  </div>`;
}

function bindCards(){
  document.querySelectorAll('[data-fav]').forEach(b=>b.onclick=async ev=>{
    ev.stopPropagation(); hap('medium');
    const c=b.dataset.fav;
    S.favs = S.favs.includes(c)? S.favs.filter(x=>x!==c) : S.favs.concat([c]);
    render(); saveCache();
    try{ await api('/api/favorites?toggle='+encodeURIComponent(c)); }catch(e){}
  });
  document.querySelectorAll('.card[data-code]').forEach(c=>c.onclick=()=>{
    hap(); S.q=''; $('#q').value=''; switchView('areas');
    const code=c.dataset.code, hits=S.warnings.filter(w=>w.area_code===code);
    $('#arealist').innerHTML = (hits.length
      ? `<button class="chip on" style="margin-bottom:11px" onclick="renderAreas()">← Все районы</button>`+hits.map(warnHtml).join('')
      : `<button class="chip on" style="margin-bottom:11px" onclick="renderAreas()">← Все районы</button><div class="empty"><span class="ic">✅</span>По этому району сейчас нет действующих предупреждений.</div>`);
    bindWarns();
  });
}

function bindWarns(){
  document.querySelectorAll('[data-more]').forEach(b=>b.onclick=()=>{
    const t=b.closest('.warn').querySelector('[data-txt]');
    t.classList.toggle('clip');
    b.textContent = t.classList.contains('clip')?'Показать целиком':'Свернуть';
  });
  document.querySelectorAll('[data-map]').forEach(b=>b.onclick=()=>{
    hap(); const w=S.warnings.find(x=>String(x.id)===b.dataset.map);
    if(w){ switchView('map'); setTimeout(()=>focusWarning(w),70); }
  });
}

/* --- карта --- */
function initMap(){
  if(map) return;
  map=L.map('map',{worldCopyJump:true}).setView([25,0],2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap'}).addTo(map);
  drawZones(); drawMap();
}
function renderMapChips(){
  if(!S.stats) return;
  const codes=(S.stats.areas||[]).filter(a=>a.in_force>0).map(a=>a.code);
  $('#mapchips').innerHTML=['all'].concat(codes).map(c=>
    `<button class="chip ${mapArea===c?'on':''}" data-m="${c}">${c==='all'?'Все районы':c}</button>`).join('');
  document.querySelectorAll('[data-m]').forEach(b=>b.onclick=()=>{
    mapArea=b.dataset.m; renderMapChips(); drawMap(); hap();
  });
}
function shapeLayer(pts,type,popup,color){
  let l;
  if(type==='polygon'&&pts.length>=3) l=L.polygon(pts,{color:color,weight:2,fillOpacity:.14});
  else if(type==='line'&&pts.length>=2) l=L.polyline(pts,{color:color,weight:3});
  else l=L.circleMarker(pts[0],{radius:6,color:color,fillColor:color,fillOpacity:.85,weight:2});
  return l.bindPopup(popup);
}
function drawMap(){
  if(!map) return;
  wLayers.forEach(l=>map.removeLayer(l)); wLayers=[];
  const list=S.warnings.filter(w=>w.shapes&&w.shapes.length&&(mapArea==='all'||w.area_code===mapArea));
  list.forEach(w=>{
    const popup=`<b>${esc(w.area_code)} №${esc(w.msg_number||'—')}</b><br>${esc((w.text||'').slice(0,240))}…`;
    w.shapes.forEach(s=>{
      const l=shapeLayer(s.points,s.type,popup,'#e8a33e'); l.addTo(map); wLayers.push(l);
    });
  });
}
function drawZones(){
  if(!map||!S.zones) return;
  zLayers.forEach(l=>map.removeLayer(l)); zLayers=[];
  (S.zones.zones||[]).forEach(z=>{
    if(!S.zoneOn[z.id]) return;
    const col=(S.zones.groups[z.group]||{}).color||'#6fb3f0';
    const l=L.polygon(z.points,{color:col,weight:2,dashArray:'7 5',fillOpacity:.07})
      .bindPopup(`<b>${esc(z.name)}</b><br>${esc(z.note)}<br><br><i>${esc(S.zones.disclaimer)}</i>`);
    l.addTo(map); zLayers.push(l);
  });
}
function renderZoneList(){
  if(!S.zones){ $('#zonelist').innerHTML='<div class="sk card"></div>'; return; }
  const g=S.zones.groups||{};
  let html=`<div class="hint">⚠️ ${esc(S.zones.disclaimer)}</div>`;
  Object.keys(g).forEach(gk=>{
    html+=`<h3 class="sec">${esc(g[gk].title)}</h3>`;
    (S.zones.zones||[]).filter(z=>z.group===gk).forEach(z=>{
      html+=`<div class="sw" data-zone="${z.id}">
        <div style="min-width:0">
          <div class="t"><i style="background:${g[gk].color}"></i>${esc(z.name)}</div>
          <div class="d">${esc(z.note.slice(0,110))}${z.note.length>110?'…':''}</div>
        </div>
        <div class="toggle ${S.zoneOn[z.id]?'on':''}"></div>
      </div>`;
    });
  });
  $('#zonelist').innerHTML=html;
  document.querySelectorAll('[data-zone]').forEach(el=>el.onclick=()=>{
    const id=el.dataset.zone;
    S.zoneOn[id]=!S.zoneOn[id];
    el.querySelector('.toggle').classList.toggle('on',S.zoneOn[id]);
    hap(); saveCache(); drawZones();
  });
}
function focusWarning(w){
  initMap(); mapArea='all'; renderMapChips(); drawMap();
  const all=[]; w.shapes.forEach(s=>s.points.forEach(p=>all.push(p)));
  if(all.length===1) map.setView(all[0],8);
  else map.fitBounds(L.latLngBounds(all),{padding:[40,40]});
}

/* --- рейс --- */
function setupPort(inputId,suggId){
  const inp=$(inputId), sug=$(suggId); let t=null;
  inp.oninput=()=>{
    clearTimeout(t); const v=inp.value.trim();
    if(v.length<2){ sug.classList.remove('on'); return; }
    t=setTimeout(async()=>{
      try{
        const r=await api('/api/ports?q='+encodeURIComponent(v));
        sug.innerHTML=(r.results||[]).map(p=>`<div data-p="${esc(p.name)}">${esc(p.label)}</div>`).join('');
        sug.classList.toggle('on',(r.results||[]).length>0);
        sug.querySelectorAll('[data-p]').forEach(d=>d.onclick=()=>{
          inp.value=d.dataset.p; sug.classList.remove('on'); hap();
        });
      }catch(e){ sug.classList.remove('on'); }
    },220);
  };
  inp.onblur=()=>setTimeout(()=>sug.classList.remove('on'),180);
}
async function runVoyage(){
  const f=$('#pfrom').value.trim(), to=$('#pto').value.trim();
  if(!f||!to){ $('#voyout').innerHTML='<div class="empty">Укажи оба порта.</div>'; return; }
  $('#voyout').innerHTML='<div class="sk card"></div><div class="sk card"></div>';
  hap('medium');
  try{
    const r=await api(`/api/voyage?from=${encodeURIComponent(f)}&to=${encodeURIComponent(to)}&corridor=${S.corridor}`);
    if(r.error){ $('#voyout').innerHTML=`<div class="empty"><span class="ic">⚠️</span>${esc(r.error)}</div>`; return; }
    const w=r.count===1?'предупреждение':(r.count>=2&&r.count<=4?'предупреждения':'предупреждений');
    $('#voyout').innerHTML=`
      <div class="voyhead up">
        <div class="big">🚢 На вашем маршруте найдено ${r.count} активных ${w}.</div>
        <div class="sm">${esc(r.from.label)} → ${esc(r.to.label)} · <span class="mono">${r.distance_nm}</span> миль · коридор ±<span class="mono">${r.corridor_nm}</span> миль</div>
      </div>
      <div id="vmap"></div>
      ${r.results.length? r.results.map(warnHtml).join('')
        :'<div class="empty"><span class="ic">✅</span>По этому маршруту действующих предупреждений с координатами нет.</div>'}`;
    bindWarns(); setTimeout(()=>drawVoy(r),70);
  }catch(e){
    $('#voyout').innerHTML='<div class="empty"><span class="ic">📡</span>Нет связи с сервером. Попробуй позже.</div>';
  }
}
function drawVoy(r){
  if(vmap){ vmap.remove(); vmap=null; }
  vmap=L.map('vmap',{worldCopyJump:true});
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OSM'}).addTo(vmap);
  const line=L.polyline(r.route,{color:'#6fb3f0',weight:3,dashArray:'7 6'}).addTo(vmap);
  L.marker([r.from.lat,r.from.lon]).bindPopup(esc(r.from.label)).addTo(vmap);
  L.marker([r.to.lat,r.to.lon]).bindPopup(esc(r.to.label)).addTo(vmap);
  r.results.forEach(w=>{
    (w.shapes||[]).forEach(s=>{
      shapeLayer(s.points,s.type,`<b>${esc(w.area_code)} №${esc(w.msg_number||'—')}</b><br>${w.distance_nm} миль от курса`,'#e8a33e').addTo(vmap);
    });
  });
  vmap.fitBounds(line.getBounds(),{padding:[25,25]});
}

/* --- навигация --- */
function switchView(v){
  S.view=v;
  ['dash','areas','map','voy'].forEach(x=>$('#v-'+x).classList.toggle('hidden',x!==v));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.v===v));
  if(v==='map') setTimeout(()=>{ initMap(); map.invalidateSize(); drawZones(); drawMap(); },60);
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{ hap(); switchView(t.dataset.v); });
document.querySelectorAll('#chips .chip').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('#chips .chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); S.filter=c.dataset.f; renderAreas(); hap();
});
document.querySelectorAll('[data-s]').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('[data-s]').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); S.sort=c.dataset.s; renderAreas(); hap();
});
document.querySelectorAll('#corr .chip').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('#corr .chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); S.corridor=+c.dataset.c; hap();
});
let qt=null;
$('#q').oninput=e=>{ clearTimeout(qt); qt=setTimeout(()=>{ S.q=e.target.value.trim(); renderAreas(); },230); };
$('#refresh').onclick=()=>{ hap(); load(true); };
$('#govoy').onclick=runVoyage;
setupPort('#pfrom','#sfrom'); setupPort('#pto','#sto');

if(loadCache()) render();
load(false);
setInterval(()=>{ if(S.view==='dash'||S.view==='areas') load(false); },120000);
</script>
</body>
</html>
"""
