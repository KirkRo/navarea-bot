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

Оформление: тёмная база с латунным акцентом под морскую тему, светлая
тема переключается тапом по компасу в шапке и запоминается.
"""

MINI_APP_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>WatchKeeper</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
:root{
  --bg:#0a1520; --bg2:#0d1c29;
  --surf:rgba(21,33,47,.82); --surf2:rgba(28,42,58,.7);
  --text:#f4f8fc; --muted:#7f96ac; --dim:#5b7086;
  --amber:#f0a03c; --amber2:#ff8b3d; --amber-soft:rgba(240,160,60,.13);
  --ok:#3fc97f; --hot:#ff6b4a; --sea:#4d93d6;
  /* Морская навигационная палитра: голубой -- навигация, зелёный -- норма,
     жёлтый -- внимание, красный -- опасность, фиолетовый -- ассистент. */
  --blue:#46b8ff; --cyan:#62dcff; --green:#26d69d; --purple:#d477ff;
  --ai1:#1689d6; --ai2:#8d5cff; --ai3:#d96bff;
  --ai:linear-gradient(90deg,var(--ai1),var(--ai2) 55%,var(--ai3));
  --line:rgba(127,150,172,.16);
  --r-xl:26px; --r-lg:20px; --r-md:15px; --r-sm:11px;
  --sh:0 14px 38px rgba(0,0,0,.45);
  --glow:0 8px 26px rgba(240,160,60,.32);
}
body.light{
  --bg:#f2f5f9; --bg2:#e8edf4; --surf:rgba(255,255,255,.9); --surf2:rgba(255,255,255,.72);
  --text:#0e1c2b; --muted:#5d7488; --dim:#8093a6; --line:rgba(14,28,43,.1);
  --sh:0 12px 32px rgba(20,40,60,.13);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{overscroll-behavior-y:contain}
body{
  margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Segoe UI',Roboto,sans-serif;
  font-size:15px;line-height:1.45;padding-bottom:96px;letter-spacing:-.1px;
}
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(760px 420px at 82% -8%, rgba(240,160,60,.16), transparent 62%),
    radial-gradient(620px 460px at -12% 6%, rgba(77,147,214,.14), transparent 60%);
}
/* Одна раскладка и на телефоне, и на компьютере: Mini App живёт в узком
   окне Telegram, и вторая, «настольная» вёрстка только расходилась бы с
   первой. Ширина ограничена, содержимое прокручивается вертикально. */
.wrap{padding:max(10px,env(safe-area-inset-top)) 15px 0;max-width:430px;margin:0 auto;position:relative;z-index:1}
.mono{font-variant-numeric:tabular-nums;font-feature-settings:'tnum'}

/* ---- Шапка ---- */
.hdr{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:16px}
.hello{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:6px;margin-bottom:3px}
.h1{font-size:29px;font-weight:800;line-height:1.1;letter-spacing:-.9px}
.h1 span{background:linear-gradient(105deg,var(--amber),var(--amber2));
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.avatar{
  width:44px;height:44px;border-radius:15px;flex:none;position:relative;cursor:pointer;
  background:linear-gradient(140deg,#1b3348,#122232);border:1px solid var(--line);
  display:flex;align-items:center;justify-content:center;font-size:21px;
  transition:transform .22s cubic-bezier(.34,1.6,.5,1);
}
.avatar:active{transform:scale(.9)}

/* ---- Лампа переключения темы ----
   Не абстрактная иконка, а палубный светильник: в тёмной теме он погашен,
   в светлой -- горит. При нажатии видно, как нить накала разгорается. */
.lamp{width:24px;height:24px;display:block}
.lamp .glass{fill:rgba(207,224,242,.16);stroke:#9db6d4;stroke-width:1.4}
.lamp .base{fill:#7f96ac}
.lamp .fil{stroke:#8296aa;stroke-width:1.4;fill:none;transition:stroke .4s}
.lamp .halo{fill:#ffd894;opacity:0;transition:opacity .4s}
body.light .lamp .glass{fill:rgba(255,214,132,.5);stroke:#e0a13c}
body.light .lamp .fil{stroke:#ff9d2e}
body.light .lamp .halo{opacity:.55;animation:lampGlow 3.2s ease-in-out infinite}
body.light .lamp .base{fill:#b98a3c}
@keyframes lampGlow{0%,100%{opacity:.35}50%{opacity:.75}}

/* ---- Огонёк состояния GPS ----
   Переехал с кнопки темы на кнопку позиции: зелёный пульс -- место
   получено, красный -- геопозиция выключена или недоступна. */
.geobtn b{
  position:absolute;top:-3px;right:-3px;width:11px;height:11px;border-radius:50%;
  background:var(--ok);border:2.5px solid var(--bg);animation:beatOk 2.2s infinite;
}
.geobtn b.off{background:var(--hot);animation:beatNo 1.4s infinite}
.geobtn b.wait{background:var(--amber);animation:beatWait 1.1s infinite}
@keyframes beatOk{0%,100%{box-shadow:0 0 0 0 rgba(63,201,127,.55)}70%{box-shadow:0 0 0 8px rgba(63,201,127,0)}}
@keyframes beatNo{0%,100%{box-shadow:0 0 0 0 rgba(255,107,74,.6)}70%{box-shadow:0 0 0 7px rgba(255,107,74,0)}}
@keyframes beatWait{0%,100%{box-shadow:0 0 0 0 rgba(240,160,60,.6)}70%{box-shadow:0 0 0 7px rgba(240,160,60,0)}}
@media (prefers-reduced-motion: reduce){
  .geobtn b,body.light .lamp .halo{animation:none}
}

/* ---- Поиск ---- */
.srow{display:flex;gap:9px;margin-bottom:16px}
.sbox{
  flex:1;display:flex;align-items:center;gap:9px;padding:0 14px;height:50px;
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-md);
  backdrop-filter:blur(16px);transition:border-color .22s,box-shadow .22s;
}
.sbox:focus-within{border-color:var(--amber);box-shadow:0 0 0 4px var(--amber-soft)}
.sbox svg{width:17px;height:17px;flex:none;stroke:var(--muted)}
.sbox input{
  flex:1;background:none;border:none;outline:none;color:var(--text);font-size:14.5px;
  font-family:inherit;min-width:0;
}
.sbox input::placeholder{color:var(--dim)}
.fbtn{
  width:50px;height:50px;flex:none;border-radius:var(--r-md);border:none;cursor:pointer;
  background:linear-gradient(140deg,var(--amber),var(--amber2));box-shadow:var(--glow);
  display:flex;align-items:center;justify-content:center;font-size:18px;color:#16232f;
  transition:transform .2s cubic-bezier(.34,1.6,.5,1);
}
.fbtn:active{transform:scale(.9)}

/* ---- Плитки-категории ---- */
.cats,.chips{
  display:flex;gap:9px;overflow-x:auto;overflow-y:hidden;padding:2px 0 12px;
  scrollbar-width:none;-webkit-overflow-scrolling:touch;
  touch-action:pan-x;overscroll-behavior-x:contain;
}
.cats::-webkit-scrollbar,.chips::-webkit-scrollbar{display:none}
.cat{
  flex:none;width:74px;padding:11px 6px 9px;border-radius:var(--r-md);cursor:pointer;
  background:var(--surf);border:1px solid var(--line);text-align:center;
  transition:all .25s cubic-bezier(.34,1.4,.5,1);backdrop-filter:blur(12px);
}
.cat:active{transform:scale(.93)}
.cat.on{background:linear-gradient(150deg,var(--amber),var(--amber2));border-color:transparent;box-shadow:var(--glow)}
.cat .ci{font-size:21px;display:block;margin-bottom:4px}
.cat .cn{font-size:10.5px;font-weight:650;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cat.on .cn{color:#16232f}
.cat .cb{
  display:inline-block;min-width:17px;font-size:9.5px;font-weight:750;border-radius:9px;
  padding:1px 5px;margin-top:3px;background:var(--amber-soft);color:var(--amber);
}
.cat.on .cb{background:rgba(22,35,47,.24);color:#16232f}

/* ---- Заставка-герой ---- */
.hero{
  position:relative;border-radius:var(--r-xl);overflow:hidden;margin-bottom:15px;
  height:186px;box-shadow:var(--sh);border:1px solid var(--line);
}
.heroSvg{position:absolute;inset:0;width:100%;height:100%}
.heroGrad{
  position:absolute;inset:0;
  background:linear-gradient(100deg,rgba(6,16,26,.93) 4%,rgba(6,16,26,.62) 44%,transparent 76%);
}
.heroIn{position:absolute;left:19px;top:19px;right:19px}
.hchip{
  display:inline-flex;align-items:center;gap:5px;font-size:9.5px;font-weight:750;
  background:rgba(240,160,60,.2);color:var(--amber);border:1px solid rgba(240,160,60,.36);
  border-radius:20px;padding:3px 9px;text-transform:uppercase;letter-spacing:.7px;
  backdrop-filter:blur(8px);
}
.hnum{font-size:46px;font-weight:850;line-height:1;margin:9px 0 1px;letter-spacing:-2px;color:#fff}
.hsub{font-size:12.5px;color:#c2d4e4;max-width:63%}
.hbtn{
  position:absolute;left:19px;bottom:17px;border:none;cursor:pointer;
  background:linear-gradient(140deg,var(--amber),var(--amber2));color:#16232f;
  border-radius:13px;padding:10px 17px;font-size:13px;font-weight:750;font-family:inherit;
  box-shadow:var(--glow);display:flex;align-items:center;gap:7px;
  transition:transform .2s cubic-bezier(.34,1.6,.5,1);
}
.hbtn:active{transform:scale(.93)}

/* ---- Корпус судна со статистикой ---- */
.hull{position:relative;margin-bottom:17px;filter:drop-shadow(0 16px 30px rgba(0,0,0,.42))}
.hullTop{
  background:linear-gradient(165deg,var(--surf2),var(--surf));
  border:1px solid var(--line);border-bottom:none;
  border-radius:var(--r-lg) var(--r-lg) 0 0;padding:15px 15px 13px;
  backdrop-filter:blur(18px);
}
.hullBody{
  height:34px;margin-top:-1px;
  background:linear-gradient(180deg,var(--surf),rgba(15,26,38,.9));
  border:1px solid var(--line);border-top:none;
  clip-path:polygon(0 0,100% 0,90% 100%,10% 100%);
}
.hullWave{height:20px;margin-top:-9px;overflow:hidden;border-radius:0 0 var(--r-lg) var(--r-lg)}
.hullWave svg{width:200%;height:100%;animation:drift 11s linear infinite}
@keyframes drift{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.hgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
.hcell{text-align:center;padding:5px 2px;border-radius:var(--r-sm);transition:background .22s}
.hcell:active{background:var(--amber-soft)}
.hcell .v{font-size:23px;font-weight:800;line-height:1;letter-spacing:-.7px}
.hcell.a .v{color:var(--amber)}
.hcell.h .v{color:var(--hot)}
.hcell .k{font-size:9px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.55px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hullPort{
  position:absolute;left:50%;transform:translateX(-50%);bottom:19px;
  display:flex;gap:11px;z-index:2;
}
.hullPort i{width:6px;height:6px;border-radius:50%;background:rgba(240,160,60,.5);
  box-shadow:0 0 7px rgba(240,160,60,.75)}

/* ---- Секции ---- */
.sech{display:flex;align-items:baseline;justify-content:space-between;margin:0 0 11px}
.sech h3{font-size:16.5px;font-weight:750;margin:0;letter-spacing:-.4px}
.sech a{font-size:12.5px;color:var(--amber);text-decoration:none;font-weight:650;cursor:pointer}

/* ---- Карточка предупреждения ---- */
.wcard{
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-lg);
  padding:14px;margin-bottom:11px;position:relative;overflow:hidden;
  backdrop-filter:blur(16px);box-shadow:var(--sh);
}
.wcard::before{
  content:'';position:absolute;left:0;top:0;bottom:0;width:3px;
  background:linear-gradient(180deg,var(--amber),var(--amber2));
}
.wtop{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}
.wtag{
  background:var(--amber-soft);color:var(--amber);font-size:11px;font-weight:750;
  border-radius:8px;padding:3px 9px;border:1px solid rgba(240,160,60,.22);
}
.wnew{background:var(--hot);color:#fff;font-size:9px;font-weight:800;border-radius:8px;
  padding:3px 7px;letter-spacing:.5px;animation:blink 2.3s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.5}}
.wreg{font-size:11.5px;color:var(--muted)}
.wdist{font-size:11px;color:var(--amber);font-weight:700;margin-left:auto}
.wtxt{font-size:13.2px;line-height:1.5;color:var(--text);opacity:.88;white-space:pre-wrap;word-break:break-word}
.wtxt.clip{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.wact{display:flex;gap:8px;margin-top:12px;align-items:center;flex-wrap:wrap}
.btn{
  border:none;cursor:pointer;font-family:inherit;font-weight:700;font-size:12.5px;
  border-radius:12px;padding:9px 15px;transition:transform .18s cubic-bezier(.34,1.6,.5,1),opacity .18s;
  background:linear-gradient(140deg,var(--amber),var(--amber2));color:#16232f;box-shadow:var(--glow);
}
.btn:active{transform:scale(.93)}
.btn.g{background:var(--surf2);color:var(--muted);border:1px solid var(--line);box-shadow:none}
.btn.wide{width:100%;padding:15px;font-size:15px;border-radius:var(--r-md);justify-content:center}
.heart{
  margin-left:auto;width:34px;height:34px;flex:none;border-radius:50%;border:1px solid var(--line);
  background:var(--surf2);cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center;
  transition:transform .26s cubic-bezier(.34,1.7,.5,1),color .2s;color:var(--dim);
}
.heart.on{color:var(--amber);border-color:rgba(240,160,60,.42);background:var(--amber-soft)}
.heart:active{transform:scale(1.32)}

/* ---- Карточка района ---- */
.acard{
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-lg);
  padding:13px;display:flex;align-items:center;gap:12px;cursor:pointer;margin-bottom:10px;
  backdrop-filter:blur(16px);transition:transform .2s cubic-bezier(.34,1.4,.5,1),border-color .2s;
}
.acard:active{transform:scale(.98);border-color:rgba(240,160,60,.4)}
.acode{
  width:54px;height:54px;flex:none;border-radius:var(--r-md);
  background:linear-gradient(150deg,var(--amber-soft),rgba(240,160,60,.05));
  border:1px solid rgba(240,160,60,.2);color:var(--amber);
  display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13.5px;
}
.amid{flex:1;min-width:0}
.anm{font-size:14.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.asub{font-size:11.5px;color:var(--muted);margin-top:2px}
.acnt{font-size:22px;font-weight:800;letter-spacing:-.6px;flex:none}

/* ---- Карта ---- */
.mapwrap{position:relative;border-radius:var(--r-lg);overflow:hidden;border:1px solid var(--line);box-shadow:var(--sh)}
#map{height:60vh}
#vmap{height:38vh;border-radius:var(--r-lg);border:1px solid var(--line);margin:13px 0;overflow:hidden}
.leaflet-container{background:#081422;font-family:inherit}
.leaflet-popup-content-wrapper{background:#111f2e;color:#eef4fa;border-radius:14px;border:1px solid rgba(127,150,172,.24)}
.leaflet-popup-tip{background:#111f2e}
.mapctl{
  position:absolute;top:11px;right:11px;z-index:700;background:rgba(11,22,34,.9);
  border:1px solid var(--line);border-radius:var(--r-md);padding:10px 12px;font-size:11.5px;
  backdrop-filter:blur(16px);max-width:178px;box-shadow:var(--sh);
}
.mapctl .ttl{font-size:9px;color:var(--dim);text-transform:uppercase;letter-spacing:.8px;margin:0 0 6px;font-weight:700}
.mapctl .ttl+.ttl{margin-top:10px}
.mapctl label{display:flex;align-items:center;gap:8px;padding:3.5px 0;cursor:pointer;color:#eef4fa}
.mapctl input{accent-color:var(--amber);width:14px;height:14px;margin:0}
.cursorpos{
  position:absolute;bottom:11px;left:11px;z-index:700;background:rgba(11,22,34,.9);
  border:1px solid var(--line);border-radius:var(--r-sm);padding:8px 11px;
  font-size:11.5px;backdrop-filter:blur(16px);font-variant-numeric:tabular-nums;box-shadow:var(--sh);
}
.cursorpos .lb{font-size:8.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.7px;font-weight:700}
.cursorpos .vl{color:var(--amber);font-weight:750;margin-top:2px;font-size:12.5px}
.wlabel{background:rgba(8,20,34,.92);border:1px solid rgba(240,160,60,.5);color:#f5e3c4;
  border-radius:7px;padding:2px 7px;font-size:10px;font-weight:700;white-space:nowrap;box-shadow:none}
.leaflet-tooltip.wlabel::before{display:none}
.mapstat{display:flex;gap:9px;flex-wrap:wrap;font-size:11.5px;color:var(--muted);margin:11px 0 4px}
.mapstat b{color:var(--amber)}
.legend{display:flex;gap:13px;flex-wrap:wrap;font-size:11.5px;color:var(--muted);margin:9px 0 15px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:4px;margin-right:6px;vertical-align:-1px}

/* ---- Переключатели ---- */
.sw{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:13px 14px;background:var(--surf);border:1px solid var(--line);
  border-radius:var(--r-md);margin-bottom:9px;cursor:pointer;backdrop-filter:blur(14px);
  transition:border-color .2s;
}
.sw:active{border-color:rgba(240,160,60,.4)}
.sw .t{font-size:13.5px;font-weight:700;display:flex;align-items:center;gap:9px}
.sw .t i{width:11px;height:11px;border-radius:4px;flex:none}
.sw .d{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.4}
.toggle{
  width:48px;height:27px;border-radius:20px;background:rgba(127,150,172,.26);
  position:relative;flex:none;transition:background .26s;
}
.toggle::after{
  content:'';position:absolute;top:3px;left:3px;width:21px;height:21px;border-radius:50%;
  background:#fff;transition:transform .3s cubic-bezier(.34,1.7,.5,1);box-shadow:0 2px 6px rgba(0,0,0,.3);
}
.toggle.on{background:linear-gradient(140deg,var(--amber),var(--amber2))}
.toggle.on::after{transform:translateX(21px)}
.hint{font-size:11.5px;color:var(--muted);line-height:1.5;padding:12px 14px;
  background:var(--surf2);border:1px solid var(--line);border-radius:var(--r-md);margin-bottom:13px}

/* ---- Рейс ---- */
.fld{margin-bottom:13px;position:relative}
.fld label{display:block;font-size:10px;color:var(--dim);margin-bottom:7px;
  text-transform:uppercase;letter-spacing:.9px;font-weight:750}
.sugg{
  position:absolute;top:100%;left:0;right:0;background:#111f2e;border:1px solid var(--line);
  border-radius:var(--r-md);margin-top:6px;z-index:900;max-height:220px;overflow-y:auto;display:none;
  box-shadow:0 16px 34px rgba(0,0,0,.5);
}
.sugg.on{display:block;animation:drop .2s cubic-bezier(.34,1.4,.5,1)}
@keyframes drop{from{opacity:0;transform:translateY(-8px) scale(.98)}to{opacity:1;transform:none}}
.sugg div{padding:12px 14px;font-size:13.5px;cursor:pointer;color:#eef4fa}
.sugg div+div{border-top:1px solid rgba(127,150,172,.1)}
.sugg div:active{background:var(--amber-soft)}
.voyhead{
  background:linear-gradient(140deg,rgba(240,160,60,.2),rgba(255,139,61,.05));
  border:1px solid rgba(240,160,60,.34);border-radius:var(--r-lg);padding:16px;margin:15px 0;
  box-shadow:var(--sh);
}
.voyhead .big{font-size:17px;font-weight:750;margin-bottom:5px;letter-spacing:-.4px}
.voyhead .sm{font-size:12.5px;color:var(--muted)}

/* ================= Главный экран =================
   Собран по макету: шапка, судно, подсказки ассистента, сводка с мостика,
   тревога, кнопка Ask AI. Плотной таблицы инструментов здесь сознательно
   нет -- она уехала во вкладку «Инструменты»: с главного экрана человек
   должен за три секунды понять, что это помощник вахтенного, а не список
   калькуляторов. */

/* --- шапка --- */
.wkhdr{display:flex;align-items:center;gap:11px;margin-bottom:13px}
.wkmark{
  width:38px;height:38px;flex:none;border-radius:50%;background:#082a42;
  border:1px solid #35aaff;display:flex;align-items:center;justify-content:center;color:#eef8ff;
}
body.light .wkmark{background:#dceefb;border-color:#2b8fd8;color:#0d3050}
.wkmark svg{width:22px;height:22px}
.wkname{flex:1;min-width:0}
.wkname .n1{font-size:15px;font-weight:850;letter-spacing:.4px;line-height:1.1}
.wkname .n2{font-size:9.5px;font-weight:700;color:var(--muted);margin-top:2px;letter-spacing:.2px}
.wkclock{text-align:right;flex:none}
.wkclock .t{font-size:15px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.1}
.wkclock .t span{font-size:8.5px;font-weight:700;color:var(--muted);margin-left:2px}
.wkclock .d{font-size:8.5px;color:var(--muted);margin-top:2px}
/* Второстепенные переключатели: язык, тема, позиция. Ушли под шапку,
   чтобы не спорить за место с часами и уведомлениями. */
.hdrtools{display:flex;align-items:center;gap:8px;margin-bottom:13px;flex-wrap:wrap}
.hdrtools .hello{font-size:9.5px;color:var(--muted)}
.wkbell{
  width:34px;height:34px;flex:none;border-radius:50%;background:var(--surf2);
  border:1px solid var(--line);color:var(--text);position:relative;cursor:pointer;
  display:flex;align-items:center;justify-content:center;padding:0;
}
.wkbell svg{width:17px;height:17px}
.wkbell b{
  position:absolute;top:-4px;right:-4px;min-width:16px;height:16px;border-radius:9px;
  background:#ff4d58;color:#fff;font-size:9px;font-weight:800;line-height:16px;padding:0 4px;
}
.wkbell b:empty{display:none}

/* --- герой: судно и приветствие --- */
.wkhero{
  position:relative;border-radius:var(--r-lg);overflow:hidden;border:1px solid #24526c;
  background:linear-gradient(135deg,#092a40,#071c2d 55%,#10223a);
  box-shadow:var(--sh);padding:17px 16px 15px;min-height:212px;
}
body.light .wkhero{background:linear-gradient(135deg,#dceaf6,#eaf2fa 55%,#e2ecf7);border-color:#b9d2e4}

/* ---- Живая сцена: Одесский порт ----
   Воронцовский маяк, Потёмкинская лестница, памятник Дюку, портовые
   краны и судно на ходу. Объём даётся слоями: дальний план почти не
   двигается, ближние волны идут быстрее и перекрывают друг друга --
   тот же приём, что в театральной перспективе.

   Всё нарисовано и анимировано средствами SVG и CSS: ни одной картинки
   и ни одной внешней библиотеки. В рейсе спутниковый канал дорогой,
   и тянуть ради заставки мегабайты неправильно. */
.wkhero .art{position:absolute;inset:0;pointer-events:none;overflow:hidden;border-radius:var(--r-lg)}
.wkhero .art svg{width:100%;height:100%;display:block}
.wkhero .eyebrow,.wkhero .greet,.wkhero .sub,.wkvessel{position:relative;z-index:2}
.wkhero::after{
  content:'';position:absolute;inset:0;z-index:1;pointer-events:none;border-radius:var(--r-lg);
  background:linear-gradient(100deg,rgba(4,17,28,.92) 0%,rgba(4,17,28,.72) 38%,rgba(4,17,28,.15) 66%,transparent 100%);
}
body.light .wkhero::after{
  background:linear-gradient(100deg,rgba(233,241,248,.94) 0%,rgba(233,241,248,.76) 38%,rgba(233,241,248,.2) 66%,transparent 100%);
}

/* маяк: огонь моргает, луч обходит горизонт */
@keyframes lhLamp{0%,72%{opacity:.35}76%,88%{opacity:1}92%,100%{opacity:.35}}
@keyframes lhBeam{0%{opacity:0}70%{opacity:0}78%{opacity:.5}86%{opacity:.5}100%{opacity:0}}
@keyframes lhSweep{from{transform:rotate(-24deg)}to{transform:rotate(24deg)}}
.lhLamp{animation:lhLamp 4s infinite}
.lhBeam{animation:lhBeam 4s infinite;transform-origin:0 0}
.lhSweep{animation:lhSweep 8s ease-in-out infinite alternate;transform-origin:0 0}

/* судно идёт по воде и покачивается */
@keyframes shipSail{from{transform:translateX(-58px)}to{transform:translateX(226px)}}
@keyframes shipRoll{0%,100%{transform:rotate(-1.1deg) translateY(0)}50%{transform:rotate(1.1deg) translateY(1.6px)}}
.shipGo{animation:shipSail 46s linear infinite}
.shipRoll{animation:shipRoll 4.4s ease-in-out infinite;transform-origin:50% 90%}
/* ходовые огни: правый зелёный, левый красный, топовый белый */
@keyframes navRed{0%,46%{opacity:.35}50%,60%{opacity:1}64%,100%{opacity:.35}}
@keyframes navGreen{0%,20%{opacity:.35}24%,34%{opacity:1}38%,100%{opacity:.35}}
@keyframes mastFlash{0%,88%{opacity:.3}91%,95%{opacity:1}98%,100%{opacity:.3}}
.navRed{animation:navRed 3s infinite}
.navGreen{animation:navGreen 3s infinite}
.mastFlash{animation:mastFlash 2.2s infinite}

/* вода: три слоя с разной скоростью плюс блик по поверхности */
@keyframes waveA{from{transform:translateX(0)}to{transform:translateX(-90px)}}
@keyframes waveB{from{transform:translateX(0)}to{transform:translateX(-120px)}}
@keyframes waveC{from{transform:translateX(0)}to{transform:translateX(-70px)}}
@keyframes shimmer{0%,100%{opacity:.18}50%{opacity:.44}}
.waveA{animation:waveA 13s linear infinite}
.waveB{animation:waveB 9s linear infinite}
.waveC{animation:waveC 19s linear infinite}
.shimmer{animation:shimmer 6s ease-in-out infinite}

/* окна города зажигаются вразнобой */
@keyframes winBlink{0%,100%{opacity:.25}45%,55%{opacity:.95}}
.win{animation:winBlink 7s ease-in-out infinite}
.win:nth-child(3n){animation-duration:9s;animation-delay:-2s}
.win:nth-child(4n){animation-duration:11s;animation-delay:-5s}
.win:nth-child(5n){animation-duration:6s;animation-delay:-3.5s}

/* портовый кран возит стрелой */
@keyframes craneSwing{0%,100%{transform:rotate(-3deg)}50%{transform:rotate(3deg)}}
.craneArm{animation:craneSwing 14s ease-in-out infinite;transform-origin:12px 6px}

@media (prefers-reduced-motion: reduce){
  .lhLamp,.lhBeam,.lhSweep,.shipGo,.shipRoll,.navRed,.navGreen,.mastFlash,
  .waveA,.waveB,.waveC,.shimmer,.win,.craneArm{animation:none}
}
.wkhero .eyebrow{font-size:9px;font-weight:800;letter-spacing:1.2px;color:var(--cyan);position:relative}
body.light .wkhero .eyebrow{color:#0a6ea8}
.wkhero .greet{font-size:23px;font-weight:850;letter-spacing:-.6px;margin-top:12px;position:relative;max-width:200px}
.wkhero .sub{font-size:10px;font-weight:700;color:var(--muted);margin-top:5px;position:relative;max-width:200px}
.wkvessel{
  display:flex;align-items:center;gap:8px;margin-top:auto;padding-top:26px;
  font-size:9.5px;position:relative;flex-wrap:wrap;
}
.wkvessel .dot{width:8px;height:8px;border-radius:50%;background:var(--green);flex:none;
  box-shadow:0 0 8px rgba(38,214,157,.8)}
.wkvessel .dot.off{background:var(--dim);box-shadow:none}
.wkvessel .lb{font-weight:800;letter-spacing:.3px}
.wkvessel .nm{color:var(--muted)}
.wkvessel .st{color:var(--green);font-weight:800}
.wkvessel .st.off{color:var(--dim)}

/* --- подсказки ассистента --- */
.wksech{display:flex;align-items:baseline;justify-content:space-between;margin:20px 0 11px;gap:10px}
.wksech h3{font-size:15px;font-weight:850;margin:0;letter-spacing:-.3px}
.wksech a{font-size:9px;font-weight:800;color:var(--blue);cursor:pointer;letter-spacing:.4px}
.wkprompts{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.wkprompt{
  display:flex;align-items:center;gap:10px;padding:11px 10px;border-radius:12px;
  background:linear-gradient(180deg,#0d2435,#081a28);border:1px solid #1d4057;
  cursor:pointer;text-align:left;color:inherit;font-family:inherit;min-height:58px;
  transition:transform .12s,border-color .18s;
}
body.light .wkprompt{background:linear-gradient(180deg,#fff,#eef4fa);border-color:#c7d8e6}
.wkprompt:active{transform:scale(.975);border-color:var(--blue)}
.wkprompt .ic{
  width:30px;height:30px;flex:none;border-radius:50%;display:flex;
  align-items:center;justify-content:center;font-size:15px;font-weight:800;
}
.wkprompt .tx{min-width:0;display:flex;flex-direction:column;gap:3px}
.wkprompt .t1,.wkprompt .t2{display:block}
.wkprompt .t1{font-size:10.5px;font-weight:800;line-height:1.2}
.wkprompt .t2{font-size:8.5px;color:var(--muted);line-height:1.25}

/* --- сводка с мостика --- */
.wksnap{
  display:flex;gap:0;border-radius:14px;padding:15px 0;
  background:linear-gradient(180deg,#0d2435,#081a28);border:1px solid #1d4057;
}
body.light .wksnap{background:linear-gradient(180deg,#fff,#eef4fa);border-color:#c7d8e6}
.wksnap>div{flex:1;min-width:0;padding:0 14px}
.wksnap .divider{flex:none;width:1px;padding:0;background:#1d3b50;align-self:stretch}
body.light .wksnap .divider{background:#cddced}
.wklb{font-size:8px;font-weight:800;letter-spacing:.7px;color:var(--muted);text-transform:uppercase}
.wkbig{font-size:20px;font-weight:850;letter-spacing:-.5px;margin-top:6px;line-height:1.1}
.wkmid{font-size:14px;font-weight:800;font-variant-numeric:tabular-nums}
.wksm{font-size:9px;color:var(--muted);margin-top:3px}
.wkbar{height:5px;border-radius:3px;background:#203447;margin-top:11px;overflow:hidden}
body.light .wkbar{background:#d7e2ec}
.wkbar i{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,#8d5cff,#b968ff)}
.wkpct{font-size:9px;font-weight:800;color:var(--purple);margin-top:7px}
.wkduo{display:flex;gap:14px;margin-top:6px}
.wkok{
  width:30px;height:30px;border-radius:50%;background:#0d3b31;border:1px solid var(--green);
  color:var(--green);font-size:9px;font-weight:800;display:flex;align-items:center;justify-content:center;
  float:right;margin-top:-6px;
}
.wkok.warn{background:#3b2f0d;border-color:var(--amber);color:var(--amber)}

/* --- полоса тревоги --- */
.wkalert{
  display:flex;align-items:center;gap:11px;width:100%;margin-top:14px;padding:12px 13px;
  border-radius:12px;background:#211b20;border:1px solid #60333a;cursor:pointer;
  color:inherit;font-family:inherit;text-align:left;
}
body.light .wkalert{background:#fdeff0;border-color:#e9bcc0}
.wkalert.ok{background:#132a26;border-color:#265046}
body.light .wkalert.ok{background:#e8f7f1;border-color:#a9dcc9}
.wkalert .ic{
  width:26px;height:26px;flex:none;border-radius:50%;background:#4c2228;color:var(--hot);
  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;
}
.wkalert.ok .ic{background:#12463a;color:var(--green)}
.wkalert .tx{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.wkalert .t1,.wkalert .t2{display:block}
.wkalert .t1{font-size:10.5px;font-weight:800}
.wkalert .t2{font-size:8.5px;color:var(--muted);line-height:1.35}
.wkalert .ar{font-size:17px;color:var(--muted);flex:none}

/* --- кнопка ассистента --- */
.wkask{
  position:relative;margin-top:14px;border-radius:16px;overflow:hidden;
  background:#0a1c2b;border:1px solid #3d416e;padding:14px 13px 13px;
}
body.light .wkask{background:#f4f0ff;border-color:#cfc4ee}
.wkask::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:var(--ai)}
.wkask .top{display:flex;align-items:center;gap:12px}
.wkask .orb{
  width:40px;height:40px;flex:none;border-radius:50%;background:#102d4a;border:1px solid #4aaeff;
  display:flex;align-items:center;justify-content:center;gap:5px;
}
body.light .wkask .orb{background:#dceefb}
.wkask .orb i{width:6px;height:6px;border-radius:50%;display:block}
.wkask .orb i:first-child{background:var(--cyan)}
.wkask .orb i:last-child{background:var(--ai2)}
.wkask .t1{font-size:14px;font-weight:850}
.wkask .t2{font-size:8.5px;color:var(--muted);margin-top:2px}
.wkaskrow{display:flex;align-items:center;gap:9px;margin-top:12px}
.wkaskfield{
  flex:1;min-width:0;border-radius:8px;background:#0c2131;border:1px solid #31536a;
  padding:8px 11px;font-size:9.5px;color:var(--muted);cursor:pointer;text-align:left;
  font-family:inherit;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
body.light .wkaskfield{background:#fff;border-color:#c7d8e6}
.wkasksend{
  width:32px;height:32px;flex:none;border-radius:50%;background:var(--ai);border:none;
  color:#fff;font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;
}

/* ---- Нижняя навигация ----
   Ровно пять пунктов, ASK AI в середине и заметно крупнее остальных:
   это главное действие приложения, а не ещё одна вкладка. */
.tabs{
  position:fixed;bottom:0;left:0;right:0;z-index:1000;display:flex;
  justify-content:center;gap:0;
  background:rgba(7,23,37,.95);border-top:1px solid #1a3b51;
  backdrop-filter:blur(22px);padding:8px 6px calc(8px + env(safe-area-inset-bottom));
}
body.light .tabs{background:rgba(255,255,255,.96);border-top-color:var(--line)}
.tabsin{display:flex;width:100%;max-width:430px;align-items:flex-end}
.tab{
  flex:1;border:none;background:none;cursor:pointer;color:var(--dim);
  font-size:9px;font-weight:800;font-family:inherit;padding:4px 2px 2px;
  border-radius:var(--r-sm);position:relative;transition:color .24s;
  display:flex;flex-direction:column;align-items:center;gap:5px;
}
.tab .ic{
  width:38px;height:38px;border-radius:50%;background:#0b1d2b;
  display:flex;align-items:center;justify-content:center;
  transition:transform .3s cubic-bezier(.34,1.7,.5,1),background .24s;
}
body.light .tab .ic{background:#e6edf5}
.tab .ic svg{width:20px;height:20px}
.tab .lb{font-size:9px;font-weight:800;letter-spacing:.2px;white-space:nowrap}
.tab.on{color:var(--blue)}
.tab.on .ic{background:#0b2b42;transform:translateY(-2px)}
body.light .tab.on .ic{background:#d6eaf9}
/* центральная кнопка ассистента */
.tab-ask{flex:1.15}
.tab-ask .ic{
  width:52px;height:52px;background:var(--ai);
  border:2px solid #9a66ff;box-shadow:0 0 18px rgba(154,102,255,.45);
  font-size:13px;font-weight:850;color:#fff;letter-spacing:.5px;margin-top:-14px;
}
body.light .tab-ask .ic{background:var(--ai)}
.tab-ask.on .ic{background:var(--ai);transform:translateY(-2px) scale(1.04)}
.tab-ask{color:var(--purple)}
.tab-ask.on{color:var(--purple)}

/* ---- Переходы, скелетоны, пустые ---- */
section{animation:enter .38s cubic-bezier(.22,.95,.3,1)}
@keyframes enter{from{opacity:0;transform:translateY(13px) scale(.995)}to{opacity:1;transform:none}}
.up{animation:up .42s cubic-bezier(.24,1.2,.4,1) backwards}
@keyframes up{from{opacity:0;transform:translateY(15px)}to{opacity:1;transform:none}}
.sk{background:var(--surf);border-radius:var(--r-lg);position:relative;overflow:hidden;border:1px solid var(--line)}
.sk::after{content:'';position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent);animation:sh 1.5s infinite}
@keyframes sh{100%{transform:translateX(100%)}}
.sk.hero{height:186px;margin-bottom:15px}.sk.hull{height:118px;margin-bottom:17px}
.sk.card{height:78px;margin-bottom:11px}
.empty{text-align:center;padding:44px 20px;color:var(--muted);font-size:13.5px}
.empty .ic{font-size:40px;display:block;margin-bottom:12px;opacity:.42}
.offline{
  background:rgba(255,107,74,.13);border:1px solid rgba(255,107,74,.36);
  border-radius:var(--r-md);padding:12px 14px;font-size:12.5px;margin-bottom:14px;display:none;
}
.offline.on{display:block;animation:up .34s}
.hidden{display:none!important}
/* ---- Кнопка позиции с устройства ---- */
.geobtn{
  width:44px;height:44px;flex:none;border-radius:15px;cursor:pointer;
  background:var(--surf);border:1px solid var(--line);color:var(--muted);
  display:flex;align-items:center;justify-content:center;
  transition:transform .22s cubic-bezier(.34,1.6,.5,1),color .2s,border-color .2s;
}
.geobtn:active{transform:scale(.9)}
.geobtn.on{color:var(--ok);border-color:rgba(63,201,127,.4);background:rgba(63,201,127,.1)}
.geobtn.err{color:var(--hot);border-color:rgba(255,107,74,.4)}
.geobtn.busy{color:var(--amber);border-color:rgba(240,160,60,.4)}
.geobtn.busy .ico{animation:geospin 1.1s linear infinite}
.geobtn.off{color:var(--muted);opacity:.5}
.geobtn.off::after{content:'';position:absolute;width:26px;height:1.5px;background:var(--hot);
  transform:rotate(-45deg);border-radius:1px}
.geobtn{position:relative}
.mypos-ctl a{display:flex!important;align-items:center;justify-content:center;
  width:30px;height:30px;background:#12202f;color:#cfe0f2;border-radius:4px}
.mypos-ctl a:hover{background:#1b2f45}
@keyframes geospin{to{transform:rotate(360deg)}}
.geoline{
  display:flex;align-items:center;gap:9px;padding:11px 13px;margin-bottom:12px;
  border-radius:var(--r-md);background:var(--surf);border:1px solid var(--line);
  font-size:12px;color:var(--muted);cursor:pointer;
}
.geoline .ico{color:var(--amber);flex:none}
.geoline b{color:var(--text);font-weight:650;font-family:ui-monospace,monospace;font-size:12.5px}
.geouse{
  background:var(--surf2);border:1px solid var(--line);border-radius:var(--r-sm);
  color:var(--muted);font-size:11px;font-weight:650;font-family:inherit;
  padding:8px 11px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;margin-bottom:11px;
}
.geouse:active{border-color:var(--amber);color:var(--amber)}

/* ---- Тренажёр ЦИВ: корпус Furuno FS-2575C ----
   Сверено с фотографиями реальной станции. Сетка на клавиатуре --
   flexbox, не CSS grid: так надёжнее на разных WebView внутри Telegram.

   Экран вынесен над органами управления и занимает всю ширину корпуса:
   на телефоне трёхколоночная раскладка настоящего прибора оставляла
   дисплею меньше полутора сантиметров, читать на нём было нечего. */
.radio{
  background:linear-gradient(155deg,#48463f,#282621);
  border:1px solid #55534b;border-radius:12px;padding:12px 12px 14px;
  box-shadow:0 20px 46px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.05);
  max-width:520px;margin:0 auto;
}
.rplates{display:flex;justify-content:center;gap:8px;margin:0 0 9px;flex-wrap:wrap}
.rplate{
  background:#e9ecef;color:#15181c;font-size:10px;font-weight:800;letter-spacing:.3px;
  border-radius:3px;padding:5px 10px;text-align:center;line-height:1.25;
  border:1px solid #b8bec4;box-shadow:0 1px 2px rgba(0,0,0,.3);
}
.rhdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding:0 2px;gap:8px}
.rnameplate{
  background:#dfe3e6;color:#1a1d20;font-size:7.4px;font-weight:700;line-height:1.35;
  border-radius:2px;padding:3px 6px;border:1px solid #aab0b6;flex:1;min-width:0;
}
.rfuruno{
  flex:none;font-weight:800;font-size:15px;letter-spacing:1px;font-style:italic;
  background-image:linear-gradient(180deg,#e8ebee,#9ba1a8);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}

.rbody{display:flex;flex-direction:column;gap:9px}
.rctrls{display:flex;gap:8px;align-items:stretch}
.rleft{width:74px;flex:none;display:flex;flex-direction:column;align-items:center;gap:6px}
.rmid{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;gap:7px;padding-top:2px}
.rspeaker{width:100%;background:#1a1c1e;border-radius:5px;padding:6px 8px}
.rspeaker i{display:block;height:2.8px;background:#000;border-radius:2px;margin:2.8px 0}
.rknob{width:38px;height:38px;border-radius:50%;
  background:radial-gradient(circle at 35% 30%,#54595f,#1c1e20 72%);
  border:1px solid #61656b;position:relative;box-shadow:0 2px 4px rgba(0,0,0,.5)}
.rknob{touch-action:none;user-select:none;-webkit-user-select:none}
.rknob.turning{border-color:var(--amber);box-shadow:0 0 0 3px var(--amber-soft),0 2px 4px rgba(0,0,0,.5)}
.rbigknob{touch-action:none;user-select:none;-webkit-user-select:none}
.rbigknob.turning{border-color:var(--amber);box-shadow:0 0 0 3px var(--amber-soft),0 3px 6px rgba(0,0,0,.5)}
.knobval{
  position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
  font-size:11px;font-weight:800;color:var(--amber);pointer-events:none;
  text-shadow:0 0 4px rgba(0,0,0,.9);opacity:0;transition:opacity .15s;
}
.rknob.turning .knobval,.rbigknob.turning .knobval{opacity:1}
.rknob::after{content:'';position:absolute;top:3px;left:50%;width:2px;height:12px;
  background:#8a9096;transform:translateX(-50%);border-radius:1px}
.rklabel{font-size:7.2px;color:#a8aeb4;text-align:center;font-weight:700;letter-spacing:.2px;line-height:1.2}
.rleds{display:flex;gap:10px;align-items:center;margin-top:1px}
.rled{display:flex;align-items:center;gap:4px}
.rled i{width:6.5px;height:6.5px;border-radius:50%;background:#3a3d40;flex:none}
.rled i.amber{background:#ffb020;box-shadow:0 0 5px #ffb020}
.rled i.green{background:#3fc97f;box-shadow:0 0 5px #3fc97f}
.rled span{font-size:7px;color:#a8aeb4;font-weight:700}

.rdistwrap{width:100%;text-align:center}
.rdistcover{
  width:58px;height:42px;margin:0 auto;position:relative;cursor:pointer;
  background:linear-gradient(160deg,rgba(220,230,240,.1),rgba(220,230,240,.02));
  border:1.5px solid #62666c;border-radius:5px;
}
.rdistbtn{position:absolute;inset:6px;border-radius:3px;
  background:linear-gradient(160deg,#f0503e,#b8281a);border:1px solid #ff7a68;
  display:flex;align-items:center;justify-content:center;
  font-size:6.4px;font-weight:800;color:#ffe4de;letter-spacing:.3px;
  box-shadow:0 0 6px rgba(240,80,62,.55), inset 0 1px 1px rgba(255,255,255,.3)}
.rdistbtn.arming{animation:rarmpulse .45s infinite}
@keyframes rarmpulse{50%{background:linear-gradient(160deg,#ff7a68,#e0402c);box-shadow:0 0 14px rgba(255,90,68,.85)}}
.rpwroff{font-size:7px;color:#a8aeb4;font-weight:700;margin-top:4px;letter-spacing:.3px}
.rdistcap{font-size:6.6px;color:#8a9098;text-align:center;line-height:1.35;margin-top:4px;padding:0 3px;max-width:150px}

/* --- экран --- */
.rscreen{width:100%;display:flex;gap:6px;align-items:stretch}
.rsoft{width:16px;flex:none;display:flex;flex-direction:column;justify-content:space-evenly;padding:26px 0}
.rsoft i{display:block;height:2px;background:#8a9096;border-radius:1px}
.lcd{
  flex:1;min-width:0;
  background:linear-gradient(175deg,#0f2440,#0a1a30);
  border:2px solid #05070a;border-radius:5px;padding:9px 10px;
  min-height:300px;display:flex;flex-direction:column;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  color:#dce8f4;font-size:12px;position:relative;overflow:hidden;
  transition:filter .18s;
}
/* Яркость и контраст: дневной, ночной и зелёный режимы -- как кнопка
   BRILL на настоящей станции. Ночной приглушён и уведён в красный,
   чтобы не сажать адаптацию глаз на тёмном мостике. */
.lcd.br-day{filter:brightness(1.14) contrast(1.08) saturate(1.05)}
.lcd.br-night{filter:brightness(.5) contrast(1.2) sepia(.6) hue-rotate(-38deg) saturate(2.8)}
.lcd.br-green{filter:hue-rotate(-88deg) saturate(1.35) brightness(1.04)}
.lcd.alert{background:linear-gradient(175deg,#3a1210,#280a08)}
.lcdtop{display:flex;justify-content:space-between;align-items:center;font-size:9.6px;
  color:#8fa8c4;margin-bottom:5px;flex:none;gap:6px}
.lcdtop .ssb{border:1px solid #2c4468;border-radius:8px;padding:0 5px;font-weight:800;color:#cfe0f2}
.lcdfoot{
  display:flex;justify-content:space-between;gap:6px;font-size:8.6px;color:#8fa8c4;
  border-top:1px solid #24406a;margin-top:auto;padding-top:4px;flex:none;
}
.lcdfoot b{color:#fff;font-weight:800}
.lcdfoot .k{border:1px solid #2c4468;border-radius:3px;padding:0 3px;color:#cfe0f2;font-weight:800}
.lcdfoot .go{color:#ffd79a;font-weight:800}
.lcdfoot .go.on{background:#ffd79a;color:#1a1408;border-radius:3px;padding:0 4px}

/* заголовок раздела внутри экрана */
.lhead{background:#1e3155;color:#e8eef5;font-size:11px;font-weight:800;letter-spacing:.4px;
  padding:2px 6px;margin-bottom:5px;flex:none}
.lhead.red{background:#a5231a}

/* --- дежурный экран: CH / TX / RX --- */
.lrow1{display:flex;gap:5px;align-items:stretch;margin-bottom:5px;flex:none}
.ldist{
  background:#1a2c48;color:#e8eef5;font-size:8.6px;font-weight:800;text-align:center;
  border-radius:2px;padding:3px;line-height:1.2;flex:none;width:34px;
  display:flex;align-items:center;justify-content:center;border:1px solid #2c4468;
}
.ldist.alert{background:#c0281c;animation:rdblink 1s steps(2) infinite}
@keyframes rdblink{50%{opacity:.4}}
.lch{
  flex:1;min-width:0;background:linear-gradient(180deg,#e9dfc4,#d8cba4);color:#1a1408;
  border-radius:2px;padding:3px 8px;display:flex;align-items:baseline;gap:6px;
  border:2px solid transparent;
}
.lch.sel{border-color:#ffb020;box-shadow:0 0 0 2px rgba(255,176,32,.35)}
.lch.edit{border-color:#fff;animation:ledit .8s steps(2) infinite}
@keyframes ledit{50%{box-shadow:0 0 0 3px rgba(255,255,255,.6)}}
.lch .l{font-size:9px;font-weight:800}
.lch .n{font-size:23px;font-weight:800;letter-spacing:.3px}
.lch .bd{font-size:8px;font-weight:800;margin-left:auto;opacity:.75}
.lnb{flex:none;width:20px;display:flex;align-items:center;justify-content:center;
  font-size:7.6px;font-weight:800;color:#9db6d4;border:1px solid #2c4468;border-radius:50%;}
.lmenu{flex:none;width:60px;display:flex;flex-direction:column;justify-content:space-around;gap:1px}
.lmenu .mi{display:flex;align-items:center;gap:3px;font-size:7.4px;color:#c2d4e8;line-height:1.05}
.lmenu .mi b{color:#fff;font-weight:800}
.lfreq{font-size:11px;display:flex;gap:6px;align-items:baseline;margin:3px 0;flex:none;
  padding:1px 4px;border:2px solid transparent;border-radius:3px}
.lfreq.sel{border-color:#5ba6e8;background:rgba(93,166,232,.14)}
.lfreq.edit{border-color:#ffb020;background:rgba(255,176,32,.16);animation:ledit .8s steps(2) infinite}
.lfreq .lb{color:#8fa8c4;width:20px;font-weight:800}
.lfreq .v{color:#fff;font-weight:700;font-size:13px}
.lfreq .u{color:#8fa8c4}
.lmode{font-size:8.6px;color:#9db6d4;display:flex;gap:9px;margin:4px 0 3px;font-weight:700;flex:none}
.lmeter{font-size:8px;color:#8fa8c4;display:flex;align-items:center;gap:4px;margin-bottom:3px;flex:none}
.lbars{display:flex;gap:1.5px}
.lbars i{width:3.4px;height:8px;background:#274568;border-radius:.5px;display:block}
.lbars i.on{background:#5ba6e8}
.lag{display:flex;justify-content:space-between;align-items:center;font-size:8px;color:#9db6d4;margin-bottom:4px;flex:none}
.lag .attb{border:1px solid #2c4468;border-radius:8px;padding:1px 7px;font-weight:800}
.lgps{background:#152540;border:1px solid #24406a;border-radius:2px;padding:4px 6px;
  display:flex;justify-content:space-between;font-size:8.4px;color:#cfe0f2;margin-bottom:4px;flex:none}
.lgps b{color:#fff;font-weight:800;display:block;font-size:8px;text-align:right;opacity:.85}
.lmem{display:flex;gap:2px;flex:none}
.lmem i{flex:1;height:9px;border:1px solid #24406a;border-radius:1px;display:block}

/* --- MENU: слева разделы, справа их содержимое --- */
.lmenuwrap{flex:1;display:flex;gap:6px;min-height:0}
.lmcol{
  width:96px;flex:none;border:1px solid #3d5b86;background:#0c1e38;
  padding:2px;overflow-y:auto;
}
.lmcol::-webkit-scrollbar,.lmpanel::-webkit-scrollbar,.lmenuscreen::-webkit-scrollbar,
.llog::-webkit-scrollbar,.laddr::-webkit-scrollbar{width:0}
.lmcap{background:#7fd4ff;color:#04121f;font-size:8.6px;font-weight:800;padding:0 4px;letter-spacing:.5px}
.lmi{display:flex;align-items:center;gap:4px;font-size:9.6px;padding:1.5px 3px;color:#dce8f4;line-height:1.35}
.lmi .nn{
  flex:none;width:11px;height:11px;border:1px solid #5f83b5;border-radius:2px;
  display:flex;align-items:center;justify-content:center;font-size:7.4px;font-weight:800;color:#9db6d4;
}
.lmi.dim{color:#5c7799}
.lmi.dim .nn{visibility:hidden}
.lmi.sel{background:#c9d6e4;color:#0b1728;font-weight:800}
.lmi.sel .nn{border-color:#0b1728;color:#0b1728}
.lmi.act{outline:1px solid #ffb020}
.lmpanel{flex:1;min-width:0;border:1px solid #3d5b86;background:#08182e;padding:2px 3px;overflow-y:auto}
.lmpanel .ph{background:#c9d6e4;color:#0b1728;font-size:9px;font-weight:800;padding:0 4px;margin-bottom:2px}
.lmr{display:flex;align-items:center;gap:5px;font-size:9.6px;padding:1.5px 3px;color:#dce8f4;line-height:1.4}
.lmr .sq{width:7px;height:7px;flex:none;border:1px solid #5f83b5;background:#123054}
.lmr .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lmr .vl{color:#9fc4ee;font-weight:700;flex:none}
.lmr .ar{color:#9db6d4;flex:none;font-weight:800}
.lmr.sel{background:#c9d6e4;color:#0b1728}
.lmr.sel .vl{color:#12365e}
.lmr.sel .ar{color:#0b1728}
.lmr.dim{color:#5c7799}

/* --- COMPOSE MESSAGE --- */
.lcomp{flex:1;min-height:0;overflow-y:auto;position:relative}
.lcrow{display:flex;align-items:baseline;gap:6px;font-size:11px;padding:2px 3px;line-height:1.45}
.lcrow .k{width:76px;flex:none;color:#dce8f4;font-weight:700}
.lcrow .v{flex:1;min-width:0;color:#fff;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lcrow.sel{background:#c9d6e4}
.lcrow.sel .k,.lcrow.sel .v{color:#0b1728}
.lcrow.edit{background:#ffd79a}
.lcrow.edit .k,.lcrow.edit .v{color:#1a1408}
.lcrow.dim .v{color:#8fa8c4}
.lpop{
  position:absolute;left:74px;right:6px;top:0;background:#08182e;border:1px solid #7fa4d4;
  padding:2px 3px;max-height:100%;overflow-y:auto;
}
.lpop .ph{color:#9db6d4;font-size:9px;border-bottom:1px dashed #5f83b5;margin-bottom:2px;padding-bottom:1px}
.lpop .it{font-size:10.4px;padding:1.5px 4px;color:#dce8f4;line-height:1.4}
.lpop .it.sel{background:#c9d6e4;color:#0b1728;font-weight:800}
.lnote{font-size:9px;color:#9db6d4;text-align:center;line-height:1.4;margin-top:5px;flex:none}
.lnote b{color:#fff;display:block;font-weight:800}

/* --- WATCH KEEPING / SCAN --- */
.lwk{flex:1;min-height:0;display:flex;flex-direction:column;gap:3px}
.lwkcap{font-size:9.4px;color:#dce8f4;display:flex;gap:14px;font-weight:800;letter-spacing:.4px}
.lwktab{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #3d5b86}
.lwktab i{
  border:1px solid #24406a;font-style:normal;font-size:10.4px;color:#dce8f4;
  padding:2px 4px;min-height:18px;display:flex;align-items:center;gap:3px;
  font-variant-numeric:tabular-nums;
}
.lwktab i.on{background:#c9d6e4;color:#0b1728;font-weight:800}
.lwktab i.hit{background:#ffb020;color:#1a1408;font-weight:800}
.lwktab i b{color:#7fd4ff;font-weight:800}
.lwktab i.on b{color:#0b1728}
.lscanmsg{font-size:9.4px;color:#ffd79a;text-align:center;min-height:13px;font-weight:700}

/* --- список/лог на весь экран --- */
.lmenuscreen{flex:1;overflow-y:auto;font-size:12px;line-height:1.75}
.lmenuscreen .it{padding-left:2px}
.lmenuscreen .it.sel{background:rgba(93,166,232,.2);border-left:2px solid #5ba6e8;padding-left:7px;margin-left:-9px;color:#fff}
.llog{flex:1;overflow-y:auto;font-size:11.4px;line-height:1.6;white-space:pre-wrap;color:#dce8f4}
.laddr{flex:1;overflow-y:auto;font-size:10.6px;line-height:1.6}
.laddr .it{display:flex;gap:6px;padding:1px 3px}
.laddr .it.sel{background:#c9d6e4;color:#0b1728;font-weight:800}
.laddr .it .mm{color:#9fc4ee;font-variant-numeric:tabular-nums}
.laddr .it.sel .mm{color:#12365e}
.blink{animation:lcdblink 1.1s steps(2) infinite}
@keyframes lcdblink{50%{opacity:.25}}

/* --- клавиатура --- */
.rright{width:150px;flex:none;display:flex;flex-direction:column;gap:5px}
.rkgrid{display:flex;flex-wrap:wrap;gap:4px}
.rkgrid .rkey{width:calc((100% - 8px)/3)}
.rfngrid{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}
.rfngrid .rkey{width:calc((100% - 4px)/2)}
.rkey{
  background:linear-gradient(180deg,#3d4249,#26292d);border:1px solid #4a4f55;border-radius:5px;
  padding:6px 2px;text-align:center;box-shadow:0 1.5px 0 #17181a, inset 0 1px 0 rgba(255,255,255,.08);
  cursor:pointer;transition:transform .08s;box-sizing:border-box;
}
.rkey:active{transform:translateY(1.5px);box-shadow:0 0 0 #17181a, inset 0 1px 0 rgba(255,255,255,.05)}
.rkey .kt{font-size:8.6px;font-weight:800;color:#e6eaee;line-height:1}
.rkey .ks{font-size:5.8px;font-weight:700;color:#8a9098;margin-top:1px}
.rkey.on{background:linear-gradient(180deg,#8a6a24,#5f4715);border-color:#c79a3a}
.rkey.on .kt{color:#ffe9c2}
.rkey.ok{background:linear-gradient(180deg,#2f6b46,#1f4a30);border-color:#3d7d54}
.rkey.ok .kt{color:#d8ffe6}
.rkey.warn{background:linear-gradient(180deg,#7a5a20,#5a4116);border-color:#8d6a28}
.rkey.warn .kt{color:#ffe9c2}
.rbigknob{
  width:62px;height:62px;border-radius:50%;margin:6px auto 2px;cursor:pointer;
  background:radial-gradient(circle at 32% 28%,#565b62,#1c1e20 70%);
  border:1px solid #63686e;box-shadow:0 3px 6px rgba(0,0,0,.5);position:relative;
}
.rbigknob.pushed{border-color:#ffb020;box-shadow:0 0 0 3px rgba(255,176,32,.35),0 3px 6px rgba(0,0,0,.5)}
.rbigknob .kdial{
  position:absolute;top:0;left:0;right:0;bottom:0;border-radius:50%;
  transition:none;pointer-events:none;
}
.rbigknob .kdial::after{content:'';position:absolute;top:6px;left:50%;width:3.5px;height:17px;
  background:#a2a8ae;transform:translateX(-50%);border-radius:1.5px}
.rbigknob .cap{position:absolute;bottom:-10px;left:50%;transform:translateX(-50%);
  font-size:5.8px;color:#a8aeb4;font-weight:700;white-space:nowrap}

.rcompose{display:flex;gap:7px;align-items:flex-end;margin-top:14px}
.rcbtn{
  flex:1;background:linear-gradient(180deg,#3d4249,#26292d);border:1px solid #4a4f55;border-radius:5px;
  padding:8px 3px;font-size:7.4px;font-weight:800;color:#dfe4e8;text-align:center;line-height:1.15;
  cursor:pointer;
}
.rcbtn.on{background:linear-gradient(180deg,#8a6a24,#5f4715);border-color:#c79a3a;color:#ffe9c2}
.rbracket{border-top:1px solid #4a4f55;margin-top:3px;padding-top:2px;font-size:5.6px;
  color:#8a9098;text-align:center;font-weight:700;letter-spacing:.2px}

.rfooter{
  background:#e9ecef;color:#15181c;font-size:8px;font-weight:800;letter-spacing:.3px;
  border-radius:3px;padding:6px 12px;text-align:center;margin:10px auto 0;max-width:180px;
  border:1px solid #b8bec4;box-shadow:0 1px 2px rgba(0,0,0,.3);
}
/* Подсказка по органам управления под корпусом */
.rlegend2{
  display:flex;flex-wrap:wrap;gap:6px;margin-top:11px;justify-content:center;
}
.rlegend2 span{
  font-size:10.5px;color:var(--muted);background:var(--surf2);border:1px solid var(--line);
  border-radius:8px;padding:4px 9px;
}
.rlegend2 b{color:var(--amber);font-weight:800}

/* На широком экране корпус ближе к оригиналу: экран остаётся сверху,
   но органы управления расходятся шире и всё становится крупнее. */
@media(min-width:520px){
  .lcd{min-height:340px;font-size:13px}
  .rleft{width:88px}
  .rright{width:172px}
  .rkey .kt{font-size:9.6px}
}
.dsctip{
  background:var(--surf);border:1px solid var(--line);border-left:3px solid var(--amber);
  border-radius:var(--r-md);padding:12px 14px;margin-top:13px;font-size:12.5px;
  line-height:1.5;color:var(--muted);
}
.dsctip b{color:var(--text);display:block;margin-bottom:4px;font-size:12px}
.examhead{
  background:linear-gradient(140deg,rgba(240,160,60,.17),rgba(255,139,61,.04));
  border:1px solid rgba(240,160,60,.32);border-radius:var(--r-lg);padding:14px;margin-bottom:13px;
}
.examhead .q{font-size:14px;font-weight:700;line-height:1.4}
.examhead .n{font-size:11px;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:.7px}
.verdict{border-radius:var(--r-md);padding:13px 14px;margin-top:12px;font-size:12.5px;line-height:1.5}
.verdict.ok{background:rgba(63,201,127,.13);border:1px solid rgba(63,201,127,.36)}
.verdict.no{background:rgba(255,107,74,.13);border:1px solid rgba(255,107,74,.36)}
.verdict b{display:block;margin-bottom:5px;font-size:13px}

/* ---- EPIRB / SART: карточка оборудования ----
   Силуэты проверены рендером в headless-браузере: узнаваемый оранжевый
   корпус, антенна, купол/строб у EPIRB, поворотный переключатель у SART. */
.eqhero{
  background:linear-gradient(160deg,#153c60,#0c2138);border:1px solid var(--line);
  border-radius:var(--r-lg);padding:18px 15px;display:flex;align-items:center;gap:16px;
  box-shadow:var(--sh);
}
.eqhero svg{width:76px;flex:none}
.eqinfo{flex:1;min-width:0}
.eqinfo .nm{font-size:16px;font-weight:800;letter-spacing:-.3px}
.eqinfo .md{font-size:11px;color:#9db6d4;margin-top:2px}
.eqstatus{display:inline-flex;align-items:center;gap:6px;font-size:10px;font-weight:750;
  border-radius:20px;padding:4px 10px;margin-top:8px}
.eqstatus.ok{background:rgba(63,201,127,.16);color:#6fe3a6;border:1px solid rgba(63,201,127,.34)}
.eqstatus.watch{background:rgba(240,160,60,.16);color:#ffc372;border:1px solid rgba(240,160,60,.34)}
.eqstatus.soon{background:rgba(255,139,61,.18);color:#ffb066;border:1px solid rgba(255,139,61,.4)}
.eqstatus.expired{background:rgba(255,107,74,.18);color:#ff9080;border:1px solid rgba(255,107,74,.4)}
.eqstatus.unknown{background:rgba(133,150,172,.14);color:#9aabbd;border:1px solid rgba(133,150,172,.28)}

.eqchk{
  display:flex;align-items:center;gap:11px;padding:12px 13px;border-radius:var(--r-md);
  background:var(--surf);border:1px solid var(--line);margin-bottom:8px;cursor:pointer;
}
.eqchk .box{
  width:21px;height:21px;flex:none;border-radius:6px;border:1.5px solid var(--line);
  display:flex;align-items:center;justify-content:center;transition:all .18s;
}
.eqchk.on .box{background:var(--ok);border-color:var(--ok);color:#0b1e14}
.eqchk .t{font-size:12.5px;font-weight:600;flex:1}
.eqchk.on .t{color:var(--muted);text-decoration:line-through;text-decoration-color:rgba(133,150,172,.5)}
.eqprogress{
  height:5px;border-radius:3px;background:var(--surf2);overflow:hidden;margin:11px 0 15px;
}
.eqprogress i{display:block;height:100%;background:linear-gradient(90deg,var(--amber),var(--amber2));
  border-radius:3px;transition:width .3s}

.eqsteps{counter-reset:step}
.eqstep{
  display:flex;gap:12px;padding:13px 0;border-bottom:1px solid var(--line);
}
.eqstep:last-child{border-bottom:none}
.eqstep .num{
  counter-increment:step;flex:none;width:26px;height:26px;border-radius:50%;
  background:var(--amber-soft);color:var(--amber);font-weight:800;font-size:12px;
  display:flex;align-items:center;justify-content:center;
}
.eqstep .num::before{content:counter(step)}
.eqstep .txt{flex:1;min-width:0}
.eqstep .txt .st{font-size:13px;font-weight:700}
.eqstep .txt .sd{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.45}

.eqhist{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:var(--r-sm);
  background:var(--surf2);margin-bottom:7px}
.eqhist .dot{width:9px;height:9px;border-radius:50%;flex:none}
.eqhist .dot.pass{background:var(--ok);box-shadow:0 0 6px rgba(63,201,127,.6)}
.eqhist .dot.fail{background:var(--hot);box-shadow:0 0 6px rgba(255,107,74,.6)}
.eqhist .dt{flex:1;font-size:12px;color:var(--text)}
.eqhist .rs{font-size:10.5px;font-weight:750;text-transform:uppercase;letter-spacing:.4px}
.eqhist .rs.pass{color:var(--ok)}
.eqhist .rs.fail{color:var(--hot)}

.eqfield{margin-bottom:11px}
.eqfield label{display:block;font-size:10.5px;color:var(--muted);margin-bottom:6px;
  text-transform:uppercase;letter-spacing:.5px}
.eqfield input{
  width:100%;background:var(--surf);border:1px solid var(--line);color:var(--text);
  border-radius:var(--r-sm);padding:11px 13px;font-size:14px;font-family:inherit;outline:none;
}
.eqfield input:focus{border-color:var(--amber)}

/* ---- EPIRB / SART: живые органы управления ---- */
.eqdev{flex:none;display:flex;flex-direction:column;align-items:center;gap:9px}
.eqhero.alarm{border-color:rgba(255,107,74,.5);
  background:linear-gradient(160deg,#4a1d18,#2a0f0c);animation:eqalarm 1.4s ease-in-out infinite}
@keyframes eqalarm{50%{border-color:rgba(255,107,74,.85)}}
.eqctl{display:flex;gap:6px}
.eqbtn{
  border:1px solid #4a4f55;border-radius:8px;padding:7px 11px;cursor:pointer;
  font-family:inherit;font-size:10.5px;font-weight:800;letter-spacing:.4px;
  background:linear-gradient(180deg,#3d4249,#26292d);color:#dfe4e8;
  box-shadow:0 2px 0 #17181a;transition:transform .08s;
}
.eqbtn:active{transform:translateY(2px);box-shadow:0 0 0 #17181a}
.eqbtn.test.holding{background:linear-gradient(180deg,#f0a03c,#c07a20);color:#16232f;
  animation:eqhold .4s infinite}
@keyframes eqhold{50%{background:linear-gradient(180deg,#ffc372,#e09030)}}
.eqbtn.arm{background:linear-gradient(180deg,#6b2822,#43140f);color:#ffb3a8;border-color:#8d3a30}
.eqbtn.arm.on{background:linear-gradient(180deg,#f0503e,#b8281a);color:#fff;border-color:#ff7a68;
  box-shadow:0 0 12px rgba(240,80,62,.6)}

.eqsw{display:flex;flex-direction:column;gap:4px;width:74px}
.swpos{
  border:1px solid #4a4f55;border-radius:7px;padding:6px 4px;cursor:pointer;
  font-family:inherit;font-size:9.5px;font-weight:800;letter-spacing:.5px;
  background:linear-gradient(180deg,#3d4249,#26292d);color:#9aa0a6;transition:all .15s;
}
.swpos.on.off{background:linear-gradient(180deg,#4a4f55,#32363b);color:#e6eaee}
.swpos.on.test{background:linear-gradient(180deg,#f0a03c,#c07a20);color:#16232f;
  box-shadow:0 0 10px rgba(240,160,60,.5)}
.swpos.on.on{background:linear-gradient(180deg,#f0503e,#b8281a);color:#fff;
  box-shadow:0 0 12px rgba(240,80,62,.6)}

.eqleds{display:flex;flex-wrap:wrap;gap:9px;margin-top:10px}
.eqled{display:flex;align-items:center;gap:5px}
.eqled i{width:8px;height:8px;border-radius:50%;background:#2a3038;flex:none;
  border:1px solid rgba(255,255,255,.08);transition:all .2s}
.eqled i.on.green{background:#3fc97f;box-shadow:0 0 8px #3fc97f;border-color:#3fc97f}
.eqled i.on.amber{background:#ffb020;box-shadow:0 0 8px #ffb020;border-color:#ffb020}
.eqled i.on.white{background:#fff;box-shadow:0 0 10px #fff;border-color:#fff}
.eqled i.on.red{background:#ff6b4a;box-shadow:0 0 10px #ff6b4a;border-color:#ff6b4a}
.eqled i.blink{animation:eqblink .55s steps(2) infinite}
@keyframes eqblink{50%{opacity:.25}}
.eqled span{font-size:8.5px;font-weight:750;color:#9db6d4;letter-spacing:.3px}

.eqphase{
  background:var(--surf);border:1px solid var(--line);border-left:3px solid var(--amber);
  border-radius:var(--r-md);padding:12px 14px;margin-top:11px;font-size:12.5px;
  line-height:1.5;color:var(--muted);
}
.eqphase.alarm{border-left-color:var(--hot);background:rgba(255,107,74,.1);color:#ffb3a8;font-weight:650}

/* ---- Радарная отметка SART ---- */
.ppiwrap{background:#04140c;border:2px solid #0a2818;border-radius:var(--r-lg);padding:8px;
  box-shadow:var(--sh);margin-bottom:11px}
/* Квадрат гарантированной пропорции через padding-top, а не только через
   viewBox у самого svg -- на части WebView без явной высоты контейнер
   схлопывается в полоску, даже если у svg есть viewBox. */
.ppiratio{width:100%;padding-top:100%;position:relative}
.ppiratio svg{position:absolute;top:0;left:0;right:0;bottom:0;width:100%;height:100%;display:block}
.sweepline{animation:sartsweep 4s linear infinite;transform-origin:150px 150px}
@keyframes sartsweep{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
.rngbtns{display:flex;gap:7px;margin-bottom:15px}
.rngbtn{
  flex:1;background:var(--surf2);border:1px solid var(--line);border-radius:var(--r-sm);
  padding:10px 4px;text-align:center;font-size:11.5px;font-weight:700;color:var(--muted);
  cursor:pointer;font-family:inherit;
}
.rngbtn.on{background:linear-gradient(140deg,var(--amber),var(--amber2));color:var(--accent-text);border-color:transparent}

/* ---- Визуализация тракта сигнала ---- */
.satwrap{background:radial-gradient(ellipse at 50% 120%,#0d2b4a,#040a12 70%);
  border:1px solid #1a3550;border-radius:var(--r-lg);padding:6px;overflow:hidden;margin-bottom:11px}
.satwrap svg{width:100%;display:block}
.vzbeam{animation:vzpulse 1.6s ease-in-out infinite}
.vzbeam2{animation:vzdash 1.1s linear infinite}
@keyframes vzpulse{50%{opacity:.35}}
@keyframes vzdash{to{stroke-dashoffset:-18}}
.bviewwrap{background:#050d16;border:1px solid #16304a;border-radius:var(--r-lg);
  padding:8px;overflow:hidden;margin-bottom:11px}
.bviewwrap svg{width:100%;display:block}

.satchain{display:flex;flex-direction:column;gap:2px}
.satstep{display:flex;align-items:flex-start;gap:10px;padding:7px 2px;opacity:.42}
.satstep.done{opacity:1}
.satstep.now{opacity:1}
.satstep i{
  width:9px;height:9px;border-radius:50%;flex:none;margin-top:4px;
  background:var(--surf2);border:1.5px solid var(--line);
}
.satstep.done i{background:var(--ok);border-color:var(--ok)}
.satstep.now i{background:var(--amber);border-color:var(--amber);
  box-shadow:0 0 0 4px var(--amber-soft);animation:eqblink .7s steps(2) infinite}
.satstep .ss{font-size:12.5px;font-weight:650}
.satstep.now .ss{color:var(--amber)}
.satstep .sd{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.45}

/* ---- Шапка раздела: кнопка назад и название в одной строке ---- */
.vhead{
  display:flex;align-items:center;gap:11px;margin:0 0 14px;
  padding-top:2px;
}
.vhead .vback{
  width:38px;height:38px;flex:none;border-radius:12px;cursor:pointer;
  background:var(--surf);border:1px solid var(--line);color:var(--text);
  display:flex;align-items:center;justify-content:center;font-family:inherit;
  transition:transform .2s cubic-bezier(.34,1.6,.5,1),border-color .2s;
}
.vhead .vback:active{transform:scale(.9);border-color:var(--amber)}
.vhead h3{
  margin:0;font-size:19px;font-weight:800;letter-spacing:-.4px;
  flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.vhead .vsub{font-size:11px;color:var(--muted);font-weight:600;flex:none}

/* ---- Тропические циклоны ---- */
.cycroute{display:flex;align-items:center;gap:7px;padding:10px 13px;margin-bottom:12px;
  border-radius:var(--r-md);background:var(--surf2);border:1px solid var(--line);
  font-size:12px;color:var(--muted);font-weight:600}
.cyccard{
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-lg);
  padding:15px;margin-bottom:11px;position:relative;overflow:hidden;
}
.cyccard::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--muted);opacity:.5}
.cyccard.critical::before{background:linear-gradient(180deg,#ff6b4a,#d8402f);opacity:1}
.cyccard.warning::before{background:linear-gradient(180deg,#ff8b3d,#e0701f);opacity:1}
.cyccard.watch::before{background:linear-gradient(180deg,#f0a03c,#c07a20);opacity:1}
.cyccard.critical{border-color:rgba(255,107,74,.4)}
.cychead{display:flex;align-items:center;justify-content:space-between;gap:9px;margin-bottom:3px}
.cycname{font-size:17px;font-weight:800;letter-spacing:-.3px}
.cyctag{font-size:10px;font-weight:800;border-radius:20px;padding:3px 10px;text-transform:uppercase;letter-spacing:.4px}
.cyctag.critical{background:rgba(255,107,74,.18);color:#ff9080;border:1px solid rgba(255,107,74,.4)}
.cyctag.warning{background:rgba(255,139,61,.18);color:#ffb066;border:1px solid rgba(255,139,61,.4)}
.cyctag.watch{background:rgba(240,160,60,.16);color:#ffc372;border:1px solid rgba(240,160,60,.34)}
.cyctag.info{background:rgba(133,150,172,.14);color:#9aabbd;border:1px solid rgba(133,150,172,.28)}
.cycsub{font-size:12px;color:var(--muted);margin-bottom:11px}
.cycdist{background:var(--surf2);border-radius:var(--r-md);padding:11px 12px;margin-bottom:11px}
.cycdist .cd{display:flex;justify-content:space-between;align-items:baseline;gap:9px;padding:4px 0;font-size:12px;color:var(--muted)}
.cycdist .cd b{color:var(--text);font-family:ui-monospace,monospace;font-weight:700;white-space:nowrap}
.cycdist .cd.hi b{color:var(--amber);font-size:15px}
.cycrows .cr{display:flex;justify-content:space-between;align-items:center;gap:9px;
  padding:6px 0;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted)}
.cycrows .cr:last-child{border-bottom:none}
.cycrows .cr b{color:var(--text);font-family:ui-monospace,monospace;font-weight:650;font-size:11.5px;text-align:right}
.cycarrow{display:inline-block;color:var(--amber);margin-right:4px;font-weight:800}
.cycfc{margin-top:9px;background:var(--surf2);border-radius:var(--r-sm);padding:9px 11px}
.fcrow{display:flex;justify-content:space-between;gap:8px;padding:5px 0;font-size:11px;
  color:var(--muted);font-family:ui-monospace,monospace;border-bottom:1px solid var(--line)}
.fcrow:last-child{border-bottom:none}
.fcrow .fp{color:var(--text)}
.fcrow .fw{color:var(--amber);font-weight:700}

.arow .auto{
  font-style:normal;font-size:9px;font-weight:750;color:var(--ok);
  background:rgba(63,201,127,.14);border-radius:6px;padding:1px 5px;margin-left:5px;
}
.needq{font-size:12px;color:var(--amber);margin-bottom:9px;font-weight:650}
.needf{display:flex;flex-direction:column;gap:7px;margin-bottom:10px}
.needin{
  background:var(--surf2);border:1px solid var(--line);color:var(--text);
  border-radius:var(--r-sm);padding:11px 13px;font-size:14px;font-family:inherit;outline:none;
  -webkit-appearance:none;
}
.needin:focus{border-color:var(--amber)}
.amsg.colreg{border-left:3px solid var(--amber)}

/* ---- Ask WatchKeeper ---- */
.askbox{
  min-height:200px;padding-bottom:8px;
}
.askintro{text-align:center;padding:26px 14px 18px}
.askintro .ai{color:var(--amber);margin-bottom:11px}
.askintro .at{font-size:17px;font-weight:800;letter-spacing:-.3px}
.askintro .as{font-size:12.5px;color:var(--muted);margin-top:7px;line-height:1.5;max-width:300px;
  margin-left:auto;margin-right:auto}
.askex{display:flex;flex-direction:column;gap:8px;margin-bottom:14px}
.exbtn{
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-md);
  padding:12px 14px;font-size:12.5px;color:var(--muted);text-align:left;
  cursor:pointer;font-family:inherit;line-height:1.4;
}
.exbtn:active{border-color:var(--amber);color:var(--text)}

.amsg{margin-bottom:11px;font-size:13.5px;line-height:1.5}
.amsg.me{
  background:linear-gradient(140deg,var(--amber),var(--amber2));color:var(--accent-text);
  padding:11px 14px;border-radius:var(--r-md);border-bottom-right-radius:5px;
  margin-left:auto;max-width:85%;width:fit-content;font-weight:600;
}
.amsg.bot{
  background:var(--surf);border:1px solid var(--line);padding:12px 14px;
  border-radius:var(--r-md);border-bottom-left-radius:5px;max-width:92%;
}
.amsg.bot.card{max-width:100%}
.amsg .ahead{display:flex;align-items:center;gap:7px;font-size:12px;font-weight:750;
  color:var(--amber);margin-bottom:9px}
.amsg .atext{color:var(--text);white-space:pre-wrap}
.amsg .ahint{font-size:11px;color:var(--muted);margin-top:8px}
.arows{margin-bottom:11px}
.arow{display:flex;justify-content:space-between;align-items:center;padding:6px 0;
  border-bottom:1px solid var(--line);font-size:12.5px;color:var(--muted)}
.arow:last-child{border-bottom:none}
.arow b{color:var(--text);font-family:ui-monospace,monospace;font-weight:700}

.askbar{
  position:sticky;bottom:calc(66px + env(safe-area-inset-bottom));
  display:flex;gap:8px;padding:9px 0 4px;background:linear-gradient(180deg,transparent,var(--bg) 22%);
}
/* Пока открыта клавиатура, нижняя панель уезжает вниз вместе со страницей,
   а не всплывает над клавиатурой: иначе она наезжает на поле ввода и на
   последние сообщения. Строка ввода при этом остаётся на виду. */
body.kbd .tabs{transform:translateY(140%);pointer-events:none}
body.kbd{padding-bottom:14px}
body.kbd .askbar{bottom:0}
.tabs{transition:transform .18s ease}
/* При выключенном движении панель просто убирается без проезда: плавность
   тут украшение, а поведение должно остаться тем же. */
@media (prefers-reduced-motion: reduce){ .tabs{transition:none} }
.askinput{
  flex:1;min-width:0;background:var(--surf);border:1px solid var(--line);color:var(--text);
  border-radius:var(--r-md);padding:13px 15px;font-size:15px;font-family:inherit;outline:none;
  -webkit-appearance:none;
}
.askinput:focus{border-color:var(--amber)}
.asksend{
  width:46px;height:46px;flex:none;border-radius:var(--r-md);cursor:pointer;border:none;
  background:linear-gradient(140deg,var(--amber),var(--amber2));color:var(--accent-text);
  display:flex;align-items:center;justify-content:center;font-family:inherit;
}
.asksend:active{transform:scale(.94)}
.tab-ask .ico{color:var(--amber)}

/* ---- Разделы инструментов ---- */
.catgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
@media(min-width:640px){.catgrid{grid-template-columns:repeat(3,1fr)}}
.catcard{
  position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:8px;
  padding:15px 14px;border-radius:var(--r-lg);cursor:pointer;font-family:inherit;text-align:left;
  background:var(--surf);border:1px solid var(--line);backdrop-filter:blur(16px);
  transition:transform .2s cubic-bezier(.34,1.4,.5,1),border-color .2s;
}
.catcard:active{transform:scale(.96);border-color:rgba(240,160,60,.45)}
.catcard .ci{
  width:40px;height:40px;border-radius:13px;display:flex;align-items:center;justify-content:center;
  background:var(--amber-soft);border:1px solid rgba(240,160,60,.22);color:var(--amber);
}
.catcard .cn{font-size:13.5px;font-weight:700;color:var(--text);line-height:1.25}
.catcard .cq{
  position:absolute;top:13px;right:13px;font-size:10px;font-weight:800;
  color:var(--muted);background:var(--surf2);border:1px solid var(--line);
  border-radius:8px;padding:2px 7px;
}
.backrow{
  display:flex;align-items:center;gap:8px;margin-bottom:12px;padding:9px 13px;
  border-radius:var(--r-md);cursor:pointer;font-family:inherit;font-size:13px;font-weight:650;
  background:var(--surf);border:1px solid var(--line);color:var(--muted);
}
.backrow:active{border-color:var(--amber);color:var(--amber)}
.cnt2{font-size:12px;color:var(--muted);font-weight:650}

/* ---- Кнопки-фильтры ---- */
.chip{
  background:var(--surf);border:1px solid var(--line);color:var(--muted);
  border-radius:20px;padding:6px 13px;font-size:12.5px;white-space:nowrap;cursor:pointer;
  flex:none;transition:all .18s;font-family:inherit;
}
.chip:active{transform:scale(.94)}
.chip.on{background:linear-gradient(140deg,var(--amber),var(--amber2));
  color:var(--accent-text);border-color:transparent;font-weight:650;box-shadow:var(--glow)}

/* ---- Анимации морской заставки ---- */
.ship{animation:sail 26s linear infinite}
@keyframes sail{
  0%{transform:translate(-110px,0)}
  50%{transform:translate(180px,-2px)}
  100%{transform:translate(460px,0)}
}
.beamRay{transform-origin:357px 75px;animation:sweep 8s ease-in-out infinite;mix-blend-mode:screen}
@keyframes sweep{0%,100%{transform:rotate(-20deg);opacity:.2}50%{transform:rotate(16deg);opacity:.9}}
.lamp{animation:lampGlow 2.6s ease-in-out infinite}
@keyframes lampGlow{0%,100%{opacity:.5}50%{opacity:1}}
.gulls{animation:glide 19s linear infinite}
@keyframes glide{0%{transform:translate(0,0)}50%{transform:translate(150px,-8px)}100%{transform:translate(320px,2px)}}
.w1{animation:wave 9s ease-in-out infinite}
.w2{animation:wave 12s ease-in-out infinite reverse}
.w3{animation:wave 16s ease-in-out infinite}
@keyframes wave{0%,100%{transform:translateX(0)}50%{transform:translateX(100px)}}
@keyframes ping{0%{transform:scale(.35);opacity:.9}80%{transform:scale(1.15);opacity:0}100%{opacity:0}}
.showall{
  width:100%;margin-top:10px;padding:11px;border-radius:var(--r-md);cursor:pointer;
  background:var(--surf);border:1px dashed var(--line);color:var(--muted);
  font-family:inherit;font-size:12.5px;font-weight:650;
  transition:border-color .2s,color .2s;
}
.showall:active{border-color:var(--amber);color:var(--amber)}

.errbar{
  position:fixed;left:10px;right:10px;top:calc(10px + env(safe-area-inset-top));z-index:3000;
  background:rgba(255,107,74,.95);color:#fff;border-radius:12px;padding:10px 12px;
  font-size:11.5px;line-height:1.4;display:none;box-shadow:0 10px 30px rgba(0,0,0,.5);
}
.errbar.on{display:block}
.errbar b{display:block;font-size:12.5px;margin-bottom:3px}
.errbar .x{position:absolute;top:6px;right:9px;font-size:16px;cursor:pointer;opacity:.8}
.mapgear{
  position:absolute;top:11px;right:11px;z-index:701;width:40px;height:40px;border-radius:13px;
  background:rgba(11,22,34,.92);border:1px solid var(--line);color:var(--text);cursor:pointer;
  display:flex;align-items:center;justify-content:center;backdrop-filter:blur(14px);
  box-shadow:var(--sh);transition:transform .2s cubic-bezier(.34,1.6,.5,1),color .2s;
}
.mapgear:active{transform:scale(.88)}
.mapgear.on{color:var(--amber);border-color:rgba(240,160,60,.45)}
.mapctl{display:none}
.mapctl.on{display:block;top:59px;animation:drop .2s cubic-bezier(.34,1.4,.5,1)}
.fromship{
  display:inline-flex;align-items:center;gap:4px;margin-left:7px;font-size:9px;font-weight:750;
  background:rgba(77,147,214,.16);color:var(--sea);border:1px solid rgba(77,147,214,.3);
  border-radius:7px;padding:1px 6px;text-transform:none;letter-spacing:0;vertical-align:1px;
}
.fromship .ico{width:10px;height:10px}
.tinput.fromship-in{border-color:rgba(77,147,214,.4)}
.vkey{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:13px 0}
.vk{background:var(--surf);border:1px solid var(--line);border-radius:var(--r-sm);
  padding:10px 6px;text-align:center}
.vk .vkv{font-size:17px;font-weight:800;color:var(--amber);line-height:1.1}
.vk .vkl{font-size:9px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:.5px}
.vsec{background:var(--surf);border:1px solid var(--line);border-radius:var(--r-md);
  margin-bottom:9px;overflow:hidden}
.vsech{display:flex;align-items:center;gap:9px;padding:13px 14px;cursor:pointer;
  font-size:13.5px;font-weight:700}
.vsech .ico{color:var(--amber)}
.vsarrow{margin-left:auto;color:var(--muted);transform:rotate(-90deg);transition:transform .25s}
.vsec.open .vsarrow{transform:rotate(90deg)}
.vsbody{display:none;padding:0 14px 12px}
.vsec.open .vsbody{display:block}
.vsrow{display:flex;align-items:center;gap:11px;padding:12px 13px;margin-bottom:8px;
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-md);cursor:pointer;
  transition:transform .18s,border-color .18s}
.vsrow:active{transform:scale(.98);border-color:rgba(240,160,60,.4)}
.vsi{width:34px;height:34px;flex:none;border-radius:11px;display:flex;align-items:center;
  justify-content:center;background:var(--amber-soft);color:var(--amber)}
.vsn{font-size:14px;font-weight:700}
.vsd{font-size:11.5px;color:var(--muted);margin-top:2px}
.quick{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:4px}
@media(min-width:640px){.quick{grid-template-columns:repeat(4,1fr)}}
.qbtn{
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-md);
  padding:14px 12px;cursor:pointer;display:flex;flex-direction:column;gap:8px;
  backdrop-filter:blur(14px);transition:transform .2s cubic-bezier(.34,1.4,.5,1),border-color .2s;
}
.qbtn:active{transform:scale(.96);border-color:rgba(240,160,60,.42)}
.qbtn .qi{
  width:36px;height:36px;border-radius:12px;display:flex;align-items:center;justify-content:center;
  background:var(--amber-soft);color:var(--amber);border:1px solid rgba(240,160,60,.22);
}
.qbtn .qt{font-size:13px;font-weight:700;line-height:1.25}
.qbtn .qs{font-size:11px;color:var(--muted);line-height:1.3}
.subtabs{
  display:flex;gap:5px;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;
  margin:0 -15px 14px;padding:0 15px 2px;position:relative;
  /* Свойства ниже нужны, чтобы лента таскалась пальцем в мобильном
     браузере. Раньше здесь стояла маска-градиент по краю: на iOS она
     создаёт отдельный слой отрисовки и глушит горизонтальный свайп --
     лента прокручивалась только программно, а рукой нет. */
  -webkit-overflow-scrolling:touch;
  touch-action:pan-x;
  overscroll-behavior-x:contain;
  cursor:grab;
}
.subtabs:active{cursor:grabbing}

.subtabs::-webkit-scrollbar{display:none}
.subtab{
  flex:none;border:1px solid var(--line);background:var(--surf);color:var(--muted);
  border-radius:11px;padding:8px 11px;font-size:12.5px;font-weight:650;font-family:inherit;
  cursor:pointer;white-space:nowrap;display:flex;align-items:center;gap:5px;
  transition:all .2s cubic-bezier(.34,1.4,.5,1);backdrop-filter:blur(12px);
}
.subtab:active{transform:scale(.94)}
.subtab.on{
  background:linear-gradient(140deg,var(--amber),var(--amber2));
  color:var(--accent-text);border-color:transparent;box-shadow:var(--glow);
}
.subtab .ico{width:15px;height:15px}
.subtab .cnt{
  font-size:9.5px;font-weight:800;border-radius:8px;padding:1px 5px;
  background:var(--amber-soft);color:var(--amber);
}
.subtab.on .cnt{background:rgba(22,35,47,.22);color:var(--accent-text)}
.legs{display:flex;align-items:flex-start;gap:7px;margin-top:9px;padding-top:9px;
  border-top:1px solid rgba(240,160,60,.22);font-size:11.5px;color:var(--muted);line-height:1.45}
.legs .ico{color:var(--amber);margin-top:2px}
.topback{
  position:sticky;top:0;z-index:60;margin-bottom:12px;display:flex;align-items:center;gap:9px;
  padding:calc(11px + env(safe-area-inset-top)) 15px 11px;margin:0 -16px 4px;
  background:linear-gradient(180deg,var(--bg) 72%,transparent);
}
.topback button{
  width:40px;height:40px;flex:none;border-radius:13px;cursor:pointer;
  background:var(--surf);border:1px solid var(--line);color:var(--text);
  display:flex;align-items:center;justify-content:center;
  transition:transform .2s cubic-bezier(.34,1.6,.5,1);
}
.topback button:active{transform:scale(.88)}
.topback .tb{font-size:14.5px;font-weight:700;min-width:0;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}

/* ---- Тариф и платные разделы ---- */
.trialbar{
  display:flex;align-items:center;gap:11px;padding:12px 14px;margin-bottom:14px;
  border-radius:var(--r-md);background:linear-gradient(120deg,rgba(240,160,60,.16),rgba(255,139,61,.04));
  border:1px solid rgba(240,160,60,.3);cursor:pointer;
}
.trialbar.free{background:rgba(127,150,172,.08);border-color:var(--line)}
.trialbar .ti{width:34px;height:34px;flex:none;border-radius:11px;display:flex;
  align-items:center;justify-content:center;background:var(--amber-soft);color:var(--amber)}
.trialbar .tt{flex:1;min-width:0}
.trialbar .t1{font-size:13.5px;font-weight:700}
.trialbar .t2{font-size:11.5px;color:var(--muted);margin-top:2px;line-height:1.35}
.trialbar .tg{font-size:11px;font-weight:750;color:var(--amber);white-space:nowrap}

.lockwrap{position:relative}
.lockwrap.locked>*:not(.lockover){filter:blur(3px);opacity:.4;pointer-events:none;user-select:none}
.lockover{
  position:absolute;inset:0;z-index:20;display:flex;flex-direction:column;
  align-items:center;justify-content:center;text-align:center;padding:24px;gap:11px;
}
.lockover .li{
  width:56px;height:56px;border-radius:19px;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(150deg,var(--amber),var(--amber2));color:#16232f;box-shadow:var(--glow);
}
.lockover .lt{font-size:16px;font-weight:750}
.lockover .ls{font-size:12.5px;color:var(--muted);max-width:280px;line-height:1.45}
.premtag{
  display:inline-flex;align-items:center;gap:4px;font-size:9px;font-weight:800;
  background:var(--amber-soft);color:var(--amber);border:1px solid rgba(240,160,60,.3);
  border-radius:7px;padding:2px 6px;margin-left:6px;vertical-align:1px;letter-spacing:.4px;
}
.plans{display:grid;gap:11px;margin-bottom:13px}
.plan{
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-lg);
  padding:15px;backdrop-filter:blur(16px);
}
.plan.on{border-color:rgba(240,160,60,.45);
  background:linear-gradient(150deg,rgba(240,160,60,.1),var(--surf))}
.plan .pt{font-size:15px;font-weight:750;display:flex;align-items:center;justify-content:space-between}
.plan .pp{font-size:22px;font-weight:800;color:var(--amber);letter-spacing:-.5px}
.plan ul{margin:11px 0 0;padding:0;list-style:none}
.plan li{font-size:12.5px;color:var(--muted);padding:4px 0 4px 20px;position:relative;line-height:1.4}
.plan li::before{content:'';position:absolute;left:2px;top:11px;width:7px;height:7px;
  border-radius:50%;background:var(--amber);opacity:.75}
.plan.gray li::before{background:var(--muted);opacity:.5}
.buystate{font-size:12.5px;line-height:1.45;color:var(--muted);margin-top:10px;text-align:center}
.buystate:empty{display:none}
.buystate.ok{color:var(--ok)}
.buystate.no{color:var(--hot)}

/* ---- Админ-панель ----
   Кнопки действий узкие и в ряд: панель открывают с телефона, и попасть
   пальцем в строку списка проще, чем в мелкую иконку. */
.admbig{font-size:34px;font-weight:800;color:var(--amber);letter-spacing:-1px;line-height:1.1}
.admbar{height:7px;border-radius:6px;background:var(--surf2);overflow:hidden;margin:9px 0 5px;
  border:1px solid var(--line)}
.admbar i{display:block;height:100%;background:linear-gradient(90deg,var(--amber),var(--amber2))}
.admgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:4px}
.admcell{background:var(--surf2);border:1px solid var(--line);border-radius:var(--r-sm);padding:10px 9px}
.admcell b{display:block;font-size:19px;font-weight:800;letter-spacing:-.4px}
.admcell span{font-size:10.5px;color:var(--muted);line-height:1.35;display:block;margin-top:2px}
.admcell.hot{background:rgba(255,107,74,.12);border-color:rgba(255,107,74,.34)}

/* Вкладки разделов. Прокручиваются вбок: пять пунктов с подписями в
   ширину телефона не влезают, а резать подписи до иконок хуже -- по одной
   иконке не угадать, где деньги, а где система. */
.admnav{display:flex;gap:6px;overflow-x:auto;margin-bottom:12px;padding-bottom:2px;
  -webkit-overflow-scrolling:touch;scrollbar-width:none}
.admnav::-webkit-scrollbar{display:none}
.admnav button{flex:0 0 auto;display:flex;align-items:center;gap:6px;cursor:pointer;
  border:1px solid var(--line);background:var(--surf);color:var(--muted);
  font-family:inherit;font-size:12px;font-weight:700;padding:9px 13px;border-radius:11px}
.admnav button.on{background:var(--amber-soft);border-color:rgba(240,160,60,.4);color:var(--amber)}
.admnav button .ico{width:14px;height:14px}
.admhead{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.admhead-r{text-align:right}
.admmid{font-size:20px;font-weight:800;letter-spacing:-.4px}
.admsub{font-size:11px;color:var(--muted);margin-top:2px;line-height:1.35}
.admline{display:flex;align-items:baseline;justify-content:space-between;font-size:11.5px;
  color:var(--muted);margin-bottom:5px}
.admline b{font-size:15px;font-weight:800;color:var(--fg,inherit)}
.admchart{width:100%;height:46px;display:block;color:var(--muted)}
.admdates{display:flex;justify-content:space-between;font-size:10px;color:var(--dim);margin-top:5px}
/* Планшет расхождения. Ширину ограничиваем: на планшете и в широком
   окне круг иначе растягивается на весь экран и перестаёт читаться. */
.tplot{display:flex;justify-content:center;margin:4px 0 10px}
.rplot{width:100%;max-width:320px;height:auto;color:var(--muted)}
.tres+.tplot{margin-top:10px}

.admtext{width:100%;box-sizing:border-box;background:var(--surf2);border:1px solid var(--line);
  border-radius:var(--r-sm);color:inherit;font-family:inherit;font-size:13.5px;padding:11px 12px;
  resize:vertical}
.admtext:focus{outline:none;border-color:rgba(240,160,60,.45)}
.admseg{display:flex;gap:6px;margin-bottom:9px}
.admseg button{flex:1;border:1px solid var(--line);background:var(--surf2);color:var(--muted);
  font-family:inherit;font-size:11.5px;font-weight:700;padding:9px 6px;border-radius:10px;cursor:pointer}
.admseg button.on{background:var(--amber-soft);border-color:rgba(240,160,60,.34);color:var(--amber)}
.admacts{display:flex;flex-wrap:wrap;gap:6px;margin:-3px 0 10px}
.admacts .btn{flex:1 1 auto;min-width:70px;padding:9px 8px;font-size:11.5px}
.admpay{background:var(--surf2);border:1px solid var(--line);border-radius:var(--r-sm);
  padding:11px 13px;margin-bottom:8px}
.admpay.gone{opacity:.55}
.admpay .pw{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:13px;font-weight:700}
.admpay .pd{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.45}
.admpay .pc{font-size:9.5px;color:var(--dim);margin-top:5px;word-break:break-all;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}

/* ---- Выбор даты ----
   Свой календарь вместо системного: системный на телефоне присылает
   change на каждый прокрученный барабан, и раздел, который на это
   перерисовывается, закрывал окно на середине выбора. Здесь дата
   уходит наружу один раз -- по кнопке «Готово». */
.dpick{
  /* Выше и нижней навигации (1000), и раскрытой карточки .detail (1200):
     иначе панель вкладок закрывала снизу как раз строку с «Готово». */
  position:fixed;inset:0;z-index:2500;display:none;align-items:flex-end;justify-content:center;
  background:rgba(4,10,17,.66);backdrop-filter:blur(5px);
}
.dpick.on{display:flex}
.dpbox{
  width:100%;max-width:430px;background:var(--bg2);border:1px solid var(--line);
  border-bottom:0;border-radius:var(--r-xl) var(--r-xl) 0 0;box-shadow:var(--sh);
  padding:15px 15px calc(15px + env(safe-area-inset-bottom,0px));
  animation:dpup .2s ease-out;max-height:94vh;overflow-y:auto;
}
@keyframes dpup{from{transform:translateY(26px);opacity:0}}
.dplabel{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;
  color:var(--dim);text-align:center;margin-bottom:11px}
.dphead{display:flex;align-items:center;gap:8px;margin-bottom:11px}
.dpnav{
  width:36px;height:36px;flex:none;border-radius:11px;border:1px solid var(--line);
  background:var(--surf2);color:var(--text);font-size:17px;font-weight:800;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
}
.dpnav:active{border-color:var(--amber);color:var(--amber)}
.dptitle{
  flex:1;min-width:0;text-align:center;font-size:16px;font-weight:750;cursor:pointer;
  padding:7px 6px;border-radius:11px;border:1px solid transparent;
}
.dptitle:active{border-color:var(--amber);color:var(--amber)}
.dpwk{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin-bottom:5px}
.dpwk span{text-align:center;font-size:9.5px;font-weight:800;color:var(--dim);letter-spacing:.4px}
.dpgrid{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}
.dpd{
  height:38px;display:flex;align-items:center;justify-content:center;border-radius:11px;
  font-size:14.5px;cursor:pointer;font-variant-numeric:tabular-nums;color:var(--text);
  border:1px solid transparent;
}
.dpd.mut{color:var(--dim);opacity:.5}
.dpd.today{border-color:rgba(240,160,60,.5)}
.dpd.on{background:linear-gradient(150deg,var(--amber),var(--amber2));color:#160d02;font-weight:800}
.dpgrid2{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;max-height:238px;overflow-y:auto}
.dpc{
  padding:10px 4px;text-align:center;border-radius:11px;font-size:13.5px;cursor:pointer;
  border:1px solid var(--line);background:var(--surf2);color:var(--text);
  font-variant-numeric:tabular-nums;
}
.dpc.on{background:linear-gradient(150deg,var(--amber),var(--amber2));color:#160d02;font-weight:800;border-color:transparent}
.dpsel{text-align:center;font-size:13px;color:var(--muted);margin-top:12px;min-height:18px}
.dpsel b{color:var(--amber)}
.dpbar{display:flex;gap:8px;margin-top:12px}
.dpbar .btn{flex:1;margin:0}
.dpbar .btn[disabled]{opacity:.4;pointer-events:none}
.datefield{
  width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;
  background:var(--surf2);border:1px solid var(--line);border-radius:var(--r-md);
  padding:12px 14px;font-size:15px;color:var(--text);cursor:pointer;text-align:left;
}
.datefield:active{border-color:var(--amber)}
.datefield .dv{font-variant-numeric:tabular-nums;font-weight:650}
.datefield .dv.none{color:var(--dim);font-weight:400}
.datefield .dico{color:var(--amber);display:flex;flex:none}

/* ---- Список выбора (вахта и прочее) ---- */
.pkopt{
  display:flex;align-items:center;gap:11px;padding:12px 13px;border-radius:var(--r-md);
  border:1px solid var(--line);background:var(--surf2);cursor:pointer;margin-bottom:7px;
}
.pkopt:active{border-color:var(--amber)}
.pkopt.on{border-color:rgba(240,160,60,.5);
  background:linear-gradient(150deg,rgba(240,160,60,.12),var(--surf2))}
.pkopt .mark{
  width:19px;height:19px;flex:none;border-radius:50%;border:2px solid var(--line);
  display:flex;align-items:center;justify-content:center;
}
.pkopt.on .mark{border-color:var(--amber)}
.pkopt.on .mark::after{content:'';width:9px;height:9px;border-radius:50%;background:var(--amber)}
.pkopt .pkt{flex:1;min-width:0}
.pkopt .pk1{font-size:14.5px;font-weight:650;line-height:1.25}
.pkopt .pk2{font-size:12px;color:var(--muted);margin-top:2px;font-variant-numeric:tabular-nums}
.pklist{max-height:56vh;overflow-y:auto;margin:0 -2px;padding:0 2px}

/* ---- Ask AI: сценарии и режим ответа ---- */
.askbar2{display:flex;gap:7px;margin-bottom:10px;flex-wrap:wrap}
.askchip{
  display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:750;
  padding:6px 11px;border-radius:999px;border:1px solid var(--line);background:var(--surf2);
  color:var(--muted);cursor:pointer;font-family:inherit;
}
.askchip .ico{width:12px;height:12px;margin:0}
.askchip.lib.on{border-color:var(--ai2);color:var(--purple);background:rgba(141,92,255,.12)}
.askchip.mode{color:var(--blue);border-color:rgba(70,184,255,.3)}
.askcats{margin-bottom:9px}
.askscen{display:flex;flex-direction:column;gap:7px;margin-bottom:14px}
.scen{
  display:flex;flex-direction:column;gap:4px;text-align:left;padding:11px 12px;
  border-radius:var(--r-md);border:1px solid var(--line);background:var(--surf);
  cursor:pointer;font-family:inherit;color:inherit;
}
.scen:active{border-color:var(--ai2)}
.scen .st{font-size:13px;font-weight:750}
.scen .sq{font-size:11px;color:var(--muted);line-height:1.35}
.scen .sm{font-size:10px;color:var(--amber);display:flex;align-items:center;gap:4px}
.scen .sm.ok{color:var(--ok)}
.scen .sm .ico{width:11px;height:11px;margin:0}

/* ---- Уведомления ---- */
.ntf{
  display:flex;gap:11px;padding:12px 13px;border-radius:var(--r-md);
  border:1px solid var(--line);background:var(--surf);margin-bottom:8px;cursor:pointer;
  text-align:left;width:100%;font-family:inherit;color:inherit;
}
.ntf.new{border-color:rgba(70,184,255,.4);background:linear-gradient(150deg,rgba(70,184,255,.09),var(--surf))}
.ntf .ic{
  width:32px;height:32px;flex:none;border-radius:50%;display:flex;position:relative;
  align-items:center;justify-content:center;background:var(--surf2);color:var(--blue);
}
.ntf .ic .ico{width:15px;height:15px;margin:0;position:relative;z-index:2}
.ntf.urgent .ic{background:rgba(255,107,74,.16);color:var(--hot)}
/* Непрочитанное пульсирует: расходящееся кольцо и лёгкое дыхание самой
   иконки. Прочитанное стоит спокойно -- иначе в ленте рябит всё сразу. */
.ntf .ic::after{
  content:'';position:absolute;inset:0;border-radius:50%;z-index:1;
  border:2px solid currentColor;opacity:0;
}
.ntf.new .ic::after{animation:ntfRing 2.4s ease-out infinite}
.ntf.new .ic{animation:ntfBreath 2.4s ease-in-out infinite}
.ntf.new.urgent .ic::after,.ntf.new.urgent .ic{animation-duration:1.3s}
@keyframes ntfRing{0%{transform:scale(1);opacity:.55}70%{transform:scale(1.65);opacity:0}100%{opacity:0}}
@keyframes ntfBreath{0%,100%{transform:scale(1)}50%{transform:scale(1.07)}}
/* Заголовок и текст -- разными строками: до этого оба были строчными
   элементами и слипались в одну строку. */
.ntf .tx{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.ntf .t1,.ntf .t2,.ntf .t3{display:block}
.ntf .t1{font-size:13.5px;font-weight:750;line-height:1.3}
.ntf .t2{font-size:11.5px;color:var(--muted);line-height:1.45}
.ntf .t3{font-size:10px;color:var(--dim);margin-top:2px}
.ntf .dot{width:8px;height:8px;border-radius:50%;background:var(--blue);flex:none;margin-top:6px;
  animation:ntfBreath 1.8s ease-in-out infinite}
.ntf.urgent .dot{background:var(--hot)}
@media (prefers-reduced-motion: reduce){
  .ntf.new .ic,.ntf.new .ic::after,.ntf .dot{animation:none}
}

/* ---- Мои порты ---- */
.pcard{
  display:flex;gap:11px;align-items:flex-start;padding:12px 13px;border-radius:var(--r-md);
  border:1px solid var(--line);background:var(--surf);margin-bottom:8px;
}
.pcard .num{
  width:26px;height:26px;flex:none;border-radius:50%;background:var(--amber-soft);
  color:var(--amber);font-size:12px;font-weight:800;
  display:flex;align-items:center;justify-content:center;
}
.pcard .tx{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.pcard .t1,.pcard .t2{display:block}
.pcard .t1{font-size:14.5px;font-weight:750}
.pcard .t2{font-size:11.5px;color:var(--muted);line-height:1.35}
.pcard .t3{font-size:11px;color:var(--sea);margin-top:2px;display:flex;align-items:center;gap:5px}
.pcard .acts{display:flex;flex-direction:column;gap:5px;flex:none}
.pact{
  width:28px;height:28px;border-radius:9px;border:1px solid var(--line);background:var(--surf2);
  color:var(--muted);font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;
  padding:0;font-family:inherit;
}
.pact:active{border-color:var(--amber);color:var(--amber)}
.pact.del:active{border-color:var(--hot);color:var(--hot)}
.pleg{
  display:flex;align-items:center;gap:8px;margin:-4px 0 8px 26px;padding-left:12px;
  border-left:2px dashed var(--line);font-size:11px;color:var(--muted);min-height:22px;
}
.ptotal{
  display:flex;justify-content:space-between;align-items:center;padding:13px 14px;
  border-radius:var(--r-md);background:var(--surf2);border:1px solid var(--line);margin:12px 0;
}
.ptotal b{font-size:19px;font-weight:800;color:var(--amber);font-variant-numeric:tabular-nums}

/* ---- Погода в порту ---- */
.wxcard{
  border-radius:var(--r-lg);border:1px solid var(--line);background:var(--surf);
  padding:15px;margin-bottom:11px;
}
.wxhead{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:11px}
.wxhead .nm{font-size:15px;font-weight:800}
.wxhead .at{font-size:10px;color:var(--muted);font-variant-numeric:tabular-nums}
.wxgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.wxcell{background:var(--surf2);border-radius:var(--r-sm);padding:9px 10px;border:1px solid var(--line)}
.wxcell .v{font-size:16px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.15}
.wxcell .k{font-size:9px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:.5px}
.wxcell.hot .v{color:var(--hot)}
.wxcell.warn .v{color:var(--amber)}
.wxmaps{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px}
.wxmap{
  display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:750;
  padding:7px 11px;border-radius:999px;border:1px solid var(--line);background:var(--surf2);
  color:var(--sea);cursor:pointer;font-family:inherit;
}
.wxmap:active{border-color:var(--sea)}
/* Карта соразмерна окну Mini App, а не «сколько влезет»: на телефоне это
   примерно треть высоты. И её всегда можно закрыть -- внутри самой Windy
   кнопки закрытия нет. */
.wxwrap{position:relative;margin-top:11px}
.wxembed{
  display:block;width:100%;height:clamp(180px,38vh,320px);
  border:1px solid var(--line);border-radius:var(--r-md);background:var(--surf2);
}
/* Крестик слева: справа у Windy свои кнопки масштаба, и наш перекрывал их */
.wxclose{
  position:absolute;top:8px;left:8px;z-index:2;width:30px;height:30px;border-radius:50%;
  background:rgba(9,20,32,.86);border:1px solid var(--line);color:#fff;font-size:16px;
  line-height:1;cursor:pointer;font-family:inherit;display:flex;align-items:center;justify-content:center;
}
.wxnote{font-size:10px;color:var(--dim);margin-top:6px;text-align:center}

/* ---- Справка ---- */
.faqcat{margin-bottom:9px;border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surf);overflow:hidden}
.faqhead{
  display:flex;align-items:center;gap:10px;padding:13px 14px;cursor:pointer;
  font-size:14px;font-weight:750;width:100%;background:none;border:none;
  color:inherit;font-family:inherit;text-align:left;
}
.faqhead .ico{width:16px;height:16px;margin:0;color:var(--amber);flex:none}
.faqhead .cnt{margin-left:auto;font-size:10px;color:var(--dim);font-weight:700}
.faqhead .ar{color:var(--muted);transition:transform .2s;flex:none}
.faqcat.on .faqhead .ar{transform:rotate(90deg)}
.faqitems{display:none;padding:0 14px 6px}
.faqcat.on .faqitems{display:block}
.faqq{
  border-top:1px solid var(--line);padding:11px 0 0;width:100%;background:none;border-left:0;
  border-right:0;border-bottom:0;text-align:left;font-family:inherit;color:inherit;cursor:pointer;
}
.faqq .q{font-size:13px;font-weight:700;line-height:1.35;display:flex;gap:7px}
.faqq .q::before{content:'?';color:var(--amber);font-weight:800;flex:none}
.faqq .a{font-size:12.5px;color:var(--muted);line-height:1.5;margin:7px 0 11px 15px;display:none}
.faqq.on .a{display:block}
.faqq .a b{color:var(--text)}
.faqempty{font-size:12.5px;color:var(--muted);padding:14px 2px}

/* ---- Поддержка ---- */
.supmsg{
  max-width:86%;padding:10px 13px;border-radius:var(--r-md);font-size:13.5px;line-height:1.45;
  margin-bottom:9px;white-space:pre-wrap;word-break:break-word;
}
.supmsg.me{margin-left:auto;background:var(--amber-soft);border:1px solid rgba(240,160,60,.3)}
.supmsg.owner{background:var(--surf);border:1px solid var(--line)}
.supmsg .who{font-size:9.5px;font-weight:800;letter-spacing:.4px;color:var(--muted);
  text-transform:uppercase;margin-bottom:4px}
.supmsg.owner .who{color:var(--sea)}

/* ---- Три часа в настройках ---- */
.clocks{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
.clk{
  background:var(--surf2);border:1px solid var(--line);border-radius:var(--r-sm);
  padding:9px 6px;text-align:center;
}
.clk b{display:block;font-size:17px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.1}
.clk span{display:block;font-size:9px;color:var(--muted);margin-top:3px;
  text-transform:uppercase;letter-spacing:.5px}



.vhero{
  position:relative;border-radius:var(--r-lg);overflow:hidden;
  background:linear-gradient(150deg,#153c60,#0c2138);border:1px solid var(--line);
  padding:17px 16px 26px;box-shadow:var(--sh);
}
.vwave{position:absolute;left:0;right:0;bottom:-4px;width:200%;height:40px;opacity:.32;
  animation:drift 12s linear infinite}
.vin{position:relative;z-index:2}
.vin .ico{color:var(--amber);margin:0 0 9px}
.vt{font-size:16px;font-weight:750}
.vs{font-size:12.5px;color:#b9cadb;margin-top:5px;line-height:1.45}
.vname{font-size:22px;font-weight:800;letter-spacing:-.6px;line-height:1.15}
.vmeta{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}
.vinput{
  width:100%;background:var(--surf);border:1px solid var(--line);color:var(--text);
  border-radius:var(--r-sm);padding:12px 13px;font-size:15px;font-family:inherit;outline:none;
  transition:border-color .2s,box-shadow .2s;-webkit-appearance:none;
}
.vinput:focus{border-color:var(--amber);box-shadow:0 0 0 3px var(--amber-soft)}
.langbtn{
  width:44px;height:44px;flex:none;border-radius:15px;cursor:pointer;
  background:var(--surf);border:1px solid var(--line);color:var(--muted);
  display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;
  letter-spacing:.5px;transition:transform .22s cubic-bezier(.34,1.6,.5,1),color .2s;
}
.langbtn:active{transform:scale(.9);color:var(--amber)}

/* ---- Радиостанции ---- */
.rcard{
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-lg);
  padding:13px 14px;margin-bottom:10px;position:relative;overflow:hidden;
  backdrop-filter:blur(16px);cursor:pointer;
  transition:transform .2s cubic-bezier(.34,1.4,.5,1),border-color .2s;
}
.rcard:active{transform:scale(.98);border-color:rgba(240,160,60,.4)}
.rcard::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--muted);opacity:.5}
.rcard.auto::before{background:linear-gradient(180deg,#3fc97f,#2fa864);opacity:1}
.rcard.reliable::before{background:linear-gradient(180deg,var(--amber),var(--amber2));opacity:1}
.rtop{display:flex;align-items:center;gap:10px}
.rwave{
  width:42px;height:42px;flex:none;border-radius:13px;position:relative;
  background:var(--amber-soft);border:1px solid rgba(240,160,60,.24);
  display:flex;align-items:center;justify-content:center;color:var(--amber);overflow:hidden;
}
.rcard.auto .rwave{background:rgba(63,201,127,.14);border-color:rgba(63,201,127,.3);color:var(--ok)}
.rwave i{
  position:absolute;inset:0;border-radius:50%;border:1.5px solid currentColor;
  opacity:0;animation:rping 2.8s ease-out infinite;
}
.rwave i:nth-child(2){animation-delay:.9s}
.rwave i:nth-child(3){animation-delay:1.8s}
@keyframes rping{0%{transform:scale(.2);opacity:.75}75%{transform:scale(1.1);opacity:0}100%{opacity:0}}
.rwave .ico{position:relative;z-index:2;width:19px;height:19px;margin:0}
.rmid{flex:1;min-width:0}
.rname{font-size:14.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rmmsi{font-size:13px;color:var(--amber);font-weight:700;letter-spacing:.4px;margin-top:1px}
.rcov{font-size:11.5px;color:var(--muted);margin-top:6px;line-height:1.4}
.rtags{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.rtag{
  font-size:10px;font-weight:700;border-radius:7px;padding:3px 8px;
  background:var(--surf2);border:1px solid var(--line);color:var(--muted);
}
.rtag.ok{background:rgba(63,201,127,.14);border-color:rgba(63,201,127,.34);color:var(--ok)}
.rtag.am{background:var(--amber-soft);border-color:rgba(240,160,60,.3);color:var(--amber)}
.rcopy{
  width:34px;height:34px;flex:none;border-radius:11px;border:1px solid var(--line);
  background:var(--surf2);color:var(--muted);cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:transform .22s cubic-bezier(.34,1.6,.5,1),color .2s;
}
.rcopy:active{transform:scale(.85);color:var(--amber)}
.rcopy.done{color:var(--ok);border-color:rgba(63,201,127,.4)}
.rmapwrap{position:relative;border-radius:var(--r-lg);overflow:hidden;
  border:1px solid var(--line);box-shadow:var(--sh);margin-bottom:13px}
#rmap{height:46vh}
.rlegend{display:flex;gap:13px;flex-wrap:wrap;font-size:11.5px;color:var(--muted);margin:0 0 15px}
.rlegend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.rpop{min-width:190px}
.rpop .pn{font-size:14px;font-weight:750;margin-bottom:3px}
.rpop .pm{font-size:15px;font-weight:800;color:#f0a03c;letter-spacing:.5px;margin-bottom:6px}
.rpop .pr{font-size:11px;line-height:1.4;color:#b9cadb}
.rpop .pb{
  display:inline-block;margin-top:7px;font-size:10px;font-weight:750;border-radius:7px;padding:3px 8px;
}
.rpop .pb.ok{background:rgba(63,201,127,.2);color:#6fe3a6}
.rpop .pb.am{background:rgba(240,160,60,.2);color:#ffc372}
.rpop .pb.no{background:rgba(127,150,172,.18);color:#a8bccf}
.station-dot{border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 3px rgba(0,0,0,.35)}

/* ---- График и тепловая карта ---- */
.chart{background:var(--surf);border:1px solid var(--line);border-radius:var(--r-lg);
  padding:13px 14px 9px;backdrop-filter:blur(14px)}
.chart svg{width:100%;height:110px;display:block;overflow:visible}
.chartAx{display:flex;justify-content:space-between;font-size:10.5px;color:var(--muted);margin-top:7px}
.heat{display:flex;align-items:center;gap:10px;padding:7px 12px;background:var(--surf);
  border:1px solid var(--line);border-radius:var(--r-sm);margin-bottom:7px;cursor:pointer;
  transition:border-color .2s}
.heat:active{border-color:rgba(240,160,60,.42)}
.heat .hc{font-size:11.5px;font-weight:800;color:var(--amber);width:56px;flex:none}
.heat .hb{flex:1;height:9px;background:rgba(127,150,172,.14);border-radius:5px;overflow:hidden}
.heat .hb i{display:block;height:100%;border-radius:5px;
  background:linear-gradient(90deg,var(--amber),var(--amber2));animation:grow .7s cubic-bezier(.25,1,.4,1)}
@keyframes grow{from{width:0!important}}
.heat .hn{font-size:13.5px;font-weight:750;width:38px;text-align:right;flex:none}

/* ---- Инструменты ---- */
.tinput{
  width:100%;background:var(--surf);border:1px solid var(--line);color:var(--text);
  border-radius:var(--r-sm);padding:12px 13px;font-size:15px;font-family:inherit;outline:none;
  transition:border-color .2s,box-shadow .2s;-webkit-appearance:none;appearance:none;
}
.tinput:focus{border-color:var(--amber);box-shadow:0 0 0 3px var(--amber-soft)}
select.tinput{background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),
  linear-gradient(135deg,var(--muted) 50%,transparent 50%);
  background-position:calc(100% - 18px) 50%,calc(100% - 13px) 50%;
  background-size:5px 5px,5px 5px;background-repeat:no-repeat;padding-right:36px}
.tres{
  display:flex;align-items:center;justify-content:space-between;gap:11px;
  padding:12px 14px;border-radius:var(--r-sm);background:var(--surf2);
  border:1px solid var(--line);margin-bottom:8px;
}
.tres.hi{background:linear-gradient(120deg,rgba(240,160,60,.17),rgba(255,139,61,.05));
  border-color:rgba(240,160,60,.36)}
.tres.warn{background:rgba(255,107,74,.13);border-color:rgba(255,107,74,.4)}
.tres .tl{font-size:12.5px;color:var(--muted);flex:1;min-width:0}
.tres .tv{font-size:15px;font-weight:750;text-align:right}
.tres.hi .tv{color:var(--amber);font-size:18px}
.tres.warn .tv{color:var(--hot)}
.thead{display:flex;align-items:center;gap:13px;margin-bottom:5px}
.thead .ti{
  width:50px;height:50px;flex:none;border-radius:16px;color:var(--amber);
  background:var(--amber-soft);border:1px solid rgba(240,160,60,.28);
  display:flex;align-items:center;justify-content:center;
}

/* ---- Иконки ---- */
.ico{width:20px;height:20px;flex:none;display:block;margin:0 auto}
.ico.sm{width:16px;height:16px}
.ico.xs{width:14px;height:14px}
.ico.lg{width:26px;height:26px}
.cat .ico{margin-bottom:5px;color:var(--muted)}
.cat.on .ico{color:#16232f}
.tab .ico{margin:0 auto 3px;color:currentColor;transition:transform .32s cubic-bezier(.34,1.7,.5,1)}
.tab.on .ico{transform:translateY(-3px) scale(1.14)}
.btn .ico{display:inline-block;vertical-align:-3px;margin-right:5px}
.empty .ico{width:44px;height:44px;margin:0 auto 13px;opacity:.4;color:var(--muted)}
.hchip .ico{width:11px;height:11px}
.acode .ico{width:23px;height:23px;color:var(--amber)}

/* ---- Сетка районов в две колонки ---- */
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:11px}
@media(min-width:700px){.grid2{grid-template-columns:repeat(3,1fr)}}
.gcard{
  position:relative;background:var(--surf);border:1px solid var(--line);
  border-radius:var(--r-lg);overflow:hidden;cursor:pointer;backdrop-filter:blur(16px);
  transition:transform .22s cubic-bezier(.34,1.4,.5,1),border-color .22s;box-shadow:var(--sh);
}
.gcard:active{transform:scale(.965);border-color:rgba(240,160,60,.42)}
.gtop{
  height:74px;position:relative;overflow:hidden;
  background:linear-gradient(150deg,#123a5c,#0c2138);
}
.gtop svg.bgw{position:absolute;left:0;right:0;bottom:-2px;width:200%;height:32px;opacity:.42}
.gtop .gi{
  position:absolute;left:12px;top:12px;width:34px;height:34px;border-radius:11px;
  background:rgba(240,160,60,.17);border:1px solid rgba(240,160,60,.3);
  display:flex;align-items:center;justify-content:center;color:var(--amber);
}
.gtop .gi .ico{width:19px;height:19px;margin:0}
.gstar{
  position:absolute;right:9px;top:9px;width:30px;height:30px;border-radius:50%;
  background:rgba(8,18,30,.62);border:1px solid rgba(255,255,255,.13);cursor:pointer;
  display:flex;align-items:center;justify-content:center;color:rgba(255,255,255,.5);
  transition:transform .26s cubic-bezier(.34,1.7,.5,1),color .2s;backdrop-filter:blur(6px);
}
.gstar .ico{width:15px;height:15px;margin:0}
.gstar.on{color:var(--amber)}
.gstar.on .ico{fill:var(--amber)}
.gstar:active{transform:scale(1.28)}
.gbadge{
  position:absolute;left:12px;bottom:9px;background:var(--hot);color:#fff;
  font-size:9px;font-weight:800;border-radius:7px;padding:2.5px 7px;letter-spacing:.4px;
  animation:blink 2.3s infinite;
}
.gbody{padding:11px 12px 13px}
.gcode{font-size:11px;font-weight:800;color:var(--amber);letter-spacing:.5px}
.gname{font-size:13px;font-weight:700;margin-top:2px;line-height:1.3;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:34px}
.gfoot{display:flex;align-items:baseline;justify-content:space-between;margin-top:9px}
.gcnt{font-size:21px;font-weight:800;letter-spacing:-.6px}
.gsub{font-size:10px;color:var(--muted)}

/* ---- Экран деталей ---- */
.detail{
  position:fixed;inset:0;z-index:1200;background:var(--bg);overflow-y:auto;
  display:none;padding-bottom:34px;
}
.detail.on{display:block;animation:slideUp .34s cubic-bezier(.22,.95,.3,1)}
@keyframes slideUp{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
.dhero{position:relative;height:255px}
#dmap{position:absolute;inset:0}
.dfade{
  position:absolute;left:0;right:0;bottom:0;height:96px;pointer-events:none;
  background:linear-gradient(180deg,transparent,var(--bg) 92%);
}
.dnav{
  position:absolute;top:calc(13px + env(safe-area-inset-top));left:13px;right:13px;
  display:flex;justify-content:space-between;z-index:600;
}
.dbtn{
  width:42px;height:42px;border-radius:14px;border:1px solid rgba(255,255,255,.15);
  background:rgba(8,18,30,.7);backdrop-filter:blur(14px);cursor:pointer;
  display:flex;align-items:center;justify-content:center;color:#eef4fa;
  transition:transform .22s cubic-bezier(.34,1.6,.5,1);
}
.dbtn:active{transform:scale(.88)}
.dbtn.on{color:var(--amber);border-color:rgba(240,160,60,.45)}
.dbtn.on .ico{fill:var(--amber)}
.dbody{padding:0 16px;margin-top:-30px;position:relative;z-index:5}
.dtop{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:10px}
.dtitle{font-size:23px;font-weight:800;letter-spacing:-.7px;line-height:1.15;margin:2px 0 5px}
.dreg{font-size:13px;color:var(--muted);margin-bottom:15px;display:flex;align-items:center;gap:6px}
.dpanel{
  background:var(--surf);border:1px solid var(--line);border-radius:var(--r-lg);
  padding:15px;margin-bottom:12px;backdrop-filter:blur(16px);
}
.dpanel h4{margin:0 0 9px;font-size:11px;color:var(--dim);text-transform:uppercase;
  letter-spacing:.9px;font-weight:750}
.dtext{font-size:14px;line-height:1.62;white-space:pre-wrap;word-break:break-word;opacity:.94}
.dcoords{display:grid;gap:7px}
.dcoord{
  display:flex;align-items:center;justify-content:space-between;gap:9px;
  padding:9px 12px;background:var(--surf2);border-radius:var(--r-sm);
  font-size:12.5px;border:1px solid var(--line);cursor:pointer;
}
.dcoord:active{border-color:rgba(240,160,60,.4)}
.dcoord .cv{color:var(--amber);font-weight:700}
.dcoord .ct{color:var(--muted);font-size:11px}
.dmeta{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:13px}
.dchip{
  display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:650;
  background:var(--surf2);border:1px solid var(--line);border-radius:20px;padding:6px 12px;color:var(--muted);
}
.dchip .ico{width:13px;height:13px}
.dbar{
  position:sticky;bottom:0;padding:13px 16px calc(13px + env(safe-area-inset-bottom));
  background:linear-gradient(180deg,transparent,var(--bg) 30%);display:flex;gap:9px;
}
</style>
</head>
<body>

<div class="wrap">

  <div class="wkhdr" id="header">
    <div class="wkmark" data-notr>
      <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
        <path d="M24 9v24M17 20c4 4 10 4 14 0M17 33c4 5 10 5 14 0M13 39h22"/>
      </svg>
    </div>
    <div class="wkname" data-notr>
      <div class="n1">WATCHKEEPER</div>
      <div class="n2" id="hdrSub">Your Digital Assistance</div>
    </div>
    <div class="wkclock">
      <div class="t" id="hdrClock">--:--<span>UTC</span></div>
      <div class="d" id="hdrDate">—</div>
    </div>
    <button class="wkbell" id="notifBtn" aria-label="Уведомления">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <path d="M6 17h12M8 16v-6a4 4 0 0 1 8 0v6M11 20h2"/>
      </svg>
      <b id="notifCnt"></b>
    </button>
  </div>
  <div class="hdrtools">
    <button class="geobtn" id="geoBtn" title="Позиция с устройства"></button>
    <button class="langbtn" id="langBtn">RU</button>
    <div class="avatar" id="themeBtn" title="Тема оформления" data-notr>
      <svg class="lamp" viewBox="0 0 24 24" aria-hidden="true">
        <circle class="halo" cx="12" cy="10" r="9"/>
        <path class="glass" d="M12 3a6 6 0 0 0-3.6 10.8V16h7.2v-2.2A6 6 0 0 0 12 3z"/>
        <path class="fil" d="M10 10.5 11 8.5 12 10.5 13 8.5 14 10.5"/>
        <rect class="base" x="9.4" y="16.6" width="5.2" height="1.6" rx=".7"/>
        <rect class="base" x="9.4" y="19" width="5.2" height="1.6" rx=".7"/>
      </svg>
    </div>
    <span class="hello" id="hello"></span>
    <span class="hello" id="buildId" style="font-size:9px;opacity:.5"></span>
  </div>

  <div class="srow" id="topSearch">
    <div class="sbox">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input id="q" placeholder="Номер, координаты, текст…">
    </div>
    <button class="fbtn" id="fbtn"></button>
  </div>

  <div class="cats" id="cats"></div>

  <div class="subtabs" id="subtabs"></div>
  <div class="trialbar hidden" id="trialbar"></div>
  <div class="errbar" id="errbar"></div>
  <div class="offline" id="offline"><span id="offIco"></span>Нет связи. Показаны последние сохранённые данные.</div>

  <!-- ГЛАВНАЯ -->
  <section id="v-dash">
    <!-- Судно и приветствие -->
    <div class="wkhero" id="hero">
      <div class="art" data-notr>
        <!-- xMidYMax: низ кадра всегда прижат к низу карточки, поэтому море
             доходит до края, а не обрывается посередине -->
        <svg viewBox="0 0 400 200" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
          <defs>
            <linearGradient id="hSky" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#071a2c"/><stop offset=".55" stop-color="#12406b"/>
              <stop offset="1" stop-color="#2a5c7e"/>
            </linearGradient>
            <linearGradient id="hSea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#1a6390"/><stop offset="1" stop-color="#071d31"/>
            </linearGradient>
            <radialGradient id="hGlow" cx=".5" cy=".5" r=".5">
              <stop offset="0" stop-color="#ffd894" stop-opacity=".85"/>
              <stop offset="1" stop-color="#ffd894" stop-opacity="0"/>
            </radialGradient>
            <linearGradient id="hBeam" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stop-color="#ffe6b0" stop-opacity=".55"/>
              <stop offset="1" stop-color="#ffe6b0" stop-opacity="0"/>
            </linearGradient>
          </defs>

          <rect width="400" height="200" fill="url(#hSky)"/>

          <!-- звёзды -->
          <g fill="#dcecff">
            <circle cx="36" cy="22" r="1" opacity=".7"/><circle cx="88" cy="14" r=".8" opacity=".5"/>
            <circle cx="150" cy="28" r="1" opacity=".65"/><circle cx="214" cy="17" r=".9" opacity=".55"/>
            <circle cx="278" cy="30" r="1" opacity=".6"/><circle cx="336" cy="19" r=".8" opacity=".5"/>
            <circle cx="376" cy="38" r="1" opacity=".55"/><circle cx="118" cy="44" r=".7" opacity=".4"/>
          </g>

          <!-- Одесса: город на холме, слева Потёмкинская лестница и Дюк -->
          <g>
            <!-- склон берега -->
            <path d="M0 112 L118 96 L214 100 L400 92 L400 132 L0 132 Z" fill="#0b2137"/>
            <!-- силуэт застройки -->
            <g fill="#102b45">
              <rect x="6" y="80" width="20" height="32"/><rect x="30" y="72" width="14" height="40"/>
              <rect x="48" y="86" width="18" height="26"/><rect x="70" y="76" width="12" height="36"/>
              <rect x="150" y="82" width="16" height="20"/><rect x="170" y="74" width="20" height="28"/>
              <rect x="194" y="86" width="14" height="16"/>
              <rect x="238" y="78" width="18" height="18"/><rect x="260" y="70" width="12" height="26"/>
              <rect x="278" y="82" width="22" height="14"/>
            </g>
            <!-- окна -->
            <g fill="#ffd894">
              <rect class="win" x="10" y="86" width="3" height="4"/><rect class="win" x="17" y="86" width="3" height="4"/>
              <rect class="win" x="10" y="94" width="3" height="4"/><rect class="win" x="34" y="78" width="3" height="4"/>
              <rect class="win" x="34" y="88" width="3" height="4"/><rect class="win" x="52" y="92" width="3" height="4"/>
              <rect class="win" x="59" y="92" width="3" height="4"/><rect class="win" x="74" y="82" width="3" height="4"/>
              <rect class="win" x="155" y="88" width="3" height="4"/><rect class="win" x="176" y="80" width="3" height="4"/>
              <rect class="win" x="183" y="80" width="3" height="4"/><rect class="win" x="243" y="84" width="3" height="4"/>
              <rect class="win" x="264" y="76" width="3" height="4"/><rect class="win" x="284" y="88" width="3" height="4"/>
            </g>

            <!-- Потёмкинская лестница -->
            <g fill="#16334f">
              <path d="M96 112 L140 112 L136 116 L100 116 Z"/>
              <path d="M99 117 L137 117 L133 121 L103 121 Z"/>
              <path d="M102 122 L134 122 L131 126 L105 126 Z"/>
              <path d="M105 127 L131 127 L128 131 L108 131 Z"/>
            </g>
            <g stroke="#22496b" stroke-width=".7">
              <path d="M96 112 L100 131"/><path d="M140 112 L136 131"/>
            </g>
            <!-- памятник Дюку на верхней площадке -->
            <g>
              <rect x="115" y="98" width="6" height="12" fill="#1d3f5e"/>
              <rect x="113" y="96" width="10" height="3" fill="#22496b"/>
              <path d="M118 96 L118 88" stroke="#9fc0da" stroke-width="2.2" stroke-linecap="round"/>
              <circle cx="118" cy="86" r="1.9" fill="#b7d3e8"/>
              <path d="M118 91 L114 89" stroke="#9fc0da" stroke-width="1.4" stroke-linecap="round"/>
              <path d="M118 90 L122 93" stroke="#9fc0da" stroke-width="1.4" stroke-linecap="round"/>
            </g>

            <!-- портовые краны справа -->
            <g stroke="#1b3f5e" stroke-width="2" fill="none">
              <path d="M312 112 L312 84 M326 112 L326 84"/>
              <g transform="translate(300,78)">
                <g class="craneArm">
                  <path d="M12 6 L52 6" stroke="#1b3f5e" stroke-width="2.4"/>
                  <path d="M12 6 L2 14" stroke="#1b3f5e" stroke-width="2"/>
                  <path d="M40 6 L40 16" stroke="#1b3f5e" stroke-width="1.4"/>
                  <rect x="37" y="16" width="6" height="5" fill="#1b3f5e" stroke="none"/>
                </g>
              </g>
              <path d="M352 112 L352 88 M366 112 L366 88 M352 88 L390 88"/>
            </g>
            <!-- контейнеры на причале -->
            <g>
              <rect x="306" y="104" width="14" height="7" fill="#2c5a7d"/>
              <rect x="322" y="104" width="14" height="7" fill="#33506b"/>
              <rect x="306" y="96" width="14" height="7" fill="#26506f"/>
              <rect x="344" y="104" width="14" height="7" fill="#2f5f82"/>
            </g>
          </g>

          <!-- Воронцовский маяк на молу -->
          <g>
            <path d="M196 132 L262 132 L262 138 L196 138 Z" fill="#0d2740"/>
            <path d="M222 132 L224 104 L234 104 L236 132 Z" fill="#e9eff5"/>
            <path d="M229 132 L229 104 L234 104 L236 132 Z" fill="#c3d0dc"/>
            <path d="M223.4 118 h11.2 l.5 6 h-12.2 z" fill="#c9463a"/>
            <path d="M224.5 108 h8.9 l.4 5 h-9.7 z" fill="#c9463a"/>
            <rect x="221" y="100" width="16" height="4" fill="#1d3f5e"/>
            <rect x="223.5" y="93" width="11" height="8" rx="1.5" fill="#3d5f80"/>
            <rect class="lhLamp" x="225" y="94" width="8" height="6" rx="1" fill="#ffd894"/>
            <circle class="lhLamp" cx="229" cy="97" r="9" fill="url(#hGlow)"/>
            <path d="M223 93 L229 87 L235 93 Z" fill="#1d3f5e"/>
            <rect x="228.2" y="82" width="1.6" height="5" fill="#1d3f5e"/>
            <!-- луч, обходящий горизонт -->
            <g transform="translate(229,97)">
              <g class="lhSweep">
                <polygon class="lhBeam" points="0,0 190,-46 190,46" fill="url(#hBeam)"/>
              </g>
            </g>
          </g>

          <!-- море от линии горизонта и до низа кадра -->
          <rect y="132" width="400" height="68" fill="url(#hSea)"/>
          <!-- лунная дорожка -->
          <path class="shimmer" d="M216 133 L242 133 L272 200 L186 200 Z" fill="#ffd894" opacity=".18"/>
          <!-- дальняя зыбь у горизонта: почти неподвижная, даёт глубину -->
          <g class="waveA" opacity=".55">
            <path d="M-100 141 q25 -3 50 0 t50 0 t50 0 t50 0 t50 0 t50 0 t50 0 t50 0 t50 0 t50 0 v8 h-600 z"
                  fill="#15547f"/>
          </g>

          <!-- Судно идёт по воде между дальней и средней волной.
               Смещение вниз вынесено в отдельную обёртку: CSS-анимация
               задаёт свой transform и полностью перебивает атрибут
               transform на том же элементе -- с ним судно улетало наверх,
               к нулю координат. -->
          <g class="shipGo">
            <g transform="translate(0,131)">
            <g class="shipRoll">
              <!-- отражение в воде -->
              <path d="M6 27 L66 27 L60 36 L12 36 Z" fill="#0a2f4e" opacity=".45"/>
              <!-- корпус -->
              <path d="M6 16 L66 16 L60 26 L12 26 Z" fill="#132f47"/>
              <path d="M6 16 L66 16 L65.4 18 L6.6 18 Z" fill="#25577f"/>
              <!-- надстройка и груз -->
              <rect x="46" y="6" width="16" height="10" rx="1" fill="#1b3f5e"/>
              <rect x="49" y="8.5" width="3" height="3" fill="#cfe6fb" opacity=".9"/>
              <rect x="55" y="8.5" width="3" height="3" fill="#cfe6fb" opacity=".9"/>
              <rect x="14" y="10" width="7" height="6" fill="#2c5a7d"/>
              <rect x="24" y="10" width="7" height="6" fill="#33506b"/>
              <rect x="34" y="10" width="7" height="6" fill="#26506f"/>
              <rect x="14" y="4" width="7" height="6" fill="#2f5f82"/>
              <rect x="24" y="4" width="7" height="6" fill="#2c5a7d"/>
              <!-- мачта и огни -->
              <path d="M57 6 L57 -4" stroke="#8fa8c0" stroke-width="1.4"/>
              <circle class="mastFlash" cx="57" cy="-5" r="1.8" fill="#ffffff"/>
              <circle class="navGreen" cx="64" cy="20" r="1.7" fill="#3fc97f"/>
              <circle class="navRed" cx="8" cy="20" r="1.7" fill="#ff5c65"/>
              <!-- бурун у форштевня и кильватерный след -->
              <path d="M60 26 q7 1 11 4 q-6 1 -12 -1 z" fill="#cfe6fb" opacity=".5"/>
              <path d="M12 26 q-9 2 -16 5 q10 1 18 -2 z" fill="#cfe6fb" opacity=".35"/>
            </g>
            </g>
          </g>

          <!-- волны: три слоя, ближние идут быстрее и перекрывают корпус,
               поэтому судно сидит в воде, а не висит над ней -->
          <g class="waveA">
            <path d="M-100 152 q25 -6 50 0 t50 0 t50 0 t50 0 t50 0 t50 0 t50 0 t50 0 t50 0 t50 0 v60 h-600 z"
                  fill="#0f4269" opacity=".9"/>
          </g>
          <g class="waveB">
            <path d="M-130 166 q30 -7 60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 v50 h-660 z"
                  fill="#0b3151" opacity=".95"/>
          </g>
          <g class="waveC">
            <path d="M-80 182 q20 -5 40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 v40 h-560 z"
                  fill="#071f36"/>
          </g>
        </svg>
      </div>
      <div class="eyebrow">BRIDGE INTELLIGENCE</div>
      <div class="greet" id="heroGreet">Спокойной вахты</div>
      <div class="sub" id="heroSub">Помощник вахтенного на связи</div>
      <div class="wkvessel" id="vessel-status"></div>
    </div>

    <!-- Подсказки ассистента вместо таблицы инструментов -->
    <div class="wksech"><h3>Чем помочь?</h3><a id="askAll">Все запросы →</a></div>
    <div class="wkprompts" id="ai-prompts"></div>

    <!-- Сводка с мостика -->
    <div class="wksech"><h3>Сводка с мостика</h3><a id="snapLive">LIVE ›</a></div>
    <div class="wksnap" id="bridge-snapshot"></div>

    <!-- Тревога -->
    <button class="wkalert" id="alert-strip"></button>

    <!-- Ассистент -->
    <div class="wkask" id="ask-ai">
      <div class="top">
        <div class="orb"><i></i><i></i></div>
        <div style="min-width:0">
          <div class="t1" data-notr>Ask AI</div>
          <div class="t2">Помощник на мостике</div>
        </div>
      </div>
      <div class="wkaskrow">
        <button class="wkaskfield" id="askOpen">Спроси про навигацию, ГМССБ, погоду…</button>
        <button class="wkasksend" id="askGo" aria-label="Открыть ассистента">➤</button>
      </div>
    </div>


    <div id="lastCalcBox"></div>
    <div id="histBox"></div>
  </section>

  <!-- РАЙОНЫ -->
  <section id="v-areas" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Районы</h3></div>
    <div class="sech"><h3 id="areasTitle">Все районы</h3><a id="sortBtn">По количеству ⇅</a></div>
    <div id="arealist"><div class="sk card"></div><div class="sk card"></div><div class="sk card"></div></div>
  </section>

  <!-- КАРТА -->
  <section id="v-map" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Обстановка</h3></div>
    <div class="chips" id="mapchips"></div>
    <div class="mapwrap">
      <div id="map"></div>
      <button class="mapgear" id="mapGear"></button>
      <div class="mapctl" id="mapCtl">
        <p class="ttl">Подложка</p>
        <label><input type="radio" name="base" value="dark" checked>Тёмная</label>
        <label><input type="radio" name="base" value="ocean">Океан</label>
        <label><input type="radio" name="base" value="osm">OpenStreetMap</label>
        <p class="ttl">Слои</p>
        <label><input type="checkbox" id="lyAreas" checked>Районы и полосы</label>
        <label><input type="checkbox" id="lyPoints" checked>Точечные объекты</label>
        <label><input type="checkbox" id="lyLabels" checked>Подписи номеров</label>
      </div>
      <div class="cursorpos">
        <div class="lb">Позиция курсора</div>
        <div class="vl mono" id="curpos">—</div>
      </div>
    </div>
    <div class="mapstat" id="mapstat"></div>
    <div class="legend">
      <span><i style="background:#f0a03c"></i>Предупреждения</span>
      <span><i style="background:#3fc97f"></i>MARPOL Прил. V</span>
      <span><i style="background:#4d93d6"></i>Судовые сообщения</span>
    </div>
  </section>

  <!-- СПРАВОЧНЫЕ ЗОНЫ -->
  <section id="v-zones" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Справочные зоны</h3></div>
    <div class="sech" style="display:none"><h3>Справочные зоны</h3></div>
    <div id="zonelist"></div>
  </section>

  <!-- ИНСТРУМЕНТЫ -->
  <section id="v-tools" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Инструменты</h3></div>
    <div class="hint" id="toolsHint"></div>
    <div id="toollist"></div>
  </section>

  <!-- ЧЕК-ЛИСТЫ И СЕРТИФИКАТЫ -->
  <section id="v-bridge" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Чек-листы</h3></div>
    <div id="bridgeBox"></div>
  </section>

  <!-- СПРАВОЧНИКИ -->
  <section id="v-refs" class="hidden">
    <div id="refBox"></div>
  </section>

  <!-- РАДИО -->
  <section id="v-radio" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Тест MF/HF DSC</h3></div>
    <div class="sech" style="display:none"><h3>Тест MF/HF DSC</h3></div>
    <div class="hint" id="radioHint"></div>
    <div class="chips" id="rchips"></div>
    <div class="rmapwrap"><div id="rmap"></div></div>
    <div class="rlegend">
      <span><i style="background:#3fc97f"></i>Автоподтверждение</span>
      <span><i style="background:#f0a03c"></i>Отвечает стабильно</span>
      <span><i style="background:#7f96ac"></i>Отвечает не всегда</span>
    </div>
    <div id="radiolist"><div class="sk card"></div><div class="sk card"></div></div>
  </section>

  <!-- МОЁ СУДНО -->
  <section id="v-ship" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Моё судно</h3></div>
    <div id="vesselBox"><div class="sk card"></div><div class="sk card"></div></div>
  </section>

  <!-- МОИ ПОРТЫ -->
  <section id="v-ports" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Мои порты</h3></div>
    <div class="hint" id="portsHint"></div>
    <div class="fld">
      <label>Добавить порт захода</label>
      <div class="sbox" id="pnewBox"><input id="pnew" placeholder="Например Constanta" autocomplete="off"></div>
      <div class="sugg" id="snew"></div>
    </div>
    <div id="portsBox"></div>
  </section>

  <!-- СПРАВКА -->
  <section id="v-faq" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Справка</h3></div>
    <div class="sbox" style="margin-bottom:12px">
      <input id="faqQ" placeholder="Найти в справке…" autocomplete="off">
    </div>
    <div id="faqBox"></div>
  </section>

  <!-- ПОДДЕРЖКА -->
  <section id="v-support" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Поддержка</h3></div>
    <div class="hint" id="supHint"></div>
    <div id="supBox" class="askbox"></div>
    <div class="askbar">
      <input id="supInput" class="askinput" placeholder="Опиши, что случилось…" autocomplete="off">
      <button id="supSend" class="asksend">→</button>
    </div>
  </section>

  <!-- УВЕДОМЛЕНИЯ -->
  <section id="v-notif" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Уведомления</h3>
      <a id="notifClear" class="vsub">Прочитано</a></div>
    <div id="notifBox"></div>
  </section>

  <!-- АДМИН-ПАНЕЛЬ (только владельцу) -->
  <section id="v-admin" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Админ-панель</h3>
      <a id="admReload" class="vsub">Обновить</a></div>
    <div id="admBox"></div>
  </section>

  <!-- НАСТРОЙКИ -->
  <section id="v-settings" class="hidden">
    <div id="settingsBox"></div>
  </section>

  <!-- ЦИКЛОНЫ -->
  <section id="v-cyc" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Тропические циклоны</h3></div>
    <div id="cycBox"></div>
  </section>

  <!-- ASK WATCHKEEPER -->
  <section id="v-ask" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Ask WatchKeeper</h3>
      <a id="askClear" class="vsub">Очистить</a></div>
    <div id="askBox" class="askbox"></div>
    <div class="askbar">
      <input id="askInput" class="askinput" placeholder="Спроси про расчёт, маршрут или вахту…" autocomplete="off">
      <button id="askSend" class="asksend">→</button>
    </div>
  </section>

  <!-- ТРЕНАЖЁР ЦИВ -->
  <section id="v-dsc" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Тренажёр ЦИВ</h3></div>
    <div class="sech" style="display:none"><h3>Тренажёр ЦИВ</h3></div>
    <div id="dscBox"><div class="sk card"></div></div>
  </section>

  <!-- EPIRB TEST -->
  <section id="v-epirb" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>EPIRB Test</h3></div>
    <div class="sech" style="display:none"><h3>EPIRB Test</h3></div>
    <div id="epirbBox"><div class="sk card"></div></div>
  </section>

  <!-- SART TEST -->
  <section id="v-sart" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>SART Test</h3></div>
    <div class="sech" style="display:none"><h3>SART Test</h3></div>
    <div id="sartBox"><div class="sk card"></div></div>
  </section>

  <!-- РЕЙС -->
  <section id="v-voy" class="hidden">
    <div class="vhead"><button class="vback" data-back></button><h3>Планирование перехода</h3></div>
    <div class="sech" style="display:none"><h3>Планирование перехода</h3></div>
    <div class="fld">
      <label>Порт отправления</label>
      <div class="sbox" id="pfromBox"><input id="pfrom" placeholder="Например Constanta" autocomplete="off"></div>
      <div class="sugg" id="sfrom"></div>
    </div>
    <div class="fld">
      <label>Порт прибытия</label>
      <div class="sbox" id="ptoBox"><input id="pto" placeholder="Например Santos" autocomplete="off"></div>
      <div class="sugg" id="sto"></div>
    </div>
    <div class="fld">
      <label>Ширина коридора</label>
      <div class="cats" id="corr">
        <div class="cat" data-c="50"><span class="cn">50 миль</span></div>
        <div class="cat on" data-c="150"><span class="cn">150 миль</span></div>
        <div class="cat" data-c="300"><span class="cn">300 миль</span></div>
        <div class="cat" data-c="500"><span class="cn">500 миль</span></div>
      </div>
    </div>
    <button class="btn wide" id="govoy">Проложить и проверить</button>
    <div id="voyout"></div>
  </section>
</div>

<div class="detail" id="detail">
  <div class="dhero">
    <div id="dmap"></div>
    <div class="dfade"></div>
    <div class="dnav">
      <button class="dbtn" id="dBack"></button>
      <button class="dbtn" id="dFav"></button>
    </div>
  </div>
  <div class="dbody">
    <div class="dtop" id="dTop"></div>
    <div class="dtitle" id="dTitle"></div>
    <div class="dreg" id="dReg"></div>
    <div class="dmeta" id="dMeta"></div>
    <div class="dpanel"><h4>Текст предупреждения</h4><div class="dtext" id="dText"></div></div>
    <div class="dpanel"><h4>Координаты</h4><div class="dcoords" id="dCoords"></div></div>
  </div>
  <div class="dbar">
    <button class="btn wide" id="dToMap">На общую карту</button>
  </div>
</div>

<div class="detail" id="tool">
  <div class="dbody">
    <div class="topback">
      <button id="tBackTop"></button>
      <span class="tb" id="tBackTitle"></span>
    </div>
    <div class="thead">
      <div class="ti" id="tIcon"></div>
      <div style="min-width:0">
        <div class="dtitle hidden" id="tName" style="font-size:20px;margin:0"></div>
        <div class="gsub" id="tDesc" style="display:block;margin-top:3px"></div>
      </div>
    </div>
    <div class="dpanel" style="margin-top:15px"><h4>Исходные данные</h4><div id="tFields"></div></div>
    <div class="dpanel"><h4>Результат</h4><div id="tResults"></div></div>
    <div class="hint">Расчёт справочный. Решение принимает судоводитель по официальным пособиям и данным судна.</div>
  </div>
  <div class="dbar"><button class="btn wide" id="tBack">Назад к инструментам</button></div>
</div>

<nav class="tabs" id="bottom-navigation">
  <div class="tabsin">
    <button class="tab on" data-g="home" data-i="gauge"><span class="ic"></span><span class="lb">Главная</span></button>
    <button class="tab" data-g="tools" data-i="sliders"><span class="ic"></span><span class="lb">Инструменты</span></button>
    <button class="tab tab-ask" data-g="ask" id="bottom-ask-ai"><span class="ic" data-notr>AI</span><span class="lb" data-notr>ASK AI</span></button>
    <button class="tab" data-g="map" data-i="map"><span class="ic"></span><span class="lb">Карта</span></button>
    <button class="tab" data-g="profile" data-i="ship"><span class="ic"></span><span class="lb">Моё судно</span></button>
  </div>
</nav>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
/* ---- Векторные иконки (вместо эмодзи) ---- */
const ICONS={
  target:'<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.2" fill="currentColor" stroke="none"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  compass:'<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2.1 5-5 2.1 2.1-5z" fill="currentColor" stroke="none"/>',
  search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/>',
  sliders:'<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2" fill="currentColor" stroke="none"/><circle cx="10" cy="12" r="2" fill="currentColor" stroke="none"/><circle cx="18" cy="18" r="2" fill="currentColor" stroke="none"/>',
  gauge:'<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4.5-5"/><circle cx="12" cy="18" r="1.6" fill="currentColor" stroke="none"/>',
  globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18"/>',
  map:'<path d="M9 4L3 6.5v13L9 17l6 2.5 6-2.5v-13L15 6.5z"/><path d="M9 4v13M15 6.5v13"/>',
  ship:'<path d="M3 17l1.6-5.4a1 1 0 0 1 .96-.72h12.88a1 1 0 0 1 .96.72L21 17"/><path d="M7 11V7h10v4M12 4v3"/><path d="M2 20c1.5 0 1.5-1.4 3-1.4S6.5 20 8 20s1.5-1.4 3-1.4S12.5 20 14 20s1.5-1.4 3-1.4S18.5 20 20 20"/>',
  anchor:'<circle cx="12" cy="4.5" r="2.2"/><path d="M12 6.7V21M6.5 11H17.5M4 15a8 8 0 0 0 16 0"/>',
  lighthouse:'<path d="M9 21l1.2-10h3.6L15 21z"/><path d="M9.6 15h4.8M10 11V8h4v3"/><path d="M12 4.5V8M8.5 6l-3-1.5M15.5 6l3-1.5"/>',
  wave:'<path d="M2 9c2.2 0 2.2-2 4.4-2S8.6 9 10.8 9 13 7 15.2 7s2.2 2 4.4 2M2 14c2.2 0 2.2-2 4.4-2s2.2 2 4.4 2 2.2-2 4.4-2 2.2 2 4.4 2M2 19c2.2 0 2.2-2 4.4-2s2.2 2 4.4 2 2.2-2 4.4-2 2.2 2 4.4 2"/>',
  alert:'<path d="M12 4.5L2.8 20h18.4z"/><path d="M12 10v4.5M12 17.2v.2"/>',
  star:'<path d="M12 3.6l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
  archive:'<rect x="3" y="4" width="18" height="4.5" rx="1.4"/><path d="M5 8.5V19a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8.5M10 13h4"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5.3l3.4 2"/>',
  back:'<path d="M15 5l-7 7 7 7"/>',
  radar:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12l6.4-6.4"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
  route:'<circle cx="6" cy="18" r="2.6"/><circle cx="18" cy="6" r="2.6"/><path d="M8.4 16.4C11 14 10 11 12.5 9.4c1.2-.8 2.2-1.2 3.1-1.4" stroke-dasharray="3 2.6"/>',
  flag:'<path d="M6 21V4M6 4h11l-2 3.5L17 11H6"/>',
  buoy:'<path d="M12 3v6M8.6 9h6.8l1.6 6H7z"/><path d="M2 19c2 0 2-1.5 4-1.5S8 19 10 19s2-1.5 4-1.5S16 19 18 19s2-1.5 4-1.5"/>',
  iceberg:'<path d="M12 4l4.5 8h-9z"/><path d="M4 20l4-8h8l4 8z"/><path d="M2 16.5c2 0 2-1.2 4-1.2"/>',
  sun:'<circle cx="12" cy="10" r="3.6"/><path d="M12 3v2M12 15v1.5M5 10H3M21 10h-2M7 5L5.6 3.6M18.4 3.6L17 5"/><path d="M2 19c2.2 0 2.2-1.6 4.4-1.6S8.6 19 10.8 19s2.2-1.6 4.4-1.6 2.2 1.6 4.4 1.6"/>'
};
function ico(n,cls,sw){
  return `<svg class="ico ${cls||''}" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="${sw||1.8}" stroke-linecap="round" stroke-linejoin="round">${ICONS[n]||''}</svg>`;
}
/* какой значок какому району */
const AREA_ICON={
  I:'wave','I-COASTAL':'lighthouse',II:'wave',III:'sun',IV:'sun',V:'wave',VI:'wave',VII:'wave',
  VIII:'sun',IX:'sun',X:'wave',XI:'wave',XII:'wave',XIII:'iceberg',XIV:'wave',XV:'wave',
  XVI:'buoy',XVII:'iceberg',XVIII:'iceberg',XIX:'iceberg',XX:'iceberg',XXI:'iceberg',
  HYDROLANT:'globe',HYDROPAC:'globe'
};
const areaIcon=c=>c.startsWith('COASTAL:')?'lighthouse':(AREA_ICON[c]||'flag');

/* ================= Морские расчёты =================
   Всё считается прямо в приложении, без обращения к серверу --
   в рейсе связь пропадает, а калькулятор должен работать всегда. */
const R_NM=3440.065, D2R=Math.PI/180, R2D=180/Math.PI;
const norm360=d=>((d%360)+360)%360;

/* -- расстояния и курсы -- */
function gcDistance(la1,lo1,la2,lo2){
  const p1=la1*D2R,p2=la2*D2R,dp=(la2-la1)*D2R,dl=(lo2-lo1)*D2R;
  const a=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
  return 2*R_NM*Math.asin(Math.min(1,Math.sqrt(a)));
}
function initialBearing(la1,lo1,la2,lo2){
  const p1=la1*D2R,p2=la2*D2R,dl=(lo2-lo1)*D2R;
  const y=Math.sin(dl)*Math.cos(p2);
  const x=Math.cos(p1)*Math.sin(p2)-Math.sin(p1)*Math.cos(p2)*Math.cos(dl);
  return norm360(Math.atan2(y,x)*R2D);
}
function finalBearing(la1,lo1,la2,lo2){
  return norm360(initialBearing(la2,lo2,la1,lo1)+180);
}
function rhumbDistance(la1,lo1,la2,lo2){
  const p1=la1*D2R,p2=la2*D2R,dp=p2-p1;
  let dl=Math.abs(lo2-lo1)*D2R;
  if(dl>Math.PI) dl=2*Math.PI-dl;
  const dPsi=Math.log(Math.tan(Math.PI/4+p2/2)/Math.tan(Math.PI/4+p1/2));
  const q=Math.abs(dPsi)>1e-11?dp/dPsi:Math.cos(p1);
  return Math.sqrt(dp*dp+q*q*dl*dl)*R_NM;
}
function rhumbBearing(la1,lo1,la2,lo2){
  const p1=la1*D2R,p2=la2*D2R;
  let dl=(lo2-lo1)*D2R;
  if(Math.abs(dl)>Math.PI) dl=dl>0?-(2*Math.PI-dl):(2*Math.PI+dl);
  const dPsi=Math.log(Math.tan(Math.PI/4+p2/2)/Math.tan(Math.PI/4+p1/2));
  return norm360(Math.atan2(dl,dPsi)*R2D);
}

/* -- координаты -- */
function parseCoord(txt){
  if(!txt) return null;
  const t=String(txt).trim().toUpperCase().replace(/,/g,'.');
  let m=t.match(/^(\d{1,3})[°\s-](\d{1,2}(?:\.\d+)?)['\s-]*(\d{1,2}(?:\.\d+)?)?["\s]*([NSEW])?$/);
  if(m){
    let v=+m[1]+(+m[2])/60+(m[3]?(+m[3])/3600:0);
    if(m[4]==='S'||m[4]==='W') v=-v;
    return v;
  }
  m=t.match(/^(-?\d+(?:\.\d+)?)°?\s*([NSEW])?$/);
  if(m){ let v=+m[1]; if(m[2]==='S'||m[2]==='W') v=-Math.abs(v); return v; }
  return null;
}
function toDDM(v,isLat){
  const h=v>=0?(isLat?'N':'E'):(isLat?'S':'W'),a=Math.abs(v);
  const d=Math.floor(a),m=(a-d)*60;
  return `${String(d).padStart(isLat?2:3,'0')}°${m.toFixed(3).padStart(6,'0')}'${h}`;
}
function toDMS(v,isLat){
  const h=v>=0?(isLat?'N':'E'):(isLat?'S':'W'),a=Math.abs(v);
  const d=Math.floor(a),mf=(a-d)*60,m=Math.floor(mf),s=(mf-m)*60;
  return `${String(d).padStart(isLat?2:3,'0')}°${String(m).padStart(2,'0')}'${s.toFixed(1).padStart(4,'0')}"${h}`;
}

/* -- проседание (Barrass, упрощённая) -- */
function squat(cb,v,confined){
  return confined ? (cb*v*v)/50 : (cb*v*v)/100;
}

/* -- запас воды под килём -- */
function ukc(chartedDepth,tide,draft,sq,heelAllow,waveAllow){
  const avail=chartedDepth+tide;
  const need=draft+sq+(heelAllow||0)+(waveAllow||0);
  return {available:avail, required:need, ukc:avail-need};
}

/* -- якорная стоянка -- */
function anchorSwing(chainLen,depth,hawseHeight,loa){
  const vert=depth+(hawseHeight||0);
  const horiz=chainLen>vert?Math.sqrt(chainLen*chainLen-vert*vert):0;
  return {horizontal:horiz, radius:horiz+(loa||0), scope:depth>0?chainLen/vert:0};
}

/* -- надводный габарит -- */
function airDraft(chartedClearance,hat,tideNow,shipAirDraft){
  const actual=chartedClearance+(hat-tideNow);
  return {actual:actual, margin:actual-shipAirDraft};
}

/* -- CPA / TCPA -- */
function cpaTcpa(ownCrs,ownSpd,tgtBrg,tgtRng,tgtCrs,tgtSpd){
  const rx=tgtRng*Math.sin(tgtBrg*D2R), ry=tgtRng*Math.cos(tgtBrg*D2R);
  const ovx=ownSpd*Math.sin(ownCrs*D2R), ovy=ownSpd*Math.cos(ownCrs*D2R);
  const tvx=tgtSpd*Math.sin(tgtCrs*D2R), tvy=tgtSpd*Math.cos(tgtCrs*D2R);
  const vx=tvx-ovx, vy=tvy-ovy;
  const v2=vx*vx+vy*vy;
  if(v2<1e-9) return {cpa:tgtRng, tcpa:0, relCourse:0, relSpeed:0, opening:true};
  const tcpa=-(rx*vx+ry*vy)/v2;
  const cx=rx+vx*tcpa, cy=ry+vy*tcpa;
  return {
    cpa:Math.sqrt(cx*cx+cy*cy),
    tcpa:tcpa,
    relCourse:norm360(Math.atan2(vx,vy)*R2D),
    relSpeed:Math.sqrt(v2),
    opening:tcpa<0
  };
}

/* ================= Маневренный планшет =================
   Рисунок к расчёту расхождения. Цифры CPA и TCPA отвечают, насколько
   близко и когда, но не показывают, с какого борта цель пройдёт и куда
   ведёт линия относительного движения. На разборе манёвра спрашивают
   именно это.

   Планшет ориентирован по норду, как бумажный: своё судно в центре,
   север вверху. Цель ставится по пеленгу и дистанции, от неё идёт линия
   относительного движения, и на ней отмечена точка кратчайшего
   сближения. Свой вектор и вектор цели нарисованы отдельно, чтобы было
   видно, из чего сложилось относительное движение. */

/* Экранные координаты точки: пеленг от норда по часовой, дальность в
   милях. Ось Y на экране растёт вниз, поэтому север это минус. */
function rpPoint(cx, cy, scale, bearing, range){
  const a = bearing * Math.PI / 180;
  return [cx + Math.sin(a) * range * scale, cy - Math.cos(a) * range * scale];
}

function radarPlot(inp, r){
  const size = 240, cx = 120, cy = 118, R = 96;
  // Шкала подбирается под дистанцию цели и округляется вверх до целых
  // миль: планшет с подписью «7.3 мили на кольце» читать неудобно.
  const maxRange = Math.max(2, Math.ceil(inp.tr * 1.35));
  const scale = R / maxRange;
  const fmt = n => (Math.round(n * 10) / 10);

  const tgt = rpPoint(cx, cy, scale, inp.tb, inp.tr);

  // Линию относительного движения ведём на час вперёд или до точки
  // сближения, смотря что дальше: короткая линия не показывает, куда
  // цель уходит после расхождения.
  const runTime = r.opening ? 0.5 : Math.max(0.3, Math.min(3, (r.tcpa || 0) * 1.6));
  const relDist = r.relSpeed * runTime;
  const relEnd = [tgt[0] + Math.sin(r.relCourse * Math.PI / 180) * relDist * scale,
                  tgt[1] - Math.cos(r.relCourse * Math.PI / 180) * relDist * scale];

  // Точка сближения лежит на линии относительного движения
  const cpaPt = r.opening ? null
    : [tgt[0] + Math.sin(r.relCourse * Math.PI / 180) * r.relSpeed * r.tcpa * scale,
       tgt[1] - Math.cos(r.relCourse * Math.PI / 180) * r.relSpeed * r.tcpa * scale];

  // Векторы движения: свой от центра, цели от отметки цели, оба за 1 час
  const own = rpPoint(cx, cy, scale, inp.oc, Math.min(inp.os, maxRange * 0.42));
  const tv = [tgt[0] + Math.sin(inp.tc * Math.PI / 180) * Math.min(inp.ts, maxRange * 0.42) * scale,
              tgt[1] - Math.cos(inp.tc * Math.PI / 180) * Math.min(inp.ts, maxRange * 0.42) * scale];

  const rings = [1 / 3, 2 / 3, 1].map(k =>
    `<circle cx="${cx}" cy="${cy}" r="${(R * k).toFixed(1)}" fill="none"
       stroke="currentColor" stroke-opacity="${k === 1 ? .5 : .22}" stroke-width="1"/>`).join('');

  const spokes = [0, 45, 90, 135, 180, 225, 270, 315].map(b => {
    const p = rpPoint(cx, cy, scale, b, maxRange);
    return `<line x1="${cx}" y1="${cy}" x2="${p[0].toFixed(1)}" y2="${p[1].toFixed(1)}"
      stroke="currentColor" stroke-opacity=".14" stroke-width="1"/>`;
  }).join('');

  const marks = [[0, 'N'], [90, 'E'], [180, 'S'], [270, 'W']].map(([b, t]) => {
    const p = rpPoint(cx, cy, scale, b, maxRange * 1.1);
    return `<text x="${p[0].toFixed(1)}" y="${(p[1] + 3).toFixed(1)}" text-anchor="middle"
      font-size="9" fill="currentColor" fill-opacity=".55">${t}</text>`;
  }).join('');

  const danger = !r.opening && r.cpa < 1;
  const relColor = danger ? 'var(--no, #e5484d)' : 'var(--amber, #e8a33e)';

  return `<svg viewBox="0 0 ${size} ${size}" class="rplot" role="img"
    aria-label="Маневренный планшет">
    <g color="var(--muted, #8b95a5)">${rings}${spokes}${marks}</g>

    <line x1="${cx}" y1="${cy}" x2="${own[0].toFixed(1)}" y2="${own[1].toFixed(1)}"
      stroke="var(--ok, #46a758)" stroke-width="2.2" stroke-linecap="round"/>
    <circle cx="${cx}" cy="${cy}" r="3.4" fill="var(--ok, #46a758)"/>

    <line x1="${tgt[0].toFixed(1)}" y1="${tgt[1].toFixed(1)}"
      x2="${relEnd[0].toFixed(1)}" y2="${relEnd[1].toFixed(1)}"
      stroke="${relColor}" stroke-width="1.6" stroke-dasharray="5 3"/>
    <line x1="${tgt[0].toFixed(1)}" y1="${tgt[1].toFixed(1)}"
      x2="${tv[0].toFixed(1)}" y2="${tv[1].toFixed(1)}"
      stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity=".75"/>
    <circle cx="${tgt[0].toFixed(1)}" cy="${tgt[1].toFixed(1)}" r="4"
      fill="none" stroke="${relColor}" stroke-width="2"/>

    ${cpaPt ? `<circle cx="${cpaPt[0].toFixed(1)}" cy="${cpaPt[1].toFixed(1)}" r="3"
        fill="${relColor}"/>
      <line x1="${cx}" y1="${cy}" x2="${cpaPt[0].toFixed(1)}" y2="${cpaPt[1].toFixed(1)}"
        stroke="${relColor}" stroke-width="1" stroke-opacity=".55" stroke-dasharray="2 2"/>
      <text x="${cpaPt[0].toFixed(1)}" y="${(cpaPt[1] - 7).toFixed(1)}" text-anchor="middle"
        font-size="9" fill="${relColor}">CPA ${fmt(r.cpa)}</text>` : ''}

    <text x="8" y="14" font-size="9" fill="currentColor" fill-opacity=".6"
      >${maxRange} ${tr('миль на кольце')}</text>
    <text x="${size - 8}" y="14" text-anchor="end" font-size="9"
      fill="currentColor" fill-opacity=".6">${tr('векторы за 1 ч')}</text>
    <text x="8" y="${size - 8}" font-size="9" fill="var(--ok, #46a758)"
      >— ${tr('своё судно')}</text>
    <text x="${size - 8}" y="${size - 8}" text-anchor="end" font-size="9" fill="${relColor}"
      >-- ${tr('линия относительного движения')}</text>
  </svg>`;
}

/* Классический признак опасности столкновения: пеленг не меняется.
   Считаем изменение за десять минут по той же геометрии. */
function bearingTrend(bearing, range, r){
  if(r.opening) return tr('цель расходится');
  const step = 10 / 60;
  const nb = Math.atan2(
    Math.sin(bearing * Math.PI / 180) * range + Math.sin(r.relCourse * Math.PI / 180) * r.relSpeed * step,
    Math.cos(bearing * Math.PI / 180) * range + Math.cos(r.relCourse * Math.PI / 180) * r.relSpeed * step
  ) * 180 / Math.PI;
  const delta = ((nb - bearing + 540) % 360) - 180;
  if(Math.abs(delta) < 0.5) return tr('почти не меняется, опасность столкновения');
  return (Math.abs(delta) < 3 ? tr('меняется медленно') : tr('меняется заметно'))
       + ': ' + (delta > 0 ? tr('вправо') : tr('влево')) + ' '
       + Math.abs(delta).toFixed(1) + '° ' + tr('за 10 мин');
}

/* -- точка перекладки руля -- */
function wheelOver(radius,courseChange){
  const a=Math.abs(courseChange)*D2R;
  return {
    distance:radius*Math.tan(a/2),
    advance:radius*Math.sin(a),
    transfer:radius*(1-Math.cos(a))
  };
}

/* -- рейс и топливо -- */
function voyage(distance,speed,consPerDay){
  const hours=speed>0?distance/speed:0;
  const days=hours/24;
  return {hours:hours, days:days, total:days*(consPerDay||0)};
}
function requiredSpeed(distance,hoursAvailable){
  return hoursAvailable>0?distance/hoursAvailable:0;
}

/* -- шкала Бофорта -- */
const BEAUFORT=[
 [0,0,0.9,'Штиль','Зеркально гладкое море',0],
 [1,1,3,'Тихий','Рябь',0.1],
 [2,4,6,'Лёгкий','Небольшие волны',0.2],
 [3,7,10,'Слабый','Гребни начинают опрокидываться',0.6],
 [4,11,16,'Умеренный','Небольшие волны, барашки',1],
 [5,17,21,'Свежий','Умеренные волны',2],
 [6,22,27,'Сильный','Крупные волны, пена',3],
 [7,28,33,'Крепкий','Море вздымается, пена полосами',4],
 [8,34,40,'Очень крепкий','Умеренно высокие волны',5.5],
 [9,41,47,'Шторм','Высокие волны, видимость снижена',7],
 [10,48,55,'Сильный шторм','Очень высокие волны, море белое',9],
 [11,56,63,'Жестокий шторм','Исключительно высокие волны',11.5],
 [12,64,99,'Ураган','Воздух наполнен пеной и брызгами',14]
];
function beaufort(knots){
  for(const b of BEAUFORT) if(knots<=b[2]) return b;
  return BEAUFORT[BEAUFORT.length-1];
}

/* -- солнце и сумерки (алгоритм NOAA) -- */
function sunTimes(lat,lon,date){
  const rad=D2R;
  const dayMs=86400000, J1970=2440588, J2000=2451545;
  const toJulian=d=>d.valueOf()/dayMs-0.5+J1970;
  const fromJulian=j=>new Date((j+0.5-J1970)*dayMs);
  const d=toJulian(date)-J2000;
  const M=rad*(357.5291+0.98560028*d);
  const C=rad*(1.9148*Math.sin(M)+0.02*Math.sin(2*M)+0.0003*Math.sin(3*M));
  const P=rad*102.9372;
  const L=M+C+P+Math.PI;
  const dec=Math.asin(Math.sin(rad*23.4397)*Math.sin(L));
  const n=Math.round(d-0.0009-(-lon*rad)/(2*Math.PI));
  const ds=0.0009+(-lon*rad)/(2*Math.PI)+n;
  const Ms=rad*(357.5291+0.98560028*ds);
  const Ls=Ms+rad*(1.9148*Math.sin(Ms)+0.02*Math.sin(2*Ms)+0.0003*Math.sin(3*Ms))+P+Math.PI;
  const Jtransit=J2000+ds+0.0053*Math.sin(Ms)-0.0069*Math.sin(2*Ls);
  const decs=Math.asin(Math.sin(rad*23.4397)*Math.sin(Ls));
  function hourAngle(h){
    const co=(Math.sin(h*rad)-Math.sin(lat*rad)*Math.sin(decs))/(Math.cos(lat*rad)*Math.cos(decs));
    if(co>1) return null;   /* не восходит */
    if(co<-1) return NaN;   /* не заходит */
    return Math.acos(co);
  }
  function times(h){
    const w=hourAngle(h);
    if(w===null) return {rise:null,set:null,polar:'ночь'};
    if(Number.isNaN(w)) return {rise:null,set:null,polar:'день'};
    const a=0.0009+(w+(-lon*rad))/(2*Math.PI)+n;
    const Jset=J2000+a+0.0053*Math.sin(Ms)-0.0069*Math.sin(2*Ls);
    const Jrise=Jtransit-(Jset-Jtransit);
    return {rise:fromJulian(Jrise), set:fromJulian(Jset), polar:null};
  }
  return {
    sun:times(-0.833),
    civil:times(-6),
    nautical:times(-12),
    astro:times(-18),
    noon:fromJulian(Jtransit)
  };
}

/* ================= Мореходная астрономия =================
   Считается прямо на устройстве: сеть не нужна, в рейсе это и есть
   основной режим работы.

   Что здесь есть: часовой угол и склонение Солнца и Луны, приведение
   измеренной высоты к истинной, счислимая высота с азимутом и перенос
   линии положения. Светило можно задать и вручную, часовым углом со
   склонением из бумажного альманаха: так считаются звёзды и планеты,
   пока их нет в расчёте.

   Точность проверена против эталонных эфемерид DE421: Солнце держит
   0.5 угловой минуты, Луна одну. Ряды здесь усечённые, полные занимают
   сотни членов. Для контроля места этого достаточно, для официальной
   прокладки положен Морской астрономический ежегодник. Так и написано
   в самом разделе, чтобы никто не принял расчёт за замену ежегодника. */

const AS_D2R = Math.PI / 180, AS_R2D = 180 / Math.PI;
const asSin = d => Math.sin(d * AS_D2R), asCos = d => Math.cos(d * AS_D2R);
const asTan = d => Math.tan(d * AS_D2R);
/* Приведение к диапазону 0-360: часовые углы растут без конца, а на
   круге интересен только остаток. */
const asNorm = d => ((d % 360) + 360) % 360;

function asJD(date){
  return date.valueOf() / 86400000 + 2440587.5;
}

/* Гринвичское звёздное время: с него начинается любой часовой угол.
   Формула из Astronomical Almanac, расхождение за век меньше секунды. */
function asGMST(date){
  const d = asJD(date) - 2451545.0;
  const T = d / 36525;
  return asNorm(280.46061837 + 360.98564736629 * d + 0.000387933 * T * T);
}

/* Часовой угол точки Овна: от него отсчитываются звёзды через SHA. */
function asGHAAries(date){ return asGMST(date); }

/* -- Солнце -- */
function asSun(date){
  const T = (asJD(date) - 2451545.0) / 36525;
  const L0 = asNorm(280.46646 + 36000.76983 * T);           // средняя долгота
  const M  = asNorm(357.52911 + 35999.05029 * T);           // средняя аномалия
  const C  = (1.914602 - 0.004817 * T) * asSin(M)
           + (0.019993 - 0.000101 * T) * asSin(2 * M)
           + 0.000289 * asSin(3 * M);                        // уравнение центра
  const lon = L0 + C;                                        // истинная долгота
  const e = 0.016708634 - 0.000042037 * T;
  const v = M + C;
  const R = 1.000001018 * (1 - e * e) / (1 + e * asCos(v));  // расстояние, а.е.
  const eps = 23.439291 - 0.0130042 * T;                     // наклон эклиптики

  const ra = Math.atan2(asCos(eps) * asSin(lon), asCos(lon)) * AS_R2D;
  const dec = Math.asin(asSin(eps) * asSin(lon)) * AS_R2D;
  return {
    name: 'Солнце',
    gha: asNorm(asGMST(date) - ra),
    dec: dec,
    sd: 16.0 / R,        // видимый полудиаметр в минутах
    hp: 0.0024 / R,      // горизонтальный параллакс, минуты
    limb: true
  };
}

/* -- Луна --
   Ряды Брауна в изложении Meeus. Членов намеренно много: на шести
   главных расчёт врал на два градуса по долготе, а это 120 миль по
   месту. С набором ниже расхождение с эталонными эфемеридами держится
   в пределах одной угловой минуты, что проверено отдельной проверкой
   moontest. */
const AS_MOON_LON = [
  [6.288774, 0, 0, 1, 0], [1.274027, 2, 0, -1, 0], [0.658314, 2, 0, 0, 0],
  [0.213618, 0, 0, 2, 0], [-0.185116, 0, 1, 0, 0], [-0.114332, 0, 0, 0, 2],
  [0.058793, 2, 0, -2, 0], [0.057066, 2, -1, -1, 0], [0.053322, 2, 0, 1, 0],
  [0.045758, 2, -1, 0, 0], [-0.040923, 0, 1, -1, 0], [-0.034720, 1, 0, 0, 0],
  [-0.030383, 0, 1, 1, 0], [0.015327, 2, 0, 0, -2], [-0.012528, 0, 0, 1, 2],
  [0.010980, 0, 0, 1, -2], [0.010675, 4, 0, -1, 0], [0.010034, 0, 0, 3, 0],
  [0.008548, 4, 0, -2, 0]
];
const AS_MOON_LAT = [
  [5.128122, 0, 0, 0, 1], [0.280602, 0, 0, 1, 1], [0.277693, 0, 0, 1, -1],
  [0.173237, 2, 0, 0, -1], [0.055413, 2, 0, -1, 1], [0.046271, 2, 0, -1, -1],
  [0.032573, 2, 0, 0, 1], [0.017198, 0, 0, 2, 1], [0.009266, 2, 0, 1, -1],
  [0.008822, 0, 0, 2, -1], [0.008216, 2, -1, 0, -1], [0.004324, 2, 0, -2, -1]
];
const AS_MOON_DIST = [
  [-20905.355, 0, 0, 1, 0], [-3699.111, 2, 0, -1, 0], [-2955.968, 2, 0, 0, 0],
  [-569.925, 0, 0, 2, 0], [48.888, 0, 1, 0, 0], [-3149.0, 0, 0, 0, 2],
  [246.158, 2, 0, -2, 0], [-152.138, 2, -1, -1, 0], [-170.733, 2, 0, 1, 0],
  [-204.586, 2, -1, 0, 0], [-129.620, 0, 1, -1, 0], [108.743, 1, 0, 0, 0],
  [104.755, 0, 1, 1, 0]
];

/* Земное время опережает всемирное примерно на 69 секунд (эпоха 2020-х).
   Ряды построены на земном времени, и без поправки Луна уходит почти на
   минуту дуги. */
const AS_DELTA_T_DAYS = 69 / 86400;

function asMoon(date){
  const T = (asJD(date) + AS_DELTA_T_DAYS - 2451545.0) / 36525;
  const Lp = asNorm(218.3164477 + 481267.88123421 * T);      // средняя долгота
  const D  = asNorm(297.8501921 + 445267.1114034 * T);       // элонгация
  const M  = asNorm(357.5291092 + 35999.0502909 * T);        // аномалия Солнца
  const Mp = asNorm(134.9633964 + 477198.8675055 * T);       // аномалия Луны
  const F  = asNorm(93.2720950 + 483202.0175233 * T);        // аргумент широты

  const sum = (terms, fn) => terms.reduce(
    (acc, [c, d, m, mp, f]) => acc + c * fn(d * D + m * M + mp * Mp + f * F), 0);

  const lon = Lp + sum(AS_MOON_LON, asSin);
  const lat = sum(AS_MOON_LAT, asSin);
  const dist = 385000.56 + sum(AS_MOON_DIST, asCos);          // км

  const eps = 23.439291 - 0.0130042 * T;
  const sl = asSin(lon), cl = asCos(lon), sb = asSin(lat), cb = asCos(lat);
  const ra = Math.atan2(sl * asCos(eps) - (sb / cb) * asSin(eps), cl) * AS_R2D;
  const dec = Math.asin(sb * asCos(eps) + cb * asSin(eps) * sl) * AS_R2D;

  const hp = Math.asin(6378.14 / dist) * AS_R2D * 60;         // параллакс, минуты
  return {
    name: 'Луна',
    gha: asNorm(asGMST(date) - ra),
    dec: dec,
    sd: 0.2725 * hp,
    hp: hp,
    limb: true
  };
}

/* -- Приведение измеренной высоты к истинной --
   Порядок обязателен: сперва инструмент, потом наклонение горизонта,
   потом рефракция, и только затем полудиаметр с параллаксом. Меняешь
   порядок -- ошибаешься на минуту, а это миля. */
function asObserved(hs, opts){
  const o = opts || {};
  const ie = +o.ie || 0;              // поправка индекса, минуты
  const eye = +o.eye || 0;            // высота глаза, метры
  const dip = eye > 0 ? 1.76 * Math.sqrt(eye) : 0;   // наклонение горизонта
  const ha = hs + ie / 60 - dip / 60;                // видимая высота

  // Рефракция Бенётта, минуты дуги
  const R = ha > -0.5 ? 1 / asTan(ha + 7.31 / (ha + 4.4)) : 0;
  let h = ha - R / 60;

  const sd = +o.sd || 0, hp = +o.hp || 0;
  if (o.limb === 'lower') h += sd / 60;
  else if (o.limb === 'upper') h -= sd / 60;
  if (hp) h += (hp * asCos(h)) / 60;   // параллакс в высоте

  return { ho: h, dip: dip, refraction: R, ha: ha };
}

/* -- Счислимая высота и азимут --
   Основная формула сферического треугольника. Азимут через atan2, а не
   через arcsin: последний теряет четверть, и линия ложится зеркально. */
function asHcZn(lat, lon, gha, dec){
  const lha = asNorm(gha + lon);      // восточная долгота со знаком плюс
  const sh = asSin(lat) * asSin(dec) + asCos(lat) * asCos(dec) * asCos(lha);
  const hc = Math.asin(Math.max(-1, Math.min(1, sh))) * AS_R2D;
  const zn = asNorm(Math.atan2(-asSin(lha) * asCos(dec),
                               asCos(lat) * asSin(dec) - asSin(lat) * asCos(dec) * asCos(lha)) * AS_R2D);
  return { hc: hc, zn: zn, lha: lha };
}

/* -- Перенос линии положения --
   Разность истинной и счислимой высоты в минутах и есть перенос в милях:
   одна минута дуги это одна миля. Знак решает, куда переносить. */
function asIntercept(ho, hc){
  const a = (ho - hc) * 60;
  return { miles: Math.abs(a), toward: a >= 0, value: a };
}

function asBody(kind, date){
  return kind === 'moon' ? asMoon(date) : asSun(date);
}

/* Градусы в морскую запись: 41°25.4' */
function asDM(deg, isLat){
  const sign = deg < 0 ? (isLat ? 'S' : 'W') : (isLat ? 'N' : 'E');
  const a = Math.abs(deg);
  const d = Math.floor(a);
  const m = (a - d) * 60;
  return `${d}°${m.toFixed(1)}'${sign}`;
}
function asHms(deg){
  const a = asNorm(deg);
  const d = Math.floor(a);
  return `${d}°${((a - d) * 60).toFixed(1)}'`;
}

/* -- конвертер единиц -- */
const UNITS={
  length:{title:'Длина',base:'м',u:{'м':1,'фут':0.3048,'сажень':1.8288,'кабельтов':185.2,'миля':1852,'км':1000}},
  speed:{title:'Скорость',base:'уз',u:{'уз':1,'км/ч':0.539957,'м/с':1.94384,'миль/ч':0.868976}},
  mass:{title:'Масса',base:'т',u:{'т':1,'кг':0.001,'фунт':0.000453592,'длинная т':1.01605}},
  volume:{title:'Объём',base:'м³',u:{'м³':1,'литр':0.001,'баррель':0.158987,'галлон US':0.00378541}},
  temp:{title:'Температура',base:'°C',u:{}}
};
function convert(cat,from,to,val){
  if(cat==='temp'){
    let c = from==='°F' ? (val-32)*5/9 : (from==='K' ? val-273.15 : val);
    return to==='°F' ? c*9/5+32 : (to==='K' ? c+273.15 : c);
  }
  const u=UNITS[cat].u;
  return val*u[from]/u[to];
}

/* ================= Инструменты ================= */
const F=(v,n)=>Number.isFinite(v)?v.toFixed(n===undefined?2:n):'—';
const hm=h=>{
  if(!Number.isFinite(h))return '—';
  const neg=h<0; h=Math.abs(h);
  const d=Math.floor(h/24), hh=Math.floor(h%24), mm=Math.round((h%1)*60);
  const u=(typeof LANG!=='undefined'&&LANG==='en')?['d','h','min']:['сут','ч','мин'];
  return (neg?'−':'')+(d?d+' '+u[0]+' ':'')+hh+' '+u[1]+' '+String(mm).padStart(2,'0')+' '+u[2];
};
const utc=d=>d?String(d.getUTCHours()).padStart(2,'0')+':'+String(d.getUTCMinutes()).padStart(2,'0'):'—';

const TOOLS=[
 {id:'dist',cat:'nav',icon:'route',name:'Расстояние и курс',
  desc:'Ортодромия, локсодромия, начальный и конечный курс',
  fields:[
   {k:'la1',l:'Широта отхода',t:'coord',def:'41-25.4N'},
   {k:'lo1',l:'Долгота отхода',t:'coord',def:'002-10.0E'},
   {k:'la2',l:'Широта прихода',t:'coord',def:'36-08.0N'},
   {k:'lo2',l:'Долгота прихода',t:'coord',def:'005-21.0W'}],
  calc:v=>{
   const a=parseCoord(v.la1),b=parseCoord(v.lo1),c=parseCoord(v.la2),d=parseCoord(v.lo2);
   if([a,b,c,d].some(x=>x===null)) return [{l:'Ошибка',v:'Проверь формат координат'}];
   return [
    {l:'Ортодромия',v:F(gcDistance(a,b,c,d),1)+' миль',hi:1},
    {l:'Локсодромия',v:F(rhumbDistance(a,b,c,d),1)+' миль'},
    {l:'Начальный курс',v:F(initialBearing(a,b,c,d),1)+'°'},
    {l:'Конечный курс',v:F(finalBearing(a,b,c,d),1)+'°'},
    {l:'Курс по локсодромии',v:F(rhumbBearing(a,b,c,d),1)+'°'},
    {l:'Обратный курс',v:F(norm360(initialBearing(a,b,c,d)+180),1)+'°'}];
  }},

 {id:'eta',cat:'nav',icon:'clock',name:'ETA и скорость',
  desc:'Время в пути, требуемая скорость, время прибытия',
  fields:[
   {k:'d',l:'Расстояние',t:'num',u:'миль',def:'2921'},
   {k:'s',l:'Скорость',t:'num',u:'узлов',def:'14'},
   {k:'ha',l:'Времени в запасе (для требуемой скорости)',t:'num',u:'часов',def:'200'}],
  calc:v=>{
   const r=voyage(+v.d,+v.s,0);
   const now=new Date(), eta=new Date(now.getTime()+r.hours*3600000);
   return [
    {l:'Время в пути',v:hm(r.hours),hi:1},
    {l:'В сутках',v:F(r.days,2)+' сут'},
    {l:'ETA (UTC от сейчас)',v:eta.toISOString().slice(0,16).replace('T',' ')},
    {l:'Требуемая скорость',v:F(requiredSpeed(+v.d,+v.ha),2)+' узлов'}];
  }},

 {id:'coord',cat:'nav',icon:'compass',name:'Конвертер координат',
  desc:'Градусы, минуты, секунды и десятичные',
  fields:[
   {k:'la',l:'Широта',t:'coord',def:'41-25.40N'},
   {k:'lo',l:'Долгота',t:'coord',def:'077-09.96W'}],
  calc:v=>{
   const a=parseCoord(v.la),b=parseCoord(v.lo);
   if(a===null||b===null) return [{l:'Ошибка',v:'Проверь формат'}];
   return [
    {l:'Десятичные',v:a.toFixed(6)+', '+b.toFixed(6),hi:1},
    {l:'Градусы и минуты',v:toDDM(a,true)+' '+toDDM(b,false)},
    {l:'Градусы, минуты, секунды',v:toDMS(a,true)+' '+toDMS(b,false)}];
  }},

 {id:'ukc',cat:'depth',icon:'buoy',name:'Запас воды под килём',
  desc:'UKC с учётом прилива, проседания, крена и волнения',
  fields:[
   {k:'cd',l:'Глубина по карте',t:'num',u:'м',def:'15.0'},
   {k:'td',l:'Высота прилива',t:'num',u:'м',def:'1.8'},
   {k:'dr',l:'Осадка',t:'num',u:'м',def:'12.5'},
   {k:'sq',l:'Проседание (squat)',t:'num',u:'м',def:'1.15'},
   {k:'hl',l:'Поправка на крен',t:'num',u:'м',def:'0.2'},
   {k:'wv',l:'Поправка на волнение',t:'num',u:'м',def:'0.3'}],
  calc:v=>{
   const r=ukc(+v.cd,+v.td,+v.dr,+v.sq,+v.hl,+v.wv);
   const pct=(+v.dr)>0?(r.ukc/(+v.dr)*100):0;
   return [
    {l:'Доступная глубина',v:F(r.available)+' м'},
    {l:'Требуется',v:F(r.required)+' м'},
    {l:'Запас под килём',v:F(r.ukc)+' м',hi:1,warn:r.ukc<1},
    {l:'В процентах от осадки',v:F(pct,1)+' %'}];
  }},

 {id:'squat',cat:'depth',icon:'wave',name:'Проседание на ходу',
  desc:'Squat по упрощённой формуле Барраса',
  fields:[
   {k:'cb',l:'Коэффициент общей полноты Cb',t:'num',def:'0.80'},
   {k:'v',l:'Скорость',t:'num',u:'узлов',def:'12'},
   {k:'w',l:'Акватория',t:'sel',opts:['Открытая вода','Стеснённая / канал'],def:'Открытая вода'}],
  calc:v=>{
   const conf=v.w!=='Открытая вода';
   const s=squat(+v.cb,+v.v,conf);
   const half=squat(+v.cb,(+v.v)/2,conf);
   return [
    {l:'Проседание',v:F(s)+' м',hi:1},
    {l:'При половинной скорости',v:F(half)+' м'},
    {l:'Формула',v:conf?'Cb × V² / 50':'Cb × V² / 100'}];
  }},

 {id:'air',cat:'depth',icon:'lighthouse',name:'Проход под мостом',
  desc:'Надводный габарит и запас по высоте',
  fields:[
   {k:'cc',l:'Габарит по карте (над HAT)',t:'num',u:'м',def:'52.0'},
   {k:'hat',l:'HAT',t:'num',u:'м',def:'2.4'},
   {k:'tn',l:'Текущий прилив',t:'num',u:'м',def:'1.1'},
   {k:'ad',l:'Надводный габарит судна',t:'num',u:'м',def:'48.5'}],
  calc:v=>{
   const r=airDraft(+v.cc,+v.hat,+v.tn,+v.ad);
   return [
    {l:'Фактический просвет',v:F(r.actual)+' м'},
    {l:'Запас по высоте',v:F(r.margin)+' м',hi:1,warn:r.margin<1}];
  }},

 {id:'anchor',cat:'anchor',icon:'anchor',name:'Якорная стоянка',
  desc:'Радиус циркуляции на якоре и длина скопа',
  fields:[
   {k:'ch',l:'Вытравлено цепи',t:'num',u:'м',def:'165'},
   {k:'dp',l:'Глубина',t:'num',u:'м',def:'30'},
   {k:'hh',l:'Высота клюза над водой',t:'num',u:'м',def:'10'},
   {k:'loa',l:'Длина судна',t:'num',u:'м',def:'180'}],
  calc:v=>{
   const r=anchorSwing(+v.ch,+v.dp,+v.hh,+v.loa);
   const shackles=(+v.ch)/27.5;
   return [
    {l:'Радиус циркуляции',v:F(r.radius,1)+' м',hi:1},
    {l:'Горизонтальная проекция цепи',v:F(r.horizontal,1)+' м'},
    {l:'Скоп (цепь / глубина)',v:F(r.scope,2)+' : 1',warn:r.scope<3},
    {l:'Вытравлено смычек',v:F(shackles,1)}];
  }},

 {id:'cpa',cat:'radar',icon:'radar',name:'CPA и TCPA',
  desc:'Расхождение с целью, планшет и цифры',
  fields:[
   {k:'oc',l:'Свой курс',t:'num',u:'°',def:'0'},
   {k:'os',l:'Своя скорость',t:'num',u:'узлов',def:'20'},
   {k:'tb',l:'Пеленг на цель',t:'num',u:'°',def:'30'},
   {k:'tr',l:'Дистанция до цели',t:'num',u:'миль',def:'8'},
   {k:'tc',l:'Курс цели',t:'num',u:'°',def:'240'},
   {k:'ts',l:'Скорость цели',t:'num',u:'узлов',def:'15'}],
  calc:v=>{
   const r=cpaTcpa(+v.oc,+v.os,+v.tb,+v.tr,+v.tc,+v.ts);
   return [
    {svg:radarPlot({oc:+v.oc,os:+v.os,tb:+v.tb,tr:+v.tr,tc:+v.tc,ts:+v.ts},r)},
    {l:'CPA',v:F(r.cpa,2)+' миль',hi:1,warn:r.cpa<1&&!r.opening},
    {l:'TCPA',v:r.opening?'цель расходится':hm(r.tcpa)},
    {l:'Курс относительного движения',v:F(r.relCourse,1)+'°'},
    {l:'Скорость сближения',v:F(r.relSpeed,1)+' узлов'},
    {l:'Пеленг меняется',v:bearingTrend(+v.tb, +v.tr, r)}];
  }},

 {id:'magnetron',cat:'radar',icon:'radar',name:'Ресурс магнетрона',
  desc:'Сколько процентов ресурса радара выработано и что осталось',
  fields:[
   {k:'rx',l:'RX time (наработка по счётчику)',t:'num',u:'часов',def:'1424.7'},
   {k:'life',l:'Номинальный ресурс магнетрона',t:'num',u:'часов',def:'5000'},
   {k:'day',l:'Наработка в сутки (0 = без прогноза)',t:'num',u:'часов',def:'0'}],
  calc:v=>{
   const rx=+v.rx, life=+v.life;
   if(!(life>0)) return [{l:'Ошибка',v:'Ресурс должен быть больше нуля'}];
   const used=rx*100/life;          // (RX time × 100) / ресурс
   const left=100-used;             // остаток ресурса
   const hoursLeft=life-rx;
   const rows=[
    {l:'Осталось ресурса',v:F(left,2)+' %',hi:1,warn:left<20},
    {l:'Выработано',v:F(used,2)+' %'},
    // подстановка чисел, чтобы можно было сверить с расчётом на калькуляторе
    {l:'Проверка',v:F(rx,1)+' × 100 ÷ '+F(life,0)+' = '+F(used,3)},
    {l:'Отработано часов',v:F(rx,1)+' ч'},
    {l:'Осталось часов',v:F(hoursLeft,1)+' ч',warn:hoursLeft<500}];
   const day=+v.day;
   if(day>0&&hoursLeft>0){
     const days=hoursLeft/day;
     rows.push({l:'Хватит примерно на',v:F(days,0)+' сут ('+F(days/30.4,1)+' мес)'});
   }
   if(left<20) rows.push({l:'Внимание',v:'Пора заказывать замену',warn:1});
   else if(left<40) rows.push({l:'Внимание',v:'Планируй замену заранее',warn:1});
   return rows;
  }},

 {id:'wop',cat:'radar',icon:'compass',name:'Точка перекладки руля',
  desc:'Wheel Over Point, advance и transfer',
  fields:[
   {k:'r',l:'Радиус циркуляции',t:'num',u:'миль',def:'0.5'},
   {k:'cc',l:'Изменение курса',t:'num',u:'°',def:'60'},
   {k:'sp',l:'Скорость (для времени)',t:'num',u:'узлов',def:'14'}],
  calc:v=>{
   const r=wheelOver(+v.r,+v.cc);
   const t=(+v.sp)>0?r.distance/(+v.sp):0;
   return [
    {l:'Перекладка за',v:F(r.distance,3)+' миль',hi:1},
    {l:'В кабельтовых',v:F(r.distance*10,1)},
    {l:'Времени до точки',v:hm(t)},
    {l:'Advance',v:F(r.advance,3)+' миль'},
    {l:'Transfer',v:F(r.transfer,3)+' миль'}];
  }},

 {id:'fuel',cat:'voyage',icon:'ship',name:'Топливо на переход',
  desc:'Расход, остаток и запас',
  fields:[
   {k:'d',l:'Расстояние',t:'num',u:'миль',def:'2921'},
   {k:'s',l:'Скорость',t:'num',u:'узлов',def:'14'},
   {k:'c',l:'Расход в сутки',t:'num',u:'т',def:'32'},
   {k:'rob',l:'Топлива на борту',t:'num',u:'т',def:'420'},
   {k:'res',l:'Неснижаемый запас',t:'num',u:'%',def:'10'}],
  calc:v=>{
   const r=voyage(+v.d,+v.s,+v.c);
   const reserve=(+v.rob)*(+v.res)/100;
   const left=(+v.rob)-r.total;
   return [
    {l:'Время в пути',v:hm(r.hours)},
    {l:'Потребуется топлива',v:F(r.total,1)+' т',hi:1},
    {l:'Останется',v:F(left,1)+' т',warn:left<reserve},
    {l:'Неснижаемый запас',v:F(reserve,1)+' т'},
    {l:'Хватает',v:left>=reserve?'да, с запасом '+F(left-reserve,1)+' т':'НЕТ, не хватает '+F(reserve-left,1)+' т',warn:left<reserve}];
  }},

 {id:'sun',cat:'weather',icon:'sun',name:'Восход, заход, сумерки',
  desc:'Для планирования вахт и смены режима наблюдения',
  fields:[
   {k:'la',l:'Широта',t:'coord',def:'41-25.4N'},
   {k:'lo',l:'Долгота',t:'coord',def:'002-10.0E'},
   {k:'dt',l:'Дата (ГГГГ-ММ-ДД, пусто = сегодня)',t:'text',def:''}],
  calc:v=>{
   const a=parseCoord(v.la),b=parseCoord(v.lo);
   if(a===null||b===null) return [{l:'Ошибка',v:'Проверь координаты'}];
   const d=v.dt?new Date(v.dt+'T12:00:00Z'):new Date();
   if(isNaN(d)) return [{l:'Ошибка',v:'Проверь дату'}];
   const t=sunTimes(a,b,d);
   const row=(n,x)=>({l:n,v:x.polar?('круглые сутки '+x.polar):(utc(x.rise)+' — '+utc(x.set))});
   return [
    {l:'Дата (UTC)',v:d.toISOString().slice(0,10)},
    Object.assign(row('Восход — заход',t.sun),{hi:1}),
    row('Гражданские сумерки',t.civil),
    row('Навигационные сумерки',t.nautical),
    row('Астрономические сумерки',t.astro),
    {l:'Полдень (UTC)',v:utc(t.noon)}];
  }},

 {id:'almanac',cat:'weather',icon:'star',name:'Альманах: Солнце и Луна',
  desc:'Часовой угол, склонение, высота и азимут в счислимом месте',
  fields:[
   {k:'body',l:'Светило',t:'sel',opts:['Солнце','Луна'],def:'Солнце'},
   {k:'la',l:'Счислимая широта',t:'coord',def:'41-25.4N'},
   {k:'lo',l:'Счислимая долгота',t:'coord',def:'002-10.0E'},
   {k:'dt',l:'Дата и время UTC (ГГГГ-ММ-ДД ЧЧ:ММ, пусто = сейчас)',t:'text',def:''}],
  calc:v=>{
   const a=parseCoord(v.la), b=parseCoord(v.lo);
   if(a===null||b===null) return [{l:'Ошибка',v:'Проверь координаты'}];
   const d=v.dt?new Date(v.dt.trim().replace(' ','T')+':00Z'):new Date();
   if(isNaN(d)) return [{l:'Ошибка',v:'Проверь дату и время'}];
   const body=asBody(v.body==='Луна'?'moon':'sun', d);
   const s=asHcZn(a, b, body.gha, body.dec);
   return [
    {l:'Момент UTC',v:d.toISOString().slice(0,16).replace('T',' ')},
    {l:'Гринвичский часовой угол',v:asHms(body.gha),hi:1},
    {l:'Склонение',v:asDM(body.dec,true),hi:1},
    {l:'Местный часовой угол',v:asHms(s.lha)},
    {l:'Счислимая высота',v:asDM(s.hc,true).replace(/[NS]$/,'')},
    {l:'Азимут',v:s.zn.toFixed(1)+'°'},
    {l:'Полудиаметр',v:body.sd.toFixed(1)+"'"},
    {l:'Горизонтальный параллакс',v:body.hp.toFixed(1)+"'"},
    {l:'Точность расчёта',v:v.body==='Луна'?'около 1 угловой минуты':'около 0.5 угловой минуты'},
    {l:'Официальный источник',v:'Морской астрономический ежегодник'}];
  }},

 {id:'sight',cat:'weather',icon:'target',name:'Линия положения по светилу',
  desc:'Поправки высоты и перенос от счислимого места',
  fields:[
   {k:'body',l:'Светило',t:'sel',opts:['Солнце','Луна','Задать вручную'],def:'Солнце'},
   {k:'hs',l:'Измеренная высота (градусы)',t:'num',def:'45.5'},
   {k:'limb',l:'Край диска',t:'sel',opts:['нижний','верхний','центр'],def:'нижний'},
   {k:'ie',l:'Поправка индекса',t:'num',u:'минут',def:'0'},
   {k:'eye',l:'Высота глаза',t:'num',u:'м',def:'12'},
   {k:'la',l:'Счислимая широта',t:'coord',def:'41-25.4N'},
   {k:'lo',l:'Счислимая долгота',t:'coord',def:'002-10.0E'},
   {k:'dt',l:'Дата и время UTC (ГГГГ-ММ-ДД ЧЧ:ММ, пусто = сейчас)',t:'text',def:''},
   {k:'gha',l:'Часовой угол вручную (градусы)',t:'num',def:''},
   {k:'dec',l:'Склонение вручную (градусы, южное со знаком минус)',t:'num',def:''}],
  calc:v=>{
   const a=parseCoord(v.la), b=parseCoord(v.lo);
   if(a===null||b===null) return [{l:'Ошибка',v:'Проверь координаты'}];
   const d=v.dt?new Date(v.dt.trim().replace(' ','T')+':00Z'):new Date();
   if(isNaN(d)) return [{l:'Ошибка',v:'Проверь дату и время'}];

   let body;
   if(v.body==='Задать вручную'){
     if(v.gha===''||v.dec==='') return [{l:'Ошибка',v:'Введи часовой угол и склонение из ежегодника'}];
     body={name:'вручную', gha:+v.gha, dec:+v.dec, sd:0, hp:0};
   } else body=asBody(v.body==='Луна'?'moon':'sun', d);

   const limb=v.limb==='нижний'?'lower':(v.limb==='верхний'?'upper':'center');
   const corr=asObserved(+v.hs, {ie:+v.ie, eye:+v.eye, sd:body.sd, hp:body.hp, limb:limb});
   const s=asHcZn(a, b, body.gha, body.dec);
   const it=asIntercept(corr.ho, s.hc);
   return [
    {l:'Момент UTC',v:d.toISOString().slice(0,16).replace('T',' ')},
    {l:'Наклонение горизонта',v:'−'+corr.dip.toFixed(1)+"'"},
    {l:'Рефракция',v:'−'+corr.refraction.toFixed(1)+"'"},
    {l:'Истинная высота',v:asDM(corr.ho,true).replace(/[NS]$/,''),hi:1},
    {l:'Счислимая высота',v:asDM(s.hc,true).replace(/[NS]$/,'')},
    {l:'Перенос',v:it.miles.toFixed(1)+' миль '+(it.toward?'к светилу':'от светила'),hi:1},
    {l:'Азимут линии',v:s.zn.toFixed(1)+'°'},
    {l:'Линию проложить',v:'перпендикулярно азимуту '+s.zn.toFixed(0)+'° в точке переноса'}];
  }},

 {id:'bft',cat:'weather',icon:'wave',name:'Шкала Бофорта',
  desc:'Ветер, состояние моря и высота волны',
  fields:[{k:'w',l:'Скорость ветра',t:'num',u:'узлов',def:'22'}],
  calc:v=>{
   const b=beaufort(+v.w);
   return [
    {l:'Балл',v:b[0]+' — '+b[3],hi:1},
    {l:'Диапазон',v:b[1]+'–'+b[2]+' узлов'},
    {l:'Состояние моря',v:b[4]},
    {l:'Характерная высота волны',v:b[5]+' м'},
    {l:'В м/с',v:F(convert('speed','уз','м/с',+v.w),1)}];
  }},

 {id:'units',cat:'weather',icon:'sliders',name:'Конвертер единиц',
  desc:'Длина, скорость, масса, объём, температура',
  fields:[
   {k:'cat',l:'Величина',t:'sel',opts:['Длина','Скорость','Масса','Объём','Температура'],def:'Длина'},
   {k:'val',l:'Значение',t:'num',def:'1'}],
  calc:v=>{
   const map={'Длина':'length','Скорость':'speed','Масса':'mass','Объём':'volume','Температура':'temp'};
   const c=map[v.cat]||'length';
   if(c==='temp'){
     const val=+v.val;
     return [
      {l:'°C',v:F(val,2),hi:1},
      {l:'°F',v:F(convert('temp','°C','°F',val),2)},
      {l:'K',v:F(convert('temp','°C','K',val),2)}];
   }
   const base=Object.keys(UNITS[c].u)[0];
   return Object.keys(UNITS[c].u).map((u,i)=>
     ({l:u,v:F(convert(c,base,u,+v.val),u==='км'||u==='миля'?3:2),hi:i===0}));
  }}
];

/* ---- Дополнительные инструменты ---- */
TOOLS.push(
 {id:'trim',cat:'stab',icon:'ship',name:'Дифферент и осадки',
  desc:'Дифферент, средняя осадка, прогиб и перегиб',
  fields:[
   {k:'f',l:'Осадка носом',t:'num',u:'м',def:'8.20'},
   {k:'a',l:'Осадка кормой',t:'num',u:'м',def:'9.40'},
   {k:'m',l:'Осадка на миделе',t:'num',u:'м',def:'8.90'},
   {k:'lbp',l:'Длина между перпендикулярами',t:'num',u:'м',def:'180'}],
  calc:v=>{
   const t=trimCalc(+v.f,+v.a,+v.lbp), h=hogSag(+v.f,+v.a,+v.m);
   return [
    {l:'Дифферент',v:F(Math.abs(t.trim))+' м на '+(t.byStern?'корму':'нос'),hi:1},
    {l:'Средняя осадка (нос+корма)/2',v:F(t.mean,3)+' м'},
    {l:'Отклонение миделя',v:F(h.deviation,3)+' м ('+(h.sag?'прогиб':'перегиб')+')'},
    {l:'Mean of means',v:F(h.meanOfMean,3)+' м'},
    {l:'Quarter mean (для водоизмещения)',v:F(h.quarterMean,3)+' м'},
    {l:'Дифферент от длины',v:F(t.trimPct,2)+' %'}];
  }},

 {id:'fwa',cat:'stab',icon:'wave',name:'FWA и поправка на плотность',
  desc:'Пресноводная поправка и поправка на плотность порта',
  fields:[
   {k:'w',l:'Водоизмещение',t:'num',u:'т',def:'20000'},
   {k:'tpc',l:'TPC',t:'num',u:'т/см',def:'30'},
   {k:'d',l:'Плотность воды в порту',t:'num',u:'кг/м³',def:'1015'}],
  calc:v=>{
   const r=fwaCalc(+v.w,+v.tpc,+v.d);
   return [
    {l:'FWA (пресная вода)',v:F(r.fwa,1)+' мм',hi:1},
    {l:'DWA (док-вода)',v:F(r.dwa,1)+' мм'},
    {l:'В сантиметрах',v:F(r.dwa/10,2)+' см'},
    {l:'Формула',v:'FWA = W / (4 × TPC)'}];
  }},

 {id:'tpc',cat:'stab',icon:'buoy',name:'TPC и изменение осадки',
  desc:'Тонны на сантиметр и осадка от груза',
  fields:[
   {k:'a',l:'Площадь ватерлинии',t:'num',u:'м²',def:'3000'},
   {k:'d',l:'Плотность',t:'num',u:'т/м³',def:'1.025'},
   {k:'w',l:'Принимаемый груз',t:'num',u:'т',def:'300'}],
  calc:v=>{
   const tpc=tpcCalc(+v.a,+v.d);
   return [
    {l:'TPC',v:F(tpc,2)+' т/см',hi:1},
    {l:'Изменение осадки',v:F(draftChange(+v.w,tpc),1)+' см'},
    {l:'В метрах',v:F(draftChange(+v.w,tpc)/100,3)+' м'}];
  }},

 {id:'dwt',cat:'stab',icon:'archive',name:'Дедвейт',
  desc:'Сколько дедвейта занято и сколько осталось',
  fields:[
   {k:'t',l:'Дедвейт судна',t:'num',u:'т',def:'50000'},
   {k:'c',l:'Груз',t:'num',u:'т',def:'32000'},
   {k:'b',l:'Балласт',t:'num',u:'т',def:'4000'},
   {k:'f',l:'Топливо',t:'num',u:'т',def:'2500'},
   {k:'w',l:'Пресная вода',t:'num',u:'т',def:'300'},
   {k:'s',l:'Запасы',t:'num',u:'т',def:'200'}],
  calc:v=>{
   const r=dwtCalc(+v.t,+v.c,+v.b,+v.f,+v.w,+v.s);
   return [
    {l:'Занято',v:F(r.used,0)+' т'},
    {l:'Остаётся',v:F(r.remaining,0)+' т',hi:1,warn:r.remaining<0},
    {l:'Использовано',v:F(r.pct,1)+' %'}];
  }},

 {id:'sail',cat:'nav',icon:'route',name:'Плавания',
  desc:'Плоское, параллельное, средней широты, Меркатора',
  fields:[
   {k:'la1',l:'Широта отхода',t:'coord',def:'40-00.0N'},
   {k:'lo1',l:'Долгота отхода',t:'coord',def:'074-00.0W'},
   {k:'la2',l:'Широта прихода',t:'coord',def:'38-42.0N'},
   {k:'lo2',l:'Долгота прихода',t:'coord',def:'009-09.0W'}],
  calc:v=>{
   const a=parseCoord(v.la1),b=parseCoord(v.lo1),c=parseCoord(v.la2),d=parseCoord(v.lo2);
   if([a,b,c,d].some(x=>x===null)) return [{l:'Ошибка',v:'Проверь координаты'}];
   const ml=midLatSailing(a,b,c,d), mc=mercatorSailing(a,b,c,d);
   return [
    {l:'Меркатор: курс',v:F(mc.course,1)+'°',hi:1},
    {l:'Меркатор: расстояние',v:F(mc.distance,1)+' миль'},
    {l:'Меридиональная разность (DMP)',v:F(mc.dmp,1)},
    {l:'Средняя широта: курс',v:F(ml.course,1)+'°'},
    {l:'Средняя широта: расстояние',v:F(ml.distance,1)+' миль'},
    {l:'Разность широт',v:F(ml.dLat,1)+' миль'},
    {l:'Отшествие',v:F(ml.departure,1)+' миль'},
    {l:'Ортодромия для сравнения',v:F(gcDistance(a,b,c,d),1)+' миль'}];
  }},

 {id:'compass',cat:'nav',icon:'compass',name:'Поправка компаса',
  desc:'Гирокомпас, склонение, девиация, курсовой угол',
  fields:[
   {k:'g',l:'Пеленг по гирокомпасу',t:'num',u:'°',def:'087.5'},
   {k:'t',l:'Истинный пеленг',t:'num',u:'°',def:'089.0'},
   {k:'tc',l:'Истинный курс',t:'num',u:'°',def:'045'},
   {k:'var',l:'Склонение (E плюс, W минус)',t:'num',u:'°',def:'-5'},
   {k:'dev',l:'Девиация (E плюс, W минус)',t:'num',u:'°',def:'2'},
   {k:'hd',l:'Свой курс (для курсового угла)',t:'num',u:'°',def:'090'},
   {k:'tb',l:'Пеленг на объект',t:'num',u:'°',def:'135'}],
  calc:v=>{
   const ce=compassError(+v.g,+v.t);
   const mc=magneticChain(+v.tc,+v['var'],+v.dev);
   const rb=relativeBearing(+v.hd,+v.tb);
   return [
    {l:'Поправка гирокомпаса',v:F(ce.error,1)+'° '+ce.side,hi:1},
    {l:'Истинный курс',v:F(mc.true,1)+'°'},
    {l:'Магнитный курс',v:F(mc.magnetic,1)+'°'},
    {l:'Компасный курс',v:F(mc.compass,1)+'°'},
    {l:'Общая поправка',v:F(mc.totalError,1)+'°'},
    {l:'Курсовой угол',v:F(rb.relative,1)+'° '+rb.side}];
  }},

 {id:'setdrift',cat:'nav',icon:'wave',name:'Течение: направление и снос',
  desc:'По разнице между курсом через воду и путём по грунту',
  fields:[
   {k:'cw',l:'Курс через воду',t:'num',u:'°',def:'000'},
   {k:'sw',l:'Скорость через воду',t:'num',u:'узлов',def:'10'},
   {k:'cg',l:'Путь по грунту',t:'num',u:'°',def:'015'},
   {k:'sg',l:'Скорость по грунту',t:'num',u:'узлов',def:'10.5'},
   {k:'h',l:'За сколько часов',t:'num',u:'ч',def:'4'}],
  calc:v=>{
   const r=setDrift(+v.cw,+v.sw,+v.cg,+v.sg,+v.h);
   return [
    {l:'Направление течения',v:F(r.set,1)+'°',hi:1},
    {l:'Скорость течения',v:F(r.rate,2)+' узлов'},
    {l:'Снос за период',v:F(r.drift,2)+' миль'}];
  }},

 {id:'ecdis',cat:'depth',icon:'radar',name:'Параметры ECDIS',
  desc:'Safety depth, safety contour, XTD',
  fields:[
   {k:'dr',l:'Осадка',t:'num',u:'м',def:'12.5'},
   {k:'uk',l:'Требуемый UKC по политике компании',t:'num',u:'м',def:'1.5'},
   {k:'sq',l:'Проседание',t:'num',u:'м',def:'1.2'},
   {k:'td',l:'Минимальный прилив на переходе',t:'num',u:'м',def:'0.5'},
   {k:'cw',l:'Ширина фарватера (для XTD)',t:'num',u:'м',def:'300'},
   {k:'bm',l:'Ширина судна',t:'num',u:'м',def:'32'},
   {k:'mg',l:'Запас до бровки',t:'num',u:'м',def:'40'}],
  calc:v=>{
   const e=ecdisParams(+v.dr,+v.uk,+v.sq,+v.td);
   const x=xtdCalc(+v.cw,+v.bm,+v.mg);
   return [
    {l:'Safety depth',v:F(e.safetyDepth,2)+' м',hi:1},
    {l:'Safety contour (ближайшая изобата)',v:e.safetyContour+' м'},
    {l:'Shallow contour',v:e.shallowContour+' м'},
    {l:'Deep contour',v:e.deepContour+' м'},
    {l:'XTD',v:F(x.xtd,1)+' м',warn:!x.safe},
    {l:'XTD в кабельтовых',v:F(x.xtdCables,3)}];
  }},

 {id:'moon',cat:'weather',icon:'sun',name:'Луна',
  desc:'Восход, заход, фаза и освещённость',
  fields:[
   {k:'la',l:'Широта',t:'coord',def:'41-25.4N'},
   {k:'lo',l:'Долгота',t:'coord',def:'002-10.0E'},
   {k:'dt',l:'Дата (пусто = сегодня)',t:'text',def:''}],
  calc:v=>{
   const a=parseCoord(v.la),b=parseCoord(v.lo);
   if(a===null||b===null) return [{l:'Ошибка',v:'Проверь координаты'}];
   const d=v.dt?new Date(v.dt+'T12:00:00Z'):new Date();
   if(isNaN(d)) return [{l:'Ошибка',v:'Проверь дату'}];
   const m=moonTimes(a,b,d);
   return [
    {l:'Фаза',v:m.phaseName,hi:1},
    {l:'Освещённость диска',v:m.illum+' %'},
    {l:'Восход Луны (UTC)',v:utc(m.rise)},
    {l:'Заход Луны (UTC)',v:utc(m.set)}];
  }}
);

const TOOL_CATS={
  nav:{t:'Навигация',i:'compass'},
  depth:{t:'Глубина и осадка',i:'buoy'},
  stab:{t:'Осадка и остойчивость',i:'ship'},
  anchor:{t:'Якорь',i:'anchor'},
  radar:{t:'Радар и манёвр',i:'radar'},
  voyage:{t:'Рейс',i:'ship'},
  weather:{t:'Погода и единицы',i:'wave'}
};

/* ---- Остойчивость и осадка ---- */
function trimCalc(fwd,aft,lbp){
  const trim=aft-fwd, mean=(fwd+aft)/2;
  return {trim:trim, mean:mean, byStern:trim>0,
          trimPct:lbp>0?trim/lbp*100:0};
}
function hogSag(fwd,aft,mid){
  const meanFA=(fwd+aft)/2;
  const dev=mid-meanFA;                      /* + прогиб (sag), − перегиб (hog) */
  const meanOfMean=(meanFA+mid)/2;
  const quarterMean=(meanFA+7*mid)/8;        /* mean of means */
  return {deviation:dev, sag:dev>0, meanOfMean:meanOfMean, quarterMean:quarterMean};
}
function fwaCalc(displacement,tpc,density){
  /* FWA = W / (4 * TPC) в мм; DWA пропорционально плотности */
  const fwa=tpc>0?displacement/(4*tpc):0;    /* мм */
  const dwa=fwa*(1025-density)/25;
  return {fwa:fwa, dwa:dwa};
}
function tpcCalc(areaWaterplane,density){
  /* TPC = A × ρ / 100, где A в м², ρ в т/м³ (морская вода 1.025) */
  return areaWaterplane*density/100;         /* т на см */
}
function dwtCalc(dwtTotal,cargo,ballast,fuel,fw,stores){
  const used=cargo+ballast+fuel+fw+stores;
  return {used:used, remaining:dwtTotal-used, pct:dwtTotal>0?used/dwtTotal*100:0};
}
function draftChange(weight,tpc){
  return tpc>0?weight/tpc:0;                 /* см */
}

/* ---- Плавания ---- */
function planeSailing(dLatMin,course){
  const c=course*D2R;
  const dist=Math.abs(Math.cos(c))>1e-9?dLatMin/Math.cos(c):0;
  return {distance:dist, departure:dist*Math.sin(c)};
}
function parallelSailing(dLonMin,lat){
  return {departure:dLonMin*Math.cos(lat*D2R)};
}
function midLatSailing(la1,lo1,la2,lo2){
  const dLat=(la2-la1)*60, dLon=(lo2-lo1)*60;
  const mLat=(la1+la2)/2;
  const dep=dLon*Math.cos(mLat*D2R);
  const course=norm360(Math.atan2(dep,dLat)*R2D);
  return {dLat:dLat, dLon:dLon, departure:dep, midLat:mLat,
          course:course, distance:Math.hypot(dLat,dep)};
}
function mercatorSailing(la1,lo1,la2,lo2){
  const dLat=(la2-la1)*60, dLon=(lo2-lo1)*60;
  const mp=l=>7915.7045*Math.log10(Math.tan(Math.PI/4+l*D2R/2))
              -23.2689*Math.sin(l*D2R)-0.0526*Math.pow(Math.sin(l*D2R),3);
  const dmp=mp(la2)-mp(la1);
  const course=norm360(Math.atan2(dLon,dmp)*R2D);
  const dist=Math.abs(Math.cos(course*D2R))>1e-9?Math.abs(dLat/Math.cos(course*D2R)):Math.abs(dLon);
  return {dLat:dLat, dLon:dLon, dmp:dmp, course:course, distance:dist};
}

/* ---- Компас ---- */
function compassError(gyroBrg,trueBrg){
  let e=trueBrg-gyroBrg;
  if(e>180)e-=360; if(e<-180)e+=360;
  return {error:Math.abs(e), side:e>=0?'E':'W', signed:e};
}
function magneticChain(trueCrs,variation,deviation){
  const magnetic=norm360(trueCrs-variation);
  const compass=norm360(magnetic-deviation);
  return {true:norm360(trueCrs), magnetic:magnetic, compass:compass,
          totalError:variation+deviation};
}
function relativeBearing(ownHeading,trueBearing){
  return {relative:norm360(trueBearing-ownHeading),
          side:norm360(trueBearing-ownHeading)<180?'правый борт':'левый борт'};
}

/* ---- Течение ---- */
function setDrift(crsThrough,spdThrough,crsOverGround,spdOverGround,hours){
  const ax=spdThrough*Math.sin(crsThrough*D2R), ay=spdThrough*Math.cos(crsThrough*D2R);
  const bx=spdOverGround*Math.sin(crsOverGround*D2R), by=spdOverGround*Math.cos(crsOverGround*D2R);
  const cx=bx-ax, cy=by-ay;
  const rate=Math.hypot(cx,cy);
  return {set:norm360(Math.atan2(cx,cy)*R2D), drift:rate*(hours||1), rate:rate};
}

/* ---- Параметры ECDIS ---- */
function ecdisParams(draft,ukcPolicy,squatV,tideMin,contours){
  const safetyDepth=draft+squatV+ukcPolicy-tideMin;
  const list=(contours||[5,10,15,20,30,50]).slice().sort((a,b)=>a-b);
  const safetyContour=list.find(c=>c>=safetyDepth)||list[list.length-1];
  return {safetyDepth:safetyDepth, safetyContour:safetyContour,
          shallowContour:Math.max(0,Math.floor(safetyDepth/2)),
          deepContour:safetyContour*2};
}
function xtdCalc(channelWidth,beam,margin){
  const half=channelWidth/2;
  const xtd=half-beam/2-margin;
  return {xtd:xtd, xtdCables:xtd/185.2, safe:xtd>0};
}

/* ---- Луна ---- */
function moonTimes(lat,lon,date){
  /* приближённый расчёт по часовому перебору высоты Луны */
  const rad=D2R;
  function moonPos(d){
    const days=(d-new Date(Date.UTC(2000,0,1,12)))/86400000;
    const L=rad*(218.316+13.176396*days);
    const M=rad*(134.963+13.064993*days);
    const F=rad*(93.272+13.229350*days);
    const l=L+rad*6.289*Math.sin(M);
    const b=rad*5.128*Math.sin(F);
    const e=rad*23.4397;
    const ra=Math.atan2(Math.sin(l)*Math.cos(e)-Math.tan(b)*Math.sin(e),Math.cos(l));
    const dec=Math.asin(Math.sin(b)*Math.cos(e)+Math.cos(b)*Math.sin(e)*Math.sin(l));
    const gmst=rad*(280.16+360.9856235*days);
    const H=gmst+rad*lon-ra;
    const alt=Math.asin(Math.sin(rad*lat)*Math.sin(dec)+Math.cos(rad*lat)*Math.cos(dec)*Math.cos(H));
    return alt;
  }
  const start=new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth(),date.getUTCDate()));
  let rise=null,set=null,prev=moonPos(start);
  for(let h=1;h<=24;h++){
    const t=new Date(start.getTime()+h*3600000), cur=moonPos(t);
    if(prev<0&&cur>=0&&!rise) rise=t;
    if(prev>=0&&cur<0&&!set) set=t;
    prev=cur;
  }
  /* фаза */
  const days=(date-new Date(Date.UTC(2000,0,6,18,14)))/86400000;
  const phase=((days/29.530588853)%1+1)%1;
  const names=['новолуние','растущий серп','первая четверть','растущая луна',
               'полнолуние','убывающая луна','последняя четверть','убывающий серп'];
  return {rise:rise, set:set, phase:phase,
          phaseName:names[Math.floor(phase*8+0.5)%8],
          illum:Math.round((1-Math.cos(2*Math.PI*phase))/2*100)};
}

/* ================= Справочники ================= */
/* Сигнальные флаги: рисуем SVG, а не картинками -- работает офлайн и не грузит сеть */
const FLAGS={
 A:['Alfa','У меня спущен водолаз, держитесь в стороне','<rect width="60" height="40" fill="#fff"/><path d="M60 0 H30 v40 H60 l-12-20z" fill="#0b60b0"/>'],
 B:['Bravo','Гружу или выгружаю опасный груз','<path d="M0 0 h60 l-14 20 14 20 H0z" fill="#d0342c"/>'],
 C:['Charlie','Да, утверждение','<rect width="60" height="40" fill="#0b60b0"/><rect y="8" width="60" height="8" fill="#fff"/><rect y="16" width="60" height="8" fill="#d0342c"/><rect y="24" width="60" height="8" fill="#fff"/>'],
 D:['Delta','Держитесь в стороне, управляюсь с трудом','<rect width="60" height="40" fill="#f0c419"/><rect y="10" width="60" height="20" fill="#0b2f6b"/>'],
 E:['Echo','Изменяю свой курс вправо','<rect width="60" height="20" fill="#0b60b0"/><rect y="20" width="60" height="20" fill="#d0342c"/>'],
 F:['Foxtrot','Я не управляюсь, держите связь','<rect width="60" height="40" fill="#fff"/><path d="M30 6 L54 34 H6z" fill="#d0342c"/>'],
 G:['Golf','Мне нужен лоцман','<rect width="60" height="40" fill="#f0c419"/><rect x="10" width="10" height="40" fill="#0b60b0"/><rect x="30" width="10" height="40" fill="#0b60b0"/><rect x="50" width="10" height="40" fill="#0b60b0"/>'],
 H:['Hotel','У меня на борту лоцман','<rect width="30" height="40" fill="#fff"/><rect x="30" width="30" height="40" fill="#d0342c"/>'],
 I:['India','Изменяю свой курс влево','<rect width="60" height="40" fill="#f0c419"/><circle cx="30" cy="20" r="9" fill="#000"/>'],
 J:['Juliett','У меня пожар, имею опасный груз','<rect width="60" height="40" fill="#0b60b0"/><rect y="13" width="60" height="14" fill="#fff"/>'],
 K:['Kilo','Желаю установить связь с вами','<rect width="60" height="40" fill="#f0c419"/><path d="M60 0 H30 v40 H60z" fill="#0b60b0"/>'],
 L:['Lima','Остановите судно немедленно','<rect width="60" height="40" fill="#f0c419"/><rect width="30" height="20" fill="#000"/><rect x="30" y="20" width="30" height="20" fill="#000"/>'],
 M:['Mike','Моё судно остановлено, хода не имею','<rect width="60" height="40" fill="#0b60b0"/><path d="M0 0 L60 40 M60 0 L0 40" stroke="#fff" stroke-width="9"/>'],
 N:['November','Нет, отрицание','<rect width="60" height="40" fill="#fff"/><rect width="15" height="10" fill="#0b60b0"/><rect x="30" width="15" height="10" fill="#0b60b0"/><rect x="15" y="10" width="15" height="10" fill="#0b60b0"/><rect x="45" y="10" width="15" height="10" fill="#0b60b0"/><rect y="20" width="15" height="10" fill="#0b60b0"/><rect x="30" y="20" width="15" height="10" fill="#0b60b0"/><rect x="15" y="30" width="15" height="10" fill="#0b60b0"/><rect x="45" y="30" width="15" height="10" fill="#0b60b0"/>'],
 O:['Oscar','Человек за бортом','<path d="M0 0 h60 L0 40z" fill="#d0342c"/><path d="M60 0 v40 H0z" fill="#f0c419"/>'],
 P:['Papa','Всем прибыть на борт, судно снимается','<rect width="60" height="40" fill="#0b2f6b"/><rect x="18" y="10" width="24" height="20" fill="#fff"/>'],
 Q:['Quebec','Моё судно незаражённое, прошу свободную практику','<rect width="60" height="40" fill="#f0c419"/>'],
 R:['Romeo','Принято','<rect width="60" height="40" fill="#d0342c"/><rect x="26" width="8" height="40" fill="#f0c419"/><rect y="16" width="60" height="8" fill="#f0c419"/>'],
 S:['Sierra','Мои движители работают на задний ход','<rect width="60" height="40" fill="#fff"/><rect x="14" y="9" width="32" height="22" fill="#0b2f6b"/>'],
 T:['Tango','Держитесь в стороне, произвожу парное траление','<rect width="20" height="40" fill="#d0342c"/><rect x="20" width="20" height="40" fill="#fff"/><rect x="40" width="20" height="40" fill="#0b60b0"/>'],
 U:['Uniform','Вы идёте к опасности','<rect width="60" height="40" fill="#fff"/><rect width="30" height="20" fill="#d0342c"/><rect x="30" y="20" width="30" height="20" fill="#d0342c"/>'],
 V:['Victor','Мне требуется помощь','<rect width="60" height="40" fill="#fff"/><path d="M0 0 L60 40 M60 0 L0 40" stroke="#d0342c" stroke-width="9"/>'],
 W:['Whiskey','Мне требуется медицинская помощь','<rect width="60" height="40" fill="#0b60b0"/><rect x="8" y="6" width="44" height="28" fill="#fff"/><rect x="17" y="12" width="26" height="16" fill="#d0342c"/>'],
 X:['Xray','Приостановите ваши намерения','<rect width="60" height="40" fill="#fff"/><rect x="26" width="8" height="40" fill="#0b60b0"/><rect y="16" width="60" height="8" fill="#0b60b0"/>'],
 Y:['Yankee','Меня дрейфует на якоре','<rect width="60" height="40" fill="#f0c419"/><path d="M-10 0 l80 53 M-10 8 l80 53 M-10 16 l80 53 M-10 -8 l80 53 M-10 -16 l80 53" stroke="#d0342c" stroke-width="6"/>'],
 Z:['Zulu','Мне требуется буксир','<path d="M0 0 L30 20 L0 40z" fill="#f0c419"/><path d="M0 0 L30 20 L60 0z" fill="#000"/><path d="M60 0 L30 20 L60 40z" fill="#0b60b0"/><path d="M0 40 L30 20 L60 40z" fill="#d0342c"/>']
};

/* МППСС-72: ключевые правила своими словами, не дословный текст конвенции */
const COLREG=[
 ['5','Наблюдение','Постоянно вести надлежащее наблюдение зрением, слухом и всеми доступными средствами, чтобы полностью оценить обстановку и риск столкновения.'],
 ['6','Безопасная скорость','Идти с такой скоростью, чтобы можно было принять эффективные меры и остановиться в пределах расстояния, соответствующего обстоятельствам. Учитывать видимость, плотность движения, маневренность, состояние моря, осадку и ограничения радара.'],
 ['7','Риск столкновения','Использовать все средства для определения риска. Считать, что риск есть, если пеленг на приближающееся судно заметно не меняется. Не делать выводов по неполной информации, особенно по скудным радарным данным.'],
 ['8','Действия по предупреждению','Действия должны быть решительными, своевременными и заметными для другого судна. Изменение курса предпочтительнее изменения скорости, если места достаточно. Проверять эффективность до полного расхождения.'],
 ['9','Плавание в узкостях','Держаться внешней стороны фарватера по правому борту насколько это безопасно. Судно менее 20 м, парусное и занятое ловом рыбы не должны затруднять движение судна, которое может следовать только в пределах узкости.'],
 ['10','Системы разделения движения','Следовать в полосе в принятом направлении, держаться в стороне от линии разделения, входить и выходить на конечных участках или под малым углом. Пересекать по возможности под прямым углом к направлению потока.'],
 ['12','Парусные суда','При разных галсах уступает судно на левом галсе. При одинаковых галсах уступает наветренное. Если галс другого не определён, уступать в любом случае.'],
 ['13','Обгон','Обгоняющий уступает дорогу обгоняемому. Обгон это подход с направления более 22.5° позади траверза. Последующее изменение пеленга не освобождает от обязанности держаться в стороне до полного расхождения.'],
 ['14','Сближение прямо','При встрече на противоположных курсах оба изменяют курс вправо, чтобы разойтись левыми бортами. При сомнении считать, что такая ситуация есть, и действовать соответственно.'],
 ['15','Пересечение курсов','Уступает то судно, которое имеет другое справа. Избегать пересечения курса впереди него.'],
 ['16','Действия уступающего','Предпринять заблаговременные и решительные действия для расхождения на безопасном расстоянии.'],
 ['17','Действия судна, которому уступают','Сохранять курс и скорость. Может действовать самостоятельно, когда становится ясно, что уступающий не предпринимает должных мер. При невозможности избежать столкновения одними действиями уступающего обязано действовать.'],
 ['18','Взаимные обязанности','Порядок уступания: судно с механическим двигателем уступает парусному, занятому ловом рыбы, ограниченному в маневре и лишённому возможности управляться.'],
 ['19','Ограниченная видимость','Идти безопасной скоростью с готовой к немедленному манёвру машиной. Избегать поворота влево на судно впереди траверза, кроме случая обгона, и поворота на судно на траверзе или позади.'],
 ['35','Звуковые сигналы в тумане','Судно на ходу с механическим двигателем: один продолжительный не реже чем каждые 2 минуты. На ходу без хода: два продолжительных. Ограниченное в маневре, парусное, на буксире: один продолжительный и два коротких.']
];

/* Частоты и каналы GMDSS */
const GMDSS=[
 ['Бедствие и безопасность','VHF канал 16','156.800 МГц','Голосовая связь, слуховая вахта'],
 ['ЦИВ (DSC)','VHF канал 70','156.525 МГц','Цифровой избирательный вызов'],
 ['ЦИВ (DSC)','MF','2187.5 кГц','Бедствие и безопасность'],
 ['Голос MF','MF','2182 кГц','Бедствие, срочность, безопасность'],
 ['ЦИВ (DSC)','HF 4 МГц','4207.5 кГц','Бедствие и безопасность'],
 ['ЦИВ (DSC)','HF 6 МГц','6312.0 кГц','Бедствие и безопасность'],
 ['ЦИВ (DSC)','HF 8 МГц','8414.5 кГц','Бедствие и безопасность'],
 ['ЦИВ (DSC)','HF 12 МГц','12577.0 кГц','Бедствие и безопасность'],
 ['ЦИВ (DSC)','HF 16 МГц','16804.5 кГц','Бедствие и безопасность'],
 ['NAVTEX','Международный','518 кГц','Английский язык, стандартные передачи'],
 ['NAVTEX','Национальный','490 кГц','Местный язык'],
 ['NAVTEX','Тропический','4209.5 кГц','Дополнительный диапазон'],
 ['АРБ (EPIRB)','COSPAS-SARSAT','406.0-406.1 МГц','Спутниковый радиобуй'],
 ['АРБ (EPIRB)','Приводной','121.5 МГц','Ближний привод'],
 ['SART','Радар','9.2-9.5 ГГц','Отклик на 3 см радар (X-band)'],
 ['AIS-SART','AIS','161.975 / 162.025 МГц','AIS каналы 1 и 2'],
 ['Мостик-мостик','VHF канал 13','156.650 МГц','Безопасность мореплавания'],
 ['Мостик-мостик','VHF канал 6','156.300 МГц','Связь при поисково-спасательных работах']
];


/* ================= Язык интерфейса =================
   Перевод делается проходом по готовой разметке после отрисовки, а не
   подстановкой в каждой строке кода. Так переводится и то, что рисуется
   динамически, без правки сотни мест. Значения полей ввода не трогаем --
   там данные пользователя. */
const DICT={
 'Панель':'Dashboard','Районы':'Areas','Карта':'Map','Мостик':'Bridge',
 'Радио':'Radio','Судно':'Ship','Рейс':'Voyage',
 'Спокойной вахты':'Have a good watch','Инструменты вахтенного помощника':'Bridge officer toolkit',
 'Данные из кэша':'Cached data','В эфире':'Live','на связи':'online','офлайн':'offline',
 'действующих предупреждений по твоим районам':'warnings in force in your areas',
 'Открыть карту →':'Open chart →','Действует':'In force','Сегодня':'Today',
 'За 7 дней':'Last 7 days','В архиве':'Archived','Все':'All','Все районы':'All areas',
 'Избранные районы':'Favourite areas','Все →':'All →','Найдено':'Found',
 'Поиск: номер, координаты, текст…':'Search: number, position, text…',
 'По количеству ⇅':'By count ⇅','По новизне ⇅':'By newest ⇅','По номеру ⇅':'By code ⇅',
 'Целиком':'Full text','Подробнее':'Details','Свернуть':'Collapse','На карте':'On chart',
 'На общую карту':'Open on main chart','Назад к инструментам':'Back to tools',
 'Текст предупреждения':'Warning text','Координаты':'Positions','Позиция курсора':'Cursor position',
 'Подложка':'Base map','Тёмная':'Dark','Океан':'Ocean','Слои':'Layers',
 'Районы и полосы':'Areas and lanes','Точечные объекты':'Point objects','Подписи номеров':'Number labels',
 'Предупреждения':'Warnings','Судовые сообщения':'Ship reporting','Справочные зоны':'Reference zones',
 'Инструменты мостика':'Bridge tools','Исходные данные':'Input','Результат':'Result',
 'Навигация':'Navigation','Глубина и осадка':'Depth and draught','Якорь':'Anchoring',
 'Радар и манёвр':'Radar and manoeuvring','Погода и единицы':'Weather and units',
 'Остойчивость':'Stability','Избранные инструменты':'Favourite tools',
 'Расстояние и курс':'Distance and course','ETA и скорость':'ETA and speed',
 'Конвертер координат':'Position converter','Запас воды под килём':'Under keel clearance',
 'Проседание на ходу':'Squat','Проход под мостом':'Air draught','Якорная стоянка':'Anchor swing',
 'CPA и TCPA':'CPA and TCPA','Точка перекладки руля':'Wheel over point',
 'Топливо на переход':'Bunkers for passage','Восход, заход, сумерки':'Sunrise, sunset, twilight',
 'Шкала Бофорта':'Beaufort scale','Конвертер единиц':'Unit converter',
 'Тест MF/HF DSC':'MF/HF DSC test','Отвечают надёжнее всего':'Most reliable to answer',
 'Остальные станции':'Other stations','Автоподтверждение':'Auto-acknowledgment',
 'Отвечает стабильно':'Answers reliably','Отвечает не всегда':'Does not always answer',
 'Моё судно':'My ship','Судно не заведено':'No ship saved','Заполнить карточку':'Fill in details',
 'Изменить данные':'Edit details','Карточка судна':'Ship particulars','Сохранить':'Save',
 'Опознавание':'Identification','Размерения':'Dimensions','Эксплуатация':'Operation',
 'Планирование перехода':'Passage planning','Порт отправления':'Port of departure',
 'Порт прибытия':'Port of arrival','Ширина коридора':'Corridor width',
 'Проложить и проверить':'Plot and check','миль':'NM','узлов':'kn','часов':'hours',
 'История':'History','Очистить всё':'Clear all','Сертификаты':'Certificates','Добавить +':'Add +',
 'Укажи оба порта.':'Enter both ports.','Нет связи с сервером. Попробуй позже.':'No connection. Try later.',
 'Ничего не нашлось. Попробуй номер, часть текста или координаты.':'Nothing found. Try a number, part of the text or a position.',
 'По этому району сейчас нет действующих предупреждений.':'No warnings in force for this area.',
 'По этому маршруту действующих предупреждений с координатами нет.':'No warnings with positions along this route.',
 'Нет связи. Показаны последние сохранённые данные.':'No connection. Showing last saved data.'
};
/* подписи полей и результатов в расчётах */
Object.assign(DICT,{
 'Широта':'Latitude','Долгота':'Longitude','Широта отхода':'Latitude from','Долгота отхода':'Longitude from',
 'Широта прихода':'Latitude to','Долгота прихода':'Longitude to','Ортодромия':'Great circle',
 'Локсодромия':'Rhumb line','Начальный курс':'Initial course','Конечный курс':'Final course',
 'Курс по локсодромии':'Rhumb course','Обратный курс':'Reciprocal course','Расстояние':'Distance',
 'Скорость':'Speed','Время в пути':'Time on passage','В сутках':'In days',
 'ETA (UTC от сейчас)':'ETA (UTC from now)','Требуемая скорость':'Required speed',
 'Времени в запасе (для требуемой скорости)':'Time available (for required speed)',
 'За сколько часов':'Hours available','Десятичные':'Decimal','Градусы и минуты':'Degrees and minutes',
 'Градусы, минуты, секунды':'Degrees, minutes, seconds','Глубина по карте':'Charted depth',
 'Высота прилива':'Height of tide','Осадка':'Draught','Проседание (squat)':'Squat',
 'Поправка на крен':'Heel allowance','Поправка на волнение':'Wave allowance',
 'Доступная глубина':'Available depth','Требуется':'Required','Запас под килём':'Under keel clearance',
 'В процентах от осадки':'Percent of draught','Требуемый UKC по политике компании':'Required UKC by company policy',
 'Коэффициент общей полноты Cb':'Block coefficient Cb','Акватория':'Water area',
 'Проседание':'Squat','При половинной скорости':'At half speed','Формула':'Formula',
 'Габарит по карте (над HAT)':'Charted clearance (above HAT)','Текущий прилив':'Tide now',
 'Надводный габарит судна':'Ship air draught','Фактический просвет':'Actual clearance',
 'Запас по высоте':'Vertical margin','Вытравлено цепи':'Cable paid out','Глубина':'Depth',
 'Высота клюза над водой':'Hawse pipe above water','Длина судна':'Ship length',
 'Радиус циркуляции':'Swing radius','Горизонтальная проекция цепи':'Horizontal scope',
 'Скоп (цепь / глубина)':'Scope (cable / depth)','Вытравлено смычек':'Shackles paid out',
 'Свой курс':'Own course','Своя скорость':'Own speed','Пеленг на цель':'Target bearing',
 'Дистанция до цели':'Target range','Курс цели':'Target course','Скорость цели':'Target speed',
 'Курс относительного движения':'Relative course','Скорость сближения':'Closing speed',
 'Изменение курса':'Course change','Скорость (для времени)':'Speed (for timing)',
 'Перекладка за':'Wheel over at','В кабельтовых':'In cables','Времени до точки':'Time to point',
 'Расход в сутки':'Consumption per day','Топлива на борту':'Bunkers on board',
 'Неснижаемый запас':'Minimum reserve','Потребуется топлива':'Fuel required',
 'Останется':'Will remain','Остаётся':'Remaining','Хватает':'Sufficient',
 'Дата (UTC)':'Date (UTC)','Дата (пусто = сегодня)':'Date (empty = today)',
 'Дата (ГГГГ-ММ-ДД, пусто = сегодня)':'Date (YYYY-MM-DD, empty = today)',
 'Полдень (UTC)':'Meridian passage (UTC)','Скорость ветра':'Wind speed','Балл':'Force',
 'Диапазон':'Range','Состояние моря':'Sea state','Характерная высота волны':'Typical wave height',
 'В м/с':'In m/s','Величина':'Quantity','Значение':'Value','В метрах':'In metres',
 'В сантиметрах':'In centimetres','Осадка носом':'Draught forward','Осадка кормой':'Draught aft',
 'Осадка на миделе':'Draught midships','Дифферент':'Trim','Средняя осадка (нос+корма)/2':'Mean draught (F+A)/2',
 'Mean of means':'Mean of means','Quarter mean (для водоизмещения)':'Quarter mean (for displacement)',
 'Отклонение миделя':'Midships deflection','Дифферент от длины':'Trim as fraction of length',
 'Длина между перпендикулярами':'Length between perpendiculars','Плотность':'Density',
 'Плотность воды в порту':'Dock water density','FWA (пресная вода)':'FWA (fresh water)',
 'DWA (док-вода)':'DWA (dock water)','Изменение осадки':'Change of draught',
 'Площадь ватерлинии':'Waterplane area','Принимаемый груз':'Cargo to load','TPC':'TPC',
 'Водоизмещение':'Displacement','Дедвейт судна':'Ship deadweight','Груз':'Cargo',
 'Балласт':'Ballast','Топливо':'Fuel','Пресная вода':'Fresh water','Запасы':'Stores',
 'Занято':'Used','Использовано':'Utilised','Ширина судна':'Ship beam',
 'Ширина фарватера (для XTD)':'Fairway width (for XTD)','Safety depth':'Safety depth',
 'Safety contour (ближайшая изобата)':'Safety contour (nearest available)','Shallow contour':'Shallow contour',
 'Deep contour':'Deep contour','XTD':'XTD','XTD в кабельтовых':'XTD in cables',
 'Запас до бровки':'Margin to edge','Минимальный прилив на переходе':'Minimum tide on passage',
 'Пеленг по гирокомпасу':'Gyro bearing','Истинный пеленг':'True bearing',
 'Поправка гирокомпаса':'Gyro error','Компасный курс':'Compass course','Магнитный курс':'Magnetic course',
 'Истинный курс':'True course','Склонение (E плюс, W минус)':'Variation (E plus, W minus)',
 'Девиация (E плюс, W минус)':'Deviation (E plus, W minus)','Общая поправка':'Total correction',
 'Курс через воду':'Course through water','Скорость через воду':'Speed through water',
 'Направление течения':'Set','Скорость течения':'Drift','Путь по грунту':'Course over ground',
 'Скорость по грунту':'Speed over ground','Снос за период':'Drift over period',
 'Разность широт':'Difference of latitude','Отшествие':'Departure',
 'Меридиональная разность (DMP)':'Meridional parts difference','Меркатор: курс':'Mercator course',
 'Меркатор: расстояние':'Mercator distance','Средняя широта: курс':'Middle latitude course',
 'Средняя широта: расстояние':'Middle latitude distance','Ортодромия для сравнения':'Great circle for comparison',
 'Фаза':'Phase','Освещённость диска':'Illumination','Восход Луны (UTC)':'Moonrise (UTC)',
 'Заход Луны (UTC)':'Moonset (UTC)','Пеленг на объект':'Bearing to object',
 'Свой курс (для курсового угла)':'Own course (for relative bearing)','Курсовой угол':'Relative bearing',
 'Ошибка':'Error','Advance':'Advance','Transfer':'Transfer','CPA':'CPA','TCPA':'TCPA','HAT':'HAT',
 /* названия и описания инструментов */
 'Дифферент и осадки':'Trim and draughts','FWA и поправка на плотность':'FWA and density correction',
 'TPC и изменение осадки':'TPC and draught change','Дедвейт':'Deadweight','Плавания':'Sailings',
 'Поправка компаса':'Compass error','Параметры ECDIS':'ECDIS settings','Луна':'Moon',
 'Течение и снос':'Set and drift','Курсовой угол и пеленг':'Relative bearing',
 'Ортодромия, локсодромия, начальный и конечный курс':'Great circle, rhumb line, initial and final course',
 'Время в пути, требуемая скорость, время прибытия':'Time on passage, required speed, arrival time',
 'Градусы, минуты, секунды и десятичные':'Degrees, minutes, seconds and decimal',
 'UKC с учётом прилива, проседания, крена и волнения':'UKC allowing for tide, squat, heel and waves',
 'Squat по упрощённой формуле Барраса':'Squat by simplified Barrass formula',
 'Надводный габарит и запас по высоте':'Air draught and vertical margin',
 'Радиус циркуляции на якоре и длина скопа':'Swing radius at anchor and scope',
 'Расхождение с целью по данным радара':'Passing distance from radar data',
 'Wheel Over Point, advance и transfer':'Wheel over point, advance and transfer',
 'Расход, остаток и запас':'Consumption, remaining and reserve',
 'Для планирования вахт и смены режима наблюдения':'For watch planning and lookout changes',
 'Ветер, состояние моря и высота волны':'Wind, sea state and wave height',
 'Длина, скорость, масса, объём, температура':'Length, speed, mass, volume, temperature',
 /* прочее в интерфейсе */
 'Открытая вода':'Open water','Стеснённая / канал':'Confined / channel',
 'Длина':'Length','Масса':'Mass','Объём':'Volume','Температура':'Temperature',
 'Проверь формат координат':'Check position format','Проверь формат':'Check format',
 'Проверь координаты':'Check positions','Проверь дату':'Check date',
 'Проверь введённые данные':'Check the input','да, с запасом':'yes, spare',
 'цель расходится':'target opening','круглые сутки':'all day',
 'Восход — заход':'Sunrise — sunset','Гражданские сумерки':'Civil twilight',
 'Навигационные сумерки':'Nautical twilight','Астрономические сумерки':'Astronomical twilight',
 'Расчёт справочный. Решение принимает судоводитель по официальным пособиям и данным судна.':
   'Reference calculation only. The decision rests with the navigator using official publications and ship data.',
 'Все расчёты выполняются прямо в приложении и работают без связи.':
   'All calculations run in the app and work offline.'
});


/* остальные подписи интерфейса */
Object.assign(DICT,{
 'Судно не заведено':'No ship saved','Найти судно по названию':'Find ship by name',
 'Заполнить вручную':'Enter manually','Изменить данные':'Edit details','Удалить судно':'Delete ship',
 'Поиск судна':'Ship search','Название, IMO или MMSI':'Name, IMO or MMSI',
 'Поиск по своим судам':'Search your own ships','Поиск по мировой базе судов':'Search the global ship database',
 'Основное':'General','Размерения':'Dimensions','Осадка':'Draught','Механическая часть':'Machinery',
 'Манёвренность и якорь':'Manoeuvring and anchoring','Оборудование мостика':'Bridge equipment',
 'Грузовое устройство':'Cargo gear','Документы':'Documents','Добавить документ':'Add document',
 'Документ судна':'Ship document','Редакция или дата':'Edition or date','Заметка':'Note',
 'Название, редакция и заметка':'Name, edition and note','Другой':'Other',
 'из карточки':'from ship card','длина, м':'length, m','ширина, м':'beam, m',
 'осадка, м':'draught, m','дедвейт, т':'deadweight, t','Судно':'Ship','Загружаю…':'Loading…',
 'Ничего не нашлось. Можно заполнить карточку вручную.':'Nothing found. You can fill in the card manually.',
 'Главная':'Home','Инструменты':'Tools','Профиль':'Profile','Обзор':'Overview',
 'Расчёты':'Calculations','Справочники':'References','Маршрут':'Route','Зоны':'Zones',
 'Настройки':'Settings','Быстрые действия':'Quick actions','Активный рейс':'Active passage',
 'Последние расчёты':'Recent calculations','Проверить маршрут':'Check route','Порт — порт':'Port to port',
 'Расхождение':'Passing distance','Все предупреждения':'All warnings','UKC и проседание':'UKC and squat',
 'Оформление':'Appearance','Тёмная тема':'Dark theme','Язык интерфейса':'Interface language',
 'Русский или английский':'Russian or English','Светлая версия для дневной вахты':'Light version for day watch',
 'Доступ':'Access','Текущий тариф':'Current plan','Данные без связи':'Offline data',
 'Последняя синхронизация':'Last sync','Очистить сохранённые данные':'Clear saved data',
 'О приложении':'About','Все →':'All →','Открыть →':'Open →','предупреждений на маршруте':'warnings on route',
 'Идёт отладка, все разделы открыты бесплатно.':'Testing in progress, all sections are open for free.',
 'Что входит в Premium':'What Premium includes','нет':'none',
 'Данные справочные. Официальным источником остаются оборудование GMDSS и NAVTEX, ECDIS и судовые пособия. Решение принимает судоводитель.':
   'Reference data only. The official source is GMDSS and NAVTEX equipment, ECDIS and ship publications. The decision rests with the navigator.',
 'Осадка и остойчивость':'Draught and stability','Справочники':'References','Чек-листы':'Checklists',
 'Сигнальные флаги':'Signal flags','МППСС-72':'COLREG 72','Частоты GMDSS':'GMDSS frequencies',
 'Архив наварий':'Warnings archive','Архив предупреждений':'Warnings archive',
 'Где сейчас горячо':'Where it is busiest','Динамика за 30 дней':'Last 30 days',
 'Течение: направление и снос':'Set and drift','Точка':'Point','Поиск':'Search','Порт':'Port',
 'Название':'Name','Действует до':'Valid until','По количеству':'By count',
 'Номер (необязательно)':'Number (optional)','Заметка (необязательно)':'Note (optional)',
 'Весь международный свод с расшифровкой':'Full international code with meanings',
 'Ключевые правила расхождения':'Key rules for passing',
 'Бедствие, NAVTEX, буи, каналы':'Distress, NAVTEX, buoys, channels',
 'Бедствие, безопасность, NAVTEX, буи':'Distress, safety, NAVTEX, buoys',
 'Поиск по отменённым за всё время':'Search all cancelled warnings',
 'Восход, заход, фаза и освещённость':'Rise, set, phase and illumination',
 'Гирокомпас, склонение, девиация, курсовой угол':'Gyro, variation, deviation, relative bearing',
 'Дифферент, средняя осадка, прогиб и перегиб':'Trim, mean draught, hog and sag',
 'Пресноводная поправка и поправка на плотность порта':'Fresh water and dock water allowance',
 'Тонны на сантиметр и осадка от груза':'Tonnes per centimetre and draught from cargo',
 'Сколько дедвейта занято и сколько осталось':'Deadweight used and remaining',
 'Плоское, параллельное, средней широты, Меркатора':'Plane, parallel, middle latitude, Mercator',
 'По разнице между курсом через воду и путём по грунту':'From course through water and course over ground',
 'Где выдан, что нужно для продления':'Where issued, what is needed to renew',
 'Номер, координаты, текст…':'Number, position, text…',
 'Поиск по букве или значению':'Search by letter or meaning',
 'Поиск по номеру или теме':'Search by number or subject',
 'Поиск по номеру, тексту или координатам':'Search by number, text or position',
 'Например O или водолаз':'For example O or diver','Например 15 или обгон':'For example 15 or overtaking',
 'Например NAVTEX или 2182':'For example NAVTEX or 2182','Например 700 или BUOY':'For example 700 or BUOY',
 'Например Constanta':'For example Constanta','Например Santos':'For example Santos',
 'Например Rotterdam':'For example Rotterdam','Например SSCEC':'For example SSCEC',
 'Сохранить сертификат':'Save certificate','Отмена':'Cancel','Назад':'Back',
 'Назад к инструментам':'Back to tools','Сохранить и закрыть':'Save and close',
 'Добавить +':'Add +','Без названия':'Unnamed','Берег':'Coastal','БЕРЕГ':'COASTAL',
 'Введи запрос, чтобы искать по архиву.':'Enter a query to search the archive.',
 'Введи хотя бы два символа.':'Enter at least two characters.',
 'В архиве ничего не нашлось.':'Nothing found in the archive.',
 'Ничего не нашлось.':'Nothing found.','Нет связи.':'No connection.',
 'В тексте нет распознанных координат.':'No positions recognised in the text.',
 'Без координат':'No positions','Заполни название и дату':'Fill in name and date',
 'Не удалось сохранить':'Could not save','нет связи':'no connection',
 'точная геометрия':'exact geometry','отменено':'cancelled',
 'Отвечают надёжнее всего':'Most reliable to answer','Остальные станции':'Other stations',
 'В этом регионе станций нет.':'No stations in this region.',
 'Не удалось загрузить справочник станций. Попробуй позже.':'Could not load the station list. Try later.',
 'Сертификатов пока нет. Добавь любой, и бот сам напомнит за 60, 30, 14, 7, 3 и 1 день до истечения.':
   'No certificates yet. Add one and the bot will remind you 60, 30, 14, 7, 3 and 1 day before expiry.',
 'Premium активен':'Premium active','Открытый доступ':'Open access',
 'MARPOL Прил. V':'MARPOL Annex V','Приход в порт':'Arrival in port','Отход из порта':'Departure from port',
 'Подготовка к PSC':'PSC preparation','пунктов':'items','пункта':'items','пункт':'item'
});

Object.assign(DICT,{
 'Бесплатно':'Free','Бесплатный тариф':'Free plan','Выполнено':'Completed','Документ':'Document',
 'Два района NAVAREA с уведомлениями':'Two NAVAREA areas with alerts',
 'Карта всех действующих предупреждений':'Chart of all warnings in force',
 'Нет связи с сервером.':'No connection to the server.',
 'Открыты все разделы. Спасибо, что поддерживаешь проект.':'All sections open. Thanks for supporting the project.',
 'Открыть всё →':'Unlock all →','Подробнее →':'Details →','Сейчас у тебя':'You have now',
 'Пять вопросов ассистенту в день':'Five assistant questions a day',
 'Расстояние, курс, ETA, координаты, единицы, Бофорт, светила':'Distance, course, ETA, positions, units, Beaufort, celestial',
 'Своё название (если выбрано «Другой»)':'Custom name (if "Other" selected)',
 'Станции MF/HF DSC и справочные зоны':'MF/HF DSC stations and reference zones'
});
Object.assign(DICT,{
 'Ресурс магнетрона':'Magnetron life',
 'Сколько процентов ресурса радара выработано и что осталось':'How much of the radar magnetron life is used and left',
 'RX time (наработка по счётчику)':'RX time (hours run)',
 'Номинальный ресурс магнетрона':'Rated magnetron life',
 'Наработка в сутки (0 = без прогноза)':'Hours per day (0 = no forecast)',
 'Осталось ресурса':'Life remaining','Выработано':'Life used',
 'Отработано часов':'Hours run','Осталось часов':'Hours remaining',
 'Хватит примерно на':'Approximately lasts',
 'Пора заказывать замену':'Time to order a replacement',
 'Планируй замену заранее':'Plan the replacement ahead',
 'Ресурс должен быть больше нуля':'Rated life must be greater than zero',
 'Внимание':'Attention','Проверка':'Check','Показать все':'Show all','Свернуть':'Collapse','Чаще всего':'Most used','сут':'d','мес':'mo'
});

/* Перевод одной строки. Раньше перевод делался только обходом готовой
   разметки, и подписи полей вида "Расстояние · миль" вместе с единицами
   в значениях ("278.2 т", "45.0° правый борт") оставались русскими.
   Теперь строки переводятся явно при формировании. */
const UNIT_MAP={
 'миль':'NM','миля':'NM','мили':'NM','узлов':'kn','узла':'kn','уз':'kn','м':'m','км':'km','фут':'ft',
 'кГц':'kHz','МГц':'MHz','ГГц':'GHz','Гц':'Hz','гПа':'hPa','мб':'mb','кВт':'kW',
 'км/ч':'km/h','миль/ч':'mph','т/сут':'t/day','литр':'litre','галлон US':'US gallon',
 'баррель':'barrel','фунт':'lb','длинная т':'long ton','баллов':'force','балла':'force',
 'дн':'d','дн.':'d','точ.':'acc.','активных':'active','объектов':'objects','объект':'object',
 'сажень':'fathom','кабельтов':'cables','кабельтовых':'cables','мм':'mm','см':'cm',
 'т':'t','кг':'kg','ч':'h','часов':'hours','часа':'hours','сут':'d','суток':'d','мес':'mo','мин':'min','минут':'min','м²':'m²','м³':'m³',
 'т/см':'t/cm','т/м³':'t/m³','кг/м³':'kg/m³','л':'l','°':'°','%':'%',
 'правый борт':'starboard','левый борт':'port','на корму':'by the stern',
 'на нос':'by the head','прогиб':'sagging','перегиб':'hogging','ровный киль':'even keel',
 'убывающая луна':'waning moon','растущая луна':'waxing moon','полнолуние':'full moon',
 'новолуние':'new moon','первая четверть':'first quarter','последняя четверть':'last quarter',
 'да, с запасом':'yes, spare','цель расходится':'target opening','пусто':'empty'
};
function tr(str){
  if(LANG!=='en'||str==null) return str;
  let s=String(str);
  if(DICT[s]) return DICT[s];
  // длинные ключи раньше коротких, иначе короткий съест часть длинного
  if(!tr._keys) tr._keys=Object.keys(DICT).sort((a,b)=>b.length-a.length);
  for(const k of tr._keys){
    if(k.length>=4&&s.indexOf(k)!==-1) s=s.split(k).join(DICT[k]);
  }
  // единицы стоят отдельным словом в конце или после разделителя
  Object.keys(UNIT_MAP).forEach(u=>{
    s=s.replace(new RegExp('(^|[\\s·(])'+u.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?=$|[\\s).,;])','g'),
                (m,p1)=>p1+UNIT_MAP[u]);
  });
  return s;
}

Object.assign(DICT,{
 'Штиль':'Calm','Тихий':'Light air','Лёгкий':'Light breeze','Слабый':'Gentle breeze',
 'Умеренный':'Moderate breeze','Свежий':'Fresh breeze','Сильный':'Strong breeze',
 'Крепкий':'Near gale','Очень крепкий':'Gale','Шторм':'Strong gale',
 'Сильный шторм':'Storm','Жестокий шторм':'Violent storm','Ураган':'Hurricane',
 'Зеркально гладкое море':'Sea like a mirror','Рябь':'Ripples',
 'Небольшие волны':'Small wavelets','Гребни начинают опрокидываться':'Crests begin to break',
 'Небольшие волны, барашки':'Small waves, whitecaps','Умеренные волны':'Moderate waves',
 'Крупные волны, пена':'Large waves, foam','Море вздымается, пена полосами':'Sea heaps up, foam in streaks',
 'Умеренно высокие волны':'Moderately high waves','Высокие волны, видимость снижена':'High waves, reduced visibility',
 'Очень высокие волны, море белое':'Very high waves, sea white',
 'Исключительно высокие волны':'Exceptionally high waves',
 'Воздух наполнен пеной и брызгами':'Air filled with foam and spray'
});
Object.assign(DICT,{
 'Тренажёр ЦИВ':'DSC Simulator','ЦИВ':'DSC','Тренажёр':'Simulator',
 'Крышка кнопки бедствия, открыть':'Distress button cover, open',
 'Удерживай 2 секунды':'Hold for 2 seconds','Режим экзамена':'Exam mode',
 'Выйти из экзамена':'Leave exam','Как это работает':'How it works',
 'Задание':'Task','верно':'correct','Верно':'Correct','Неверно':'Wrong',
 'Экзамен завершён':'Exam finished','Верных ответов':'Correct answers','из':'of',
 'Все разделы':'All sections','Под рукой':'At hand','Разделы':'Sections'
});
Object.assign(DICT,{
 'EPIRB Test':'EPIRB Test','SART Test':'SART Test',
 'Дата замены батареи':'Battery replacement date',
 'Ежемесячная проверка':'Monthly inspection','Сохранить отметки':'Save checklist',
 'Self-Test':'Self-Test','Начать самопроверку':'Start self-test',
 'Пошагово, как по руководству. Ничего не передаётся по-настоящему.':'Step by step, as in the manual. Nothing is actually transmitted.',
 'Самопроверка пройдена. Отметка добавлена в историю.':'Self-test passed. Logged to history.',
 'Пройти ещё раз':'Test again','Шаг':'Step','Следующий шаг':'Next step',
 'Завершить: PASS':'Finish: PASS','Обнаружена неисправность':'Fault detected',
 'Линия из 12 точек с интервалом 0.64 мили. Ближе 1 мили точки становятся дугами, затем полными окружностями.':
   '12 dots spaced 0.64 NM apart. Inside 1 NM they turn into arcs, then full circles.',
 'миль':'NM','мили':'NM','История проверок':'Test history','Очистить':'Clear',
 'Проверок пока нет':'No tests yet','Удалить всю историю проверок?':'Delete the whole test history?',
 'В порядке':'OK','Планируй замену':'Plan replacement','Скоро истекает':'Expiring soon',
 'Просрочено':'Expired','Срок не указан':'Not set',
 'Навигация и расчёты':'Navigation and tools',
 'Корпус: трещин и повреждений нет':'Housing: no cracks or damage',
 'Антенна не повреждена, вращается свободно':'Antenna undamaged, rotates freely',
 'Крепление (бракет) исправно, не заклинило':'Bracket sound, not jammed',
 'Гидростатический разъединитель (HRU) в пределах срока':'Hydrostatic release (HRU) within date',
 'Срок годности батареи не истёк':'Battery not expired',
 'Линь (lanyard) на месте, не перетёрт':'Lanyard present, not frayed',
 'Строб-маяк исправен':'Strobe light working','Самопроверка пройдена':'Self-test passed',
 'GPS определяет позицию':'GPS acquires position',
 'Батарея в пределах срока':'Battery within date','Дата замены батареи не подошла':'Replacement date not due',
 'Крепление (бракет) исправно':'Bracket sound','Антенна не повреждена, штырь раскладывается':'Antenna undamaged, rod extends',
 'Внешний осмотр: корпус, крышка, индикатор':'Visual check: housing, cap, indicator',
 'Нажать и удерживать TEST':'Press and hold TEST',
 'Кнопка самопроверки, не активации. Обычно 1-2 секунды.':'Self-test button, not activation. Usually 1-2 seconds.',
 'EPIRB ищет спутниковую позицию':'EPIRB searches for satellite position',
 'Индикатор GNSS (зелёный) горит около 1 секунды, когда позиция определена.':'Green GNSS indicator lights for about 1 second once a position is found.',
 'Передаётся тестовый сигнал':'Test signal is transmitted',
 'На всех частотах: 121.5 МГц, AIS и 406 МГц. Это тестовый, а не аварийный сигнал -- на спасательные службы он не поступает.':
   'On all frequencies: 121.5 MHz, AIS and 406 MHz. This is a test signal, not a distress alert -- it does not reach rescue services.',
 'Индикатор мигает по итогу':'Indicator flashes at the end',
 'Один раз -- тест пройден. Продолжает мигать -- обнаружена неисправность, смотри код ошибки в руководстве.':
   'Once -- test passed. Keeps flashing -- a fault was found, check the error code in the manual.',
 'Снять транспондер с крепления':'Remove the transponder from its bracket',
 'Тест выполняется вне бракета, с реальным излучением в эфир.':'The test is performed outside the bracket, with real emission into the air.',
 'Перевести в режим TEST':'Switch to TEST mode',
 'Обычно поворотом переключателя в положение TEST (не ON/DISTRESS) -- у Tron SART20 отдельное положение переключателя для теста.':
   'Usually by turning the switch to TEST (not ON/DISTRESS) -- Tron SART20 has a dedicated test position.',
 'Включить судовой X-диапазонный радар':'Turn on the ship\'s X-band radar',
 'На шкале 6-12 миль, чтобы интервал между точками 0.64 мили был различим.':'On the 6-12 NM range, so the 0.64 NM dot spacing is distinguishable.',
 'Наблюдать отклик на экране радара':'Watch the response on the radar display',
 'Линия из 12 точек, расходящаяся от места установки радара по пеленгу на SART.':'A line of 12 dots extending from own ship along the bearing to the SART.',
 'Вернуть в дежурный режим':'Return to standby',
 'Тест не дольше 5 минут: расходует батарею и создаёт помехи чужим радарам в зоне видимости.':'Keep the test under 5 minutes: it drains the battery and interferes with other radars in range.'
});
Object.assign(DICT,{
 'Подставить мою позицию':'Use my position','Позиция подставлена':'Position filled in',
 'Позиция недоступна':'Position unavailable','Определяю…':'Locating…',
 'Позиция не запрошена':'Position not requested',
 'доступ к геопозиции запрещён':'location access denied',
 'спутники не поймались, попробуй у окна или на крыле мостика':'no satellite fix, try near a window or on the bridge wing',
 'устройство не отдаёт позицию':'device does not provide position',
 'Моя позиция':'My position'
});
Object.assign(DICT,{
 'Показать остальные':'Show the rest','отмечено':'checked'
});
Object.assign(DICT,{
 'Ask WatchKeeper':'Ask WatchKeeper','Спроси обычными словами':'Ask in plain words',
 'Числа из вопроса подставятся в нужный расчёт. Простые вопросы разбираются без связи.':
   'Numbers from your question go straight into the right calculator. Simple questions are handled offline.',
 'Открыть расчёт':'Open calculator','Открыть с этими числами':'Open with these numbers',
 'Заодно посчитать проседание':'Also calculate squat',
 'Проверка маршрута':'Route check','Открыть проверку маршрута':'Open route check',
 'Откуда':'From','Куда':'To','Вахта':'Watch','Моя вахта':'My watch',
 'По ней считается время до заступления':'Used to count time until you go on watch',
 'Расписание берётся из настроек профиля':'Schedule comes from profile settings',
 'Ты сейчас на вахте':'You are on watch now','Следующая':'Next','Следующая вахта':'Next watch',
 'через':'in','в':'at','ч':'h','мин':'min','Думаю…':'Thinking…','Очистить':'Clear',
 'Спроси про расчёт, маршрут или вахту…':'Ask about a calculation, route or watch…',
 'Не получилось спросить: нет связи. Расчёты и справочники работают без неё.':
   'Could not ask: no connection. Calculations and references work without it.',
 'Стеснённая / канал':'Confined / channel'
});
Object.assign(DICT,{
 'Тропические циклоны':'Tropical cyclones','Циклоны':'Cyclones',
 'Сейчас от маршрута':'From route now','Наибольшее сближение':'Closest approach','Когда':'When',
 'Положение':'Position','Ветер':'Wind','порывы':'gusts','Давление в центре':'Central pressure',
 'Перемещение':'Moving','Прогноз пути':'Forecast track','Свернуть прогноз':'Hide forecast',
 'Обновить сводку':'Refresh','Активных тропических циклонов нет.':'No active tropical cyclones.',
 'Сводка циклонов сейчас недоступна. Остальные разделы работают.':'Cyclone data is unavailable right now. Other sections work.',
 'Заполни порты в разделе «Рейс», и расстояние будет считаться до линии перехода.':
   'Fill in the ports in the Voyage section and distances will be measured to your passage line.',
 'Опасно':'Dangerous','Близко':'Close','Следить':'Watch','В стороне':'Clear'
});
Object.assign(DICT,{
 'Не хватает':'Missing','Посчитать':'Calculate','само':'auto','Открыть':'Open',
 'Встречное расхождение':'Head-on','Пересекающиеся курсы':'Crossing','Обгон':'Overtaking',
 'Ограниченная видимость':'Restricted visibility','Недостаточно данных':'Not enough data',
 'Это подсказка по правилам, а не указание. Решение принимает судоводитель по обстановке.':
   'This is a reminder of the rules, not an instruction. The decision rests with the navigator.',
 'Пеленг на цель':'Target bearing','Предупреждения':'Warnings','Моя позиция':'My position'
});
/* ---- Оплата, календарь, выбор вахты ---- */
Object.assign(DICT,{
 'Готовлю счёт…':'Preparing invoice…','Оформить за':'Subscribe for','в месяц':'per month',
 'Оплачено. Premium активирован.':'Paid. Premium is active.',
 'Оплата отменена.':'Payment cancelled.',
 'Оплата не прошла. Попробуй ещё раз.':'Payment failed. Try again.',
 'Счёт закрыт. Подписка не оформлена.':'Invoice closed, no subscription.',
 'Оплата доступна только внутри Telegram. Открой приложение кнопкой в чате с ботом.':
   'Payment works only inside Telegram. Open the app from the chat with the bot.',
 'Подписка уже активна.':'Subscription is already active.',
 'Ты владелец бота, Premium и так открыт.':'You own the bot, Premium is already open.',
 'Бот не настроен: не задан токен.':'Bot is not configured: token missing.',
 'Нет связи с Telegram. Попробуй ещё раз, когда появится сеть.':
   'No connection to Telegram. Try again when the network is back.',
 'Telegram не выдал счёт. Проверь, что у бота включены платежи звёздами.':
   'Telegram did not issue an invoice. Check that Stars payments are enabled for the bot.',
 'Выбери дату':'Pick a date','Выбери год':'Pick a year','Выбери день':'Pick a day',
 'Выбрано':'Selected','Не задана':'Not set','Действует до':'Valid until',
 'Январь':'January','Февраль':'February','Март':'March','Апрель':'April','Май':'May',
 'Июнь':'June','Июль':'July','Август':'August','Сентябрь':'September','Октябрь':'October',
 'Ноябрь':'November','Декабрь':'December',
 'Янв':'Jan','Фев':'Feb','Мар':'Mar','Апр':'Apr','Июн':'Jun','Июл':'Jul','Авг':'Aug',
 'Сен':'Sep','Окт':'Oct','Ноя':'Nov','Дек':'Dec',
 'Пн':'Mo','Вт':'Tu','Ср':'We','Чт':'Th','Пт':'Fr','Сб':'Sa','Вс':'Su',
 'Какая у тебя вахта':'Which watch do you keep',
 'Второй помощник':'Second mate','Старший помощник':'Chief mate','Третий помощник':'Third mate',
 'Шесть через шесть':'Six on, six off','Дневная работа':'Day work',
 '08-17, без ходовой вахты':'08-17, no bridge watch'
});
/* ---- Автопродление и панель создателя бота ---- */
Object.assign(DICT,{
 'Автопродление':'Auto-renewal',
 'Списание раз в 30 дней, пока включено. Выключишь — списаний больше не будет':
   'Charged once every 30 days while it is on. Turn it off and nothing is charged again',
 'Выключено. Оплаченный период доработает до конца и не продлится':
   'Off. The period already paid for runs to its end and will not renew',
 'Отключить автопродление? Оплаченный период доработает до конца, дальше списаний не будет.':
   'Turn auto-renewal off? The period already paid for runs to its end, nothing is charged after that.',
 'Отключаю…':'Turning off…','Включаю…':'Turning on…',
 'Автопродление отключено. Premium доработает до конца оплаченного периода.':
   'Auto-renewal is off. Premium runs to the end of the period already paid for.',
 'Автопродление включено.':'Auto-renewal is back on.',
 'Подпиской можно управлять только внутри Telegram.':
   'The subscription can only be managed inside Telegram.',
 'Платёж не найден, отменять нечего.':'No payment found, there is nothing to cancel.',
 'Telegram не принял отмену. Попробуй через Настройки Telegram → Мои звёзды → Подписки.':
   'Telegram refused the cancellation. Try Telegram Settings → My Stars → Subscriptions.',
 'Premium открыт вручную создателем бота, списаний нет.':
   'Premium was opened manually by the bot owner, nothing is charged.',
 'Создателю бота':'For the bot owner','Админ-панель':'Admin panel',
 'Пользователи, платежи, баланс звёзд, выдача и возврат':
   'Users, payments, star balance, granting and refunds',
 'Раздел только для создателя бота.':'This section is for the bot owner only.',
 'Нет связи с сервером. Открой раздел ещё раз.':
   'No connection to the server. Open the section again.',
 'Звёзды':'Stars','Вывод':'Withdrawal','Люди':'People','Пользователи':'Users','Платежи':'Payments',
 'Обновить':'Refresh','Активные':'Active','Никого не нашлось.':'Nobody found.',
 'Платежей пока нет.':'No payments yet.',
 'Найти по id, имени или @нику':'Search by id, name or @username',
 'Баланс не пришёл':'Balance not received',
 'Это баланс бота в Telegram. Деньги за подписки приходят сюда.':
   'This is the bot balance in Telegram. Subscription money arrives here.',
 'До вывода не хватает':'Short of the withdrawal minimum by',
 'Минимума для вывода хватает.':'The withdrawal minimum is covered.',
 'Минимум для вывода':'Withdrawal minimum','Выдержка каждой звезды':'Hold on each star',
 'Срок прошли, по моему учёту':'Past the hold, by my records',
 'Вывод идёт только через Fragment и только в TON — у Bot API такого метода нет, кнопкой из бота его не вызвать. Telegram держит каждую звезду 21 день на случай возврата покупателю.':
   'Withdrawal goes through Fragment only and in TON only — Bot API has no such method, no button in the bot can call it. Telegram holds every star for 21 days in case of a refund.',
 'Открыть Fragment':'Open Fragment',
 'получено всего':'received in total','за 30 дней':'last 30 days','возвращено':'refunded',
 'всего':'total','заходили за неделю':'active this week','за сутки':'last 24 h',
 'с Premium':'on Premium','выдано вручную':'granted manually','новых за неделю':'new this week',
 'Отключили автопродление':'Auto-renewal turned off by',
 'заходил':'last seen','в приложение не заходил':'never opened the app',
 'без автопродления':'no auto-renewal','автопродление':'auto-renewal',
 'бесплатный':'free','выдан':'granted','оплачен':'paid','владелец':'owner',
 'Снять Premium':'Revoke Premium',
 'Снять Premium? Деньги при этом не возвращаются.':'Revoke Premium? No money is refunded.',
 'Вернуть звёзды':'Refund stars',
 'Вернуть звёзды покупателю? Premium будет снят, отменить возврат нельзя.':
   'Refund the stars to the buyer? Premium will be revoked, the refund cannot be undone.',
 'Возврат отдаёт звёзды покупателю целиком и снимает Premium. Отменить возврат нельзя.':
   'A refund returns the stars to the buyer in full and revokes Premium. It cannot be undone.',
 'Выполняю…':'Working…','Нет доступа.':'No access.','Не получилось.':'It did not work.',
 'Не получилось. Попробуй ещё раз.':'It did not work. Try again.',
 'Premium выдан, человек получил сообщение.':'Premium granted, the user has been notified.',
 'Premium снят.':'Premium revoked.',
 'Звёзды возвращены, Premium снят.':'Stars refunded, Premium revoked.'
});
/* ---- Планшет расхождения и мореходная астрономия ---- */
Object.assign(DICT,{
 'миль на кольце':'miles per ring','векторы за 1 ч':'vectors for 1 h',
 'своё судно':'own ship','линия относительного движения':'relative motion line',
 'Расхождение с целью, планшет и цифры':'Passing distance: the plot and the figures',
 'Пеленг меняется':'Bearing change','цель расходится':'the target is opening',
 'почти не меняется, опасность столкновения':'barely changes, risk of collision',
 'меняется медленно':'changes slowly','меняется заметно':'changes clearly',
 'вправо':'to the right','влево':'to the left','за 10 мин':'in 10 min',
 'Альманах: Солнце и Луна':'Almanac: Sun and Moon',
 'Часовой угол, склонение, высота и азимут в счислимом месте':
   'Hour angle, declination, altitude and azimuth at the DR position',
 'Светило':'Body','Солнце':'Sun','Луна':'Moon','Задать вручную':'Enter manually',
 'Счислимая широта':'DR latitude','Счислимая долгота':'DR longitude',
 'Дата и время UTC (ГГГГ-ММ-ДД ЧЧ:ММ, пусто = сейчас)':'Date and time UTC (YYYY-MM-DD HH:MM, empty = now)',
 'Момент UTC':'Moment UTC','Гринвичский часовой угол':'Greenwich hour angle',
 'Склонение':'Declination','Местный часовой угол':'Local hour angle',
 'Счислимая высота':'Computed altitude','Азимут':'Azimuth','Полудиаметр':'Semidiameter',
 'Горизонтальный параллакс':'Horizontal parallax','Точность расчёта':'Accuracy of the calculation',
 'около 1 угловой минуты':'about 1 arc minute','около 0.5 угловой минуты':'about 0.5 arc minute',
 'Официальный источник':'Official source','Морской астрономический ежегодник':'The Nautical Almanac',
 'Линия положения по светилу':'Position line from a body',
 'Поправки высоты и перенос от счислимого места':'Altitude corrections and the intercept from the DR position',
 'Измеренная высота (градусы)':'Sextant altitude (degrees)','Край диска':'Limb',
 'нижний':'lower','верхний':'upper','центр':'centre',
 'Поправка индекса':'Index error','Высота глаза':'Height of eye',
 'Часовой угол вручную (градусы)':'Hour angle by hand (degrees)',
 'Склонение вручную (градусы, южное со знаком минус)':'Declination by hand (degrees, south is negative)',
 'Введи часовой угол и склонение из ежегодника':'Enter the hour angle and declination from the almanac',
 'Наклонение горизонта':'Dip of the horizon','Рефракция':'Refraction',
 'Истинная высота':'Observed altitude','Перенос':'Intercept',
 'к светилу':'towards the body','от светила':'away from the body',
 'Азимут линии':'Azimuth of the line','Линию проложить':'Lay the line',
 'перпендикулярно азимуту':'perpendicular to azimuth','в точке переноса':'at the intercept point',
 'Проверь дату и время':'Check the date and time'
});
/* ---- Справка о гавани из World Port Index ---- */
Object.assign(DICT,{
 'Гавань и приливы':'Harbour and tides','Гавань':'Harbour','Укрытие':'Shelter',
 'Средний прилив':'Mean tide range','не указан':'not listed','От точки порта':'From the port position',
 'Это средняя величина прилива по справочнику. Для расчёта на дату и час нужны таблицы приливов порта.':
   'This is the mean tide range from the index. Working out the height for a date and hour needs the port tide tables.',
 'прибрежная природная':'coastal natural','прибрежная с молом':'coastal breakwater',
 'прибрежная со шлюзом':'coastal tide gate','речная природная':'river natural',
 'речной бассейн':'river basin','речная со шлюзом':'river tide gate',
 'озеро или канал':'lake or canal','открытый рейд':'open roadstead','тайфунная гавань':'typhoon harbor',
 'большая':'large','средняя':'medium','малая':'small','очень малая':'very small',
 'отличное':'excellent','хорошее':'good','среднее':'fair','плохое':'poor'
});
/* ---- Выгрузка предупреждений ---- */
Object.assign(DICT,{
 'Выгрузка предупреждений':'Export of warnings','Готовлю файл…':'Preparing the file…',
 'Отправил в чат:':'Sent to the chat:','шт.':'items',
 'Выгружать нечего: у предупреждений нет координат.':'Nothing to export: the warnings carry no coordinates.',
 'Выгрузка входит в Premium.':'Export is part of Premium.',
 'Не получилось отправить файл.':'The file could not be sent.',
 'На каждый район приходит свой файл, отдельным сообщением в чат с ботом: из приложения Telegram сохранять не умеет. GeoJSON, Shapefile и GeoPackage открывают QGIS и планировщики перехода, KML понимает Google Earth, GPX читают навигаторы, CSV и WKT идут в таблицу и в базу. Выгружаются отмеченные районы, а если ничего не отмечено, то все действующие.':
   'Each area arrives as its own file, in a separate message in the chat with the bot, because Telegram cannot save files from inside the app. GeoJSON, Shapefile and GeoPackage open in QGIS and passage planners, KML in Google Earth, GPX in chartplotters, CSV and WKT go into a spreadsheet or a database. Marked areas are exported, or all warnings in force when nothing is marked.',
 'Отправил файлов:':'Files sent:','не ушло':'failed',
 'Файлы для JRC, TRANSAS и FURUNO не собираются: у этих форматов ECDIS нет открытого описания, и собранный наугад файл оборудование либо не примет, либо покажет район не там, где он есть. Пришли образец выгрузки с самой ECDIS, и формат добавим.':
   'Files for JRC, TRANSAS and FURUNO are not built: these ECDIS formats have no open specification, and a file assembled by guesswork will either be rejected or place the area in the wrong position. Send a sample export from the ECDIS itself and the format will be added.'
});
/* ---- Панель создателя бота: разделы, цифры, действия ---- */
Object.assign(DICT,{
 'Обзор':'Overview','Деньги':'Money','Связь':'Messages','Система':'System',
 'Сейчас':'Right now','Требует внимания':'Needs attention','Тридцать дней':'Thirty days',
 'на балансе бота':'on the bot balance','в месяц с текущих подписок':'a month from current subscriptions',
 'человек всего':'people in total','платят сейчас':'paying now','дошли до оплаты':'reached payment',
 'пришли за неделю':'joined this week','звёзд за 30 дней':'stars in 30 days',
 'ждём в месяц':'expected a month','платили хоть раз':'have paid at least once',
 'Новые люди':'New people',
 'Ничего не ждёт ответа: обращений нет, подписки в ближайшую неделю не кончаются.':
   'Nothing is waiting: no support threads, and no subscription ends this week.',
 'Обращения без ответа':'Support threads without a reply',
 'Подписка кончается на неделе':'Subscriptions ending this week',
 'Нажми на человека, чтобы открыть карточку: платежи, устройства, районы и переписка.':
   'Tap a person to open their card: payments, devices, areas and the message thread.',
 'К списку':'Back to the list','К обращениям':'Back to the threads',
 'звёзд заплатил':'stars paid','платежей':'payments','районов':'areas','устройств':'devices',
 'Пришёл':'Joined','Был в приложении':'Last opened the app','ни разу':'never',
 'Premium до':'Premium until','Судно':'Vessel','Написать':'Write','Отправить':'Send',
 'Ответить':'Reply','Отправлено.':'Sent.','Сначала напиши текст.':'Write the text first.',
 'Сообщение придёт в чат с ботом и ляжет в переписку поддержки':
   'The message goes to the chat with the bot and into the support thread',
 'Ответ придёт в чат с ботом':'The reply goes to the chat with the bot',
 'Переписка':'Messages','Устройства':'Devices','Он':'Them','Я':'Me',
 'Одно устройство на несколько аккаунтов бывает у сменщиков и курсантов. Пробный период получает только первый из них.':
   'One device with several accounts is normal for relief crew and cadets. Only the first account gets the trial.',
 'Кончается на неделе':'Ending this week','продлится':'renews','уйдёт':'leaves',
 'автопродление выключено':'auto-renewal off',
 'У кого автопродление выключено, подписка после этой даты просто закончится.':
   'Where auto-renewal is off, the subscription simply ends after that date.',
 'Это баланс бота в Telegram. Деньги за подписки приходят сюда.':
   'This is the bot balance in Telegram. Subscription money arrives here.',
 'Вывод идёт только через Fragment и только в TON. У Bot API такого метода нет, кнопкой из бота его не вызвать. Telegram держит каждую звезду 21 день на случай возврата покупателю.':
   'Withdrawal goes through Fragment only and in TON only. Bot API has no such method, no button in the bot can call it. Telegram holds every star for 21 days in case of a refund.',
 'Обращения':'Support threads','Обращений пока нет.':'No support threads yet.',
 'сообщений':'messages','сообщ.':'msg',
 'Написать всем в колокольчик':'Post to everyone in the bell',
 'Заголовок':'Title','Что изменилось в боте':'What changed in the bot',
 'Обновление':'Release','Новость':'News','Опубликовать':'Publish',
 'Нужен заголовок.':'A title is required.',
 'Опубликовано, запись ушла в колокольчик.':'Published, the entry went to the bell.',
 'Запись появится у всех в колокольчике и подсветится как непрочитанная. Сообщением в чат она не уходит и никого не разбудит на вахте.':
   'The entry appears in everyone’s bell and is marked unread. It is not sent as a chat message and will not wake anyone on watch.',
 'Что уже опубликовано':'Already published',
 'Бот':'Bot','Сборка':'Build','База':'Database','Сервер поднят':'Server up',
 'Тарифы':'Plans','включены':'on','выключены, всё открыто':'off, everything is open',
 'Цена подписки':'Subscription price','Пробный период':'Trial period',
 'Тестовая среда Telegram':'Telegram test environment','включена':'on',
 'Предупреждения в базе':'Warnings in the database','действующих':'in force',
 'районов отмечено':'areas marked','Источники':'Sources',
 'Опросить источники сейчас':'Poll the sources now','Опрашиваю…':'Polling…',
 'Обход занимает несколько секунд: бот стучится в каждую службу и показывает, сколько сообщений она отдала прямо сейчас.':
   'The round takes a few seconds: the bot knocks on every service and shows how many messages it returned just now.'
});
/* ---- Тренажёр ЦИВ: подписи новых экранов ---- */
Object.assign(DICT,{
 'Ролик':'Dial','крутить: выбор, нажать: ввод':'turn to select, push to enter',
 'разделы станции':'station menu','день / ночь / зелёный':'day / night / green',
 'вахтенный приём':'watch keeping',
 'Крути: выбор CH/TX/RX':'Turn: pick CH/TX/RX','Крути: меняется значение':'Turn: value changes',
 'BRILL ещё раз, чтобы сменить':'BRILL again to change',
 'СКАНИРОВАНИЕ…':'SCANNING…','SCAN начинает сканирование':'SCAN to start scanning',
 'CANCEL возвращает к работе':'CANCEL to resume','Раздел недоступен':'Section unavailable',
 'Удерживай 3 секунды':'Hold for 3 seconds','нет данных GPS':'no GPS data',
 'Ввод значения':'Editing the value','Выбор поля':'Choosing a field',
 'Крути ролик: вправо больше, влево меньше. Нажми ещё раз, чтобы зафиксировать.':
   'Turn the dial: clockwise up, counter-clockwise down. Push again to confirm.',
 'Крути ролик, чтобы перейти между CH, TX и RX. Нажатие открывает поле на изменение.':
   'Turn the dial to move between CH, TX and RX. Pushing opens the field for editing.',
 'Адрес подставлен':'Address filled in',
 'Позывной из книги ушёл в поле TO. Дальше выбери приоритет, режим связи и рабочую частоту.':
   'The station from the book went into TO. Now pick priority, comm mode and working frequency.',
 'Тип сообщения':'Message type',
 'Срочность (PAN PAN) и безопасность (SECURITE) на станции задаются полем PRIORITY, а не отдельным типом сообщения. Тип отвечает только за то, кому уходит вызов.':
   'Urgency (PAN PAN) and safety (SECURITE) are set by the PRIORITY field, not by a separate message type. The type only decides who the call goes to.',
 'Вахтенный приём':'Watch keeping',
 'Станция обязана непрерывно слушать частоты бедствия. SCAN проходит их по кругу: верхняя строка — 2187.5 кГц, ниже береговые вызывные ЦИВ. Приём вызова сканирование останавливает.':
   'The station must keep a continuous watch on the distress frequencies. SCAN steps through them: the top row is 2187.5 kHz, below are the coast DSC calling channels. An incoming call stops the scan.',
 '2182 кГц':'2182 kHz',
 'Симплексная частота бедствия и вызова на ПВ. После вызова ЦИВ на 2187.5 разговор идёт голосом именно здесь.':
   'The MF simplex distress and calling frequency. After a DSC call on 2187.5 the voice traffic goes here.',
 'Слева от экрана выбирается либо готовый канал (CH), либо частоты вручную (TX и RX). Ролик крутит то, что подсвечено.':
   'You either work on a ready channel (CH) or set the frequencies by hand (TX and RX). The dial changes whatever is highlighted.',
 'Яркость экрана':'Display brilliance',
 'День — полная яркость и контраст. Ночь — приглушённый красный, чтобы не сбивать адаптацию глаз на тёмном мостике. Зелёный — старый люминофорный режим, привычный по прежним станциям.':
   'Day is full brightness and contrast. Night is dimmed red so it does not spoil dark adaptation on the bridge. Green is the old phosphor look of earlier sets.',
 'Динамик выключен':'Speaker muted','Динамик включён':'Speaker on',
 'На вахте так делать нельзя: дежурный приём должен быть слышен.':
   'Never do this on watch: the distress watch must stay audible.',
 'Дежурный приём снова слышен.':'The distress watch is audible again.',
 'Канал выбран':'Channel selected','Особые сообщения':'Special messages',
 'Здесь живёт ретрансляция бедствия: её подают за другое судно, когда берег не подтвердил его тревогу. Свой вызов бедствия при этом не подаётся.':
   'This is where the distress relay lives: you send it for another vessel when the shore has not acknowledged its alert. You never send your own distress alert instead.',
 'Прочти обстановку и подай тот вызов, который положен: DISTRESS MSG — бедствие, OTHER DSC MSG — всё остальное. Срочность и безопасность задаются полем PRIORITY, а не отдельным типом сообщения.':
   'Read the situation and send the right call: DISTRESS MSG for distress, OTHER DSC MSG for everything else. Urgency and safety are set by the PRIORITY field, not by a separate message type.',
 'Не удалось получить счёт. Попробуй ещё раз.':'Could not get an invoice. Try again.',
 'Моё судно':'My Vessel','Судно':'Vessel','Документы':'Documents','Расчёты':'Calculations',
 'МОЁ СУДНО':'MY VESSEL','НА СВЯЗИ':'ONLINE','БЕЗ СВЯЗИ':'OFFLINE',
 'Сценарии':'Scenarios','Как отвечать':'Answer style','спросит':'will ask',
 'Мои порты':'My Ports','Справка':'Help','Поддержка':'Support','Уведомления':'Notifications',
 'Прочитано':'Mark read','Уведомлений пока нет.':'No notifications yet.',
 'Портов пока нет. Добавь первый порт захода выше.':'No ports yet. Add your first port of call above.',
 'Добавить порт захода':'Add a port of call','Весь переход':'Whole passage',
 'Проверить предупреждения по рейсу':'Check warnings along the voyage',
 'Убрать порт из рейса?':'Remove this port from the voyage?',
 'Нужны хотя бы два порта.':'At least two ports are needed.',
 'Погода в порту':'Port weather','порт не найден в справочнике':'port not in the directory',
 'расстояние не посчитано':'distance not calculated',
 'Список портов захода. По нему считается переход, проверяются предупреждения и берётся погода.':
   'Your ports of call. The passage, warnings and weather are all built from this list.',
 'Погода в портах захода':'Weather at your ports','Карта прямо здесь':'Map right here',
 'ветер':'wind','порывы':'gusts','волна':'wave','зыбь':'swell','видимость':'visibility',
 'давление':'pressure','баллов':'force','гПа':'hPa',
 'Погоду сейчас получить не удалось. Карты ниже работают отдельно.':
   'Could not fetch the forecast. The maps below work independently.',
 'Добавь порты захода в разделе «Моё судно» → «Мои порты» — по ним появится сводка погоды и карты.':
   'Add ports of call in My Vessel → My Ports — the forecast and maps will follow.',
 'Добавь порты захода в «Мои порты», и расстояние будет считаться до линии перехода.':
   'Add ports of call in My Ports and distances will be measured to your passage line.',
 'Написать в поддержку':'Contact support',
 'Переписка с создателем бота прямо здесь':'Talk to the bot author right here',
 'Частые вопросы по боту и его разделам':'Common questions about the bot',
 'Пишешь напрямую создателю бота. Ответ придёт сюда и сообщением в чат.':
   'You are writing to the bot author. The reply arrives here and as a chat message.',
 'Опиши, что не работает или чего не хватает. Прочту и отвечу.':
   'Describe what is broken or missing. I read every message.',
 'Опиши, что случилось…':'Describe what happened…','Ты':'You',
 'Поддержка работает только внутри Telegram. Открой приложение кнопкой в чате с ботом.':
   'Support works only inside Telegram. Open the app from the chat with the bot.',
 'Найти в справке…':'Search the help…',
 'Инструменты рейса':'Voyage tools','Свернуть инструменты рейса':'Hide voyage tools',
 'Скорость для ETA':'Speed for ETA','Погода по всем портам':'Weather for all ports',
 'Рекомендации по переходу':'Passage guidance','Скорость для расчёта ETA':'Speed used for ETA',
 'узлах':'knots','сут':'days','на весь переход':'for the whole passage',
 'В пути на':'Underway at','Планируемый приход':'Planned arrival',
 'Груз, агент, бункеровка':'Cargo, agent, bunkers',
 'Порты захода в этом контракте. Список подставляется в погоду, проверку рейса и в ответы ассистента.':
   'Ports of call for this contract. The list feeds weather, voyage checks and the assistant.',
 'Время в шапке':'Header clock','Всемирное координированное':'Coordinated universal time',
 'Как на телефоне':'Same as the phone','Судовое':'Ship time','Судовое, ':'Ship time, ',
 'Какое время показывать':'Which time to show','Пояс судового времени':'Ship time zone',
 'Переводится приказом по судну, а не телефоном':'Set by the master’s order, not by the phone',
 'судовое':'ship','телефон':'phone',
 'Полная карта со шкалой времени открывается кнопкой Windy выше':
   'Full map with the time bar: use the Windy button above',
 'Ничего не нашлось. Спроси в поддержке, отвечу и добавлю в справку.':
   'Nothing found. Ask support, I will answer and add it here.',
 'все данные подставлены':'all data filled in',
 'Библиотека сценариев не загрузилась, нужна связь с сервером.':
   'The scenario library did not load, a server connection is needed.',
 'Тренажёры':'Simulators','Погода':'Weather','Чем помочь?':'What can I help you with?',
 'Все запросы →':'All prompts →','Сводка с мостика':'Bridge Snapshot',
 'вахтенный':'Officer','Доброе утро':'Good morning','Добрый день':'Good afternoon',
 'Добрый вечер':'Good evening','Спокойной вахты':'Steady as she goes',
 'Помощник вахтенного на связи.':'Your digital assistance is ready.',
 'Данные из памяти устройства.':'Showing data stored on this device.',
 'карточка не заполнена':'vessel card is empty',
 'Безопасность маршрута':'Route Safety','Предупреждения и NAVAREA':'Warnings & NAVAREA',
 'Навигация':'Navigation','ETA · курс · расстояние':'ETA • Course • Distance',
 'Приём вахты':'Watchkeeping','Что проверить перед вахтой':'Watch checklist',
 'Ветер · волна · видимость':'Wind • Waves • Visibility',
 'Пункт назначения':'Destination','Маршрут':'Route',
 'Проложи переход в разделе «Маршрут»':'Plan a passage in the Route section',
 'Пройденную долю покажем, когда появится позиция':'Progress appears once a position is available',
 'В пути осталось':'Time to go','Нужны позиция и скорость':'Needs position and speed',
 'Навигационное предупреждение':'Navigation alert','Обстановка спокойная':'All clear',
 'Помощник на мостике':'Your bridge assistant',
 'Спроси про навигацию, ГМССБ, погоду…':'Ask about navigation, GMDSS, weather…',
 'Какие предупреждения влияют на мой маршрут?':'What warnings affect my route?',
 'Посчитай ETA до следующей точки маршрута':'Calculate ETA for my next waypoint',
 'Что проверить перед заступлением на вахту?':'What should I check before my next watch?',
 'Дай погоду и состояние моря сейчас':'Give me the current weather and sea state',
 'Звук тренажёра':'Simulator sound',
 'Посылка ЦИВ, подтверждение и сигнал тревоги':'DSC burst, acknowledgement and alarm tone'
});
/* ================= Полный перевод: справочники =================
   Дальше идёт то, что раньше оставалось по-русски при английском
   интерфейсе: своды сигналов, правила расхождения, справочник ЦИВ,
   тексты тренажёров EPIRB и SART, справка и настройки.
   Английский -- профессиональный морской: формулировки взяты в том виде,
   в каком они приняты в МСС-65, МППСС-72 и документах ИМО. */

/* --- Международный свод сигналов: однофлажные значения --- */
Object.assign(DICT,{
 'Международный свод сигналов, однофлажные значения':
   'International Code of Signals, single-letter meanings',
 'Гружу или выгружаю опасный груз':'I am taking in, or discharging, or carrying dangerous goods',
 'Да, утверждение':'Affirmative',
 'Держитесь в стороне, управляюсь с трудом':'Keep clear of me; I am manoeuvring with difficulty',
 'Изменяю свой курс вправо':'I am altering my course to starboard',
 'Я не управляюсь, держите связь':'I am disabled; communicate with me',
 'Мне нужен лоцман':'I require a pilot',
 'У меня на борту лоцман':'I have a pilot on board',
 'Изменяю свой курс влево':'I am altering my course to port',
 'У меня пожар, имею опасный груз':'I am on fire and have dangerous cargo on board',
 'Желаю установить связь с вами':'I wish to communicate with you',
 'Остановите судно немедленно':'You should stop your vessel instantly',
 'Моё судно остановлено, хода не имею':'My vessel is stopped and making no way through the water',
 'Нет, отрицание':'Negative',
 'Человек за бортом':'Man overboard',
 'Всем прибыть на борт, судно снимается':'All persons should report on board as the vessel is about to proceed to sea',
 'Моё судно незаражённое, прошу свободную практику':'My vessel is healthy and I request free pratique',
 'Принято':'Received',
 'Мои движители работают на задний ход':'I am operating astern propulsion',
 'Держитесь в стороне, произвожу парное траление':'Keep clear of me; I am engaged in pair trawling',
 'Вы идёте к опасности':'You are running into danger',
 'Мне требуется помощь':'I require assistance',
 'Мне требуется медицинская помощь':'I require medical assistance',
 'Приостановите ваши намерения':'Stop carrying out your intentions and watch for my signals',
 'Меня дрейфует на якоре':'I am dragging my anchor',
 'Мне требуется буксир':'I require a tug',
 'У меня спущен водолаз, держитесь в стороне':'I have a diver down; keep well clear at slow speed'
});

/* --- МППСС-72: краткий пересказ правил --- */
Object.assign(DICT,{
 'Ключевые правила расхождения, кратко своими словами':
   'Key COLREG rules, in brief',
 'Это краткий пересказ для быстрого напоминания. Юридическую силу имеет официальный текст конвенции.':
   'This is a short reminder only. The official text of the Convention is what carries legal force.',
 'Правило':'Rule','Наблюдение':'Look-out','Безопасная скорость':'Safe speed',
 'Риск столкновения':'Risk of collision','Действия по предупреждению':'Action to avoid collision',
 'Плавание в узкостях':'Narrow channels','Системы разделения движения':'Traffic separation schemes',
 'Парусные суда':'Sailing vessels','Сближение прямо':'Head-on situation',
 'Пересечение курсов':'Crossing situation','Действия уступающего':'Action by give-way vessel',
 'Действия судна, которому уступают':'Action by stand-on vessel',
 'Взаимные обязанности':'Responsibilities between vessels',
 'Звуковые сигналы в тумане':'Sound signals in restricted visibility',
 'Постоянно вести надлежащее наблюдение зрением, слухом и всеми доступными средствами, чтобы полностью оценить обстановку и риск столкновения.':
   'Maintain a proper look-out by sight and hearing as well as by all available means, so as to make a full appraisal of the situation and of the risk of collision.',
 'Идти с такой скоростью, чтобы можно было принять эффективные меры и остановиться в пределах расстояния, соответствующего обстоятельствам. Учитывать видимость, плотность движения, маневренность, состояние моря, осадку и ограничения радара.':
   'Proceed at a speed at which effective action can be taken and the vessel stopped within a distance appropriate to the circumstances. Take account of visibility, traffic density, manoeuvrability, state of sea, draught and the limitations of radar.',
 'Использовать все средства для определения риска. Считать, что риск есть, если пеленг на приближающееся судно заметно не меняется. Не делать выводов по неполной информации, особенно по скудным радарным данным.':
   'Use all available means to determine risk. Deem risk to exist if the compass bearing of an approaching vessel does not appreciably change. Do not draw conclusions from scanty information, especially scanty radar information.',
 'Предпринять заблаговременные и решительные действия для расхождения на безопасном расстоянии.':
   'Take action early and positively so as to pass at a safe distance.',
 'Действия должны быть решительными, своевременными и заметными для другого судна. Изменение курса предпочтительнее изменения скорости, если места достаточно. Проверять эффективность до полного расхождения.':
   'Action shall be positive, made in ample time and readily apparent to the other vessel. An alteration of course alone is preferable if there is sea room. Check the effect until the other vessel is finally past and clear.',
 'Держаться внешней стороны фарватера по правому борту насколько это безопасно. Судно менее 20 м, парусное и занятое ловом рыбы не должны затруднять движение судна, которое может следовать только в пределах узкости.':
   'Keep as near to the outer limit of the channel on the starboard side as is safe and practicable. A vessel under 20 m, a sailing vessel and a vessel engaged in fishing shall not impede a vessel which can safely navigate only within a narrow channel.',
 'Следовать в полосе в принятом направлении, держаться в стороне от линии разделения, входить и выходить на конечных участках или под малым углом. Пересекать по возможности под прямым углом к направлению потока.':
   'Proceed in the appropriate traffic lane in the general direction of flow, keep clear of the separation line, and join or leave at the termination or at a small angle. Cross, if obliged to do so, on a heading as nearly as practicable at right angles to the flow.',
 'При разных галсах уступает судно на левом галсе. При одинаковых галсах уступает наветренное. Если галс другого не определён, уступать в любом случае.':
   'When each has the wind on a different side, the vessel with the wind on the port side keeps out of the way. With the wind on the same side, the windward vessel keeps out of the way. If in doubt as to the other’s tack, keep out of the way.',
 'При встрече на противоположных курсах оба изменяют курс вправо, чтобы разойтись левыми бортами. При сомнении считать, что такая ситуация есть, и действовать соответственно.':
   'When meeting on reciprocal courses, each shall alter course to starboard so as to pass port to port. If in doubt, assume such a situation exists and act accordingly.',
 'Уступает то судно, которое имеет другое справа. Избегать пересечения курса впереди него.':
   'The vessel which has the other on her own starboard side keeps out of the way, and shall avoid crossing ahead of the other vessel.',
 'Обгоняющий уступает дорогу обгоняемому. Обгон это подход с направления более 22.5° позади траверза. Последующее изменение пеленга не освобождает от обязанности держаться в стороне до полного расхождения.':
   'The overtaking vessel keeps out of the way of the vessel being overtaken. Overtaking means coming up from more than 22.5° abaft the beam. Any subsequent alteration of bearing does not relieve her of the duty to keep clear until finally past and clear.',
 'Сохранять курс и скорость. Может действовать самостоятельно, когда становится ясно, что уступающий не предпринимает должных мер. При невозможности избежать столкновения одними действиями уступающего обязано действовать.':
   'Keep course and speed. She may take action when it becomes apparent that the give-way vessel is not taking appropriate action, and must act when collision cannot be avoided by the give-way vessel alone.',
 'Порядок уступания: судно с механическим двигателем уступает парусному, занятому ловом рыбы, ограниченному в маневре и лишённому возможности управляться.':
   'A power-driven vessel keeps out of the way of a sailing vessel, a vessel engaged in fishing, a vessel restricted in her ability to manoeuvre and a vessel not under command.',
 'Идти безопасной скоростью с готовой к немедленному манёвру машиной. Избегать поворота влево на судно впереди траверза, кроме случая обгона, и поворота на судно на траверзе или позади.':
   'Proceed at a safe speed with engines ready for immediate manoeuvre. Avoid an alteration to port for a vessel forward of the beam, other than for a vessel being overtaken, and an alteration towards a vessel abeam or abaft the beam.',
 'Судно на ходу с механическим двигателем: один продолжительный не реже чем каждые 2 минуты. На ходу без хода: два продолжительных. Ограниченное в маневре, парусное, на буксире: один продолжительный и два коротких.':
   'A power-driven vessel making way: one prolonged blast at intervals of not more than 2 minutes. Under way but stopped: two prolonged blasts. Restricted in ability to manoeuvre, sailing or towing: one prolonged followed by two short blasts.'
});
/* --- ЦИВ: виды вызовов, характер бедствия, пояснения --- */
Object.assign(DICT,{
 'Вызов бедствия':'Distress Alert','Ретрансляция бедствия':'Distress Relay',
 'Срочность (PAN PAN)':'Urgency Call (PAN PAN)','Безопасность (SECURITE)':'Safety Call (SECURITE)',
 'Индивидуальный вызов':'Individual Call','Вызов всем судам':'All Ships Call',
 'Групповой вызов':'Group Call','Тестовый вызов':'Test Call',
 'Запрос позиции':'Position Request','Опрос присутствия':'Polling',
 'Пожар, взрыв':'Fire, explosion','Поступление воды':'Flooding','Столкновение':'Collision',
 'Посадка на мель':'Grounding','Крен, опасность опрокидывания':'Listing, danger of capsizing',
 'Затопление':'Sinking','Потеря хода, дрейф':'Disabled and adrift',
 'Бедствие без уточнения':'Undesignated distress','Оставление судна':'Abandoning ship',
 'Пиратское нападение':'Piracy / armed robbery',
 'Цифровой избирательный вызов':'Digital Selective Calling',
 'Бедствие и безопасность':'Distress and safety',
 'Бедствие, срочность, безопасность':'Distress, urgency and safety',
 'Голосовая связь, слуховая вахта':'Radiotelephony, listening watch',
 'Мостик-мостик':'Bridge-to-bridge','Безопасность мореплавания':'Safety of navigation',
 'Связь при поисково-спасательных работах':'Search and rescue communications',
 'Английский язык, стандартные передачи':'English language, standard broadcasts',
 'Местный язык':'Local language','Международный':'International','Национальный':'National',
 'Тропический':'Tropical','Дополнительный диапазон':'Additional band',
 'Голос MF':'MF radiotelephony','Спутниковый радиобуй':'Satellite EPIRB',
 'Приводной':'Homing','Ближний привод':'Local homing','Радар':'Radar',
 'Подаётся только при непосредственной опасности для судна или людей. Станция сама подставляет позицию от приёмника и передаёт по всем диапазонам. Ждём подтверждения от берегового центра, не от судов.':
   'Sent only when the vessel or persons are in grave and imminent danger. The set inserts the position from the receiver and transmits on all bands. Acknowledgement is expected from the coast station, not from other ships.',
 'Передаём за другое судно: приняли сигнал бедствия, а берег его не подтвердил. Свой сигнал бедствия при этом не подаём -- иначе спасатели будут искать нас, а не терпящего бедствие.':
   'Sent on behalf of another vessel: her distress alert was received but the shore has not acknowledged it. Never send your own distress alert instead, or the rescue services will look for you rather than for the casualty.',
 'Серьёзная ситуация, но непосредственной опасности гибели нет: потеря хода в стороне от судоходства, тяжёлый больной на борту.':
   'A serious situation with no grave and imminent danger: disabled clear of traffic, or a seriously ill person on board.',
 'Навигационные и метеорологические предупреждения: плавающий объект, неработающий буй, шторм.':
   'Navigational and meteorological warnings: a floating object, an unlit buoy, a gale.',
 'Вызов конкретного судна или береговой станции по её MMSI. Указываем рабочую частоту, на которой будем говорить.':
   'A call to a particular ship or coast station by MMSI. State the working frequency on which the traffic will follow.',
 'Всем, кто в зоне слышимости. В обычной обстановке применяется только с категорией срочности или безопасности.':
   'To all stations within range. In normal traffic it is used only with the urgency or safety category.',
 'Судам одной группы: флот компании, суда в конвое. Групповой MMSI начинается с нуля и заранее прописан в станции.':
   'To vessels of one group: a company fleet or ships in convoy. A group MMSI begins with a zero and is pre-programmed in the set.',
 'Проверка работоспособности ЦИВ на ВЧ и ПВ. Направляется береговой станции, она отвечает подтверждением. На 2187.5 кГц проверка делается именно тестовым вызовом, а не вызовом бедствия.':
   'A check of DSC operation on MF and HF. Addressed to a coast station, which answers with an acknowledgement. On 2187.5 kHz the daily test is made with a test call, never with a distress alert.',
 'Запрос координат другого судна. Оно может ответить автоматически или отклонить запрос -- это его право.':
   'A request for another vessel’s position. She may answer automatically or refuse the request, which is her right.',
 'Проверка, находится ли станция в зоне связи. Ответ приходит автоматически, без участия вахтенного на той стороне.':
   'A check that a station is within range. The reply is automatic, with no action by the watchkeeper at the other end.',
 'Подтверждение (ACK) означает, что вызов принят. При бедствии подтверждать имеет право береговой центр -- судно подтверждает только если берег молчит и судно способно помочь.':
   'An acknowledgement means the call has been received. A distress alert is acknowledged by the coast station; a ship acknowledges only if the shore stays silent and she is able to assist.',
 'Диапазон выбирают по дальности и времени суток. Ночью проходят низкие частоты (2, 4 МГц), днём высокие (12, 16 МГц). 8 МГц работает почти всегда -- с него и начинают.':
   'The band is chosen by range and time of day. Lower frequencies (2 and 4 MHz) propagate at night, higher ones (12 and 16 MHz) by day. 8 MHz works almost always and is the usual starting point.',
 'После вызова ЦИВ переходим на парную радиотелефонную частоту того же диапазона и говорим уже голосом. ЦИВ -- только для того, чтобы привлечь внимание.':
   'After a DSC call, shift to the paired radiotelephone frequency of the same band and pass the traffic by voice. DSC only serves to attract attention.',
 'Кнопка бедствия закрыта крышкой и требует удержания около пяти секунд -- защита от случайного нажатия. Если подал по ошибке, не выключай станцию: сообщи голосом на 2182 кГц, что тревога ложная, и отмени её.':
   'The distress button is under a cover and must be held for about five seconds, to guard against accidental operation. If sent in error, do not switch the set off: cancel the alert and announce by voice on 2182 kHz that it was false.',
 'MMSI из девяти цифр. У судна первые три -- код страны, у береговой станции первые две цифры нули, у группы -- один ноль в начале.':
   'An MMSI has nine digits. A ship station begins with the three-digit country code, a coast station with two zeros, and a group with a single leading zero.',
 'Тестовый вызов не тревожит спасателей и не поднимает никого по тревоге. Именно им проверяют ЦИВ, как требует ежедневная проверка по ГМССБ.':
   'A test call raises no alarm and alerts nobody. It is the means of checking DSC required by the daily GMDSS test.',
 'Средние волны. Дальность порядка 150 миль днём, ночью больше.':
   'Medium frequency. Range of the order of 150 NM by day, more at night.',
 'Ночью и на рассвете, дальность до 300 миль.':'At night and around dawn, range up to 300 NM.',
 'Круглосуточно, средние дистанции.':'Round the clock, medium distances.',
 'Самый универсальный диапазон, работает днём и ночью.':
   'The most versatile band, usable by day and by night.',
 'День, большие дистанции.':'Daytime, long distances.',
 'День, максимальная дальность.':'Daytime, maximum range.',
 'Тренажёр. Ничего в эфир не уходит.':'Simulator. Nothing is transmitted.',
 'Тренажёр. Ничего в эфир не уходит. Перед экзаменом и работой на судне сверяйся с ALRS Volume 5 и инструкцией своей станции.':
   'Simulator. Nothing is transmitted. Before an examination and before working on board, check against ALRS Volume 5 and your own set’s manual.'
});
/* --- Задания режима экзамена по ЦИВ --- */
Object.assign(DICT,{
 'В машинном отделении пожар, экипаж не справляется, судно теряет ход. Твои действия по ЦИВ.':
   'Fire in the engine room, the crew cannot contain it and the vessel is losing propulsion. What do you send by DSC?',
 'Непосредственная опасность для судна и людей -- это вызов бедствия с указанием характера «пожар, взрыв».':
   'Grave and imminent danger to the vessel and to persons: a distress alert with the nature “fire, explosion”.',
 'Судно село на мель, поступления воды нет, крена нет, опасности для людей нет, но сняться самостоятельно не можешь.':
   'The vessel is aground, there is no flooding, no list and no danger to persons, but you cannot refloat unaided.',
 'Прямой угрозы гибели нет, значит бедствие подавать рано. Это срочность (PAN PAN). Если начнёт поступать вода или появится крен -- переходим на бедствие.':
   'There is no immediate danger of loss, so a distress alert is premature. This is urgency (PAN PAN). If flooding starts or a list develops, upgrade to distress.',
 'Приняли вызов бедствия с соседнего судна на 8414.5 кГц. Прошло пять минут, береговая станция не подтвердила приём.':
   'A distress alert from a nearby vessel was received on 8414.5 kHz. Five minutes have passed and no coast station has acknowledged it.',
 'Передаём ретрансляцию бедствия. Свой вызов бедствия подавать нельзя -- у нас самих ничего не случилось, и спасатели пойдут не туда.':
   'Send a distress relay. Never send your own distress alert: nothing has happened to you, and the rescue services would be sent to the wrong ship.',
 'Обнаружили в море полузатопленный контейнер, представляющий опасность для судоходства.':
   'A partly submerged container dangerous to navigation has been sighted at sea.',
 'Навигационная опасность для других судов -- категория безопасности (SECURITE), обычно вызовом всем судам.':
   'A navigational hazard to other vessels: the safety category (SECURITE), normally as an all ships call.',
 'Нужно проверить работу ЦИВ на ПВ, как того требует ежедневная проверка ГМССБ.':
   'DSC operation on MF has to be checked, as required by the daily GMDSS test.',
 'Для этого есть тестовый вызов береговой станции. Вызов бедствия для проверки не применяют ни при каких обстоятельствах.':
   'That is what a test call to a coast station is for. A distress alert is never used for testing under any circumstances.',
 'Человек упал за борт, судно развернулось на циркуляции, идёт поиск.':
   'A man has fallen overboard, the vessel has turned and the search is under way.',
 'Жизни человека угрожает непосредственная опасность -- вызов бедствия с характером «человек за бортом».':
   'A person’s life is in grave and imminent danger: a distress alert with the nature “man overboard”.',
 'Нужно связаться с агентом через береговую станцию Lyngby Radio для передачи заявки на снабжение.':
   'You need to reach the agent through Lyngby Radio to pass a stores requisition.',
 'Обычная деловая связь -- индивидуальный вызов береговой станции с указанием рабочей частоты.':
   'Ordinary business traffic: an individual call to the coast station, stating the working frequency.',
 'На борту тяжелобольной, нужна консультация врача, но судно на ходу и опасности нет.':
   'A seriously ill person is on board and medical advice is required, but the vessel is under way and in no danger.',
 'Медицинская консультация без угрозы гибели судна -- срочность (PAN PAN), обычно с пометкой MEDICO.':
   'Medical advice with no danger of loss: urgency (PAN PAN), normally marked MEDICO.',
 'Судно атаковано вооружёнными лицами при подходе к якорной стоянке.':
   'The vessel is under attack by armed persons on approach to the anchorage.',
 'Пиратское нападение -- отдельный вид бедствия по ITU-R M.493, подаётся вызов бедствия.':
   'Piracy is a distinct nature of distress under ITU-R M.493, and a distress alert is sent.',
 'Нужно узнать, где сейчас находится судно компании, идущее тем же районом.':
   'You need the present position of a company vessel transiting the same area.',
 'Запрос позиции. Судно вправе отклонить запрос, это нормально.':
   'A position request. The other vessel may decline it, which is entirely normal.'
});

/* --- EPIRB и SART: тексты тренажёров --- */
Object.assign(DICT,{
 'АРБ (EPIRB)':'EPIRB','Radar SART · X-диапазон':'Radar SART · X-band',
 'Куда уходит сигнал':'Where the signal goes','Порядок самопроверки':'Self-test procedure',
 'Вид с проходящего судна':'View from a passing vessel',
 'Отклик на 3 см радар (X-band)':'Response on a 3 cm (X-band) radar',
 'Маяк в дежурном режиме':'Beacon on standby','Сигнал не излучается':'Nothing is radiated',
 'Посылка на 406 МГц':'406 MHz burst','Принято спутником':'Received by satellite',
 'Ретрансляция на MEOLUT':'Relayed to a MEOLUT','Передано в MCC':'Passed to the MCC',
 'Тревога у спасателей':'Alert at the rescue centre',
 'Маяк передаёт короткими посылками примерно раз в 50 секунд':
   'The beacon transmits short bursts about every 50 seconds',
 'MEOSAR: спутники GPS, Galileo, ГЛОНАСС и BeiDou несут поисковые ретрансляторы':
   'MEOSAR: GPS, Galileo, GLONASS and BeiDou satellites carry SAR repeaters',
 'Наземная станция измеряет частоту и время посылок, вычисляет место':
   'The ground station measures burst frequency and timing and computes the position',
 'Координационный центр системы сверяет данные и опознаёт маяк по номеру':
   'The mission control centre correlates the data and identifies the beacon by its number',
 'Норматив системы: тревога доходит до спасательного центра в пределах 15 минут':
   'System requirement: the alert reaches the rescue centre within 15 minutes',
 'При самопроверке сигнал в эту цепочку не уходит: маяк лишь проверяет собственные узлы. Схема показана, чтобы было видно, что происходит при настоящем срабатывании.':
   'During a self-test nothing enters this chain: the beacon only checks its own circuits. The diagram is shown so that the real activation path is clear.',
 'Идёт передача тестового сигнала: 121.5 МГц, AIS и 406 МГц. Спасательные службы его не получают':
   'A test signal is being transmitted on 121.5 MHz, AIS and 406 MHz. The rescue services do not receive it',
 'БОЕВОЙ РЕЖИМ. На настоящем приборе сигнал уже принят спутниками COSPAS-SARSAT':
   'LIVE MODE. On a real beacon the signal has already been received by the COSPAS-SARSAT satellites',
 'БОЕВОЙ РЕЖИМ. Отвечает на все радары в зоне видимости как сигнал бедствия':
   'LIVE MODE. Responds to every radar within range as a distress signal',
 'Поиск спутниковой позиции. Зелёный индикатор загорится, когда позиция определена':
   'Acquiring a satellite position. The green light comes on once the position is fixed',
 'Один проблеск — самопроверка пройдена. Если индикатор продолжает мигать, смотри код ошибки в руководстве':
   'A single flash means the self-test has passed. If the light keeps flashing, look up the fault code in the manual',
 'Проблеск индикатора по итогу проверки':'Indicator flash on completion of the test',
 'Переключатель в положении OFF, транспондер на кронштейне':
   'Switch at OFF, transponder in its bracket',
 'Прибор в дежурном режиме, на кронштейне':'Unit on standby, in its bracket',
 'Режим TEST включён, транспондер прогревается':'TEST selected, the transponder is warming up',
 'Отвечает на облучение радаром. Смотри отклик на экране X-диапазонного радара ниже':
   'Responding to radar interrogation. See the reply on the X-band radar picture below',
 'Тест пройден. Не держи в режиме TEST дольше пяти минут: расходует батарею и мешает чужим радарам':
   'Test passed. Do not leave it in TEST for more than five minutes: it drains the battery and interferes with other radars',
 'Удерживай кнопку TEST…':'Hold the TEST button…',
 'Переведи переключатель в TEST или ON, чтобы увидеть, как отметка появляется на чужом радаре.':
   'Select TEST or ON to see how the mark appears on another vessel’s radar.',
 'Переведи переключатель на приборе выше в положение TEST.':
   'Set the switch on the unit above to TEST.',
 'Это боевое включение. На настоящем приборе SART начнёт отвечать на радары как сигнал бедствия. Продолжить в тренажёре?':
   'This is live activation. On a real unit the SART would begin replying to radars as a distress signal. Continue in the simulator?',
 'Это боевое включение. На настоящем приборе оно поднимает спасательные службы. Продолжить в тренажёре?':
   'This is live activation. On a real beacon it would alert the rescue services. Continue in the simulator?',
 'плот · 4 мили':'liferaft · 4 NM','Круг радиусом':'Circle of radius',
 'Линия / полоса':'Line / band','Район':'Area','Точность':'Accuracy'
});
/* --- Справка: вопросы и ответы --- */
Object.assign(DICT,{
 'С чего начать':'Getting started','Предупреждения и карта':'Warnings and chart',
 'Тренажёры и ГМССБ':'Simulators and GMDSS','Подписка':'Subscription',
 'Данные и приватность':'Data and privacy','Если что-то не работает':'If something is wrong',
 'Что вообще умеет WatchKeeper?':'What does WatchKeeper actually do?',
 'Три вещи. Показывает действующие предупреждения NAVAREA и береговые по твоим районам и маршруту. Считает то, что считает вахтенный: запас под килём, проседание, расхождение с целью, ETA, якорную стоянку. И отвечает на вопросы обычными словами через Ask AI, сам подставляя данные судна, позицию и погоду.':
   'Three things. It shows the NAVAREA and coastal warnings in force for your areas and route. It works out what an officer of the watch works out: under-keel clearance, squat, CPA and TCPA, ETA, anchoring. And it answers questions in plain words through Ask AI, filling in your vessel’s data, position and weather itself.',
 'С чего начать после установки?':'What should I do first?',
 'Заполни карточку судна в разделе «Моё судно» — осадка, скорость и габариты потом подставляются в расчёты сами. Отметь звёздочкой свои районы NAVAREA. Добавь порты захода в «Мои порты». Всё остальное заработает само.':
   'Fill in the vessel card under My Vessel — draught, speed and dimensions are then inserted into the calculations automatically. Star your NAVAREA areas. Add your ports of call under My Ports. Everything else follows on its own.',
 'Работает ли приложение без связи?':'Does the app work offline?',
 'Расчёты, справочники и тренажёры — да, полностью. Предупреждения, станции и зоны сохраняются на устройстве и показываются последними сохранёнными. Погода, ассистент и проверка маршрута требуют связи: они ходят на сервер.':
   'Calculations, reference data and simulators — yes, entirely. Warnings, stations and zones are cached on the device and shown as last saved. Weather, the assistant and the route check need a connection: they query the server.',
 'Заменяет ли бот приём MSI по ГМССБ?':'Does the bot replace receiving MSI by GMDSS?',
 'Нет и не может. Официальный источник — NAVTEX, приёмник Inmarsat SafetyNET и штатное оборудование ГМССБ. Бот — вспомогательный инструмент: он помогает не пропустить и разобраться, но решение принимает судоводитель по официальным пособиям.':
   'No, and it cannot. The official sources are NAVTEX, the Inmarsat SafetyNET receiver and the ship’s GMDSS equipment. The bot is an aid: it helps you not to miss things and to understand them, but the decision rests with the navigator using official publications.',
 'Откуда берутся предупреждения?':'Where do the warnings come from?',
 'Из открытых источников координаторов районов: NGA (США), UKHO (Великобритания), гидрографические службы Перу и Испании. Если подключён Sealagom, данные идут оттуда сразу по всем 21 району.':
   'From the open sources of the area co-ordinators: NGA (USA), UKHO (United Kingdom) and the hydrographic services of Peru and Spain. If Sealagom is connected, the data comes from there for all 21 areas at once.',
 'Как часто обновляются данные?':'How often is the data refreshed?',
 'Бот опрашивает источники каждые 30 минут (настраивается). Время последнего обновления по каждому району видно в списке районов.':
   'The bot polls the sources every 30 minutes (configurable). The time of the last update for each area is shown in the area list.',
 'Почему у предупреждения нет точки на карте?':'Why has a warning no position on the chart?',
 'Координаты разбираются из текста сообщения. Если в тексте их нет или они записаны непривычным способом, точка не появится. Текст при этом доступен целиком.':
   'Positions are parsed from the text of the message. If there are none, or they are written in an unusual way, no mark appears. The full text is still available.',
 'Что значит «точная геометрия»?':'What does “exact geometry” mean?',
 'Метка на карточке: район пришёл от источника готовой фигурой, а не разобран нами из текста. Такой контур точнее.':
   'A label on the card: the area arrived from the source as a ready shape rather than being parsed from the text. Such an outline is more accurate.',
 'Как следить только за своими районами?':'How do I follow only my own areas?',
 'Отметь районы звёздочкой. Они попадут в избранное на главной, и по ним будут приходить уведомления о новых предупреждениях.':
   'Star the areas. They go to your favourites and you will be notified of new warnings in them.',
 'Откуда берутся числа в расчётах?':'Where do the figures in the calculations come from?',
 'Часть подставляется из карточки судна: осадка, скорость, коэффициент полноты, длина, надводный габарит. Такие поля помечены словом «само». Остальное вводится руками.':
   'Some are taken from the vessel card: draught, speed, block coefficient, length, air draught. Such fields are marked “auto”. The rest you enter yourself.',
 'Можно ли доверять расчётам?':'Can the calculations be relied on?',
 'Это справочные расчёты по общепринятым формулам. Они не заменяют судовую документацию, таблицы манёвренных характеристик и информацию об остойчивости. Решение принимает судоводитель.':
   'They are advisory calculations using accepted formulae. They do not replace the ship’s documentation, the manoeuvring data or the stability information. The decision rests with the navigator.',
 'Почему проседание считается по-разному?':'Why is squat calculated differently?',
 'Формулы для открытой воды и для стеснённого фарватера дают разный результат — во втором случае проседание заметно больше. Выбор акватории есть прямо в расчёте.':
   'The formulae for open water and for a confined channel give different results — in a channel the squat is markedly greater. The choice of water is in the calculation itself.',
 'Расчёты платные?':'Are the calculations paid for?',
 'Нет. Всё, от чего зависит безопасность — запас под килём, проседание, расхождение, точка перекладки, якорь, габарит под мостом — бесплатно навсегда.':
   'No. Everything that safety depends on — under-keel clearance, squat, collision avoidance, wheel-over point, anchoring, air draught — is free for good.',
 'Чем ассистент отличается от обычного чат-бота?':'How is the assistant different from an ordinary chatbot?',
 'Он умеет брать данные сам. Спросишь про погоду на переходе — сам проложит маршрут через проливы, разложит время прихода по точкам и возьмёт прогноз именно на эти часы. Спросишь про предупреждения — сам отберёт те, что задевают твой маршрут.':
   'It fetches data itself. Ask about the weather on passage and it lays off the route through the straits, works out the time of arrival at each point and takes the forecast for exactly those hours. Ask about warnings and it selects those that affect your route.',
 'Что такое «Сценарии»?':'What are “Scenarios”?',
 'Готовые запросы по разделам: навигация, ECDIS, МППСС, погода, ГМССБ, вахта, груз, аварийные случаи. В шаблон уже подставлены твои данные — видно, что подставилось, а что ассистент спросит.':
   'Ready-made prompts by subject: navigation, ECDIS, COLREG, weather, GMDSS, watchkeeping, cargo, emergencies. Your data is already inserted into the template — you can see what was filled in and what the assistant will ask for.',
 'Что такое режимы ответа?':'What are the answer modes?',
 'Форма, в которой придёт ответ: коротко, для вахты, чек-листом, расчётом с проверкой, аварийным порядком действий, брифингом, записью в журнал, радиофразеологией. Выбирается кнопкой слева над перепиской.':
   'The form the answer takes: brief, for the watch, as a checklist, as a calculation with a sanity check, as emergency actions, as a briefing, as a log entry, or as radio phraseology. Chosen with the button above the conversation.',
 'Ассистент может ошибаться?':'Can the assistant be wrong?',
 'Да, как любая языковая модель. Он не выдумывает живые данные — погода и предупреждения приходят из источников, — но формулировки правил и выводы стоит проверять по МППСС, конвенциям и судовым инструкциям.':
   'Yes, like any language model. It does not invent live data — weather and warnings come from the sources — but wordings of rules and conclusions should be checked against COLREG, the conventions and the ship’s instructions.',
 'Есть ли лимит вопросов?':'Is there a limit on questions?',
 'На бесплатном тарифе — пять вопросов в сутки. На Premium ограничения нет.':
   'Five questions a day on the free plan. No limit on Premium.',
 'Тренажёр ЦИВ выходит в эфир?':'Does the DSC simulator transmit?',
 'Нет. Ничего не передаётся. Все подтверждения, задержки и ответы береговых станций имитируются внутри приложения.':
   'No. Nothing is transmitted. All acknowledgements, delays and coast station replies are simulated inside the app.',
 'Как пользоваться роликом на станции?':'How do I use the dial on the set?',
 'Поворот выбирает поле или пункт меню, нажатие открывает его на изменение. На дежурном экране ролик переключается между CH, TX и RX; нажал — крутишь значение.':
   'Turning selects a field or a menu item, pushing opens it for editing. On the standby screen the dial moves between CH, TX and RX; push it and you turn the value.',
 'Что делает кнопка BRILL?':'What does the BRILL key do?',
 'Переключает яркость и контраст экрана: день, ночь (приглушённый красный, чтобы не сбивать адаптацию глаз) и зелёный люминофорный режим.':
   'It switches display brilliance and contrast: day, night (dimmed red so as not to spoil dark adaptation) and the green phosphor mode.',
 'Зачем нужен режим экзамена?':'What is the exam mode for?',
 'Даёт обстановку, а ты выбираешь, каким вызовом отвечать. После ответа показывает разбор: почему бедствие, а не срочность, и наоборот.':
   'It gives you a situation and you choose which call to send. After your answer it explains why distress rather than urgency, or the other way round.',
 'Проверки EPIRB и SART — что записывается?':'EPIRB and SART tests — what is recorded?',
 'Отметки чек-листа, результат самопроверки и дата замены батареи. История хранится в приложении, её можно очистить.':
   'The checklist ticks, the self-test result and the battery expiry date. The history is kept in the app and can be cleared.',
 'Что входит в Premium?':'What does Premium include?',
 'Неограниченное число районов, береговые предупреждения, проверка маршрута, карточка судна, чек-листы и сертификаты, история за 30 дней, вопросы к ассистенту без лимита, расширенные расчёты.':
   'Unlimited areas, coastal warnings, the route check, the vessel card, checklists and certificates, 30 days of history, unlimited questions to the assistant and the advanced calculations.',
 'Как оплатить?':'How do I pay?',
 'Звёздами Telegram прямо в приложении: «Моё судно» → «Что входит в Premium» → «Оформить». Откроется окно оплаты Telegram. Карт и переводов не нужно.':
   'With Telegram Stars inside the app: My Vessel → What Premium includes → Subscribe. The Telegram payment window opens. No cards and no transfers are needed.',
 'Что такое звёзды Telegram?':'What are Telegram Stars?',
 'Внутренняя валюта Telegram. Покупаются в самом приложении Telegram и тратятся на цифровые товары и услуги. Подписка продлевается сама каждые 30 дней.':
   'Telegram’s internal currency. They are bought within Telegram itself and spent on digital goods and services. The subscription renews itself every 30 days.',
 'Как отменить подписку?':'How do I cancel the subscription?',
 '«Моё судно» → «Настройки» → «Доступ» → выключить «Автопродление». Оплаченный период доработает до конца. То же самое делает команда /cancel_subscription в чате с ботом.':
   '“My Vessel” → “Settings” → “Access” → turn off “Auto-renewal”. The period already paid for runs to its end. The /cancel_subscription command in the chat with the bot does the same.',
 'Что остаётся бесплатным?':'What stays free?',
 'Два района с уведомлениями, карта всех действующих предупреждений, все расчёты безопасности, справочники, станции ГМССБ, тренажёры и пять вопросов ассистенту в сутки.':
   'Two areas with notifications, the chart of all warnings in force, every safety calculation, the reference sections, the GMDSS stations, the simulators and five questions a day to the assistant.',
 'Что бот знает обо мне?':'What does the bot know about me?',
 'Идентификатор Telegram, отмеченные районы, карточку судна, сертификаты и чек-листы, порты рейса — то, что ты сам ввёл. Настройки интерфейса и последние расчёты хранятся только на устройстве.':
   'Your Telegram identifier, the areas you starred, the vessel card, certificates and checklists, and the ports of the voyage — what you entered yourself. Interface settings and recent calculations are kept on the device only.',
 'Передаётся ли моя позиция?':'Is my position sent anywhere?',
 'Только когда ты сам её запросил кнопкой или включил слежение, и только на время работы приложения. Она нужна для погоды, расстояний и экрана станции. Геопозицию можно выключить совсем в настройках.':
   'Only when you request it with the button or switch tracking on, and only while the app is running. It is needed for weather, distances and the radio display. Positioning can be switched off entirely in the settings.',
 'Как удалить свои данные?':'How do I delete my data?',
 'Напиши в поддержку из настроек — удалю карточку судна, сертификаты и порты. Локальные данные стираются кнопкой «Очистить сохранённые данные».':
   'Write to support from the settings and I will delete the vessel card, certificates and ports. Local data is cleared with the “Clear stored data” button.',
 'Приложение открылось пустым или без данных':'The app opened empty or without data',
 'Скорее всего нет связи с сервером — вверху появится полоса «Нет связи». Расчёты и справочники продолжат работать. Проверь интернет и потяни экран вниз.':
   'Most likely there is no connection to the server — an “Offline” bar appears at the top. Calculations and reference sections keep working. Check the internet and pull the screen down.',
 'Не приходят уведомления о предупреждениях':'Warning notifications do not arrive',
 'Проверь, отмечены ли районы звёздочкой и включён ли переключатель в настройках. Уведомления приходят сообщением от бота в чат.':
   'Check that the areas are starred and the switch in the settings is on. Notifications arrive as a message from the bot in the chat.',
 'Позиция не определяется':'The position is not being fixed',
 'В глубине корпуса GPS телефона часто не ловит. Выйди на крыло мостика или введи координаты вручную. Проверь, что доступ к геопозиции разрешён.':
   'Deep inside the hull a phone’s GPS often will not receive. Go out to the bridge wing or enter the position by hand. Check that access to location is allowed.',
 'Кнопка оплаты ничего не открывает':'The payment button opens nothing',
 'Оплата работает только внутри Telegram: приложение должно быть открыто кнопкой в чате с ботом, а не по ссылке в браузере.':
   'Payment works only inside Telegram: the app must be opened with the button in the chat with the bot, not by a link in a browser.',
 'Нашёл ошибку или есть предложение':'I found a bug or have a suggestion',
 'Настройки → Написать в поддержку. Переписка идёт прямо здесь, я отвечаю в этом же чате.':
   'Settings → Contact support. The conversation happens right here and I reply in the same chat.'
});
/* --- Интерфейс: настройки, списки, состояния, служебные строки --- */
Object.assign(DICT,{
 'Обстановка':'Situation','Позиция':'Position','Текущая позиция':'Present position',
 'Геопозиция':'Positioning','Геопозиция выключена':'Positioning is off',
 'Выключена, координаты вводятся вручную':'Off, positions are entered by hand',
 'Метка на карте':'Own ship on the chart',
 'Следить за своим местом, пока карта открыта':'Track own position while the chart is open',
 'Обновить позицию':'Refresh position','Отменить запрос':'Cancel the request',
 'Позиция с устройства':'Position from the device',
 'позиция недоступна':'position unavailable','геопозиция выключена в настройках':'positioning is off in the settings',
 'устройство не ответило, попробуй ещё раз':'the device did not answer, try again',
 'запрос отменён':'request cancelled','запрос не выполнен:':'request failed:',
 'Единицы и формат':'Units and format','Формат координат':'Position format',
 'Градусы с минутами или десятичные':'Degrees and minutes, or decimal',
 'Отдача при нажатии':'Haptic feedback',
 'Лёгкая вибрация на кнопках и ручках':'A light buzz on keys and knobs',
 'Тема оформления':'Colour scheme','Новые предупреждения':'New warnings',
 'Присылать, как только появятся в твоих районах':'Send as soon as they appear in your areas',
 'Сроки сертификатов':'Certificate expiry',
 'За 60, 30, 14, 7, 3 и 1 день до истечения':'60, 30, 14, 7, 3 and 1 day before expiry',
 'Батареи EPIRB и SART':'EPIRB and SART batteries',
 'За 90, 30 и 7 дней до замены':'90, 30 and 7 days before replacement',
 'Всемирное координированное, им ведётся радиожурнал':'Coordinated universal time, used for the radio log',
 'Пояс задаёшь сам:':'You set the zone yourself:','Пояс из настроек устройства':'Zone from the device settings',
 'СУД':'SHP','ТЛФ':'PHN','Готово':'Done','Закрыть':'Close','Закрыть карту':'Close the map',
 'Удалить':'Delete','Выше':'Up','Ниже':'Down','Открыть ассистента':'Open the assistant',
 'Тарифы':'Plans','Что открыто сейчас и что даёт Premium':'What is open now and what Premium adds',
 'Что входит в Premium ·':'What Premium includes ·','Открыты все разделы. Дальше':'All sections are open. After that',
 'Два района, базовые расчёты и справочники. Остальное —':'Two areas, the basic calculations and the reference sections. The rest —',
 '⭐ в месяц':'⭐ per month','⭐ / мес':'⭐ / mo','⭐ в месяц.':'⭐ per month.',
 '⭐ в месяц, это примерно 2 доллара.':'⭐ per month, about two dollars.',
 'Пробный период · осталось':'Trial period · remaining',
 'Расчёты безопасности: запас под килём, проседание, CPA/TCPA, точка перекладки, якорь, габарит под мостом':
   'Safety calculations: under-keel clearance, squat, CPA/TCPA, wheel-over point, anchoring, air draught',
 'Новый сертификат':'New certificate','Бот напомнит заранее, когда подойдёт срок':'The bot reminds you before it expires',
 'Мои суда':'My vessels','+ Судно':'+ Vessel','Типовые серии':'Typical classes',
 'в профиле':'in the profile','· размерения подставятся':'· dimensions will be filled in',
 'Заполняется один раз, подставляется во все расчёты':'Filled in once, used by every calculation',
 'Заполни карточку один раз — длина, ширина, осадка, Cb и остальное сами подставятся в расчёты запаса под килём, проседания, якорной стоянки и прохода под мостом.':
   'Fill the card in once — length, beam, draught, block coefficient and the rest are then inserted into the under-keel clearance, squat, anchoring and air draught calculations.',
 'Открой приложение из чата с ботом, чтобы карточка судна привязалась к тебе.':
   'Open the app from the chat with the bot so that the vessel card is tied to you.',
 'Удалить это судно из профиля?':'Remove this vessel from the profile?',
 'Удалить всю историю чек-листов? Отменить будет нельзя.':'Delete the whole checklist history? This cannot be undone.',
 'Удалить сохранённые данные с устройства? Настройки и избранное останутся.':
   'Delete the data stored on this device? Settings and favourites will remain.',
 'Отмечай по ходу дела. Сохранится в историю.':'Tick as you go. It is saved to the history.',
 'Нет предупреждений с координатами для этого выбора.':'No warnings with positions for this selection.',
 'Отменённые и снятые с силы, поиск за всё время':'Cancelled and no longer in force, searched over all time',
 'Отметь районы звёздочкой, чтобы следить за ними':'Star the areas to follow them',
 'График появится, когда накопятся данные за несколько дней. Снимок делается раз в сутки.':
   'The graph appears once several days of data have built up. A snapshot is taken once a day.',
 'На маршруте найдено':'Found on the route','миль по маршруту · коридор ±':'NM along the route · corridor ±',
 'миль от курса':'NM off track','миль · предупреждений на маршруте:':'NM · warnings on the route:',
 'миль всего':'NM in total','миль осталось':'NM to run','% пути пройдено':'% of the passage run',
 'предупреждение':'warning','предупреждений':'warnings','новое предупреждение':'new warning',
 'новых предупреждения':'new warnings','новых предупреждений':'new warnings','НОВЫХ':'NEW',
 'без номера':'no number','· отменено':'· cancelled','нет данных':'no data',
 'только что':'just now','мин назад':'min ago','ч назад':'h ago','дн назад':'d ago',
 'вот-вот':'imminent','истекает сегодня':'expires today','скоро истекает':'expires soon',
 'просрочен':'expired','в порядке':'in date','под контролем':'monitored','максимум':'maximum',
 'ошибка':'error','шаблон':'template','История ·':'History ·','точность':'accuracy',
 'точечных объектов из':'point objects out of','районов и полос,':'areas and lanes,',
 'Расстояние · миль':'Distance · NM','нос':'bow','НЕТ, не хватает':'NO, short by',
 'растущий серп':'waxing crescent','убывающий серп':'waning crescent',
 'Сбой в приложении':'Application failure','Часть приложения не загрузилась':'Part of the app failed to load',
 'Раздел недоступен.':'Section unavailable.','Раздел недоступен:':'Section unavailable:',
 'Не задан адрес вызова.':'No call address has been set.',
 'Поле TO -- девять цифр MMSI.':'The TO field takes a nine-digit MMSI.',
 'Помощник вахтенного на связи':'Your watchkeeping assistant is ready',
 'Прочти обстановку и подай тот вызов, который положен:':'Read the situation and send the correct call:',
 'DISTRESS MSG — бедствие, OTHER DSC MSG — всё остальное. Срочность и безопасность':
   'DISTRESS MSG for distress, OTHER DSC MSG for everything else. Urgency and safety',
 'задаются полем PRIORITY, а не отдельным типом сообщения.':
   'are set by the PRIORITY field, not by a separate message type.',
 'Станция обязана непрерывно слушать частоты бедствия. SCAN проходит их по кругу:':
   'The station must keep a continuous watch on the distress frequencies. SCAN steps through them:',
 'верхняя строка — 2187.5 кГц, ниже береговые вызывные ЦИВ. Приём вызова сканирование останавливает.':
   'the top row is 2187.5 kHz, below are the coast DSC calling channels. An incoming call stops the scan.',
 'Дай рекомендации по океанскому переходу':'Give guidance for the ocean passage',
 'по Ocean Passages for the World: рекомендованный путь,':
   'from Ocean Passages for the World: the recommended track,',
 'сезонные соображения, течения и ветры, чего избегать.':
   'seasonal considerations, currents and winds, and what to avoid.'
});
/* --- Каналы, частоты, орбиты и подписи меню станции --- */
Object.assign(DICT,{
 'VHF канал 6':'VHF channel 6','VHF канал 13':'VHF channel 13',
 'VHF канал 16':'VHF channel 16','VHF канал 70':'VHF channel 70',
 'AIS каналы 1 и 2':'AIS channels 1 and 2','ЦИВ (DSC)':'DSC',
 'Радиостанции MF/HF':'MF/HF coast stations','Записей нет.':'No entries.',
 'Как удобнее':'As it suits','По новизне':'By newest','По номеру':'By number',
 'GEO 35 890 км':'GEO 35,890 km','MEO ~20 000 км':'MEO ~20,000 km','LEO ~850 км':'LEO ~850 km',
 'Например Cape':'For example Cape','Например Ballast Water Plan':'For example Ballast Water Plan',
 'Например Rev. 3, 2025':'For example Rev. 3, 2025','Например где хранится':'For example where it is kept',
 'Судовое,':'Ship time,','день':'day','ночь':'night','до':'to','м на':'m at','сут (':'d (','мес)':'mo)',
 'Настройка станции.':'A setting of the set.',
 'Частота тонального шумоподавителя.':'Tone squelch frequency.',
 'Ниже 1000 Гц слышнее слабые сигналы,':'Below 1000 Hz weak signals are more audible,',
 'выше -- меньше шума в динамике.':'above it there is less noise in the speaker.',
 'Назначение цифровых клавиш на':'Assignment of the numeric keys to',
 'быстрые команды дежурного экрана.':'shortcuts on the standby screen.',
 'Печать журнала на судовой принтер.':'Printing the log on the ship’s printer.',
 'По ГМССБ распечатка вызовов бедствия':'Under GMDSS the printout of distress calls',
 'хранится вместе с радиожурналом.':'is kept together with the radio log.',
 'Если приёмник отказал, позицию вводят':'If the receiver has failed, the position is entered',
 'вручную и обновляют не реже чем раз':'by hand and updated at least once',
 'в четыре часа -- иначе в тревоге уйдут':'every four hours, otherwise the alert will carry',
 'старые координаты.':'a stale position.',
 'Время, через которое станция сама':'The time after which the set returns',
 'возвращается на дежурный экран.':'to the standby screen by itself.',
 'Настройки приёмника: АРУ, аттенюатор,':'Receiver settings: AGC, attenuator,',
 'режим полосы.':'bandwidth mode.',
 'Вынос тревоги на мостик и в каюту':'Repeating the alarm to the bridge and to the',
 'капитана -- обязателен по ГМССБ.':'master’s cabin is required under GMDSS.',
 'Обмен с судовой сетью: приёмник GPS,':'Exchange with the ship’s network: GPS receiver,',
 'ЭКНИС, судовой журнал.':'ECDIS, deck log.',
 'Динамик дежурного приёма. Выключать':'The watch-receiver loudspeaker. Switching it off',
 'его на вахте нельзя.':'while on watch is not permitted.',
 'Трубка. Разговор после вызова ЦИВ':'The handset. Traffic after a DSC call',
 'идёт именно по ней.':'is passed on it.',
 'Самопрослушивание своей передачи.':'Side tone of your own transmission.',
 'Уровень низкой частоты. Ручкой VOLUME':'Audio level. The VOLUME knob',
 'на панели он же и крутится.':'on the panel adjusts the same thing.',
 'Тревога при приёме бедствия.':'Alarm on receipt of a distress alert.',
 'Отключить её штатно нельзя.':'It cannot be disabled by normal means.',
 'Звук при обычном вызове в свой адрес.':'Tone on an ordinary call addressed to you.',
 'Зуммер нажатия клавиш.':'Key-press buzzer.',
 'Сброс к заводским настройкам.':'Reset to factory settings.',
 'MMSI при этом не стирается.':'The MMSI is not erased by it.',
 'Свои каналы заводят под связь с':'User channels are set up for working with a',
 'конкретной береговой станцией или':'particular coast station or with the',
 'флотом компании. На тренажёре список':'company fleet. In the simulator the list is',
 'фиксированный.':'fixed.',
 'Здесь останется всё, что станция':'Everything the set has transmitted',
 'передала за рейс.':'during the voyage is kept here.',
 'Обычные принятые вызовы хранятся':'Ordinary received calls are kept',
 'до заполнения памяти, потом':'until the memory is full, then the',
 'затираются самыми старыми.':'oldest are overwritten first.',
 'Принятые вызовы бедствия хранятся':'Received distress alerts are kept',
 'отдельно и не стираются вахтенным.':'separately and cannot be erased by the watchkeeper.',
 'Подтверждение бедствия всегда ручное:':'A distress acknowledgement is always manual:',
 'первым его даёт береговой центр, а не':'the coast station gives it first, not the',
 'судно. Автоматический ответ на чужое':'ship. An automatic reply to another vessel’s',
 'бедствие правилами запрещён.':'distress alert is prohibited by the rules.',
 'В журнал ЦИВ время пишется всемирное.':'Times in the DSC log are written in UTC.',
 'Судовое время в радиожурнале не':'Ship time is not used in the',
 'используется.':'radio log.',
 'Контрольный тон подаётся в тракт':'The test tone is fed into the audio',
 'низкой частоты. Если его не слышно':'chain. If it cannot be heard',
 'в динамике и в трубке -- неисправен':'in the speaker and the handset, the fault is in the',
 'усилитель, а не приёмник.':'amplifier, not in the receiver.',
 'У судна первые три цифры -- код страны,':'For a ship the first three digits are the country code,',
 'у береговой станции первые две нули,':'for a coast station the first two are zeros,',
 'у группы -- ноль в начале.':'and for a group there is a single leading zero.',
 'Срочность (PAN PAN) и безопасность (SECURITE) на станции задаются полем PRIORITY,':
   'Urgency (PAN PAN) and safety (SECURITE) are set on the radio by the PRIORITY field,',
 'а не отдельным типом сообщения. Тип отвечает только за то, кому уходит вызов.':
   'not by a separate message type. The type only decides who the call goes to.',
 '. Панель работает в упрощённом режиме. Пришли этот текст разработчику.':
   '. The panel is running in reduced mode. Send this text to the developer.',
 '. По ней считается время до заступления':'. Time until you go on watch is counted from it'
});
/* --- Составные строки, которые собираются в коде --- */
Object.assign(DICT,{
 'Доброе утро, вахтенный.':'Good morning, Officer.',
 'Добрый день, вахтенный.':'Good afternoon, Officer.',
 'Добрый вечер, вахтенный.':'Good evening, Officer.',
 'Спокойной вахты, вахтенный.':'Steady as she goes, Officer.',
 'Раздел входит в Premium — ':'This section is part of Premium — ',
 ' ⭐ в месяц, около 2 долларов.':' ⭐ per month, about two dollars.',
 ' Первые ':' The first ',' дн. после установки всё открыто.':' days after installation everything is open.',
 'Координаты берутся с устройства':'Positions are taken from the device',
 'Предупреждения, станции и справочники сохраняются на устройстве — в рейсе приложение открывается и работает без сети. Расчёты работают всегда.':
   'Warnings, stations and reference data are stored on the device — at sea the app opens and works without a connection. The calculations always work.',
 '50 миль':'50 NM','150 миль':'150 NM','300 миль':'300 NM','500 миль':'500 NM',
 'Ширина коридора':'Corridor width'
});
const DICT_REV=Object.fromEntries(Object.entries(DICT).map(([k,v])=>[v,k]));
let LANG=localStorage.getItem('navarea_lang')||'ru';

function applyLang(){
  const map=LANG==='en'?DICT:DICT_REV;
  // длинные фразы заменяем раньше коротких, иначе короткая съест часть длинной
  const keys=Object.keys(map).sort((a,b)=>b.length-a.length);

  const walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{
    acceptNode:n=>{
      const p=n.parentElement;
      if(!p) return NodeFilter.FILTER_REJECT;
      const tag=p.tagName;
      if(tag==='SCRIPT'||tag==='STYLE'||tag==='INPUT'||tag==='TEXTAREA') return NodeFilter.FILTER_REJECT;
      // data-notr -- имена собственные и подписи прибора. Без этого название
      // приложения в шапке превращалось в «Следитьkeeper»: слово Watch
      // отдельным текстовым узлом попадало под обратный перевод.
      if(p.closest&&p.closest('[data-notr]')) return NodeFilter.FILTER_REJECT;
      return n.nodeValue.trim()?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT;
    }
  });
  const nodes=[];
  while(walk.nextNode()) nodes.push(walk.currentNode);

  nodes.forEach(n=>{
    let v=n.nodeValue;
    const t=v.trim();
    if(map[t]){ n.nodeValue=v.replace(t,map[t]); return; }
    // не нашли целиком -- пробуем вхождения (например "131 действующих ...")
    let changed=false;
    for(const k of keys){
      if(k.length<18) continue;  // короткие слова внутри фраз не трогаем
      if(v.indexOf(k)!==-1){ v=v.split(k).join(map[k]); changed=true; }
    }
    if(changed) n.nodeValue=v;
  });

  document.querySelectorAll('input[placeholder],select option').forEach(el=>{
    if(el.tagName==='OPTION'){
      const t=el.textContent.trim();
      if(map[t]) el.textContent=map[t];
      return;
    }
    const ph=el.getAttribute('placeholder');
    if(ph&&map[ph]) el.setAttribute('placeholder',map[ph]);
  });

  const lb=$('#langBtn'); if(lb) lb.textContent=LANG==='en'?'EN':'RU';
  try{ document.documentElement.lang=LANG; }catch(e){}
}
/* Перехват ошибок: если что-то падает, показываем текст прямо на экране,
   иначе с телефона его никак не увидеть. */
(function(){
  let shown=0;
  function show(msg){
    if(shown>2) return; shown++;
    try{
      const el=document.getElementById('errbar');
      if(!el) return;
      el.innerHTML='<span class="x" onclick="this.parentNode.classList.remove(\'on\')">×</span>'+
        '<b>Сбой в приложении</b>'+String(msg).slice(0,300);
      el.classList.add('on');
    }catch(e){}
  }
  window.addEventListener('error', e=>show((e.message||'ошибка')+' @ '+((e.filename||'').split('/').pop()||'')+':'+(e.lineno||'')));
  window.addEventListener('unhandledrejection', e=>show('запрос не выполнен: '+((e.reason&&e.reason.message)||e.reason||'')));
})();

/* Нижнее меню на делегировании: обработчик один, висит на документе и
   срабатывает, даже если где-то ниже по коду случилась ошибка. Раньше
   привязка шла перебором кнопок в середине скрипта -- любая ошибка выше
   оставляла панель без обработчиков, и она выглядела мёртвой. */
/* Резервное переключение: работает напрямую через разметку и не зависит
   ни от одной функции ниже по файлу. Если основная логика по какой-то
   причине не догрузилась, панель всё равно переключает разделы. */
var FALLBACK_GROUPS={
  home:['dash','areas'],
  tools:['tools','bridge','refs','radio','dsc'],
  map:['map','voy','zones'],
  profile:['ship','settings']
};
function fallbackSwitch(g){
  var first=(FALLBACK_GROUPS[g]||['dash'])[0];
  var secs=document.querySelectorAll('section[id^="v-"]');
  for(var i=0;i<secs.length;i++){
    if(secs[i].id==='v-'+first) secs[i].classList.remove('hidden');
    else secs[i].classList.add('hidden');
  }
  var tabs=document.querySelectorAll('.tab');
  for(var j=0;j<tabs.length;j++){
    if(tabs[j].getAttribute('data-g')===g) tabs[j].classList.add('on');
    else tabs[j].classList.remove('on');
  }
}

document.addEventListener('click', function(ev){
  var el=ev.target;
  var tab=null, sub=null;
  while(el&&el!==document.body){
    if(!tab&&el.classList&&el.classList.contains('tab')) tab=el;
    if(!sub&&el.getAttribute&&el.getAttribute('data-sv')) sub=el;
    el=el.parentNode;
  }

  if(tab){
    var g=tab.getAttribute('data-g');
    try{
      if(typeof hap==='function') hap();
      if(typeof switchGroup==='function'){
        if(typeof GROUP_LAST!=='undefined'&&typeof S!=='undefined') GROUP_LAST[S_GROUP]=S.view;
        switchGroup(g);
        return;
      }
    }catch(e){ console.warn('меню:',e); }
    fallbackSwitch(g);   // основная логика недоступна -- переключаем сами
    return;
  }

  if(sub){
    var v=sub.getAttribute('data-sv');
    try{
      if(typeof hap==='function') hap();
      if(typeof switchView==='function'){ switchView(v); return; }
    }catch(e){ console.warn('подраздел:',e); }
    var secs=document.querySelectorAll('section[id^="v-"]');
    for(var k=0;k<secs.length;k++){
      if(secs[k].id==='v-'+v) secs[k].classList.remove('hidden');
      else secs[k].classList.add('hidden');
    }
  }
});


/* Перетаскивание лент мышью: на телефоне свайп работает сам, а на
   компьютере зажатую кнопку браузер не превращает в прокрутку. */
(function(){
  function makeDraggable(el){
    if(!el||el._drag) return; el._drag=true;
    let down=false, startX=0, startScroll=0, moved=0;
    el.addEventListener('mousedown', e=>{
      down=true; moved=0; startX=e.pageX; startScroll=el.scrollLeft;
      el.style.scrollBehavior='auto';
    });
    window.addEventListener('mouseup', ()=>{ down=false; el.style.scrollBehavior=''; });
    window.addEventListener('mousemove', e=>{
      if(!down) return;
      const dx=e.pageX-startX;
      moved=Math.max(moved,Math.abs(dx));
      el.scrollLeft=startScroll-dx;
      if(moved>4) e.preventDefault();
    });
    // если тащили, а не кликали -- гасим клик, чтобы не переключился раздел
    el.addEventListener('click', e=>{ if(moved>6){ e.stopPropagation(); e.preventDefault(); moved=0; } }, true);
  }
  function scan(){
    ['#subtabs','#cats','#rchips','#mapchips','#corr'].forEach(sel=>{
      const el=document.querySelector(sel); if(el) makeDraggable(el);
    });
  }
  document.addEventListener('DOMContentLoaded', scan);
  setTimeout(scan, 400);
  setTimeout(scan, 1500);
})();

const TG = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
if (TG) { TG.ready(); TG.expand(); try{ TG.setHeaderColor('#0a1520'); }catch(e){} }
const INIT = TG ? (TG.initData || '') : '';
const CK='navarea_cache_v3', ZK='navarea_zones_v2', TK='navarea_theme';

let S={stats:null,favs:[],warnings:[],zones:null,zoneOn:{},
       cat:'all',sort:'count',q:'',corridor:150,view:'dash',offline:false};
let map=null,vmap=null,wLayers=[],zLayers=[],baseLayer=null;
let LY={areas:true,points:true,labels:true};

const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const hap=t=>{
  // Отдачу можно выключить в настройках: на длинной вахте постоянная
  // вибрация раздражает, да и батарею тратит.
  if(typeof HAPTIC!=='undefined' && !HAPTIC) return;
  try{TG&&TG.HapticFeedback.impactOccurred(t||'light')}catch(e){}
};

/* тема */
if(localStorage.getItem(TK)==='light') document.body.classList.add('light');
else if(TG&&TG.colorScheme==='light'&&!localStorage.getItem(TK)) document.body.classList.add('light');
$('#themeBtn').onclick=()=>{
  document.body.classList.toggle('light'); hap('medium');
  localStorage.setItem(TK, document.body.classList.contains('light')?'light':'dark');
};

function saveCache(){
  try{
    localStorage.setItem(CK,JSON.stringify({stats:S.stats,warnings:S.warnings,favs:S.favs,at:Date.now()}));
    localStorage.setItem(ZK,JSON.stringify({zones:S.zones,on:S.zoneOn}));
  }catch(e){}
}
function loadCache(){
  try{
    const z=JSON.parse(localStorage.getItem(ZK)||'null');
    if(z){S.zones=z.zones;S.zoneOn=z.on||{}}
    const c=JSON.parse(localStorage.getItem(CK)||'null');
    if(c&&c.stats){S.stats=c.stats;S.warnings=c.warnings||[];S.favs=c.favs||[];return c.at}
  }catch(e){}
  return null;
}
/* ---- Признак устройства ----
   Нужен ровно для одного: пробный период выдаётся один раз на устройство,
   а не заново на каждый новый аккаунт Telegram. Идентификатор случайный и
   живёт только здесь; отпечаток -- часовой пояс, язык, экран и платформа,
   на сервере он хранится хешем. Личность по ним не устанавливается. */
const DEV_KEY='navarea_device';
function deviceId(){
  let d=null;
  try{ d=localStorage.getItem(DEV_KEY); }catch(e){}
  if(!d||d.length<8){
    d=(crypto&&crypto.randomUUID)?crypto.randomUUID().replace(/-/g,'')
      :(Date.now().toString(36)+Math.random().toString(36).slice(2,14));
    try{ localStorage.setItem(DEV_KEY,d); }catch(e){}
  }
  return d;
}
function deviceFingerprint(){
  try{
    const s=screen||{};
    return [
      Intl.DateTimeFormat().resolvedOptions().timeZone||'',
      navigator.language||'',
      (s.width||0)+'x'+(s.height||0),
      s.colorDepth||0,
      navigator.platform||'',
      navigator.hardwareConcurrency||0,
      navigator.maxTouchPoints||0
    ].join('|');
  }catch(e){ return ''; }
}
const DEVICE=deviceId(), DEVICE_FP=deviceFingerprint();

async function api(p){
  const sep=p.includes('?')?'&':'?';
  const r=await fetch(p+sep+'initData='+encodeURIComponent(INIT)
    +'&device='+encodeURIComponent(DEVICE)
    +'&fp='+encodeURIComponent(DEVICE_FP));
  if(!r.ok) throw new Error('HTTP '+r.status);
  return r.json();
}
/* «Столько-то назад». Число и слово собираются раздельно и слово гоняется
   через словарь: иначе строка вида «1 мин назад» целиком не находится в
   словаре и остаётся по-русски при английском интерфейсе. */
function ago(iso){
  if(!iso) return tr('нет данных');
  const d=(Date.now()-new Date(iso).getTime())/1000;
  if(d<60) return tr('только что');
  if(d<3600) return Math.floor(d/60)+' '+tr('мин назад');
  if(d<86400) return Math.floor(d/3600)+' '+tr('ч назад');
  return Math.floor(d/86400)+' '+tr('дн назад');
}
function countUp(el,to){
  const dur=680,t0=performance.now();
  (function s(t){
    const k=Math.min(1,(t-t0)/dur),e=1-Math.pow(1-k,3);
    el.textContent=Math.round(to*e);
    if(k<1) requestAnimationFrame(s);
  })(t0);
}

async function load(spin){
  try{
    // Раздельно и через allSettled: раньше падение одного запроса обнуляло
    // весь экран (районы и карта оставались пустыми). Лимит снижен -- три
    // тысячи предупреждений с разбором геометрии сервер отдавал слишком долго.
    const [stR,wrR]=await Promise.allSettled([
      api('/api/stats'), api('/api/warnings?limit=800')
    ]);
    if(stR.status==='fulfilled') S.stats=stR.value;
    if(wrR.status==='fulfilled') S.warnings=wrR.value.results||[];
    S.offline=(stR.status!=='fulfilled'&&wrR.status!=='fulfilled');
    try{const f=await api('/api/favorites');if(!f.error)S.favs=f.favorites||[]}catch(e){}
    if(!S.zones){
      try{
        const z=await api('/api/zones');S.zones=z;
        (z.zones||[]).forEach(x=>{if(S.zoneOn[x.id]===undefined)S.zoneOn[x.id]=false});
      }catch(e){}
    }
    saveCache();
  }catch(e){S.offline=true}
  $('#offline').classList.toggle('on',S.offline);
  renderGeoBtn();
  render();
}

function render(){renderCats();renderDash();renderAreas();renderZones();applyLang()}

/* --- плитки районов --- */
function renderCats(){
  if(!S.stats||!S.stats.totals) return;
  const list=(S.stats.areas||[]).slice().sort((a,b)=>b.in_force-a.in_force);
  $('#cats').innerHTML=
    `<div class="cat ${S.cat==='all'?'on':''}" data-cat="all">
       ${ico('globe')}<span class="cn">Все</span>
       <span class="cb">${S.stats.totals.in_force}</span></div>`+
    list.map(a=>`<div class="cat ${S.cat===a.code?'on':''}" data-cat="${a.code}">
       ${ico(areaIcon(a.code))}
       <span class="cn">${esc(a.code.replace('COASTAL:','Б'))}</span>
       <span class="cb">${a.in_force}</span></div>`).join('');
  document.querySelectorAll('[data-cat]').forEach(c=>c.onclick=()=>{
    S.cat=c.dataset.cat;hap();renderCats();
    if(S.view==='dash'){switchView('areas')}else{renderAreas()}
    if(S.view==='map')drawMap();
  });
}

/* --- быстрые действия на главной --- */
const QUICK=[
  {i:'route',t:'Проверить маршрут',s:'Порт — порт',go:()=>switchView('voy')},
  {i:'buoy',t:'Запас под килём',s:'UKC и проседание',go:()=>{switchView('tools');setTimeout(()=>openTool(TOOLS.find(x=>x.id==='ukc')),80)}},
  {i:'radar',t:'Расхождение',s:'CPA и TCPA',go:()=>{switchView('tools');setTimeout(()=>openTool(TOOLS.find(x=>x.id==='cpa')),80)}},
  {i:'map',t:'Карта',s:'Все предупреждения',go:()=>switchView('map')},
];

/* ---- Что человек открывает чаще всего ----
   Считаем локально, на устройстве: ничего никуда не отправляется, просто
   счётчик открытий, чтобы поднять частое наверх. */
function bump(kind,id){
  try{
    const u=JSON.parse(localStorage.getItem('navarea_usage')||'{}');
    const k=kind+':'+id; u[k]=(u[k]||0)+1;
    localStorage.setItem('navarea_usage',JSON.stringify(u));
  }catch(e){}
}
function topUsed(kind,n){
  try{
    const u=JSON.parse(localStorage.getItem('navarea_usage')||'{}');
    return Object.keys(u).filter(k=>k.indexOf(kind+':')===0)
      .sort((a,b)=>u[b]-u[a]).slice(0,n).map(k=>k.slice(kind.length+1));
  }catch(e){ return []; }
}

/* ---- Список с показом первых четырёх ---- */
const SHOWN=4;
const EXPANDED={};
function collapsible(id,items,renderItem,labelAll){
  if(!items.length) return '';
  const open=EXPANDED[id];
  const vis=open?items:items.slice(0,SHOWN);
  const hidden=items.length-vis.length;
  return `<div class="grid2">${vis.map(renderItem).join('')}</div>`+
    (items.length>SHOWN
      ? `<button class="showall" data-exp="${id}">${open?'Свернуть':(labelAll||'Показать все')+' · '+hidden}</button>`
      : '');
}
function bindExpand(rerender){
  document.querySelectorAll('[data-exp]').forEach(b=>b.onclick=()=>{
    EXPANDED[b.dataset.exp]=!EXPANDED[b.dataset.exp]; hap(); rerender();
  });
}

function renderQuick(){
  const el=$('#quick'); if(!el) return;

  // Сначала то, что человек открывает чаще всего, потом обычный набор --
  // так первые кнопки со временем становятся его личными.
  const often=topUsed('tool',4).map(id=>{
    const t=TOOLS.find(x=>x.id===id); if(!t) return null;
    return {i:t.icon,t:t.name,s:t.desc,go:()=>{switchView('tools');setTimeout(()=>openTool(t),60);}};
  }).filter(Boolean);
  const rest=QUICK.filter(q=>!often.some(o=>o.t===q.t));
  const list=often.concat(rest).slice(0,6);

  el.innerHTML=list.map((q,i)=>
    `<div class="qbtn up" style="animation-delay:${i*45}ms" data-q="${i}">
       <div class="qi">${ico(q.i)}</div>
       <div><div class="qt">${esc(q.t)}</div><div class="qs">${esc(q.s)}</div></div>
     </div>`).join('');
  document.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>{hap('medium');list[+b.dataset.q].go()});
}

/* последний проложенный маршрут и последние открытые расчёты */
function renderLastVoyage(){
  const el=$('#lastVoyBox'); if(!el) return;
  let v=null;
  try{ v=JSON.parse(localStorage.getItem('navarea_lastvoy')||'null'); }catch(e){}
  if(!v){ el.innerHTML=''; return; }
  el.innerHTML=`<div class="sech" style="margin-top:18px"><h3>Активный рейс</h3>
      <a id="openVoy">Открыть →</a></div>
    <div class="voyhead" style="margin:0" id="lastVoyCard">
      <div class="big">${esc(v.from)} → ${esc(v.to)}</div>
      <div class="sm"><span class="mono">${v.distance}</span> миль · предупреждений на маршруте: <span class="mono">${v.count}</span></div>
      ${v.legs?`<div class="legs">${ico('route','xs')}<span>${esc(v.legs)}</span></div>`:''}
    </div>`;
  const go=()=>{hap();switchView('voy')};
  const a=$('#openVoy'); if(a) a.onclick=go;
  const c=$('#lastVoyCard'); if(c) c.onclick=go;
}
function renderLastCalcs(){
  const el=$('#lastCalcBox'); if(!el) return;
  let ids=[];
  try{ ids=JSON.parse(localStorage.getItem('navarea_lastcalc')||'[]'); }catch(e){}
  const list=ids.map(id=>TOOLS.find(t=>t.id===id)).filter(Boolean).slice(0,4);
  if(!list.length){ el.innerHTML=''; return; }
  el.innerHTML=`<div class="sech" style="margin-top:18px"><h3>Последние расчёты</h3>
      <a id="allCalc">Все →</a></div>
    <div class="quick">${list.map((t,i)=>
      `<div class="qbtn up" style="animation-delay:${i*45}ms" data-lc="${t.id}">
         <div class="qi">${ico(t.icon)}</div>
         <div><div class="qt">${esc(t.name)}</div></div>
       </div>`).join('')}</div>`;
  document.querySelectorAll('[data-lc]').forEach(b=>b.onclick=()=>{
    hap('medium'); openTool(TOOLS.find(t=>t.id===b.dataset.lc));
  });
  const a=$('#allCalc'); if(a) a.onclick=()=>{hap();switchView('tools')};
}
function rememberCalc(id){
  let ids=[];
  try{ ids=JSON.parse(localStorage.getItem('navarea_lastcalc')||'[]'); }catch(e){}
  ids=[id].concat(ids.filter(x=>x!==id)).slice(0,6);
  try{ localStorage.setItem('navarea_lastcalc',JSON.stringify(ids)); }catch(e){}
}

/* --- панель --- */
/* ================= Главный экран =================
   Порядок блоков задан макетом: шапка, судно, подсказки ассистента,
   сводка с мостика, тревога, кнопка Ask AI. Цифры берутся из настоящих
   данных: если их нет -- показываем прочерк и честную подпись, а не
   правдоподобную выдумку. */

function renderClock(){
  const c=$('#hdrClock'), d=$('#hdrDate'); if(!c) return;
  const t=nowIn();
  c.innerHTML=`${String(t.getUTCHours()).padStart(2,'0')}:${
    String(t.getUTCMinutes()).padStart(2,'0')}<span>${TIME_LABEL[TIME_MODE]||'UTC'}</span>`;
  if(d) d.textContent=`${t.getUTCDate()} ${tr(DP_MON_SHORT[t.getUTCMonth()])} ${t.getUTCFullYear()}`;
}

function greetWord(){
  const h=new Date().getHours();
  if(h<5)  return 'Спокойной вахты';
  if(h<12) return 'Доброе утро';
  if(h<18) return 'Добрый день';
  return 'Добрый вечер';
}

function renderHero(){
  const g=$('#heroGreet'); if(!g) return;
  g.textContent=tr(greetWord())+', '+tr('вахтенный')+'.';
  const s=$('#heroSub');
  if(s) s.textContent=tr(S.offline?'Данные из памяти устройства.':'Помощник вахтенного на связи.');

  const v=(VES&&VES.active)||null;
  const box=$('#vessel-status'); if(!box) return;
  const online=!S.offline;
  box.innerHTML = v&&v.name
    ? `<span class="dot ${online?'':'off'}"></span>
       <span class="lb">МОЁ СУДНО</span>
       <span class="nm">${esc(v.name)}</span><span class="nm">•</span>
       <span class="st ${online?'':'off'}">${online?'НА СВЯЗИ':'БЕЗ СВЯЗИ'}</span>`
    : `<span class="dot off"></span>
       <span class="lb">МОЁ СУДНО</span>
       <span class="nm">${esc(tr('карточка не заполнена'))}</span>`;
  // Прямо в карточку судна, а не в «последний открытый раздел профиля»:
  // раньше отсюда уводило в настройки, если человек был там в прошлый раз.
  box.onclick=()=>{ hap('medium'); switchView('ship'); };
}

/* Четыре подсказки ассистента вместо таблицы инструментов */
const HOME_PROMPTS=[
  {id:'prompt-1', ic:'⚠', bg:'#0c3046', cl:'var(--blue)',
   t:'Безопасность маршрута', s:'Предупреждения и NAVAREA',
   q:'Какие предупреждения влияют на мой маршрут?'},
  {id:'prompt-2', ic:'⌁', bg:'#201b42', cl:'var(--purple)',
   t:'Навигация', s:'ETA · курс · расстояние',
   q:'Посчитай ETA до следующей точки маршрута'},
  {id:'prompt-3', ic:'✓', bg:'#10362f', cl:'var(--green)',
   t:'Приём вахты', s:'Что проверить перед вахтой',
   q:'Что проверить перед заступлением на вахту?'},
  {id:'prompt-4', ic:'☼', bg:'#332e17', cl:'var(--amber)',
   t:'Погода', s:'Ветер · волна · видимость',
   q:'Дай погоду и состояние моря сейчас'}
];
function renderPrompts(){
  const el=$('#ai-prompts'); if(!el) return;
  el.innerHTML=HOME_PROMPTS.map(p=>
    `<button class="wkprompt" id="${p.id}" data-q="${esc(p.q)}">
       <span class="ic" style="background:${p.bg};color:${p.cl}">${p.ic}</span>
       <span class="tx"><span class="t1">${esc(tr(p.t))}</span>
         <span class="t2">${esc(tr(p.s))}</span></span>
     </button>`).join('');
  el.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>{
    hap('medium'); askFromHome(b.dataset.q);
  });
}

/* Открыть ассистента и сразу задать вопрос */
function askFromHome(q){
  switchGroup('ask');
  setTimeout(()=>{ if(q) askSend(q); }, 80);
}

/* Сводка с мостика: следующая точка, доля пути, курс и скорость.
   Всё живое -- из проложенного маршрута и приёмника устройства. */
function voyState(){
  let v=null;
  try{ v=JSON.parse(localStorage.getItem('navarea_lastvoy')||'null'); }catch(e){}
  if(!v||!v.tlat) return v?{v:v}:null;
  const out={v:v};
  if(geoFresh()){
    const left=haversineNm(GEO.lat,GEO.lon,v.tlat,v.tlon);
    out.left=left;
    out.total=v.distance||left;
    out.pct=Math.max(0,Math.min(100,Math.round((1-left/Math.max(1,out.total))*100)));
    if(GEO.sog&&GEO.sog>0.5) out.hours=left/GEO.sog;
  }
  return out;
}
function haversineNm(a1,o1,a2,o2){
  const R=3440.065, r=Math.PI/180;
  const dp=(a2-a1)*r, dl=(o2-o1)*r;
  const h=Math.sin(dp/2)**2+Math.cos(a1*r)*Math.cos(a2*r)*Math.sin(dl/2)**2;
  return 2*R*Math.asin(Math.min(1,Math.sqrt(h)));
}
function hhmm(hours){
  if(hours==null||!isFinite(hours)) return null;
  const h=Math.floor(hours), m=Math.round((hours-h)*60);
  return String(h).padStart(2,'0')+'ч '+String(m).padStart(2,'0')+'м';
}
function renderSnapshot(){
  const el=$('#bridge-snapshot'); if(!el) return;
  const st=voyState();
  const cog = GEO.cog!=null ? Math.round(GEO.cog)+'°' : '—';
  const sog = GEO.sog!=null ? GEO.sog+' уз' : '—';
  const tgo = st&&st.hours!=null ? hhmm(st.hours) : null;

  const left = st&&st.v
    ? `<div class="wklb">Пункт назначения</div>
       <div class="wkbig">${esc(String(st.v.to).split(',')[0])}</div>
       <div class="wksm">${st.left!=null
          ? Math.round(st.left)+' миль осталось'
          : (st.v.distance+' миль всего')}</div>
       ${st.pct!=null
          ? `<div class="wkbar"><i style="width:${st.pct}%"></i></div>
             <div class="wkpct">${st.pct}% пути пройдено</div>`
          : `<div class="wksm" style="margin-top:11px">${esc(tr('Пройденную долю покажем, когда появится позиция'))}</div>`}`
    : `<div class="wklb">Маршрут</div>
       <div class="wkbig">—</div>
       <div class="wksm">${esc(tr('Проложи переход в разделе «Маршрут»'))}</div>`;

  el.innerHTML=`
    <div>${left}</div>
    <div class="divider"></div>
    <div>
      <div class="wkok ${S.offline?'warn':''}" data-notr>${S.offline?'OFF':'OK'}</div>
      <div class="wklb">Навигация</div>
      <div class="wkduo">
        <div><div class="wkmid">${cog}</div><div class="wksm">COG</div></div>
        <div><div class="wkmid">${sog}</div><div class="wksm">SOG</div></div>
      </div>
      <div class="wkmid" style="margin-top:13px">${tgo||'—'}</div>
      <div class="wksm">${esc(tr(tgo?'В пути осталось':'Нужны позиция и скорость'))}</div>
    </div>`;
  const live=$('#snapLive');
  if(live) live.onclick=()=>{ hap(); switchView(st&&st.v?'voy':'map'); };
}

/* Полоса тревоги: сколько предупреждений задевает маршрут, а если
   маршрута нет -- сколько их в избранных районах. */
function renderAlert(){
  const el=$('#alert-strip'); if(!el) return;
  let v=null;
  try{ v=JSON.parse(localStorage.getItem('navarea_lastvoy')||'null'); }catch(e){}

  let n=0, sub='', go='map';
  if(v&&typeof v.count==='number'){
    n=v.count; go='voy';
    sub=n?`${n} ${plural(n,'предупреждение','предупреждения','предупреждений')} на маршруте ${v.from.split(',')[0]} — ${v.to.split(',')[0]}`
         :`На маршруте ${v.from.split(',')[0]} — ${v.to.split(',')[0]} предупреждений нет`;
  } else {
    const fav=(S.stats&&S.stats.areas||[]).filter(a=>S.favs.includes(a.code));
    n=fav.reduce((s,a)=>s+(a.added_today||0),0);
    go='areas';
    sub=n?`${n} ${plural(n,'новое предупреждение','новых предупреждения','новых предупреждений')} сегодня в твоих районах`
         :(fav.length?'В твоих районах сегодня новых предупреждений нет'
                     :'Отметь районы звёздочкой, чтобы следить за ними');
  }

  el.className='wkalert'+(n?'':' ok');
  el.innerHTML=`<span class="ic">${n?'!':'✓'}</span>
    <span class="tx"><span class="t1">${esc(tr(n?'Навигационное предупреждение':'Обстановка спокойная'))}</span>
      <span class="t2">${esc(tr(sub))}</span></span>
    <span class="ar">›</span>`;
  el.onclick=()=>{ hap('medium'); switchView(go); };
}
function plural(n,one,few,many){
  const a=Math.abs(n)%100, b=a%10;
  if(a>10&&a<20) return many;
  if(b>1&&b<5) return few;
  if(b===1) return one;
  return many;
}

function renderDash(){
  renderClock(); renderHero(); renderPrompts(); renderSnapshot(); renderAlert();
  const hl=$('#hello'); if(hl) hl.textContent=S.offline?tr('Данные из кэша'):'';
  // на колокольчике -- сколько предупреждений пришло сегодня
  const nb=$('#notifCnt');
  if(nb){ const t=(S.stats&&S.stats.totals)||{}; nb.textContent=t.added_today?String(t.added_today):''; }

  renderLastCalcs();
}

function areaCard(a,i){
  const f=S.favs.includes(a.code),n=a.added_today>0;
  return `<div class="gcard up" style="animation-delay:${Math.min((i||0)*45,340)}ms" data-code="${a.code}">
    <div class="gtop">
      <svg class="bgw" viewBox="0 0 800 32" preserveAspectRatio="none">
        <path d="M0 16 q50 -10 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v20 h-800 z" fill="#4d93d6"/>
      </svg>
      <div class="gi">${ico(areaIcon(a.code))}</div>
      <button class="gstar ${f?'on':''}" data-fav="${a.code}">${ico('star')}</button>
      ${n?`<span class="gbadge">+${a.added_today} НОВЫХ</span>`:''}
    </div>
    <div class="gbody">
      <div class="gcode">${esc(a.code.replace('COASTAL:','БЕРЕГ '))}</div>
      <div class="gname">${esc(a.name)}</div>
      <div class="gfoot">
        <span class="gcnt mono">${a.in_force}</span>
        <span class="gsub">${ago(a.last_update)}</span>
      </div>
    </div>
  </div>`;
}

function warnCard(w,i){
  const sh=(w.shapes&&w.shapes.length)||0;
  return `<div class="wcard up" style="animation-delay:${Math.min((i||0)*40,320)}ms" data-open="${w.id}">
    <div class="wtop">
      <span class="wtag">${esc(w.area_code)} №${esc(w.msg_number||'—')}</span>
      ${w.region?`<span class="wreg">${esc(w.region)}</span>`:''}
      ${w.distance_nm!==undefined?`<span class="wdist">${w.distance_nm} миль от курса</span>`:''}
    </div>
    <div class="wtxt clip" data-txt>${esc(w.text)}</div>
    <div class="wact">
      ${sh?`<button class="btn" data-map="${w.id}">${ico('map','sm')}На карте${sh>1?' · '+sh:''}</button>`:''}
      <button class="btn g" data-more>Подробнее</button>
    </div>
  </div>`;
}

/* --- районы --- */
function renderAreas(){
  if(!S.stats||!S.stats.areas) return;
  const t=$('#areasTitle');

  if(S.q){
    const q=S.q.toLowerCase();
    const hits=S.warnings.filter(w=>(w.text||'').toLowerCase().includes(q)||
      (w.msg_number||'').toLowerCase().includes(q)||(w.region||'').toLowerCase().includes(q));
    if(t) t.textContent=`Найдено: ${hits.length}`;
    $('#arealist').innerHTML=hits.length?hits.slice(0,80).map(warnCard).join('')
      :`<div class="empty">${ico('search')}Ничего не нашлось. Попробуй номер, часть текста или координаты.</div>`;
    bindWarns();return;
  }

  if(S.cat!=='all'){
    const hits=S.warnings.filter(w=>w.area_code===S.cat);
    if(t) t.textContent=`NAVAREA ${S.cat}`;
    $('#arealist').innerHTML=hits.length?hits.map(warnCard).join('')
      :`<div class="empty">${ico('anchor')}По этому району сейчас нет действующих предупреждений.</div>`;
    bindWarns();return;
  }

  let list=(S.stats.areas||[]).slice();
  if(S.sort==='count') list.sort((a,b)=>b.in_force-a.in_force);
  if(S.sort==='new') list.sort((a,b)=>b.added_today-a.added_today||b.added_week-a.added_week);
  if(S.sort==='code') list.sort((a,b)=>a.code.localeCompare(b.code,undefined,{numeric:true}));
  if(t) t.textContent='Все районы';
  $('#arealist').innerHTML=collapsible('areas',list,areaCard);
  bindAreas(); bindExpand(renderAreas);
}

function bindAreas(){
  document.querySelectorAll('[data-fav]').forEach(b=>b.onclick=async ev=>{
    ev.stopPropagation();hap('medium');
    const c=b.dataset.fav;
    S.favs=S.favs.includes(c)?S.favs.filter(x=>x!==c):S.favs.concat([c]);
    render();saveCache();
    try{await api('/api/favorites?toggle='+encodeURIComponent(c))}catch(e){}
  });
  document.querySelectorAll('.gcard[data-code]').forEach(c=>c.onclick=()=>{
    hap();S.cat=c.dataset.code;S.q='';$('#q').value='';
    renderCats();switchView('areas');renderAreas();
  });
}
function bindWarns(){
  document.querySelectorAll('[data-more]').forEach(b=>b.onclick=ev=>{
    ev.stopPropagation();
    const w=S.warnings.find(x=>String(x.id)===b.closest('[data-open]').dataset.open);
    if(w) openDetail(w);
  });
  document.querySelectorAll('[data-open]').forEach(c=>c.onclick=ev=>{
    if(ev.target.closest('button')) return;
    const w=S.warnings.find(x=>String(x.id)===c.dataset.open);
    if(w) openDetail(w);
  });
  document.querySelectorAll('[data-map]').forEach(b=>b.onclick=ev=>{
    ev.stopPropagation();hap();const w=S.warnings.find(x=>String(x.id)===b.dataset.map);
    if(w){switchView('map');setTimeout(()=>focusWarning(w),80)}
  });
}

/* --- карта --- */
const BASES={
  dark:{url:'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',attr:'&copy; OSM, &copy; CARTO',sub:'abcd'},
  ocean:{url:'https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}',attr:'Esri Ocean'},
  osm:{url:'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',attr:'&copy; OpenStreetMap'}
};
function setBase(k){
  if(!map)return;
  if(baseLayer)map.removeLayer(baseLayer);
  const b=BASES[k]||BASES.dark,o={maxZoom:18,attribution:b.attr};
  if(b.sub)o.subdomains=b.sub;
  baseLayer=L.tileLayer(b.url,o).addTo(map);baseLayer.setZIndex(0);
}
function fmtPos(lat,lon){
  const f=(v,p,n)=>{const h=v>=0?p:n,a=Math.abs(v),d=Math.floor(a),m=(a-d)*60;
    return `${String(d).padStart(2,'0')}-${m.toFixed(2).padStart(5,'0')}${h}`};
  return f(lat,'N','S')+' '+f(lon,'E','W');
}

/* ---- Своя позиция на карте ----
   Кружок точности показывает, насколько уверенно телефон знает место:
   в рубке погрешность бывает и полсотни метров, и это честнее скрывать
   не стоит. */
let myPosLayer=null, myPosAcc=null;

function drawMyPos(){
  if(typeof map==='undefined'||!map) return;
  if(myPosLayer){ map.removeLayer(myPosLayer); myPosLayer=null; }
  if(myPosAcc){ map.removeLayer(myPosAcc); myPosAcc=null; }
  if(!GEO_ON||GEO.lat===null) return;

  if(GEO.acc&&GEO.acc>20){
    myPosAcc=L.circle([GEO.lat,GEO.lon],{radius:GEO.acc,color:'#4d93d6',weight:1,
      fillColor:'#4d93d6',fillOpacity:.12}).addTo(map);
  }
  myPosLayer=L.circleMarker([GEO.lat,GEO.lon],{radius:7,color:'#fff',weight:2,
    fillColor:'#3fc97f',fillOpacity:1})
    .bindPopup('<b>'+tr('Моя позиция')+'</b><br>'+geoFmtLat(GEO.lat)+' '+geoFmtLon(GEO.lon)+
               (GEO.acc?('<br>'+tr('точность')+' ±'+Math.round(GEO.acc)+' м'):''))
    .addTo(map);
  myPosLayer.setZIndex&&myPosLayer.setZIndex(900);
}

function centerOnMe(){
  if(typeof map==='undefined'||!map) return;
  if(GEO.lat===null){ requestPosition().then(p=>{ if(p){ drawMyPos(); map.setView([p.lat,p.lon],9);} }); return; }
  map.setView([GEO.lat,GEO.lon],9); drawMyPos(); hap();
}

function initMap(){
  if(map)return;
  map=L.map('map',{worldCopyJump:true,zoomControl:true}).setView([25,-30],3);
  setBase('dark');
  map.on('mousemove',e=>{$('#curpos').textContent=fmtPos(e.latlng.lat,e.latlng.lng)});
  map.on('click',e=>{$('#curpos').textContent=fmtPos(e.latlng.lat,e.latlng.lng)});
  document.querySelectorAll('input[name=base]').forEach(r=>r.onchange=()=>{setBase(r.value);hap()});

  // кнопка «на мою позицию» поверх карты
  try{
    const MyBtn=L.Control.extend({
      options:{position:'topleft'},
      onAdd:function(){
        const b=L.DomUtil.create('div','leaflet-bar mypos-ctl');
        b.innerHTML='<a href="#" title="'+tr('Моя позиция')+'">'+ico('target','sm')+'</a>';
        L.DomEvent.on(b,'click',e=>{ L.DomEvent.preventDefault(e); L.DomEvent.stop(e); centerOnMe(); });
        return b;
      }
    });
    map.addControl(new MyBtn());
  }catch(e){}
  // Панель настроек занимала четверть карты -- прячем её под иконку
  const gear=$('#mapGear'), ctl=$('#mapCtl');
  if(gear&&ctl){
    gear.innerHTML=ico('sliders');
    gear.onclick=()=>{ ctl.classList.toggle('on'); gear.classList.toggle('on'); hap(); };
  }
  const bind=(id,k)=>{const el=$(id);if(el)el.onchange=()=>{LY[k]=el.checked;drawMap();hap()}};
  bind('#lyAreas','areas');bind('#lyPoints','points');bind('#lyLabels','labels');
  drawZones();drawMap();
}
function shapeLayer(pts,type,popup,color,radiusNm){
  // Фигура без точек (источник отдал пустую геометрию) раньше роняла карту
  if(!Array.isArray(pts)||!pts.length||!Array.isArray(pts[0])) return null;
  let l;
  if(type==='polygon'&&pts.length>=3) l=L.polygon(pts,{color:color,weight:2,fillOpacity:.16,fillColor:color});
  else if(type==='line'&&pts.length>=2) l=L.polyline(pts,{color:color,weight:3});
  else if(type==='circle'&&radiusNm) l=L.circle(pts[0],{radius:radiusNm*1852,color:color,weight:2,fillOpacity:.14});
  else l=L.circleMarker(pts[0],{radius:6,color:color,fillColor:color,fillOpacity:.85,weight:2});
  return l.bindPopup(popup);
}
function renderMapChips(){
  if(!S.stats)return;
  const el=$('#mapchips'); if(!el) return;
  const codes=(S.stats.areas||[]).filter(a=>a.in_force>0).map(a=>a.code);
  el.innerHTML=['all'].concat(codes).map(c=>
    `<button class="chip ${S.cat===c?'on':''}" data-mc="${c}">${c==='all'?'Все районы':esc(c.replace('COASTAL:','Берег '))}</button>`).join('');
  document.querySelectorAll('[data-mc]').forEach(b=>b.onclick=()=>{
    S.cat=b.dataset.mc;hap();renderMapChips();renderCats();drawMap();
  });
}
function drawMap(){
  if(!map)return;
  renderMapChips();
  wLayers.forEach(l=>map.removeLayer(l));wLayers=[];
  const list=S.warnings.filter(w=>w.shapes&&w.shapes.length&&(S.cat==='all'||w.area_code===S.cat));
  let nA=0,nP=0,nS=0;
  list.forEach(w=>{
    if(w.geo_source==='source')nS++;
    const popup=`<b>${esc(w.area_code)} №${esc(w.msg_number||'—')}</b>`+
      (w.region?`<br><i>${esc(w.region)}</i>`:'')+
      `<br><br>${esc((w.text||'').slice(0,300))}${(w.text||'').length>300?'…':''}`;
    w.shapes.forEach(s=>{
      const isA=s.type==='polygon'||s.type==='line'||s.type==='circle';
      if(isA&&!LY.areas)return;
      if(!isA&&!LY.points)return;
      isA?nA++:nP++;
      const l=shapeLayer(s.points,s.type,popup,'#f0a03c',s.radius_nm);
      if(!l) return;
      l.addTo(map);wLayers.push(l);
      if(LY.labels&&isA) l.bindTooltip(`${esc(w.area_code)} ${esc(w.msg_number||'')}`,
        {permanent:true,direction:'center',className:'wlabel',opacity:1});
    });
  });
  const el=$('#mapstat');
  if(el) el.innerHTML=list.length
    ?`Показано: <b>${nA}</b> районов и полос, <b>${nP}</b> точечных объектов из <b>${list.length}</b> предупреждений`+
     (nS?` · геометрия источника у <b>${nS}</b>`:'')
    :'Нет предупреждений с координатами для этого выбора.';
}
function drawZones(){
  if(!map||!S.zones)return;
  zLayers.forEach(l=>map.removeLayer(l));zLayers=[];
  (S.zones.zones||[]).forEach(z=>{
    if(!S.zoneOn[z.id])return;
    const col=(S.zones.groups[z.group]||{}).color||'#4d93d6';
    const l=L.polygon(z.points,{color:col,weight:2,dashArray:'8 6',fillOpacity:.07})
      .bindPopup(`<b>${esc(z.name)}</b><br>${esc(z.note)}<br><br><i>${esc(S.zones.disclaimer)}</i>`);
    l.addTo(map);zLayers.push(l);
  });
}
function renderZones(){
  if(!S.zones){$('#zonelist').innerHTML='<div class="sk card"></div>';return}
  const g=S.zones.groups||{};
  let h=`<div class="hint">${ico('alert','xs')} ${esc(S.zones.disclaimer)}</div>`;
  Object.keys(g).forEach(gk=>{
    h+=`<div class="sech" style="margin-top:15px"><h3 style="font-size:14px">${esc(g[gk].title)}</h3></div>`;
    (S.zones.zones||[]).filter(z=>z.group===gk).forEach(z=>{
      h+=`<div class="sw" data-zone="${z.id}">
        <div style="min-width:0">
          <div class="t"><i style="background:${g[gk].color}"></i>${esc(z.name)}</div>
          <div class="d">${esc(z.note.slice(0,105))}${z.note.length>105?'…':''}</div>
        </div><div class="toggle ${S.zoneOn[z.id]?'on':''}"></div></div>`;
    });
  });
  $('#zonelist').innerHTML=h;
  document.querySelectorAll('[data-zone]').forEach(el=>el.onclick=()=>{
    const id=el.dataset.zone;S.zoneOn[id]=!S.zoneOn[id];
    el.querySelector('.toggle').classList.toggle('on',S.zoneOn[id]);
    hap('medium');saveCache();drawZones();
  });
}
function focusWarning(w){
  initMap();drawMap();
  const all=[];(w.shapes||[]).forEach(s=>(s.points||[]).forEach(p=>all.push(p)));
  if(!all.length) return;
  if(all.length===1)map.setView(all[0],8);
  else map.fitBounds(L.latLngBounds(all),{padding:[45,45]});
}

/* --- рейс --- */
/* Подсказки при вводе порта. onPick -- что сделать с выбранным портом:
   в проверке маршрута его достаточно вписать в поле, а в «Моих портах»
   выбор сразу добавляет порт в рейс. */
function setupPort(i,s,onPick){
  const inp=$(i),sug=$(s);let t=null;
  inp.oninput=()=>{
    clearTimeout(t);const v=inp.value.trim();
    if(v.length<2){sug.classList.remove('on');return}
    t=setTimeout(async()=>{
      try{
        const r=await api('/api/ports?q='+encodeURIComponent(v));
        sug.innerHTML=(r.results||[]).map(p=>`<div data-p="${esc(p.name)}">${esc(p.label)}</div>`).join('');
        sug.classList.toggle('on',(r.results||[]).length>0);
        sug.querySelectorAll('[data-p]').forEach(d=>d.onclick=()=>{
          sug.classList.remove('on');hap();
          if(onPick){ inp.value=''; onPick(d.dataset.p); }
          else inp.value=d.dataset.p;
        });
      }catch(e){sug.classList.remove('on')}
    },220);
  };
  inp.onblur=()=>setTimeout(()=>sug.classList.remove('on'),180);
}
async function runVoyage(){
  const f=$('#pfrom').value.trim(),to=$('#pto').value.trim();
  if(!f||!to){$('#voyout').innerHTML='<div class="empty">Укажи оба порта.</div>';return}
  $('#voyout').innerHTML='<div class="sk card"></div><div class="sk card"></div>';
  hap('medium');
  try{
    const r=await api(`/api/voyage?from=${encodeURIComponent(f)}&to=${encodeURIComponent(to)}&corridor=${S.corridor}`);
    if(r.error){$('#voyout').innerHTML=`<div class="empty">${ico('alert')}${esc(r.error)}</div>`;return}
    const w=r.count===1?'предупреждение':(r.count>=2&&r.count<=4?'предупреждения':'предупреждений');
    const legs=(r.legs||[]).map(l=>esc(l.title)).join(' → ');
    $('#voyout').innerHTML=`
      <div class="voyhead up">
        <div class="big">На маршруте найдено ${r.count} активных ${w}</div>
        <div class="sm">${esc(r.from.label)} → ${esc(r.to.label)} · <span class="mono">${r.distance_nm}</span> миль по маршруту · коридор ±<span class="mono">${r.corridor_nm}</span></div>
        ${legs?`<div class="legs">${ico('route','xs')}<span>${legs}</span></div>`:''}
      </div>
      <div id="vmap"></div>
      ${r.results.length?r.results.map(warnCard).join('')
        :`<div class="empty">${ico('anchor')}По этому маршруту действующих предупреждений с координатами нет.</div>`}`;
    // Координаты концов маршрута нужны сводке с мостика: по ним и позиции
    // с устройства считается остаток пути и пройденная доля.
    try{ localStorage.setItem('navarea_lastvoy',JSON.stringify({
      from:r.from.label,to:r.to.label,distance:r.distance_nm,count:r.count,legs:legs,
      flat:r.from.lat,flon:r.from.lon,tlat:r.to.lat,tlon:r.to.lon,at:Date.now()})); }catch(e){}
    bindWarns();setTimeout(()=>drawVoy(r),80);
  }catch(e){
    $('#voyout').innerHTML=`<div class="empty">${ico('radar')}Нет связи с сервером. Попробуй позже.</div>`;
  }
}
function drawVoy(r){
  if(vmap){vmap.remove();vmap=null}
  vmap=L.map('vmap',{worldCopyJump:true});
  L.tileLayer(BASES.dark.url,{maxZoom:18,subdomains:'abcd',attribution:BASES.dark.attr}).addTo(vmap);
  const line=L.polyline(r.route,{color:'#4d93d6',weight:3,dashArray:'8 7'}).addTo(vmap);
  L.marker([r.from.lat,r.from.lon]).bindPopup(esc(r.from.label)).addTo(vmap);
  L.marker([r.to.lat,r.to.lon]).bindPopup(esc(r.to.label)).addTo(vmap);
  (r.legs||[]).forEach(l=>{
    L.circleMarker([l.lat,l.lon],{radius:5,color:'#6fb3f0',fillColor:'#0b1e30',
      fillOpacity:1,weight:2}).bindPopup(`<b>${esc(l.title)}</b><br>точка поворота`).addTo(vmap);
  });
  r.results.forEach(w=>(w.shapes||[]).forEach(s=>{
    const l=shapeLayer(s.points,s.type,`<b>${esc(w.area_code)} №${esc(w.msg_number||'—')}</b><br>${w.distance_nm} миль от курса`,'#f0a03c',s.radius_nm);
    if(l) l.addTo(vmap);
  }));
  vmap.fitBounds(line.getBounds(),{padding:[28,28]});
}

/* --- навигация --- */
/* ---- Четыре смысловые группы, подразделы лентой сверху ----
   Home    -- состояние рейса, предупреждения, вахта
   Tools   -- все расчёты и тренажёры
   Map     -- NAVAREA, маршрут, погода и поиск-спасание
   My Vessel -- судно, документы, настройки, история
   ASK AI своей группы содержимого не имеет: это главное действие
   приложения, поэтому в нижнем меню оно стоит в центре и выделено. */
const GROUPS={
  home:{t:'Главная',i:'gauge',subs:[
    {v:'dash',t:'Обзор',i:'gauge'},
    {v:'areas',t:'Районы',i:'globe'}]},
  tools:{t:'Инструменты',i:'sliders',subs:[
    {v:'tools',t:'Расчёты',i:'sliders'},
    {v:'dsc',t:'Тренажёры',i:'radar'},
    {v:'refs',t:'Справка',i:'archive'}]},
  ask:{t:'Ask WatchKeeper',i:'compass',subs:[{v:'ask',t:'Ask WatchKeeper',i:'compass'}]},
  map:{t:'Карта',i:'map',subs:[
    {v:'map',t:'Обстановка',i:'map'},
    {v:'cyc',t:'Погода',i:'wave'},
    {v:'zones',t:'Зоны',i:'globe'}]},
  profile:{t:'Моё судно',i:'ship',subs:[
    {v:'ship',t:'Судно',i:'ship'},
    {v:'ports',t:'Мои порты',i:'anchor'},
    {v:'bridge',t:'Документы',i:'flag'},
    {v:'faq',t:'Справка',i:'archive'},
    {v:'settings',t:'Настройки',i:'sliders'}]}
};
const ALL_VIEWS=['dash','areas','map','tools','bridge','refs','radio','dsc','epirb','sart','ship','settings','voy','zones','ask','cyc','ports','faq','support','notif','admin'];
const VIEW_GROUP={};
Object.keys(GROUPS).forEach(g=>GROUPS[g].subs.forEach(x=>VIEW_GROUP[x.v]=g));
// GMDSS-разделы открываются карточками с главного экрана "Инструменты", а не
// отдельными вкладками сверху -- так их не пять в ряд, а по категориям, как
// просили: сначала общий раздел, оборудование ГМССБ внутри него отдельным блоком.
['radio','dsc','epirb','sart'].forEach(v=>VIEW_GROUP[v]='tools');
// Проверка рейса открывается из «Моих портов» и из ассистента, отдельной
// вкладки у неё больше нет: маршрут задаётся списком портов захода.
VIEW_GROUP['voy']='profile';
// Админ-панель живёт в той же группе, что настройки: открывается из них и
// возврат «назад» должен приводить туда же, а не на главную.
['support','faq','admin'].forEach(v=>VIEW_GROUP[v]='profile');
VIEW_GROUP['notif']='home';
let S_GROUP='home';


/* ---- Перетаскивание горизонтальных лент пальцем ----
   Нативная прокрутка в WebView Telegram местами не срабатывает: лента
   двигалась только программно, а рукой стояла на месте. Поэтому таскаем
   сами -- слушаем указатель и двигаем scrollLeft. Обычную прокрутку это
   не ломает: если она работает, наш обработчик просто дублирует её. */
function makeDraggable(el){
  if(!el||el._drag) return;
  el._drag=true;
  let down=false, startX=0, startLeft=0, moved=0;

  const start=(x)=>{ down=true; moved=0; startX=x; startLeft=el.scrollLeft; };
  const move=(x)=>{
    if(!down) return;
    const dx=startX-x;
    moved=Math.abs(dx);
    el.scrollLeft=startLeft+dx;
  };
  const end=()=>{ down=false; };

  el.addEventListener('pointerdown',e=>{ start(e.clientX); },{passive:true});
  el.addEventListener('pointermove',e=>{
    if(!down) return;
    move(e.clientX);
    // как только палец реально поехал -- гасим нажатие на кнопке под ним
    if(moved>6&&e.cancelable) e.preventDefault();
  },{passive:false});
  el.addEventListener('pointerup',end,{passive:true});
  el.addEventListener('pointercancel',end,{passive:true});
  el.addEventListener('pointerleave',end,{passive:true});

  // если ленту протащили, нажатие по кнопке не должно срабатывать
  el.addEventListener('click',e=>{
    if(moved>6){ e.stopPropagation(); e.preventDefault(); moved=0; }
  },true);

  // запасной путь для старых движков без указателей
  el.addEventListener('touchstart',e=>{ if(e.touches[0]) start(e.touches[0].clientX); },{passive:true});
  el.addEventListener('touchmove',e=>{ if(e.touches[0]) move(e.touches[0].clientX); },{passive:true});
  el.addEventListener('touchend',end,{passive:true});
}

function bindDraggableRows(){
  document.querySelectorAll('.subtabs,.cats,.chips').forEach(makeDraggable);
}

function renderSubtabs(){
  const el=$('#subtabs'); if(!el) return;
  const okStats=S.stats&&S.stats.totals;
  const subs=(GROUPS[S_GROUP]||{}).subs||[];
  // один подраздел -- ленту не показываем, она была бы бессмысленной
  if(subs.length<2){ el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  // При четырёх и более разделах счётчики убираем: с ними лента не влезает
  // в ширину телефона, и последняя вкладка уходит за край.
  const showCnt = subs.length <= 3;
  el.innerHTML=subs.map(x=>{
    let cnt='';
    if(!showCnt) return `<button class="subtab ${S.view===x.v?'on':''}" data-sv="${x.v}">${ico(x.i,'sm')}${esc(tr(x.t))}</button>`;
    // Счётчики только если данные действительно пришли: раньше ответ вида
    // {"error": ...} ронял отрисовку подвкладок, а с ней и всё переключение
    // разделов -- нижнее меню внешне переставало работать.
    if(x.v==='areas'&&okStats) cnt=`<span class="cnt">${S.stats.totals.in_force}</span>`;
    if(x.v==='radio'&&RADIO&&Array.isArray(RADIO.stations)) cnt=`<span class="cnt">${RADIO.stations.length}</span>`;
    if(x.v==='tools'&&Array.isArray(TOOLS)) cnt=`<span class="cnt">${TOOLS.length}</span>`;
    return `<button class="subtab ${S.view===x.v?'on':''}" data-sv="${x.v}">${ico(x.i,'sm')}${esc(tr(x.t))}${cnt}</button>`;
  }).join('');
  document.querySelectorAll('[data-sv]').forEach(b=>b.onclick=()=>{hap();switchView(b.dataset.sv)});

  bindDraggableRows();

  // подводим активную вкладку в видимую часть ленты
  try{
    const act=el.querySelector('.subtab.on');
    if(act&&act.scrollIntoView) act.scrollIntoView({inline:'center',block:'nearest',behavior:'smooth'});
  }catch(e){}
}


/* ---- Возврат из раздела ----
   Кнопка ведёт на первый подраздел своей группы, а если человек уже там --
   на главный экран. Так «назад» всегда означает шаг вверх, а не выход из
   приложения. */
function goBack(){
  hap();
  const g=VIEW_GROUP[S.view]||S_GROUP;
  const subs=(GROUPS[g]||{}).subs||[];
  const first=subs[0]&&subs[0].v;
  if(TOOL_CAT){ TOOL_CAT=null; renderTools(); return; }     // внутри раздела расчётов
  if(first&&S.view!==first){ switchView(first); return; }
  if(g!=='home'){ switchGroup('home'); return; }
  switchView('dash');
}

function bindBackButtons(){
  document.querySelectorAll('[data-back]').forEach(b=>{
    if(!b.innerHTML) b.innerHTML=ico('back','sm');
    b.onclick=goBack;
  });
}

function switchView(v){
  S.view=v;
  bump('view',v);
  S_GROUP=VIEW_GROUP[v]||S_GROUP;

  ALL_VIEWS.forEach(x=>{
    const el=$('#v-'+x); if(!el) return;
    if(x===v){el.classList.remove('hidden');el.style.animation='none';void el.offsetWidth;el.style.animation=''}
    else el.classList.add('hidden');
  });
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.g===S_GROUP));
  try{ renderSubtabs(); }catch(e){ console.warn('подвкладки:',e); }
  try{ bindBackButtons(); }catch(e){}

  // Лента районов живёт в карте и в списке районов. На главной её нет:
  // главный экран отвечает на вопрос «что у меня сейчас», а не показывает
  // разбивку по регионам.
  const topCats=$('#cats'); if(topCats) topCats.classList.toggle('hidden', v!=='map'&&v!=='areas');
  const topSearch=$('#topSearch'); if(topSearch) topSearch.classList.toggle('hidden', v!=='areas');
  try{window.scrollTo({top:0,behavior:'smooth'})}catch(e){}

  if(v==='tools') renderTools();
  if(v==='refs') renderRefs();
  if(v==='bridge'){ if(gate('#bridgeBox','bridge')) loadBridge(); }
  if(v==='ship'){ if(gate('#v-ship','vessel')) loadVessel(); }
  if(v==='settings') renderSettings();
  if(v==='cyc'){ renderCyclones(); loadWeatherPorts(); if(!CYC) loadCyclones(); }
  if(v==='ask'){ renderAsk(); loadAskHints().then(renderAsk); setTimeout(bindAskInput,60); }
  if(v==='dsc'){ renderDSC(); loadDSC().then(renderDSC); }
  if(v==='epirb'){ if(gate('#epirbBox','bridge')) loadGmdss().then(()=>renderGmdss('epirb')); }
  if(v==='sart'){ if(gate('#sartBox','bridge')) loadGmdss().then(()=>renderGmdss('sart')); }
  if(v==='radio') setTimeout(()=>{renderRadio();initRmap();if(rmap)rmap.invalidateSize()},70);
  if(v==='dash'){ loadHistory(); loadNotifications(true); }
  if(v==='voy') gate('#v-voy','voyage');
  if(v==='ports'){ if(gate('#v-ports','voyage')) loadPorts(); }
  if(v==='faq') renderFaq();
  if(v!=='support') supPollStop();
  if(v==='support'){ loadSupport(); setTimeout(bindSupportInput,60); supPollStart(); }
  if(v==='notif'){ renderNotif(); loadNotifications().then(markNotifSeen); }
  if(v==='admin'){ renderAdmin(); loadAdmin(); }
  if(v==='zones') renderZones();
  if(v==='map') setTimeout(()=>{initMap();map.invalidateSize();drawZones();drawMap()},70);
  setTimeout(applyLang,30);
}

function switchGroup(g){
  S_GROUP=g;
  const subs=(GROUPS[g]||{}).subs||[];
  // возвращаемся на тот подраздел группы, где были в прошлый раз
  const last=GROUP_LAST[g]||(subs[0]&&subs[0].v);
  if(last) switchView(last);
}
const GROUP_LAST={};
// Обработчики нижнего меню вешаем в защищённом блоке и как можно раньше:
// раньше ошибка в любом другом месте оставляла панель без обработчиков,
// и внешне это выглядело как "кнопки не нажимаются".
// (нижнее меню обрабатывается делегированием в начале скрипта)
{ const ta=$('#toAreas');
  if(ta) ta.onclick=()=>{hap();S.cat='all';renderCats();switchView('areas');renderAreas()}; }
$('#fbtn').onclick=()=>{
  hap();
  const order=['count','new','code'],next=order[(order.indexOf(S.sort)+1)%3];
  S.sort=next;
  const names={count:'По количеству',new:'По новизне',code:'По номеру'};
  const sb=$('#sortBtn');if(sb)sb.textContent=names[next]+' ⇅';
  if(S.view!=='areas')switchView('areas');
  renderAreas();
};
const sb=$('#sortBtn');if(sb)sb.onclick=()=>$('#fbtn').onclick();
document.querySelectorAll('#corr .cat').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('#corr .cat').forEach(x=>x.classList.remove('on'));
  c.classList.add('on');S.corridor=+c.dataset.c;hap();
});
let qt=null;
$('#q').oninput=e=>{
  clearTimeout(qt);
  qt=setTimeout(()=>{
    S.q=e.target.value.trim();
    if(S.q&&S.view!=='areas')switchView('areas');
    renderAreas();
  },240);
};
$('#govoy').onclick=runVoyage;
setupPort('#pfrom','#sfrom');setupPort('#pto','#sto');


/* ---- Экран деталей предупреждения ---- */
let dmap=null, dCur=null;

function openDetail(w){
  dCur=w; hap('medium');
  const sh=w.shapes||[], pts=[];
  sh.forEach(s=>s.points.forEach(p=>pts.push(p)));
  const fav=S.favs.includes(w.area_code);

  $('#dTop').innerHTML=
    `<span class="wtag">${esc(w.area_code)}</span>`+
    (w.geo_source==='source'?`<span class="dchip">${ico('radar','xs')}точная геометрия</span>`:'');
  $('#dTitle').textContent=`№ ${w.msg_number||'без номера'}`;
  $('#dReg').innerHTML = w.region?`${ico('flag','xs')}${esc(w.region)}`:'';
  $('#dFav').className='dbtn'+(fav?' on':'');
  $('#dFav').innerHTML=ico('star');

  const meta=[];
  if(w.issued_at) meta.push(`<span class="dchip">${ico('clock','xs')}${esc(String(w.issued_at).slice(0,24))}</span>`);
  if(sh.length) meta.push(`<span class="dchip">${ico('map','xs')}${sh.length} ${sh.length===1?'объект':'объектов'}</span>`);
  if(w.distance_nm!==undefined) meta.push(`<span class="dchip">${ico('route','xs')}${w.distance_nm} миль от курса</span>`);
  $('#dMeta').innerHTML=meta.join('');

  $('#dText').textContent=w.text||'';

  const names={polygon:'Район',line:'Линия / полоса',point:'Точка',circle:'Круг радиусом'};
  $('#dCoords').innerHTML = pts.length
    ? sh.map((s,i)=>{
        const p=s.points[0];
        return `<div class="dcoord" data-goto="${i}">
          <span class="ct">${names[s.type]||s.type} · ${s.points.length} точ.</span>
          <span class="cv mono">${fmtPos(p[0],p[1])}</span></div>`;
      }).join('')
    : '<div class="ct" style="color:var(--muted);font-size:12.5px">В тексте нет распознанных координат.</div>';

  $('#detail').classList.add('on');
  document.body.style.overflow='hidden';

  setTimeout(()=>{
    if(dmap){dmap.remove();dmap=null}
    if(!pts.length){$('#dmap').innerHTML=
      '<div style="height:100%;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:12.5px">Без координат</div>';return}
    dmap=L.map('dmap',{zoomControl:false,attributionControl:false,worldCopyJump:true});
    L.tileLayer(BASES.dark.url,{maxZoom:18,subdomains:'abcd'}).addTo(dmap);
    sh.forEach(s=>{const l=shapeLayer(s.points,s.type,'','#f0a03c',s.radius_nm); if(l) l.addTo(dmap);});
    if(pts.length===1) dmap.setView(pts[0],8);
    else dmap.fitBounds(L.latLngBounds(pts),{padding:[45,45]});
  },60);

  document.querySelectorAll('[data-goto]').forEach(el=>el.onclick=()=>{
    const s=sh[+el.dataset.goto]; if(!s||!dmap) return;
    hap();
    if(s.points.length===1) dmap.setView(s.points[0],9);
    else dmap.fitBounds(L.latLngBounds(s.points),{padding:[35,35]});
  });
}

function closeDetail(){
  $('#detail').classList.remove('on');
  document.body.style.overflow='';
  if(dmap){dmap.remove();dmap=null}
  dCur=null; hap();
}

$('#dBack').innerHTML=ico('back');
$('#dBack').onclick=closeDetail;
$('#dFav').onclick=async()=>{
  if(!dCur)return; hap('medium');
  const c=dCur.area_code;
  S.favs=S.favs.includes(c)?S.favs.filter(x=>x!==c):S.favs.concat([c]);
  $('#dFav').className='dbtn'+(S.favs.includes(c)?' on':'');
  render();saveCache();
  try{await api('/api/favorites?toggle='+encodeURIComponent(c))}catch(e){}
};
$('#dToMap').onclick=()=>{const w=dCur;closeDetail();if(w){switchView('map');setTimeout(()=>focusWarning(w),90)}};


/* ================= Чек-листы и сертификаты ================= */
let BR=null, curCL=null, clState={};

async function loadBridge(){
  try{ BR=await api('/api/bridge?'); if(BR.error) BR=null; }catch(e){ BR=null; }
  renderBridge();
}
function bindHistory(){
  document.querySelectorAll('[data-delch]').forEach(b=>b.onclick=async ev=>{
    ev.stopPropagation();hap('medium');
    try{ BR=await api('/api/bridge?action=del_checklist&id='+b.dataset.delch); renderBridge(); }catch(e){}
  });
  const cb=$('#clearHist');
  if(cb) cb.onclick=async()=>{
    hap('medium');
    if(!confirm('Удалить всю историю чек-листов? Отменить будет нельзя.')) return;
    try{ BR=await api('/api/bridge?action=clear_checklists'); renderBridge(); }catch(e){}
  };
}
function renderBridge(){
  if(!BR||!BR.templates){
    const box=$('#bridgeBox');
    if(box) box.innerHTML=BR&&BR.error
      ? `<div class="empty">${ico('alert')}Раздел недоступен: ${esc(BR.error)}</div>`
      : '<div class="sk card"></div><div class="sk card"></div>';
    return;
  }
  if(!BR){ $('#bridgeBox').innerHTML='<div class="sk card"></div>'; return; }
  const c=BR.certificates||[], soon=c.filter(x=>x.status==='soon'||x.status==='expired').length;
  const st={expired:'просрочен',soon:'скоро истекает',watch:'под контролем',ok:'в порядке',unknown:'—'};

  let h=`<div class="sech"><h3>Чек-листы</h3></div><div class="grid2">`+
    Object.keys(BR.templates).map((k,i)=>{
      const t=BR.templates[k];
      return `<div class="gcard up" style="animation-delay:${i*45}ms" data-cl="${k}">
        <div class="gtop" style="height:60px">
          <svg class="bgw" viewBox="0 0 800 32" preserveAspectRatio="none">
            <path d="M0 16 q50 -10 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v20 h-800 z" fill="#4d93d6"/>
          </svg>
          <div class="gi">${ico(t.icon)}</div>
        </div>
        <div class="gbody">
          <div class="gname" style="min-height:auto">${esc(t.title)}</div>
          <div class="gsub" style="display:block;margin-top:3px">${t.items.length} пунктов</div>
        </div></div>`;
    }).join('')+`</div>`;

  if((BR.history||[]).length){
    h+=`<div class="sech" style="margin-top:17px"><h3>История · ${BR.history.length}</h3>
        <a id="clearHist">Очистить всё</a></div>`+
      BR.history.slice(0,12).map(x=>{
        const t=(BR.templates[x.template]||{}).title||x.template;
        const pct=x.total?Math.round(x.done/x.total*100):0;
        return `<div class="tres"><span class="tl">${esc(t)}${x.port?' · '+esc(x.port):''}<br>
          <span style="font-size:11px;opacity:.7">${esc(String(x.created_at).slice(0,10))}</span></span>
          <span class="tv" style="font-size:13px">${x.done}/${x.total} · ${pct}%</span>
          <button class="rcopy" data-delch="${x.id}" style="margin-left:9px">${ico('archive','sm')}</button></div>`;
      }).join('');
  }

  h+=`<div class="sech" style="margin-top:17px"><h3>Сертификаты${soon?` · ${soon} требуют внимания`:''}</h3>
      <a id="addCert">Добавить +</a></div>`;
  h+= c.length ? c.map(x=>{
      const cls=x.status==='expired'?'warn':(x.status==='soon'?'warn':'');
      const dl=x.days_left;
      const txt=dl<0?`просрочен на ${-dl} дн`:(dl===0?'истекает сегодня':`осталось ${dl} дн`);
      return `<div class="tres ${cls}">
        <span class="tl"><b style="color:var(--text)">${esc(x.name)}</b>
          ${x.number?`<br><span style="font-size:11px;opacity:.7">№ ${esc(x.number)}</span>`:''}
          <br><span style="font-size:11px;opacity:.7">до ${esc(x.expires)} · ${st[x.status]}</span></span>
        <span style="display:flex;align-items:center;gap:9px">
          <span class="tv" style="font-size:12.5px">${txt}</span>
          <button class="heart" style="width:28px;height:28px;font-size:15px" data-delcert="${x.id}">×</button>
        </span></div>`;
    }).join('')
    : `<div class="empty">${ico('clock')}Сертификатов пока нет. Добавь любой, и бот сам напомнит за 60, 30, 14, 7, 3 и 1 день до истечения.</div>`;

  $('#bridgeBox').innerHTML=h;
  applyLang();

  document.querySelectorAll('[data-cl]').forEach(el=>el.onclick=()=>openChecklist(el.dataset.cl));
  bindHistory();
  const ac=$('#addCert'); if(ac) ac.onclick=openCertForm;
  document.querySelectorAll('[data-delcert]').forEach(b=>b.onclick=async()=>{
    hap('medium');
    try{ await api('/api/bridge?action=del_cert&id='+b.dataset.delcert); }catch(e){}
    loadBridge();
  });
}

function openChecklist(key){
  const t=BR.templates[key]; if(!t) return;
  curCL=key; hap('medium');
  clState={port:'',items:t.items.map(x=>({t:x,done:false}))};
  $('#tName').textContent=t.title;
  $('#tDesc').textContent='Отмечай по ходу дела. Сохранится в историю.';
  $('#tIcon').innerHTML=ico(t.icon,'lg');
  $('#tFields').innerHTML=`<div class="fld"><label>Порт</label>
    <input class="tinput" id="clPort" placeholder="Например Rotterdam"></div>`;
  $('#clPort').oninput=e=>{clState.port=e.target.value};
  drawCL();
  $('#tBack').textContent='Сохранить и закрыть';
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
}
function drawCL(){
  const done=clState.items.filter(i=>i.done).length, tot=clState.items.length;
  $('#tResults').innerHTML=
    `<div class="tres hi"><span class="tl">Выполнено</span>
       <span class="tv">${done} из ${tot}</span></div>`+
    clState.items.map((i,n)=>
      `<div class="tres" data-cli="${n}" style="cursor:pointer">
         <span class="tl" style="${i.done?'text-decoration:line-through;opacity:.5':''}">${esc(i.t)}</span>
         <span class="toggle ${i.done?'on':''}" style="width:40px;height:23px"></span>
       </div>`).join('');
  document.querySelectorAll('[data-cli]').forEach(el=>el.onclick=()=>{
    const n=+el.dataset.cli;
    clState.items[n].done=!clState.items[n].done;
    hap(); drawCL();
  });
}
async function saveCL(){
  if(!curCL) return;
  const done=clState.items.every(i=>i.done);
  try{
    await api('/api/bridge?action=save_checklist&template='+encodeURIComponent(curCL)+
      '&port='+encodeURIComponent(clState.port||'')+
      '&items='+encodeURIComponent(JSON.stringify(clState.items))+
      '&completed='+(done?'1':'0'));
  }catch(e){}
  curCL=null; loadBridge();
}

function openCertForm(){
  hap('medium'); curCL=null;
  $('#tName').textContent='Новый сертификат';
  $('#tDesc').textContent='Бот напомнит заранее, когда подойдёт срок';
  $('#tIcon').innerHTML=ico('clock','lg');
  const opts=(BR.common_certs||[]).map(c=>`<option value="${esc(c)}">`).join('');
  $('#tFields').innerHTML=`
    <div class="fld"><label>Название</label>
      <input class="tinput" id="cName" list="certList" placeholder="Например SSCEC">
      <datalist id="certList">${opts}</datalist></div>
    <div class="fld"><label>Номер (необязательно)</label>
      <input class="tinput" id="cNum" placeholder="№"></div>
    <div class="fld"><label>Действует до</label>
      <button type="button" class="datefield" id="cExp" data-iso="">
        <span class="dv none">${esc(tr('Не задана'))}</span>
        <span class="dico">${ico('clock','sm')}</span>
      </button></div>
    <div class="fld"><label>Заметка (необязательно)</label>
      <input class="tinput" id="cNote" placeholder="Где выдан, что нужно для продления"></div>`;
  $('#cExp').onclick=()=>{
    const b=$('#cExp');
    dpOpen(b.dataset.iso||'', 'Действует до', iso=>{
      b.dataset.iso=iso;
      const v=b.querySelector('.dv');
      v.className='dv'+(iso?'':' none');
      v.textContent=iso?dpHuman(iso):tr('Не задана');
    });
  };
  $('#tResults').innerHTML=
    `<button class="btn wide" id="cSave">Сохранить сертификат</button>`;
  $('#cSave').onclick=async()=>{
    const n=$('#cName').value.trim(), e=$('#cExp').dataset.iso;
    if(!n||!e){ $('#tResults').insertAdjacentHTML('beforeend',
      '<div class="tres warn" style="margin-top:9px"><span class="tl">Заполни название и дату</span></div>'); return; }
    hap('medium');
    try{
      await api('/api/bridge?action=add_cert&name='+encodeURIComponent(n)+
        '&number='+encodeURIComponent($('#cNum').value.trim())+
        '&expires='+encodeURIComponent(e)+
        '&notes='+encodeURIComponent($('#cNote').value.trim()));
    }catch(err){}
    closeTool(); loadBridge();
  };
  $('#tBack').textContent='Отмена';
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
}

/* ---- Справочники и графики ---- */
let HIST=null;

async function loadHistory(){
  try{ HIST=await api('/api/history?days=30'); }catch(e){ HIST=null; }
  renderHistory();
}
function renderHistory(){
  const box=$('#histBox'); if(!box) return;
  if(!HIST){ box.innerHTML='<div class="sk card"></div>'; return; }
  const h=HIST.history||[], heat=HIST.heat||[];

  let g='';
  if(h.length>1){
    const max=Math.max(...h.map(x=>x.in_force),1);
    const w=100/h.length;
    const pts=h.map((x,i)=>`${(i*w+w/2).toFixed(2)},${(100-x.in_force/max*88).toFixed(2)}`).join(' ');
    g=`<div class="chart">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#f0a03c" stop-opacity=".45"/>
            <stop offset="100%" stop-color="#f0a03c" stop-opacity="0"/></linearGradient></defs>
          <polygon points="0,100 ${pts} 100,100" fill="url(#cg)"/>
          <polyline points="${pts}" fill="none" stroke="#f0a03c" stroke-width="1.4"
            vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
        </svg>
        <div class="chartAx"><span>${esc(h[0].day.slice(5))}</span>
          <span>максимум ${max}</span><span>${esc(h[h.length-1].day.slice(5))}</span></div>
       </div>`;
  } else {
    g=`<div class="hint">График появится, когда накопятся данные за несколько дней. Снимок делается раз в сутки.</div>`;
  }

  const mx=HIST.max_area||1;
  const bars=heat.slice(0,12).map(a=>
    `<div class="heat" data-heat="${esc(a.code)}">
       <span class="hc">${esc(a.code.replace('COASTAL:','Б'))}</span>
       <span class="hb"><i style="width:${Math.max(3,a.in_force/mx*100)}%"></i></span>
       <span class="hn mono">${a.in_force}</span>
     </div>`).join('');

  box.innerHTML=`<div class="sech"><h3>Динамика за 30 дней</h3></div>${g}
    <div class="sech" style="margin-top:15px"><h3>Где сейчас горячо</h3></div>${bars}`;
  document.querySelectorAll('[data-heat]').forEach(el=>el.onclick=()=>{
    S.cat=el.dataset.heat; hap(); renderCats(); switchView('areas'); renderAreas();
  });
}

function openFlags(){
  hap('medium'); curCL=null;
  $('#tName').textContent='Сигнальные флаги';
  $('#tDesc').textContent='Международный свод сигналов, однофлажные значения';
  $('#tIcon').innerHTML=ico('flag','lg');
  $('#tFields').innerHTML=`<div class="fld"><label>Поиск по букве или значению</label>
    <input class="tinput" id="flagQ" placeholder="Например O или водолаз"></div>`;
  const draw=q=>{
    const k=Object.keys(FLAGS).filter(x=>!q||x.toLowerCase().includes(q)||
      FLAGS[x][0].toLowerCase().includes(q)||FLAGS[x][1].toLowerCase().includes(q));
    $('#tResults').innerHTML=k.length?k.map(x=>`
      <div class="tres" style="align-items:flex-start">
        <span style="display:flex;gap:11px;align-items:center;flex:1;min-width:0">
          <svg viewBox="0 0 60 40" style="width:52px;height:35px;flex:none;border-radius:4px;border:1px solid var(--line)">${FLAGS[x][2]}</svg>
          <span class="tl" style="flex:1"><b style="color:var(--text);font-size:14px">${x} · ${esc(FLAGS[x][0])}</b>
            <br>${esc(FLAGS[x][1])}</span>
        </span>
      </div>`).join('') : `<div class="empty">${ico('search')}Ничего не нашлось.</div>`;
  };
  draw('');
  $('#flagQ').oninput=e=>draw(e.target.value.trim().toLowerCase());
  $('#tBack').textContent='Назад';
  $('#tool').classList.add('on'); document.body.style.overflow='hidden';
}

function openColreg(){
  hap('medium'); curCL=null;
  $('#tName').textContent='МППСС-72';
  $('#tDesc').textContent='Ключевые правила расхождения, кратко своими словами';
  $('#tIcon').innerHTML=ico('alert','lg');
  $('#tFields').innerHTML=`<div class="fld"><label>Поиск по номеру или теме</label>
    <input class="tinput" id="crQ" placeholder="Например 15 или обгон"></div>`;
  const draw=q=>{
    const list=COLREG.filter(r=>!q||r[0].includes(q)||r[1].toLowerCase().includes(q)||r[2].toLowerCase().includes(q));
    $('#tResults').innerHTML=list.length?list.map(r=>`
      <div class="tres" style="flex-direction:column;align-items:flex-start;gap:6px">
        <span class="wtag">Правило ${esc(r[0])}</span>
        <b style="font-size:14px">${esc(r[1])}</b>
        <span class="tl" style="text-align:left">${esc(r[2])}</span>
      </div>`).join('')+
      `<div class="hint" style="margin-top:11px">Это краткий пересказ для быстрого напоминания. Юридическую силу имеет официальный текст конвенции.</div>`
      : `<div class="empty">${ico('search')}Ничего не нашлось.</div>`;
  };
  draw('');
  $('#crQ').oninput=e=>draw(e.target.value.trim().toLowerCase());
  $('#tBack').textContent='Назад';
  $('#tool').classList.add('on'); document.body.style.overflow='hidden';
}

function openGmdss(){
  hap('medium'); curCL=null;
  $('#tName').textContent='Частоты GMDSS';
  $('#tDesc').textContent='Бедствие, безопасность, NAVTEX, буи';
  $('#tIcon').innerHTML=ico('radar','lg');
  $('#tFields').innerHTML=`<div class="fld"><label>Поиск</label>
    <input class="tinput" id="gQ" placeholder="Например NAVTEX или 2182"></div>`;
  const draw=q=>{
    const list=GMDSS.filter(r=>!q||r.join(' ').toLowerCase().includes(q));
    $('#tResults').innerHTML=list.length?list.map(r=>`
      <div class="tres">
        <span class="tl"><b style="color:var(--text)">${esc(r[0])}</b> · ${esc(r[1])}
          <br><span style="font-size:11px;opacity:.75">${esc(r[3])}</span></span>
        <span class="tv" style="font-size:13px">${esc(r[2])}</span>
      </div>`).join('') : `<div class="empty">${ico('search')}Ничего не нашлось.</div>`;
  };
  draw('');
  $('#gQ').oninput=e=>draw(e.target.value.trim().toLowerCase());
  $('#tBack').textContent='Назад';
  $('#tool').classList.add('on'); document.body.style.overflow='hidden';
}

function openArchive(){
  hap('medium'); curCL=null;
  $('#tName').textContent='Архив предупреждений';
  $('#tDesc').textContent='Отменённые и снятые с силы, поиск за всё время';
  $('#tIcon').innerHTML=ico('archive','lg');
  $('#tFields').innerHTML=`<div class="fld"><label>Поиск по номеру, тексту или координатам</label>
    <input class="tinput" id="arQ" placeholder="Например 700 или BUOY"></div>`;
  $('#tResults').innerHTML=`<div class="hint">Введи запрос, чтобы искать по архиву.</div>`;
  let t=null;
  $('#arQ').oninput=e=>{
    clearTimeout(t); const q=e.target.value.trim();
    if(q.length<2){ $('#tResults').innerHTML=`<div class="hint">Введи хотя бы два символа.</div>`; return; }
    $('#tResults').innerHTML='<div class="sk card"></div>';
    t=setTimeout(async()=>{
      try{
        const r=await api('/api/warnings?archived=1&limit=60&q='+encodeURIComponent(q));
        $('#tResults').innerHTML=(r.results||[]).length
          ? r.results.map(w=>`<div class="tres" style="flex-direction:column;align-items:flex-start;gap:5px">
              <span class="wtag">${esc(w.area_code)} №${esc(w.msg_number||'—')}${w.is_cancelled?' · отменено':''}</span>
              <span class="tl" style="text-align:left">${esc((w.text||'').slice(0,200))}…</span></div>`).join('')
          : `<div class="empty">${ico('search')}В архиве ничего не нашлось.</div>`;
      }catch(err){ $('#tResults').innerHTML=`<div class="empty">${ico('radar')}Нет связи.</div>`; }
    },260);
  };
  $('#tBack').textContent='Назад';
  $('#tool').classList.add('on'); document.body.style.overflow='hidden';
}

const REFS=[
 {id:'flags',icon:'flag',name:'Сигнальные флаги',desc:'Весь международный свод с расшифровкой',open:openFlags},
 {id:'colreg',icon:'alert',name:'МППСС-72',desc:'Ключевые правила расхождения',open:openColreg},
 {id:'gmdss',icon:'radar',name:'Частоты GMDSS',desc:'Бедствие, NAVTEX, буи, каналы',open:openGmdss},
 {id:'archive',icon:'archive',name:'Архив наварий',desc:'Поиск по отменённым за всё время',open:openArchive}
];
function renderRefs(){
  const box=$('#refBox'); if(!box) return;
  box.innerHTML=`<div class="sech"><h3>Справочники</h3></div><div class="grid2">`+
    REFS.map((r,i)=>`<div class="gcard up" style="animation-delay:${i*40}ms" data-ref="${r.id}">
      <div class="gtop" style="height:60px">
        <svg class="bgw" viewBox="0 0 800 32" preserveAspectRatio="none">
          <path d="M0 16 q50 -10 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v20 h-800 z" fill="#4d93d6"/>
        </svg>
        <div class="gi">${ico(r.icon)}</div>
      </div>
      <div class="gbody"><div class="gname" style="min-height:auto">${esc(r.name)}</div>
        <div class="gsub" style="display:block;margin-top:3px">${esc(r.desc)}</div></div>
    </div>`).join('')+`</div>`;
  document.querySelectorAll('[data-ref]').forEach(el=>el.onclick=()=>{
    const r=REFS.find(x=>x.id===el.dataset.ref); if(r) r.open();
  });
}


/* ---- Радиостанции MF/HF DSC ---- */
let RADIO=null, rmap=null, rLayers=[], rRegion='all';

async function loadRadio(){
  if(RADIO) return RADIO;
  try{
    RADIO=await api('/api/stations');
    localStorage.setItem('navarea_radio',JSON.stringify(RADIO));
  }catch(e){
    try{ RADIO=JSON.parse(localStorage.getItem('navarea_radio')||'null'); }catch(e2){}
  }
  return RADIO;
}
const replyClass=r=>r==='auto'?'ok':(r==='reliable'?'am':'no');

async function renderRadio(){
  const d=await loadRadio();
  if(d&&d.error){ $('#radiolist').innerHTML=`<div class="empty">${ico('radar')}Раздел недоступен.</div>`; return; }
  if(!d){ $('#radiolist').innerHTML=`<div class="empty">${ico('radar')}Не удалось загрузить справочник станций. Попробуй позже.</div>`; return; }

  const counts={all:d.stations.length};
  Object.keys(d.regions).forEach(k=>counts[k]=d.stations.filter(s=>s.r===k).length);
  $('#rchips').innerHTML=
    `<div class="cat ${rRegion==='all'?'on':''}" data-rr="all">${ico('globe')}
       <span class="cn">Все</span><span class="cb">${counts.all}</span></div>`+
    Object.keys(d.regions).map(k=>
      `<div class="cat ${rRegion===k?'on':''}" data-rr="${k}">${ico('radar')}
         <span class="cn">${esc(d.regions[k].split(' ')[0])}</span>
         <span class="cb">${counts[k]}</span></div>`).join('');
  document.querySelectorAll('[data-rr]').forEach(c=>c.onclick=()=>{
    rRegion=c.dataset.rr;hap();renderRadio();drawStations();
  });

  const list=d.stations.filter(s=>rRegion==='all'||s.r===rRegion);
  const best=list.filter(s=>s.reply!=='normal');
  const rest=list.filter(s=>s.reply==='normal');

  let h='';
  if(best.length){
    h+=`<div class="sech"><h3>Отвечают надёжнее всего</h3></div>`+best.map(stCard).join('');
  }
  if(rest.length){
    h+=`<div class="sech" style="margin-top:16px"><h3>Остальные станции</h3></div>`+rest.map(stCard).join('');
  }
  $('#radiolist').innerHTML=h||`<div class="empty">${ico('radar')}В этом регионе станций нет.</div>`;

  document.querySelectorAll('[data-mmsi]').forEach(b=>b.onclick=ev=>{
    ev.stopPropagation();
    const m=b.dataset.mmsi;
    try{
      navigator.clipboard.writeText(m);
      b.classList.add('done'); b.innerHTML=ico('anchor','sm');
      setTimeout(()=>{b.classList.remove('done');b.innerHTML=ico('flag','sm')},1400);
    }catch(e){}
    hap('medium');
  });
  document.querySelectorAll('[data-st]').forEach(c=>c.onclick=ev=>{
    if(ev.target.closest('button')) return;
    const s=d.stations.find(x=>x.m===c.dataset.st);
    if(s){ switchView('radio'); focusStation(s); }
  });
}

function stCard(s,i){
  const cls=s.reply==='auto'?'auto':(s.reply==='reliable'?'reliable':'');
  const lbl=(RADIO.reply_labels||{})[s.reply]||{t:'',d:''};
  const tagCls=s.reply==='auto'?'ok':(s.reply==='reliable'?'am':'');
  return `<div class="rcard ${cls} up" style="animation-delay:${Math.min((i||0)*40,300)}ms" data-st="${s.m}">
    <div class="rtop">
      <div class="rwave"><i></i><i></i><i></i>${ico('radar')}</div>
      <div class="rmid">
        <div class="rname">${esc(s.n)}</div>
        <div class="rmmsi mono">${esc(s.m)}</div>
      </div>
      <button class="rcopy" data-mmsi="${s.m}">${ico('flag','sm')}</button>
    </div>
    <div class="rcov">${esc(s.c)}</div>
    <div class="rtags">
      <span class="rtag ${tagCls}">${esc(lbl.t)}</span>
      ${s.f&&s.f!=='—'?`<span class="rtag">${esc(s.f)}</span>`:''}
    </div>
  </div>`;
}

function initRmap(){
  if(rmap) return;
  rmap=L.map('rmap',{worldCopyJump:true}).setView([25,20],2);
  L.tileLayer(BASES.dark.url,{maxZoom:18,subdomains:'abcd',attribution:BASES.dark.attr}).addTo(rmap);
  drawStations();
}
function drawStations(){
  if(!rmap||!RADIO) return;
  rLayers.forEach(l=>rmap.removeLayer(l)); rLayers=[];
  const colors={auto:'#3fc97f',reliable:'#f0a03c',normal:'#7f96ac'};
  RADIO.stations.filter(s=>rRegion==='all'||s.r===rRegion).forEach(s=>{
    const c=colors[s.reply]||colors.normal;
    const lbl=(RADIO.reply_labels||{})[s.reply]||{t:'',d:''};
    const badge=s.reply==='auto'?'ok':(s.reply==='reliable'?'am':'no');
    const m=L.circleMarker([s.lat,s.lon],{
      radius:s.reply==='normal'?6:9, color:'#fff', weight:2,
      fillColor:c, fillOpacity:.92, className:'station-dot'
    }).bindPopup(
      `<div class="rpop">
         <div class="pn">${esc(s.n)}</div>
         <div class="pm">${esc(s.m)}</div>
         <div class="pr">${esc(s.c)}${s.f&&s.f!=='—'?'<br>Частота: '+esc(s.f):''}</div>
         <span class="pb ${badge}">${esc(lbl.t)}</span>
         <div class="pr" style="margin-top:6px">${esc(lbl.d)}</div>
       </div>`,{maxWidth:250});
    m.addTo(rmap); rLayers.push(m);
  });
}
function focusStation(s){
  initRmap();
  setTimeout(()=>{
    rmap.invalidateSize();
    rmap.setView([s.lat,s.lon],5,{animate:true});
    const t=rLayers.find(l=>{
      const ll=l.getLatLng();
      return Math.abs(ll.lat-s.lat)<0.01&&Math.abs(ll.lng-s.lon)<0.01;
    });
    if(t) setTimeout(()=>t.openPopup(),420);
  },80);
}


/* ---- Тариф, пробный период, платные разделы ---- */
let ACC=null;

async function loadAccess(){
  try{ ACC=await api('/api/access'); localStorage.setItem('navarea_access',JSON.stringify(ACC)); }
  catch(e){ try{ ACC=JSON.parse(localStorage.getItem('navarea_access')||'null'); }catch(e2){} }
  renderTrialBar();
  return ACC;
}
const isPaid=()=>!!(ACC&&ACC.premium);
/* Название тарифа сервер отдаёт на двух языках: в пробном периоде в нём
   стоит число дней, и словарём приложения такую строку не перевести. */
const accTitle=()=>{
  if(!ACC) return '—';
  return (LANG==='en'&&ACC.title_en) ? ACC.title_en : (ACC.title||'—');
};
const featureName=k=>((ACC&&ACC.paid_features)||{})[k]||'';

function renderTrialBar(){
  const el=$('#trialbar'); if(!el||!ACC) return;
  // тарифы выключены на время отладки либо это владелец -- баннер не нужен
  if(ACC.paywall===false||ACC.tier==='open'||ACC.tier==='owner'){ el.classList.add('hidden'); return; }
  el.classList.remove('hidden');

  if(ACC.tier==='trial'){
    const d=(ACC.trial&&ACC.trial.days_left)||0;
    el.className='trialbar';
    el.innerHTML=`<div class="ti">${ico('star')}</div>
      <div class="tt"><div class="t1">Пробный период · осталось ${d} дн.</div>
        <div class="t2">Открыты все разделы. Дальше ${ACC.price_stars} ⭐ в месяц, это примерно 2 доллара.</div></div>
      <span class="tg">Подробнее →</span>`;
  } else if(ACC.tier==='premium'){
    el.className='trialbar';
    el.innerHTML=`<div class="ti">${ico('star')}</div>
      <div class="tt"><div class="t1">Premium активен</div>
        <div class="t2">Открыты все разделы. Спасибо, что поддерживаешь проект.</div></div>`;
  } else {
    // Если пробный уже отработал на этом устройстве под другим аккаунтом --
    // говорим об этом прямо, а не молчим о пропавшем пробном периоде.
    const blocked=(LANG==='en'&&ACC.trial_blocked_text_en)
      ? ACC.trial_blocked_text_en : ACC.trial_blocked_text;
    el.className='trialbar free';
    el.innerHTML=`<div class="ti">${ico('lighthouse')}</div>
      <div class="tt"><div class="t1">Бесплатный тариф</div>
        <div class="t2">${blocked?esc(blocked)
          :`Два района, базовые расчёты и справочники. Остальное — ${ACC.price_stars} ⭐ в месяц.`}</div></div>
      <span class="tg">Открыть всё →</span>`;
  }
  el.onclick=openPlans;
}

/* закрывает раздел, если он платный и доступа нет */
function gate(sectionId, feature){
  const el=$(sectionId); if(!el) return true;
  const old=el.querySelector('.lockover'); if(old) old.remove();
  el.classList.remove('locked');
  // Пока сведения о доступе не пришли -- ничего не закрываем: иначе
  // раздел блокируется на ровном месте при медленной сети.
  if(!ACC) return true;
  if(ACC.paywall===false) return true;
  if(isPaid()) return true;

  el.classList.add('lockwrap','locked');
  const ov=document.createElement('div');
  ov.className='lockover';
  ov.innerHTML=`<div class="li">${ico('star','lg')}</div>
    <div class="lt">${esc(featureName(feature))}</div>
    <div class="ls">Раздел входит в Premium — ${ACC?ACC.price_stars:100} ⭐ в месяц, около 2 долларов.${
      (ACC&&ACC.trial_days>0)?' Первые '+ACC.trial_days+' дн. после установки всё открыто.':''}</div>
    <button class="btn" id="lockBtn">Что входит в Premium</button>`;
  el.appendChild(ov);
  const b=ov.querySelector('#lockBtn'); if(b) b.onclick=openPlans;
  return false;
}

function openPlans(){
  hap('medium');
  const price=ACC?ACC.price_stars:100;
  const paid=(ACC&&ACC.paid_features)||{};
  $('#tName').textContent='Тарифы';
  { const b=$('#tBackTitle'); if(b) b.textContent='Тарифы'; }
  $('#tDesc').textContent='Что открыто сейчас и что даёт Premium';
  $('#tIcon').innerHTML=ico('star','lg');
  $('#tFields').innerHTML=`
    <div class="plans">
      <div class="plan gray ${!isPaid()?'on':''}">
        <div class="pt"><span>Бесплатно</span><span class="pp">0</span></div>
        <ul>
          <li>Два района NAVAREA с уведомлениями</li>
          <li>Карта всех действующих предупреждений</li>
          <li>Расчёты безопасности: запас под килём, проседание, CPA/TCPA, точка перекладки, якорь, габарит под мостом</li>
          <li>Расстояние, курс, ETA, координаты, единицы, Бофорт, светила</li>
          <li>Станции MF/HF DSC и справочные зоны</li>
          <li>Пять вопросов ассистенту в день</li>
        </ul>
      </div>
      <div class="plan ${isPaid()?'on':''}">
        <div class="pt"><span>Premium</span><span class="pp">${price} ⭐ / мес</span></div>
        <ul>${Object.keys(paid).map(k=>`<li>${esc(paid[k])}</li>`).join('')}</ul>
      </div>
    </div>
    <div class="hint">${ico('alert','xs')} Расчёты, от которых зависит безопасность, остаются бесплатными навсегда: брать за них деньги неправильно. Платно то, что экономит время и ведёт учёт.</div>`;
  $('#tResults').innerHTML = isPaid()
    ? `<div class="tres hi"><span class="tl">Сейчас у тебя</span><span class="tv">${esc(accTitle())}</span></div>`
    : `<button class="btn wide" id="buyBtn">Оформить за ${price} ⭐ в месяц</button>
       <div class="buystate" id="buyState"></div>`;
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
  curTool=null;
  applyLang();

  const bb=$('#buyBtn');
  if(bb) bb.onclick=()=>startPurchase(bb);
}

/* ---- Оплата подписки прямо из приложения ----
   Сервер делает ссылку на счёт (createInvoiceLink со звёздами), а Telegram
   открывает по ней своё окно оплаты поверх приложения. Раньше кнопка просто
   закрывала Mini App -- со стороны это и выглядело как «выкинуло на главную».*/
const BUY_ERR={
  unauthorized:'Оплата доступна только внутри Telegram. Открой приложение кнопкой в чате с ботом.',
  already_premium:'Подписка уже активна.',
  owner:'Ты владелец бота, Premium и так открыт.',
  no_token:'Бот не настроен: не задан токен.',
  network:'Нет связи с Telegram. Попробуй ещё раз, когда появится сеть.',
  telegram_error:'Telegram не выдал счёт. Проверь, что у бота включены платежи звёздами.'
};
function buySay(text, cls){
  const el=$('#buyState'); if(!el) return;
  el.className='buystate'+(cls?' '+cls:'');
  el.textContent=text||'';
}
async function startPurchase(btn){
  hap('medium');
  if(btn){ btn.disabled=true; btn.textContent=tr('Готовлю счёт…'); }
  buySay('');
  let r=null;
  try{ r=await api('/api/invoice'); }
  catch(e){ r={error:'network'}; }

  const restore=()=>{
    if(!btn) return;
    btn.disabled=false;
    btn.textContent=tr('Оформить за')+' '+((ACC&&ACC.price_stars)||100)+' ⭐ '+tr('в месяц');
  };

  if(!r||r.error||!r.link){
    restore();
    const key=(r&&r.error)||'network';
    buySay(tr(BUY_ERR[key]||'Не удалось получить счёт. Попробуй ещё раз.')
           +((r&&r.detail)?(' ('+r.detail+')'):''),'no');
    if(key==='already_premium'){ loadAccess().then(()=>{ closeTool(); renderSettings(); }); }
    return;
  }

  restore();

  // openInvoice есть начиная с Bot API 6.1; если WebView старее -- открываем
  // ссылку обычным способом, окно оплаты всё равно появится.
  if(TG&&typeof TG.openInvoice==='function'){
    try{
      TG.openInvoice(r.link, async status=>{
        if(status==='paid'){
          hap('heavy');
          buySay(tr('Оплачено. Premium активирован.'),'ok');
          await loadAccess();
          closeTool(); renderSettings(); render();
          // Бот отмечает подписку, когда до него дойдёт сообщение об оплате.
          // Иногда это на секунду позже окна -- перечитываем ещё раз.
          setTimeout(()=>loadAccess().then(()=>{ renderSettings(); render(); }), 2500);
        } else if(status==='cancelled'){
          buySay(tr('Оплата отменена.'));
        } else if(status==='failed'){
          buySay(tr('Оплата не прошла. Попробуй ещё раз.'),'no');
        } else {
          buySay(tr('Счёт закрыт. Подписка не оформлена.'));
        }
      });
      return;
    }catch(e){}
  }
  try{ TG.openTelegramLink(r.link); }
  catch(e){ window.open(r.link,'_blank'); }
}

/* ---- Автопродление подписки ----
   Кнопка отмены должна быть там же, где кнопка оплаты. Раньше отменить
   можно было только командой /cancel_subscription в чате или в настройках
   самого Telegram -- человек, который платил внутри приложения, искал
   отмену здесь и не находил её. */
function subDate(iso){
  if(!iso) return '';
  const d=new Date(iso);
  if(isNaN(d)) return String(iso).slice(0,10);
  return String(d.getDate()).padStart(2,'0')+'.'
        +String(d.getMonth()+1).padStart(2,'0')+'.'+d.getFullYear();
}
function subSay(text, cls){
  const el=$('#subState'); if(!el) return;
  el.className='buystate'+(cls?' '+cls:'');
  el.textContent=text||'';
}
const SUB_ERR={
  unauthorized:'Подпиской можно управлять только внутри Telegram.',
  no_payment:'Платёж не найден — отменять нечего.',
  network:'Нет связи с Telegram. Попробуй ещё раз, когда появится сеть.',
  telegram_error:'Telegram не принял отмену. Попробуй через Настройки Telegram → Мои звёзды → Подписки.'
};
async function toggleAutorenew(){
  const on=!!(ACC&&ACC.can_manage_sub&&!ACC.sub_cancelled);
  if(on&&!confirm(tr('Отключить автопродление? Оплаченный период доработает до конца, дальше списаний не будет.'))) return;
  hap('medium');
  subSay(tr(on?'Отключаю…':'Включаю…'));

  let r=null;
  try{ r=await api('/api/subscription?action='+(on?'cancel':'resume')); }
  catch(e){ r={error:'network'}; }

  if(!r||r.error){
    const key=(r&&r.error)||'network';
    subSay(tr(SUB_ERR[key]||'Не получилось. Попробуй ещё раз.')
           +((r&&r.detail)?(' ('+r.detail+')'):''),'no');
    return;
  }
  // Перечитываем доступ целиком: состояние подписки приходит в /api/access,
  // и настройки рисуются из него -- иначе переключатель остался бы старым.
  await loadAccess();
  renderSettings();
  subSay(tr(on?'Автопродление отключено. Premium доработает до конца оплаченного периода.'
              :'Автопродление включено.'),'ok');
}


/* ================= Выбор даты =================
   Свой календарь. Системный на телефоне отдаёт change на каждый
   прокрученный барабан -- год, месяц, день по отдельности, -- и раздел,
   который на это перерисовывается, закрывал окно на середине выбора.
   Здесь наружу уходит одна готовая дата и только по кнопке «Готово». */
const DP_MON=['Январь','Февраль','Март','Апрель','Май','Июнь',
              'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
const DP_MON_SHORT=['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];
const DP_WK=['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
const DP={y:0,m:0,d:0,cb:null,mode:'day',title:''};

const dpPad=n=>String(n).padStart(2,'0');
const dpIso=(y,m,d)=>y+'-'+dpPad(m+1)+'-'+dpPad(d);
function dpParse(iso){
  const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso||''));
  return m?{y:+m[1],m:+m[2]-1,d:+m[3]}:null;
}
function dpHuman(iso){
  const p=dpParse(iso);
  return p?dpPad(p.d)+' '+tr(DP_MON_SHORT[p.m])+' '+p.y:'';
}
const dpDaysIn=(y,m)=>new Date(Date.UTC(y,m+1,0)).getUTCDate();

/* Открыть календарь. value -- ГГГГ-ММ-ДД или пусто, cb получает
   готовую строку (или пустую, если нажали «Очистить»). */
function dpOpen(value,title,cb){
  const p=dpParse(value), now=new Date();
  DP.y = p?p.y:now.getFullYear();
  DP.m = p?p.m:now.getMonth();
  DP.d = p?p.d:0;              // 0 -- день ещё не выбран, «Готово» не активна
  DP.cb=cb; DP.mode='day'; DP.title=title||'Выбери дату';
  dpEnsure();
  $('#dpick').classList.add('on');
  document.body.style.overflow='hidden';
  dpDraw();
  hap();
}
function dpClose(){
  const el=$('#dpick'); if(!el) return;
  el.classList.remove('on');
  if(!$('#tool').classList.contains('on')&&!$('#detail').classList.contains('on'))
    document.body.style.overflow='';
  DP.cb=null;
}
function dpEnsure(){
  if($('#dpick')) return;
  const el=document.createElement('div');
  el.className='dpick'; el.id='dpick';
  el.innerHTML='<div class="dpbox" id="dpbox"></div>';
  document.body.appendChild(el);
  // тап мимо окна -- то же, что «Отмена»: ничего не сохраняем
  el.addEventListener('pointerdown',e=>{ if(e.target===el) dpClose(); });
}
function dpDraw(){
  const box=$('#dpbox'); if(!box) return;
  const today=new Date();
  const tY=today.getFullYear(), tM=today.getMonth(), tD=today.getDate();

  let body='';
  if(DP.mode==='year'){
    const from=Math.min(DP.y,tY)-6, list=[];
    for(let y=from;y<from+24;y++) list.push(y);
    body=`<div class="dpgrid2">${list.map(y=>
      `<div class="dpc ${y===DP.y?'on':''}" data-dpy="${y}">${y}</div>`).join('')}</div>`;
  } else if(DP.mode==='month'){
    body=`<div class="dpgrid2">${DP_MON_SHORT.map((n,i)=>
      `<div class="dpc ${i===DP.m?'on':''}" data-dpm="${i}">${esc(tr(n))}</div>`).join('')}</div>`;
  } else {
    // понедельник первым, как принято в судовых документах
    const first=new Date(Date.UTC(DP.y,DP.m,1)).getUTCDay();
    const lead=(first+6)%7;
    const days=dpDaysIn(DP.y,DP.m), prev=dpDaysIn(DP.y,DP.m-1);
    let cells='';
    for(let i=lead;i>0;i--) cells+=`<div class="dpd mut">${prev-i+1}</div>`;
    for(let d=1;d<=days;d++){
      const isToday=(DP.y===tY&&DP.m===tM&&d===tD);
      cells+=`<div class="dpd ${DP.d===d?'on':''} ${isToday?'today':''}" data-dpd="${d}">${d}</div>`;
    }
    const tail=(7-((lead+days)%7))%7;
    for(let d=1;d<=tail;d++) cells+=`<div class="dpd mut">${d}</div>`;
    body=`<div class="dpwk">${DP_WK.map(w=>`<span>${esc(tr(w))}</span>`).join('')}</div>
          <div class="dpgrid">${cells}</div>`;
  }

  box.innerHTML=`
    <div class="dplabel">${esc(tr(DP.title))}</div>
    <div class="dphead">
      <button class="dpnav" id="dpPrev">‹</button>
      <div class="dptitle" id="dpTitle">${DP.mode==='year'
        ? esc(tr('Выбери год'))
        : DP.mode==='month'
          ? DP.y
          : esc(tr(DP_MON[DP.m]))+' '+DP.y}</div>
      <button class="dpnav" id="dpNext">›</button>
    </div>
    ${body}
    <div class="dpsel">${DP.d
      ? esc(tr('Выбрано'))+': <b>'+dpPad(DP.d)+' '+esc(tr(DP_MON[DP.m]))+' '+DP.y+'</b>'
      : esc(tr('Выбери день'))}</div>
    <div class="dpbar">
      <button class="btn g" id="dpCancel">${esc(tr('Отмена'))}</button>
      <button class="btn g" id="dpClear">${esc(tr('Очистить'))}</button>
      <button class="btn" id="dpOk" ${DP.d?'':'disabled'}>${esc(tr('Готово'))}</button>
    </div>`;

  const step=dir=>{
    if(DP.mode==='year'){ DP.y+=dir*24; }
    else if(DP.mode==='month'){ DP.y+=dir; }
    else {
      DP.m+=dir;
      if(DP.m<0){ DP.m=11; DP.y--; }
      if(DP.m>11){ DP.m=0; DP.y++; }
      if(DP.d>dpDaysIn(DP.y,DP.m)) DP.d=dpDaysIn(DP.y,DP.m);
    }
    hap(); dpDraw();
  };
  $('#dpPrev').onclick=()=>step(-1);
  $('#dpNext').onclick=()=>step(1);
  // заголовок листает уровни: месяц -> месяцы -> годы
  $('#dpTitle').onclick=()=>{
    DP.mode = DP.mode==='day' ? 'month' : DP.mode==='month' ? 'year' : 'day';
    hap(); dpDraw();
  };
  box.querySelectorAll('[data-dpd]').forEach(el=>el.onclick=()=>{
    DP.d=+el.dataset.dpd; hap(); dpDraw();
  });
  box.querySelectorAll('[data-dpm]').forEach(el=>el.onclick=()=>{
    DP.m=+el.dataset.dpm; DP.mode='day';
    if(DP.d>dpDaysIn(DP.y,DP.m)) DP.d=dpDaysIn(DP.y,DP.m);
    hap(); dpDraw();
  });
  box.querySelectorAll('[data-dpy]').forEach(el=>el.onclick=()=>{
    DP.y=+el.dataset.dpy; DP.mode='month'; hap(); dpDraw();
  });
  $('#dpCancel').onclick=()=>{ hap(); dpClose(); };
  $('#dpClear').onclick=()=>{ const cb=DP.cb; hap('medium'); dpClose(); if(cb) cb(''); };
  $('#dpOk').onclick=()=>{
    if(!DP.d) return;
    const cb=DP.cb, iso=dpIso(DP.y,DP.m,DP.d);
    hap('medium'); dpClose(); if(cb) cb(iso);
  };
  applyLang();
}


/* ================= Список выбора =================
   То же окно снизу, но со списком вариантов. Нужен там, где раньше
   значение перебиралось тапом по строке и угадать состав было нельзя. */
function pickOpen(title, options, current, cb){
  dpEnsure();
  const box=$('#dpbox');
  $('#dpick').classList.add('on');
  document.body.style.overflow='hidden';
  hap();
  box.innerHTML=`
    <div class="dplabel">${esc(tr(title))}</div>
    <div class="pklist">${options.map(o=>`
      <div class="pkopt ${o.v===current?'on':''}" data-pk="${esc(o.v)}">
        <span class="mark"></span>
        <span class="pkt"><span class="pk1">${esc(tr(o.t))}</span>
          ${o.s?`<span class="pk2">${esc(tr(o.s))}</span>`:''}</span>
      </div>`).join('')}</div>
    <div class="dpbar"><button class="btn g" id="pkClose">${esc(tr('Закрыть'))}</button></div>`;
  box.querySelectorAll('[data-pk]').forEach(el=>el.onclick=()=>{
    const v=el.dataset.pk;
    hap('medium'); dpClose(); if(cb) cb(v);
  });
  $('#pkClose').onclick=()=>{ hap(); dpClose(); };
  applyLang();
}

/* Ходовые вахты. Ключи совпадают с WATCH_SCHEDULES на сервере --
   по ним считается время до заступления в разделе Ask. */
const WATCH_LIST=[
  {v:'2nd', t:'Второй помощник',   s:'00-04 / 12-16'},
  {v:'ch',  t:'Старший помощник',  s:'04-08 / 16-20'},
  {v:'3rd', t:'Третий помощник',   s:'08-12 / 20-24'},
  {v:'6a',  t:'Шесть через шесть', s:'00-06 / 12-18'},
  {v:'6b',  t:'Шесть через шесть', s:'06-12 / 18-24'},
  {v:'day', t:'Дневная работа',    s:'08-17, без ходовой вахты'}
];
const watchInfo=v=>WATCH_LIST.find(w=>w.v===v)||WATCH_LIST[0];


/* ---- Профиль: настройки, подписка, о приложении ---- */
function renderSettings(){
  const box=$('#settingsBox'); if(!box) return;
  const dark=!document.body.classList.contains('light');
  const tier=accTitle();
  const price=ACC?ACC.price_stars:100;
  const cached=(()=>{ try{ const c=JSON.parse(localStorage.getItem(CK)||'null');
    return c&&c.at?ago(new Date(c.at).toISOString()):'нет'; }catch(e){ return 'нет'; } })();

  box.innerHTML=`
    <div class="dpanel"><h4>Оформление</h4>
      <div class="sw" data-set="theme">
        <div style="min-width:0"><div class="t">${ico('sun','sm')}Тёмная тема</div>
          <div class="d">Светлая версия для дневной вахты</div></div>
        <div class="toggle ${dark?'on':''}"></div>
      </div>
      <div class="sw" data-set="lang">
        <div style="min-width:0"><div class="t">${ico('flag','sm')}Язык интерфейса</div>
          <div class="d">Русский или английский</div></div>
        <span class="rtag am">${LANG==='en'?'EN':'RU'}</span>
      </div>
      <div class="sw" data-set="hap">
        <div style="min-width:0"><div class="t">${ico('alert','sm')}Отдача при нажатии</div>
          <div class="d">Лёгкая вибрация на кнопках и ручках</div></div>
        <div class="toggle ${HAPTIC?'on':''}"></div>
      </div>
      <div class="sw" data-set="dscsnd">
        <div style="min-width:0"><div class="t">${ico('radar','sm')}Звук тренажёра</div>
          <div class="d">Посылка ЦИВ, подтверждение и сигнал тревоги</div></div>
        <div class="toggle ${DSC_SND?'on':''}"></div>
      </div>
    </div>

    <div class="dpanel"><h4>Позиция</h4>
      <div class="sw" data-set="geo">
        <div style="min-width:0"><div class="t">${ico('target','sm')}Геопозиция</div>
          <div class="d">${GEO_ON?'Координаты берутся с устройства':'Выключена, координаты вводятся вручную'}</div></div>
        <div class="toggle ${GEO_ON?'on':''}"></div>
      </div>
      <div class="sw" data-set="geowatch">
        <div style="min-width:0"><div class="t">${ico('map','sm')}Метка на карте</div>
          <div class="d">Следить за своим местом, пока карта открыта</div></div>
        <div class="toggle ${GEO_WATCH?'on':''}"></div>
      </div>
      <div class="tres"><span class="tl">Текущая позиция</span>
        <span class="tv mono">${GEO.busy?esc(tr('Определяю…')):(GEO.lat!==null?esc(geoFmtLat(GEO.lat)+' '+geoFmtLon(GEO.lon)):(GEO.err?esc(GEO.err):'—'))}</span></div>
      ${GEO_ON?`<button class="btn g wide" id="setGeoNow" style="margin-top:9px">${GEO.busy?esc(tr('Отменить запрос')):esc(tr('Обновить позицию'))}</button>`:''}
      ${GEO.acc?`<div class="tres"><span class="tl">Точность</span><span class="tv mono">±${Math.round(GEO.acc)} м</span></div>`:''}
    </div>

    <div class="dpanel"><h4>Вахта</h4>
      <div class="sw" data-set="watch">
        <div style="min-width:0"><div class="t">${ico('clock','sm')}Моя вахта</div>
          <div class="d">${esc(tr(watchInfo(WATCH_ROLE).t))}. По ней считается время до заступления</div></div>
        <span class="rtag am">${esc(watchInfo(WATCH_ROLE).s.split(',')[0])}</span>
      </div>
    </div>

    <div class="dpanel"><h4>Единицы и формат</h4>
      <div class="sw" data-set="coordfmt">
        <div style="min-width:0"><div class="t">${ico('compass','sm')}Формат координат</div>
          <div class="d">Градусы с минутами или десятичные</div></div>
        <span class="rtag am">${COORD_FMT==='dec'?'12.3456°':'12-20.7N'}</span>
      </div>
      <div class="sw" data-set="tz">
        <div style="min-width:0"><div class="t">${ico('clock','sm')}Время в шапке</div>
          <div class="d">${esc(tr(TIME_MODE==='utc'?'Всемирное координированное'
            :TIME_MODE==='ship'?'Судовое, '+tzText(SHIP_TZ):'Как на телефоне'))}</div></div>
        <span class="rtag am">${TIME_LABEL[TIME_MODE]}</span>
      </div>
      ${TIME_MODE==='ship'?`
      <div class="sw" data-set="shiptz">
        <div style="min-width:0"><div class="t">${ico('globe','sm')}Пояс судового времени</div>
          <div class="d">Переводится приказом по судну, а не телефоном</div></div>
        <span class="rtag am">${esc(tzText(SHIP_TZ))}</span>
      </div>`:''}
      <div class="clocks">
        <div class="clk"><b>${clockHM('utc')}</b><span>UTC</span></div>
        <div class="clk"><b>${clockHM('ship')}</b><span>${esc(tr('судовое'))}</span></div>
        <div class="clk"><b>${clockHM('phone')}</b><span>${esc(tr('телефон'))}</span></div>
      </div>
    </div>

    <div class="dpanel"><h4>Уведомления</h4>
      <div class="sw" data-set="ntf_new">
        <div style="min-width:0"><div class="t">${ico('globe','sm')}Новые предупреждения</div>
          <div class="d">Присылать, как только появятся в твоих районах</div></div>
        <div class="toggle ${NTF.warn?'on':''}"></div>
      </div>
      <div class="sw" data-set="ntf_cert">
        <div style="min-width:0"><div class="t">${ico('flag','sm')}Сроки сертификатов</div>
          <div class="d">За 60, 30, 14, 7, 3 и 1 день до истечения</div></div>
        <div class="toggle ${NTF.cert?'on':''}"></div>
      </div>
      <div class="sw" data-set="ntf_gmdss">
        <div style="min-width:0"><div class="t">${ico('radar','sm')}Батареи EPIRB и SART</div>
          <div class="d">За 90, 30 и 7 дней до замены</div></div>
        <div class="toggle ${NTF.gmdss?'on':''}"></div>
      </div>
    </div>

    <div class="dpanel"><h4>Доступ</h4>
      <div class="tres hi"><span class="tl">Текущий тариф</span><span class="tv">${esc(tier)}</span></div>
      ${(ACC&&ACC.until)?`<div class="tres"><span class="tl">Действует до</span>
        <span class="tv" style="font-size:13px">${esc(subDate(ACC.until))}</span></div>`:''}
      ${(ACC&&ACC.can_manage_sub)?`
      <div class="sw" data-set="autorenew">
        <div style="min-width:0"><div class="t">${ico('star','sm')}Автопродление</div>
          <div class="d">${ACC.sub_cancelled
            ? 'Выключено. Оплаченный период доработает до конца и не продлится'
            : 'Списание раз в 30 дней, пока включено. Выключишь — списаний больше не будет'}</div></div>
        <div class="toggle ${ACC.sub_cancelled?'':'on'}"></div>
      </div>
      <div class="buystate" id="subState"></div>`:''}
      ${(ACC&&ACC.premium_source==='granted')
        ? `<div class="hint" style="margin:9px 0 0">${ico('star','xs')} Premium открыт вручную создателем бота — списаний нет.</div>`:''}
      ${(ACC&&ACC.paywall===false)
        ? `<div class="hint" style="margin:9px 0 0">${ico('alert','xs')} Идёт отладка, все разделы открыты бесплатно.</div>`
        : `<button class="btn wide" id="setPlans" style="margin-top:9px">Что входит в Premium · ${price} ⭐</button>`}
    </div>

    ${(ACC&&ACC.owner)?`
    <div class="dpanel"><h4>Создателю бота</h4>
      <div class="sw" data-set="admin">
        <div style="min-width:0"><div class="t">${ico('sliders','sm')}Админ-панель</div>
          <div class="d">Пользователи, платежи, баланс звёзд, выдача и возврат</div></div>
        <span class="rtag am">→</span>
      </div>
    </div>`:''}

    <div class="dpanel"><h4>Выгрузка предупреждений</h4>
      <div class="admacts">
        ${['geojson:GeoJSON','json:JSON','kml:KML','gpx:GPX','wkt:WKT','csv:CSV','txt:TXT',
           'shapefile:Shapefile','gpkg:GeoPackage'].map(x=>{
          const [id,title]=x.split(':');
          return `<button class="btn g" data-exp="${id}">${title}</button>`;}).join('')}
      </div>
      <div class="buystate" id="expState"></div>
      <div class="hint" style="margin:9px 0 0">${ico('map','xs')} На каждый район приходит свой файл, отдельным сообщением в чат с ботом: из приложения Telegram сохранять не умеет. GeoJSON, Shapefile и GeoPackage открывают QGIS и планировщики перехода, KML понимает Google Earth, GPX читают навигаторы, CSV и WKT идут в таблицу и в базу. Выгружаются отмеченные районы, а если ничего не отмечено, то все действующие.</div>
      <div class="hint" style="margin:7px 0 0">${ico('alert','xs')} Файлы для JRC, TRANSAS и FURUNO не собираются: у этих форматов ECDIS нет открытого описания, и собранный наугад файл оборудование либо не примет, либо покажет район не там, где он есть. Пришли образец выгрузки с самой ECDIS, и формат добавим.</div>
    </div>

    <div class="dpanel"><h4>Данные без связи</h4>
      <div class="tres"><span class="tl">Последняя синхронизация</span><span class="tv" style="font-size:13px">${esc(cached)}</span></div>
      <div class="hint" style="margin:9px 0 0">${ico('radar','xs')} Предупреждения, станции и справочники сохраняются на устройстве — в рейсе приложение открывается и работает без сети. Расчёты работают всегда.</div>
      <button class="btn g wide" id="setClear" style="margin-top:9px">Очистить сохранённые данные</button>
    </div>

    <div class="dpanel"><h4>Поддержка</h4>
      <div class="sw" data-set="support">
        <div style="min-width:0"><div class="t">${ico('compass','sm')}Написать в поддержку</div>
          <div class="d">Переписка с создателем бота прямо здесь</div></div>
        <span class="rtag am">${(SUP&&SUP.unread)?SUP.unread:'→'}</span>
      </div>
      <div class="sw" data-set="faq">
        <div style="min-width:0"><div class="t">${ico('archive','sm')}Справка</div>
          <div class="d">Частые вопросы по боту и его разделам</div></div>
        <span class="rtag am">→</span>
      </div>
    </div>

    <div class="dpanel"><h4>О приложении</h4>
      <div class="tres"><span class="tl">WatchKeeper</span><span class="tv" style="font-size:13px">${APP_VERSION}</span></div>
      <div class="hint" style="margin:9px 0 0">${ico('alert','xs')} Данные справочные. Официальным источником остаются оборудование GMDSS и NAVTEX, ECDIS и судовые пособия. Решение принимает судоводитель.</div>
    </div>`;

  const th=box.querySelector('[data-set="theme"]');
  if(th) th.onclick=()=>{
    document.body.classList.toggle('light'); hap('medium');
    localStorage.setItem(TK, document.body.classList.contains('light')?'light':'dark');
    renderSettings();
  };
  const lg=box.querySelector('[data-set="lang"]');
  if(lg) lg.onclick=()=>{
    LANG=(LANG==='en')?'ru':'en';
    localStorage.setItem('navarea_lang',LANG); hap('medium');
    applyLang(); renderSettings(); applyLang();
  };
  const hp=box.querySelector('[data-set="hap"]');
  if(hp) hp.onclick=()=>{
    HAPTIC=!HAPTIC; localStorage.setItem('navarea_haptic',HAPTIC?'1':'0');
    if(HAPTIC) hap('medium');
    renderSettings();
  };
  const sup=box.querySelector('[data-set="support"]');
  if(sup) sup.onclick=()=>{ hap('medium'); switchView('support'); };
  const adm=box.querySelector('[data-set="admin"]');
  if(adm) adm.onclick=()=>{ hap('medium'); switchView('admin'); };
  const ar=box.querySelector('[data-set="autorenew"]');
  if(ar) ar.onclick=toggleAutorenew;
  const fq=box.querySelector('[data-set="faq"]');
  if(fq) fq.onclick=()=>{ hap('medium'); switchView('faq'); };
  const ds=box.querySelector('[data-set="dscsnd"]');
  if(ds) ds.onclick=()=>{
    DSC_SND=!DSC_SND; localStorage.setItem('navarea_dscsnd',DSC_SND?'1':'0');
    hap('medium');
    if(DSC_SND) snd('ack');   // сразу слышно, что включилось
    renderSettings();
  };
  const gn=$('#setGeoNow');
  if(gn) gn.onclick=async()=>{
    hap('medium');
    if(GEO.busy){ cancelPositionRequest(); renderSettings(); return; }
    renderSettings();
    await requestPosition();
    renderSettings();
  };
  const gs=box.querySelector('[data-set="geo"]');
  if(gs) gs.onclick=()=>{ hap('medium'); setGeoEnabled(!GEO_ON); renderSettings(); };
  const gw=box.querySelector('[data-set="geowatch"]');
  if(gw) gw.onclick=()=>{
    GEO_WATCH=!GEO_WATCH; localStorage.setItem('navarea_geowatch',GEO_WATCH?'1':'0');
    hap('medium');
    if(!GEO_WATCH) stopGeoWatch(); else if(S.view==='map') startGeoWatch();
    renderSettings();
  };
  const wt=box.querySelector('[data-set="watch"]');
  if(wt) wt.onclick=()=>{
    pickOpen('Какая у тебя вахта', WATCH_LIST, WATCH_ROLE, v=>{
      WATCH_ROLE=v;
      localStorage.setItem('navarea_watch',WATCH_ROLE);
      renderSettings();
    });
  };
  const cf=box.querySelector('[data-set="coordfmt"]');
  if(cf) cf.onclick=()=>{
    COORD_FMT=COORD_FMT==='dec'?'dm':'dec';
    localStorage.setItem('navarea_coordfmt',COORD_FMT); hap('medium'); renderSettings();
  };
  const tz=box.querySelector('[data-set="tz"]');
  if(tz) tz.onclick=()=>{
    pickOpen('Какое время показывать',[
      {v:'utc',  t:'UTC', s:'Всемирное координированное, им ведётся радиожурнал'},
      {v:'ship', t:'Судовое', s:'Пояс задаёшь сам: '+tzText(SHIP_TZ)},
      {v:'phone',t:'Как на телефоне', s:'Пояс из настроек устройства'}
    ], TIME_MODE, v=>{
      TIME_MODE=v; TIME_UTC=(v==='utc');
      localStorage.setItem('navarea_timemode',v);
      localStorage.setItem('navarea_timeutc',TIME_UTC?'1':'0');
      // Часы в шапке перерисовываем сразу: раньше время менялось только
      // после перезахода в приложение.
      renderClock(); renderSettings();
      if(S.view==='dash') renderDash();
    });
  };
  const stz=box.querySelector('[data-set="shiptz"]');
  if(stz) stz.onclick=()=>{
    const opts=[];
    for(let h=-12;h<=14;h+=0.5){
      opts.push({v:String(h), t:tzText(h), s:'Судовое '+clockHM0(h)});
    }
    pickOpen('Пояс судового времени', opts, String(SHIP_TZ), v=>{
      SHIP_TZ=parseFloat(v); localStorage.setItem('navarea_shiptz',v);
      renderClock(); renderSettings();
    });
  };
  [['ntf_new','warn'],['ntf_cert','cert'],['ntf_gmdss','gmdss']].forEach(([sel,key])=>{
    const el=box.querySelector('[data-set="'+sel+'"]');
    if(el) el.onclick=()=>{ NTF[key]=!NTF[key]; saveNtf(); hap('medium'); renderSettings(); };
  });

  box.querySelectorAll('[data-exp]').forEach(b=>b.onclick=async()=>{
    hap('medium');
    const st=$('#expState');
    const say=(t,c)=>{ if(st){ st.className='buystate'+(c?' '+c:''); st.textContent=t; } };
    b.disabled=true; say(tr('Готовлю файл…'));
    let r=null;
    try{ r=await api('/api/export?send=1&fmt='+b.dataset.exp); }
    catch(e){ r={error:'network'}; }
    b.disabled=false;
    if(r&&r.sent){
      // Показываем разбивку по районам: так сразу видно, что пришло
      // несколько файлов и какой из них про какой район.
      const list=(r.areas||[]).map(a=>a.area+' '+a.count).join(', ');
      say(tr('Отправил файлов:')+' '+r.sent+(list?' ('+list+')':'')
          +(r.failed?(' · '+tr('не ушло')+': '+r.failed):''), r.failed?'':'ok');
    }
    else if(r&&r.error==='empty') say(tr('Выгружать нечего: у предупреждений нет координат.'),'no');
    else if(r&&r.error==='premium_required') say(tr('Выгрузка входит в Premium.'),'no');
    else say(tr('Не получилось отправить файл.'),'no');
  });

  const pl=$('#setPlans'); if(pl) pl.onclick=openPlans;
  const cl=$('#setClear'); if(cl) cl.onclick=()=>{
    hap('medium');
    if(!confirm('Удалить сохранённые данные с устройства? Настройки и избранное останутся.')) return;
    try{ localStorage.removeItem(CK); localStorage.removeItem('navarea_radio');
         localStorage.removeItem('navarea_vessel'); }catch(e){}
    load(true); renderSettings();
  };
  applyLang();
}
const APP_VERSION='1.0';

/* ---- Моё судно: поиск, профиль, документы ---- */



/* ================= Тропические циклоны =================
   Смысл раздела не в красивой карте, а в ответе на вопрос вахтенного:
   мешает ли шторм моему переходу. Поэтому наверху не положение циклона,
   а расстояние до маршрута и время наибольшего сближения. */
let CYC=null, CYC_BUSY=false;

const CYC_LEVEL={
  critical:{t:'Опасно',c:'critical'},
  warning: {t:'Близко',c:'warning'},
  watch:   {t:'Следить',c:'watch'},
  info:    {t:'В стороне',c:'info'}
};

async function loadCyclones(force){
  if(CYC_BUSY) return CYC;
  CYC_BUSY=true; renderCyclones();
  // маршрут берём из раздела перехода, если он там заполнен
  const f=($('#voyFrom')&&$('#voyFrom').value)||'';
  const t=($('#voyTo')&&$('#voyTo').value)||'';
  let q='/api/cyclones';
  if(f&&t) q+='?from='+encodeURIComponent(f)+'&to='+encodeURIComponent(t);
  try{ CYC=await api(q); }
  catch(e){ CYC={storms:[],error:'net'}; }
  CYC_BUSY=false; renderCyclones();
  return CYC;
}

function cycArrow(deg){
  if(deg===null||deg===undefined) return '';
  return `<span class="cycarrow" style="transform:rotate(${deg}deg)">↑</span>`;
}

function cycWhen(iso){
  if(!iso) return '';
  const d=new Date(iso);
  const left=Math.round((d-Date.now())/60000);
  if(left<0) return String(iso).slice(11,16)+' UTC';
  const hh=Math.floor(left/60), mm=left%60;
  return String(iso).slice(0,16).replace('T',' ')+' UTC · '+
    tr('через')+' '+(hh?hh+' '+tr('ч')+' ':'')+mm+' '+tr('мин');
}

/* ---- Погода по портам захода ----
   Свой прогноз даёт цифры, которые можно вставить в расчёт, а карты Windy
   и Ventusky показывают поля ветра и волнения вокруг порта -- этого
   числами не передашь. Поэтому и то, и другое рядом. */
let WX_PORT=null;

async function loadWeatherPorts(){
  if(!PORTS) await loadPorts();
  const list=(PORTS&&PORTS.ports)||[];
  if(!list.length){ renderCyclones(); return; }
  const p=WX_PORT&&list.find(x=>x.id===WX_PORT) ? list.find(x=>x.id===WX_PORT) : list[0];
  WX_PORT=p.id;
  if(!PORT_WX[p.id]) await loadPortWeather(p);
  renderCyclones();
}

function weatherPortsHtml(){
  const list=(PORTS&&PORTS.ports)||[];
  if(!list.length){
    return `<div class="hint">${ico('alert','xs')} ${
      esc(tr('Добавь порты захода в разделе «Моё судно» → «Мои порты» — по ним появится сводка погоды и карты.'))}</div>`;
  }
  const cur=list.find(p=>p.id===WX_PORT)||list[0];
  let h=`<div class="sech"><h3>${esc(tr('Погода в портах захода'))}</h3></div>
    <div class="chips">${list.map(p=>
      `<button class="chip ${p.id===cur.id?'on':''}" data-wxp="${p.id}">${esc(p.name)}</button>`).join('')}</div>`;
  h+=PORT_WX[cur.id] ? portWxHtml(PORT_WX[cur.id], cur.id)
                     : '<div class="sk card" style="height:96px"></div>';
  return h;
}

function renderCyclones(){
  const box=$('#cycBox'); if(!box) return;

  let h=weatherPortsHtml();
  h+=`<div class="sech" style="margin-top:18px"><h3>${esc(tr('Тропические циклоны'))}</h3></div>`;

  if(CYC_BUSY&&!CYC){
    box.innerHTML=h+'<div class="sk card"></div>';
    bindWeatherPorts(box); return;
  }
  if(!CYC){ box.innerHTML=h; bindWeatherPorts(box); return; }

  if(CYC.error){
    h+=`<div class="empty">${ico('alert')}${esc(CYC.note||tr('Сводка циклонов сейчас недоступна. Остальные разделы работают.'))}</div>`;
    box.innerHTML=h; bindWeatherPorts(box); applyLang(); return;
  }

  if(CYC.route_label){
    h+=`<div class="cycroute">${ico('ship','xs')} ${esc(CYC.route_label)}</div>`;
  } else {
    h+=`<div class="hint">${ico('alert','xs')} ${esc(tr('Добавь порты захода в «Мои порты», и расстояние будет считаться до линии перехода.'))}</div>`;
  }

  if(!CYC.storms.length){
    h+=`<div class="empty">${ico('sun')}${esc(tr('Активных тропических циклонов нет.'))}</div>`;
  }

  CYC.storms.forEach(s=>{
    const lv=CYC_LEVEL[s.level]||CYC_LEVEL.info;
    const r=s.route||{};
    h+=`<div class="cyccard ${lv.c}">
      <div class="cychead">
        <div class="cycname">${esc(s.name||s.id)}</div>
        <span class="cyctag ${lv.c}">${esc(tr(lv.t))}</span>
      </div>
      <div class="cycsub">${esc(s.kind)}${s.category?' · '+esc(s.category):''}</div>

      ${r.closest_nm!==undefined&&r.closest_nm!==null?`
        <div class="cycdist">
          <div class="cd"><span>${esc(tr('Сейчас от маршрута'))}</span><b>${r.distance_now_nm} ${esc(tr('миль'))}</b></div>
          <div class="cd hi"><span>${esc(tr('Наибольшее сближение'))}</span><b>${r.closest_nm} ${esc(tr('миль'))}</b></div>
          ${r.closest_at?`<div class="cd"><span>${esc(tr('Когда'))}</span><b>${esc(cycWhen(r.closest_at))}</b></div>`:''}
        </div>`:''}

      <div class="cycrows">
        <div class="cr"><span>${esc(tr('Положение'))}</span>
          <b>${esc(geoFmtLat(s.lat))} ${esc(geoFmtLon(s.lon))}</b></div>
        <div class="cr"><span>${esc(tr('Ветер'))}</span>
          <b>${s.wind_kt||'—'} ${esc(tr('узлов'))}${s.gust_kt?(' · '+esc(tr('порывы'))+' '+s.gust_kt):''}</b></div>
        <div class="cr"><span>${esc(tr('Давление в центре'))}</span><b>${s.pressure_mb||'—'} мб</b></div>
        <div class="cr"><span>${esc(tr('Перемещение'))}</span>
          <b>${cycArrow(s.movement_dir)}${s.movement_dir!==null?Math.round(s.movement_dir)+'° ':''}${s.movement_kt?s.movement_kt+' '+tr('узлов'):'—'}</b></div>
      </div>

      ${(s.forecast||[]).length?`
        <button class="showall" data-cycfc="${esc(s.id)}">${CYC_OPEN[s.id]?esc(tr('Свернуть прогноз')):esc(tr('Прогноз пути'))+' · '+s.forecast.length}</button>
        ${CYC_OPEN[s.id]?`<div class="cycfc">${s.forecast.map(p=>`
          <div class="fcrow">
            <span class="ft">${esc(String(p.at||'').slice(5,16).replace('T',' '))}</span>
            <span class="fp">${esc(geoFmtLat(p.lat))} ${esc(geoFmtLon(p.lon))}</span>
            <span class="fw">${p.wind_kt?p.wind_kt+' уз':''}</span>
          </div>`).join('')}</div>`:''}
      `:''}
    </div>`;
  });

  h+=`<div class="hint" style="margin-top:13px">${ico('alert','xs')} ${esc(CYC.coverage||'')}</div>
      <button class="btn g wide" style="margin-top:11px" id="cycRefresh">${esc(tr('Обновить сводку'))}</button>`;

  box.innerHTML=h;
  applyLang();
  document.querySelectorAll('[data-cycfc]').forEach(b=>b.onclick=()=>{
    const id=b.dataset.cycfc; CYC_OPEN[id]=!CYC_OPEN[id]; hap(); renderCyclones();
  });
  const rf=$('#cycRefresh'); if(rf) rf.onclick=()=>{ hap('medium'); CYC=null; loadCyclones(true); };
  bindWeatherPorts(box);
}
const CYC_OPEN={};

function bindWeatherPorts(box){
  (box||document).querySelectorAll('[data-wxp]').forEach(b=>b.onclick=async()=>{
    hap();
    WX_PORT=+b.dataset.wxp;
    const p=((PORTS&&PORTS.ports)||[]).find(x=>x.id===WX_PORT);
    if(p&&!PORT_WX[p.id]){ renderCyclones(); await loadPortWeather(p); }
    renderCyclones();
  });
  bindWxMaps(box);
}

/* ================= Ask WatchKeeper =================
   Разговор с приложением обычными словами. Смысл не в переписке, а в том,
   чтобы вопрос сразу превращался в действие: расчёт с подставленными
   числами, проверка маршрута, время вахты.

   Простые вопросы разбираются на сервере без обращения к модели -- это
   мгновенно и работает при дорогом спутниковом канале. К модели уходит
   только то, что не разобралось. */
let ASKLOG = [];
let ASK_BUSY=false;
let ASK_HINTS=null;

const ASK_TOOL_TITLES={ukc:'Запас воды под килём',squat:'Проседание на ходу',
  eta:'ETA и скорость',cpa:'CPA и TCPA',dist:'Расстояние и курс'};

async function loadAskHints(){
  if(ASK_HINTS) return ASK_HINTS;
  try{ ASK_HINTS=await api('/api/ask?q='); }catch(e){ ASK_HINTS={examples:[]}; }
  return ASK_HINTS;
}

function askPush(role, data){
  ASKLOG.push(Object.assign({role, at:Date.now()}, data));
  if(ASKLOG.length>40) ASKLOG.shift();
  renderAsk();
}

/* Что приложение уже знает о судне, месте и рейсе. Именно это избавляет
   от повторного ввода: осадка лежит в карточке, позиция приходит с
   устройства, расстояние -- из проложенного маршрута. */
function askContext(){
  const v=(VES&&VES.active)||{};
  const ctx={vessel:{},position:{},route:{}};
  [['draft','draft'],['cb','cb'],['speed','speed'],['loa','loa'],
   ['hawse','hawse'],['air_draft','air_draft'],['cons','cons']].forEach(([a,b])=>{
    if(v[b]!==undefined&&v[b]!=='') ctx.vessel[a]=v[b];
  });
  if(typeof geoFresh==='function'&&geoFresh()){
    ctx.position.lat=geoFmtLat(GEO.lat); ctx.position.lon=geoFmtLon(GEO.lon);
    // отдельно в градусах: сервер по ним берёт погоду и считает расстояния,
    // а разбирать обратно «12-41.2N» ради этого незачем
    ctx.position.lat_dec=+GEO.lat.toFixed(4); ctx.position.lon_dec=+GEO.lon.toFixed(4);
  }
  if(typeof LAST_VOY!=='undefined'&&LAST_VOY&&LAST_VOY.distance_nm){
    ctx.route.distance=LAST_VOY.distance_nm;
    if(LAST_VOY.from) ctx.route.from=LAST_VOY.from.label;
    if(LAST_VOY.to)   ctx.route.to=LAST_VOY.to.label;
  }
  return ctx;
}

/* ================= Библиотека готовых запросов =================
   Человек выбирает сценарий, а приложение подставляет в шаблон то, что
   уже знает: судно, место, маршрут, вахту. Незакрытые параметры остаются
   в тексте как {ИМЯ} -- ассистент по ним спрашивает ровно недостающее,
   а не весь список заново. */
let ASK_LIB=null, ASK_LIB_CAT=null, ASK_LIB_OPEN=false;
let ASK_MODE=localStorage.getItem('navarea_askmode')||'auto';

async function loadPrompts(){
  if(ASK_LIB) return ASK_LIB;
  try{ ASK_LIB=await api('/api/prompts'); }catch(e){ ASK_LIB={groups:[],modes:[]}; }
  return ASK_LIB;
}

/* Значения параметров из того, что известно приложению */
function askParams(){
  const v=(VES&&VES.active)||{};
  const p={};
  const put=(k,val)=>{ if(val!==undefined&&val!==null&&String(val).trim()!=='') p[k]=String(val); };
  put('VESSEL_NAME',v.name); put('IMO',v.imo); put('MMSI',v.mmsi);
  put('CALLSIGN',v.callsign); put('TYPE',v.type); put('LOA',v.loa);
  put('BEAM',v.beam); put('DWT',v.dwt); put('GT',v.gt); put('CB',v.cb);
  put('AIR_DRAFT',v.air_draft);
  put('DRAFT', v.draft_now||v.draft_summer);
  put('SERVICE_SPEED', v.speed?v.speed+' узлов':'');

  if(typeof geoFresh==='function'&&geoFresh()){
    put('LAT',geoFmtLat(GEO.lat)); put('LON',geoFmtLon(GEO.lon));
    if(GEO.cog!=null) put('COG',Math.round(GEO.cog)+'°');
    if(GEO.sog!=null) put('SOG',GEO.sog+' узлов');
  }
  if(!p.SOG&&v.speed) put('SOG',v.speed+' узлов');
  const n=new Date();
  put('UTC',String(n.getUTCHours()).padStart(2,'0')+':'+String(n.getUTCMinutes()).padStart(2,'0')+' UTC');

  let voy=null;
  try{ voy=JSON.parse(localStorage.getItem('navarea_lastvoy')||'null'); }catch(e){}
  if(voy){
    put('DEPARTURE',voy.from); put('DESTINATION',voy.to);
    put('DISTANCE_NM',voy.distance); put('LEGS',voy.legs);
  }
  const w=(typeof watchInfo==='function')?watchInfo(WATCH_ROLE):null;
  if(w) put('WATCH', tr(w.t)+' '+w.s.split(',')[0]);
  return p;
}

/* Подстановка. Возвращает готовый текст и список того, чего не хватило. */
function fillParams(tpl){
  const p=askParams(), missing=[];
  const text=String(tpl).replace(/\{([A-Z_]+)\}/g,(m,k)=>{
    if(p[k]!==undefined) return p[k];
    missing.push(k);
    return m;
  });
  return {text, missing};
}

async function askSend(text, mode){
  text=(text||'').trim();
  if(!text||ASK_BUSY) return;
  askPush('me',{text});
  ASK_BUSY=true; renderAsk();
  try{
    const m=mode||ASK_MODE;
    const r=await api('/api/ask?q='+encodeURIComponent(text)
      +'&watch='+encodeURIComponent(WATCH_ROLE)
      +(m&&m!=='auto'?'&mode='+encodeURIComponent(m):'')
      +'&ctx='+encodeURIComponent(JSON.stringify(askContext())));
    askPush('bot', r);
  }catch(e){
    askPush('bot',{kind:'text',text:tr('Не получилось спросить: нет связи. Расчёты и справочники работают без неё.')});
  }
  ASK_BUSY=false; renderAsk();
}

/* Открыть расчёт с числами из вопроса */
function askOpenTool(tool, values){
  const t=TOOLS.find(x=>x.id===tool);
  if(!t){ return; }
  switchGroup('tools'); switchView('tools');
  setTimeout(()=>{
    openTool(t);
    setTimeout(()=>{
      Object.keys(values||{}).forEach(k=>{
        const el=document.querySelector(`[data-k="${k}"]`);
        if(el){ el.value=values[k]; toolVals[k]=String(values[k]); }
      });
      if(typeof saveCalcVals==='function'&&curTool) saveCalcVals(curTool.id,toolVals);
      if(typeof runTool==='function') runTool();
      hap('medium');
    },60);
  },60);
}

function askOpenRoute(from,to){
  switchGroup('map'); switchView('voy');
  setTimeout(()=>{
    if(from){ const f=$('#voyFrom'); if(f){ f.value=from; } }
    if(to){ const t=$('#voyTo'); if(t){ t.value=to; } }
    hap('medium');
  },80);
}

function askWatchText(m){
  const pad=n=>String(n).padStart(2,'0');
  const win=(w)=>w?(pad(w[0])+'-'+pad(w[1]%24)):'';
  if(m.on_watch){
    return tr('Ты сейчас на вахте')+' ('+win(m.current)+'). '+
           tr('Следующая')+': '+win(m.next_window)+' '+tr('в')+' '+String(m.next_at).slice(11,16)+' UTC.';
  }
  const left=m.next_at?Math.round((new Date(m.next_at)-Date.now())/60000):null;
  const hh=left!==null?Math.floor(left/60):null, mm=left!==null?left%60:null;
  // Если до заступления меньше минуты, писать «через 0 мин» бессмысленно
  const when = (left===null||left<1) ? tr('вот-вот')
             : tr('через')+' '+(hh?hh+' '+tr('ч')+' ':'')+mm+' '+tr('мин');
  return tr('Следующая вахта')+': '+win(m.next_window)+', '+when+
         ' ('+String(m.next_at).slice(11,16)+' UTC).';
}

/* Панель сценариев и режимов над перепиской */
function askLibHtml(){
  const lib=ASK_LIB&&ASK_LIB.groups||[];
  const modes=(ASK_LIB&&ASK_LIB.modes)||[{id:'auto',t:'Как удобнее'}];
  const cur=modes.find(m=>m.id===ASK_MODE)||modes[0];

  let h=`<div class="askbar2">
    <button class="askchip mode" id="askModeBtn">${ico('sliders','xs')}${esc(tr(cur.t))}</button>
    <button class="askchip lib ${ASK_LIB_OPEN?'on':''}" id="askLibBtn">${ico('archive','xs')}${esc(tr('Сценарии'))}</button>
  </div>`;
  if(!ASK_LIB_OPEN) return h;

  if(!lib.length) return h+`<div class="hint">${ico('alert','xs')} ${esc(tr('Библиотека сценариев не загрузилась, нужна связь с сервером.'))}</div>`;

  h+=`<div class="chips askcats">${lib.map(g=>
    `<button class="chip ${ASK_LIB_CAT===g.id?'on':''}" data-lc="${esc(g.id)}">${esc(tr(g.t))}</button>`).join('')}</div>`;

  const g=lib.find(x=>x.id===ASK_LIB_CAT)||lib[0];
  h+=`<div class="askscen">${(g.items||[]).map((it,i)=>{
    const f=fillParams(it.q);
    return `<button class="scen" data-scen="${esc(g.id)}:${i}">
      <span class="st">${esc(tr(it.t))}</span>
      <span class="sq">${esc(f.text.length>110?f.text.slice(0,110)+'…':f.text)}</span>
      ${f.missing.length
        ? `<span class="sm">${ico('alert','xs')} ${esc(tr('спросит'))}: ${esc(f.missing.join(', '))}</span>`
        : `<span class="sm ok">${ico('back','xs')} ${esc(tr('все данные подставлены'))}</span>`}
    </button>`;
  }).join('')}</div>`;
  return h;
}

function bindAskLib(){
  const mb=$('#askModeBtn');
  if(mb) mb.onclick=()=>{
    const modes=(ASK_LIB&&ASK_LIB.modes)||[];
    if(!modes.length){ loadPrompts().then(renderAsk); return; }
    pickOpen('Как отвечать', modes.map(m=>({v:m.id,t:m.t,s:m.d})), ASK_MODE, v=>{
      ASK_MODE=v; localStorage.setItem('navarea_askmode',v); renderAsk();
    });
  };
  const lb=$('#askLibBtn');
  if(lb) lb.onclick=async()=>{
    hap();
    ASK_LIB_OPEN=!ASK_LIB_OPEN;
    if(ASK_LIB_OPEN&&!ASK_LIB){ renderAsk(); await loadPrompts(); }
    if(ASK_LIB&&!ASK_LIB_CAT&&ASK_LIB.groups&&ASK_LIB.groups[0]) ASK_LIB_CAT=ASK_LIB.groups[0].id;
    renderAsk();
  };
  document.querySelectorAll('[data-lc]').forEach(b=>b.onclick=()=>{
    ASK_LIB_CAT=b.dataset.lc; hap(); renderAsk();
  });
  document.querySelectorAll('[data-scen]').forEach(b=>b.onclick=()=>{
    const [gid,idx]=b.dataset.scen.split(':');
    const g=(ASK_LIB&&ASK_LIB.groups||[]).find(x=>x.id===gid);
    const it=g&&g.items[+idx]; if(!it) return;
    hap('medium');
    ASK_LIB_OPEN=false;
    askSend(fillParams(it.q).text);
  });
}

function renderAsk(){
  const box=$('#askBox'); if(!box) return;

  let h='';
  h+=askLibHtml();
  if(!ASKLOG.length){
    const ex=(ASK_HINTS&&ASK_HINTS.examples)||[];
    h+=`<div class="askintro">
      <div class="ai">${ico('compass','lg')}</div>
      <div class="at">${esc(tr('Спроси обычными словами'))}</div>
      <div class="as">${esc(tr('Числа из вопроса подставятся в нужный расчёт. Простые вопросы разбираются без связи.'))}</div>
    </div>
    <div class="askex">${ex.map(x=>`<button class="exbtn" data-ex="${esc(x)}">${esc(x)}</button>`).join('')}</div>`;
  }

  ASKLOG.forEach(m=>{
    if(m.role==='me'){ h+=`<div class="amsg me">${esc(m.text)}</div>`; return; }

    if(m.kind==='tool'){
      const title=ASK_TOOL_TITLES[m.tool]||m.tool;
      const t=TOOLS.find(x=>x.id===m.tool);
      const rows=Object.keys(m.values||{}).map(k=>{
        const f=t&&t.fields.find(x=>x.k===k);
        const lab=f?tr(f.l):k;
        const val=m.values[k]==='confined'?tr('Стеснённая / канал'):m.values[k];
        // Помечаем то, что подставилось из карточки судна или позиции --
        // человек должен видеть, откуда взялось число, которое он не называл.
        const auto=(m.from_context||{})[k];
        return `<div class="arow"><span>${esc(lab)}${auto?' <i class="auto">'+esc(tr('само'))+'</i>':''}</span><b>${esc(String(val))}</b></div>`;
      }).join('');
      h+=`<div class="amsg bot card">
        <div class="ahead">${ico('sliders','sm')}${esc(tr('Открыть расчёт'))}: ${esc(tr(title))}</div>
        <div class="arows">${rows}</div>
        <button class="btn wide" data-open="${esc(m.tool)}" data-vals="${esc(JSON.stringify(m.values||{}))}">
          ${esc(tr('Открыть с этими числами'))}</button>
        ${m.hint_tool?`<button class="btn g wide" style="margin-top:8px"
           data-open="${esc(m.hint_tool.tool)}" data-vals="${esc(JSON.stringify(m.hint_tool.values||{}))}">
           ${esc(tr('Заодно посчитать проседание'))}</button>`:''}
      </div>`;
      return;
    }

    if(m.kind==='need'){
      // Спрашиваем только то, чего не хватает, остальное уже собрано
      const t=TOOLS.find(x=>x.id===m.tool);
      const have=Object.keys(m.values||{}).map(k=>{
        const f=t&&t.fields.find(x=>x.k===k);
        const src=(m.from_context||{})[k];
        return `<div class="arow"><span>${esc(f?tr(f.l):k)}${src?' <i class="auto">'+esc(tr('само'))+'</i>':''}</span><b>${esc(String(m.values[k]))}</b></div>`;
      }).join('');
      h+=`<div class="amsg bot card">
        <div class="ahead">${ico('sliders','sm')}${esc(tr(ASK_TOOL_TITLES[m.tool]||m.tool))}</div>
        ${have?`<div class="arows">${have}</div>`:''}
        <div class="needq">${esc(tr('Не хватает'))}: ${m.missing.map(x=>esc(tr(x.label))+(x.unit?' ('+esc(tr(x.unit))+')':'')).join(', ')}</div>
        <div class="needf">${m.missing.map(x=>
          `<input class="needin" data-need="${esc(x.k)}" inputmode="decimal"
             placeholder="${esc(tr(x.label))}${x.unit?', '+esc(tr(x.unit)):''}">`).join('')}</div>
        <button class="btn wide" data-needgo="${esc(m.tool)}" data-have="${esc(JSON.stringify(m.values||{}))}">
          ${esc(tr('Посчитать'))}</button>
      </div>`;
      return;
    }

    if(m.kind==='colreg'){
      const sit={HEAD_ON:'Встречное расхождение',CROSSING:'Пересекающиеся курсы',
                 OVERTAKING:'Обгон',RESTRICTED_VISIBILITY:'Ограниченная видимость',
                 UNKNOWN:'Недостаточно данных'}[m.situation]||m.situation;
      h+=`<div class="amsg bot card colreg">
        <div class="ahead">${ico('radar','sm')}${esc(tr(sit))}${m.rule?' · '+esc(m.rule):''}</div>
        ${m.bearing!==null&&m.bearing!==undefined?`<div class="arows"><div class="arow">
          <span>${esc(tr('Пеленг на цель'))}</span><b>${Math.round(m.bearing)}°</b></div></div>`:''}
        <div class="atext">${esc(m.action||'')}</div>
        <div class="ahint">${esc(tr('Это подсказка по правилам, а не указание. Решение принимает судоводитель по обстановке.'))}</div>
      </div>`;
      return;
    }

    if(m.kind==='view'){
      const names={NAVAREA:'Проверка маршрута',PASSAGE_PLAN:'Проверка маршрута',MSI:'Предупреждения',
        VESSEL:'Моё судно',GMDSS_EQUIPMENT:'EPIRB Test',GMDSS_SART:'SART Test',GMDSS_DSC:'Тренажёр ЦИВ',
        RADIO:'Радиостанции MF/HF',CHECKLIST:'Чек-листы',MAP:'Обстановка',POSITION:'Моя позиция'};
      h+=`<div class="amsg bot card">
        <div class="ahead">${ico('compass','sm')}${esc(tr(names[m.intent]||m.intent))}</div>
        <button class="btn wide" data-view="${esc(m.view||'')}"
          data-from="${esc(m.from||'')}" data-to="${esc(m.to||'')}">
          ${esc(tr('Открыть'))}</button>
      </div>`;
      return;
    }

    if(m.kind==='route'){
      h+=`<div class="amsg bot card">
        <div class="ahead">${ico('ship','sm')}${esc(tr('Проверка маршрута'))}</div>
        ${(m.from||m.to)?`<div class="arows">
          <div class="arow"><span>${esc(tr('Откуда'))}</span><b>${esc(m.from||'—')}</b></div>
          <div class="arow"><span>${esc(tr('Куда'))}</span><b>${esc(m.to||'—')}</b></div></div>`:''}
        <button class="btn wide" data-route="1" data-from="${esc(m.from||'')}" data-to="${esc(m.to||'')}">
          ${esc(tr('Открыть проверку маршрута'))}</button>
      </div>`;
      return;
    }

    if(m.kind==='watch'){
      h+=`<div class="amsg bot card">
        <div class="ahead">${ico('clock','sm')}${esc(tr('Вахта'))}</div>
        <div class="atext">${esc(askWatchText(m))}</div>
        <div class="ahint">${esc(tr('Расписание берётся из настроек профиля'))}</div>
      </div>`;
      return;
    }

    h+=`<div class="amsg bot"><div class="atext">${esc(m.text||'')}</div></div>`;
  });

  if(ASK_BUSY) h+=`<div class="amsg bot"><div class="atext"><span class="blink">${esc(tr('Думаю…'))}</span></div></div>`;

  box.innerHTML=h;
  applyLang();

  bindAskLib();
  document.querySelectorAll('[data-ex]').forEach(b=>b.onclick=()=>{ hap(); askSend(b.dataset.ex); });
  document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>{
    let v={}; try{ v=JSON.parse(b.dataset.vals||'{}'); }catch(e){}
    hap('medium'); askOpenTool(b.dataset.open, v);
  });
  document.querySelectorAll('[data-needgo]').forEach(b=>b.onclick=()=>{
    let v={}; try{ v=JSON.parse(b.dataset.have||'{}'); }catch(e){}
    document.querySelectorAll('[data-need]').forEach(i=>{
      const val=(i.value||'').trim();
      if(val) v[i.dataset.need]=val.replace(',','.');
    });
    hap('medium'); askOpenTool(b.dataset.needgo, v);
  });
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{
    hap('medium');
    const v=b.dataset.view;
    if(!v){ requestPosition().then(()=>renderAsk()); return; }
    if(v==='voy'&&(b.dataset.from||b.dataset.to)){ askOpenRoute(b.dataset.from,b.dataset.to); return; }
    const g=VIEW_GROUP[v]||'tools'; switchGroup(g); setTimeout(()=>switchView(v),40);
  });
  document.querySelectorAll('[data-route]').forEach(b=>b.onclick=()=>{
    hap('medium'); askOpenRoute(b.dataset.from, b.dataset.to);
  });
  try{ box.scrollTop=box.scrollHeight; }catch(e){}
}

function bindAskInput(){
  const inp=$('#askInput'), btn=$('#askSend');
  if(btn) btn.onclick=()=>{ const v=inp?inp.value:''; if(inp) inp.value=''; askSend(v); };
  if(inp) inp.onkeydown=(e)=>{
    if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); const v=inp.value; inp.value=''; askSend(v); }
  };
  const cl=$('#askClear'); if(cl) cl.onclick=()=>{ ASKLOG=[]; hap(); renderAsk(); };
}

/* ================= Уведомления =================
   Колокольчик в шапке. Лента собирается на сервере из сроков сертификатов,
   батарей ГМССБ, новых предупреждений в отмеченных районах, ответов
   поддержки и объявлений бота. Открыл ленту -- счётчик обнулился. */
let NTF_FEED=null, NTF_BUSY=false;

async function loadNotifications(silent){
  if(NTF_BUSY) return NTF_FEED;
  NTF_BUSY=true;
  try{ NTF_FEED=await api('/api/notifications'); }
  catch(e){ NTF_FEED={items:[],unread:0,error:'net'}; }
  NTF_BUSY=false;
  paintBell();
  if(!silent) renderNotif();
  return NTF_FEED;
}
function paintBell(){
  const b=$('#notifCnt'); if(!b) return;
  const n=(NTF_FEED&&NTF_FEED.unread)||0;
  b.textContent=n?String(n>99?'99+':n):'';
}
const NTF_ICON={support:'compass',cert:'flag',gmdss:'radar',warning:'alert',
                release:'sliders',news:'globe'};
function renderNotif(){
  const box=$('#notifBox'); if(!box) return;
  if(!NTF_FEED){ box.innerHTML='<div class="sk card"></div><div class="sk card"></div>'; return; }
  const items=NTF_FEED.items||[];
  if(!items.length){
    box.innerHTML=`<div class="empty">${ico('star')}${esc(tr('Уведомлений пока нет.'))}</div>`;
    return;
  }
  // Заголовки и тексты собираются на сервере с подставленными числами и
  // названиями, поэтому он отдаёт их сразу на двух языках -- словарём
  // приложения такую строку не перевести.
  const pick=(ru,en)=>(LANG==='en'&&en)?en:ru;
  box.innerHTML=items.map((it,i)=>{
    const title=pick(it.title,it.title_en), body=pick(it.body,it.body_en);
    return `<button class="ntf ${it.unread?'new':''} ${it.urgent?'urgent':''}" data-ntf="${i}">
       <span class="ic">${ico(NTF_ICON[it.kind]||'globe','sm')}</span>
       <span class="tx"><span class="t1">${esc(title)}</span>
         ${body?`<span class="t2">${esc(body)}</span>`:''}
         <span class="t3">${esc(ago(it.at))}</span></span>
       ${it.unread?'<span class="dot"></span>':''}
     </button>`;
  }).join('');
  box.querySelectorAll('[data-ntf]').forEach(b=>b.onclick=()=>{
    const it=items[+b.dataset.ntf]; hap('medium');
    if(!it||!it.go) return;
    const g=VIEW_GROUP[it.go]||'home';
    switchGroup(g); setTimeout(()=>switchView(it.go),40);
  });
  applyLang();
}
async function markNotifSeen(){
  try{ NTF_FEED=await api('/api/notifications?seen=1'); }catch(e){}
  paintBell(); renderNotif();
}

/* ================= Мои порты =================
   Раздел «Рейс» слился сюда: маршрут задаётся списком портов захода, а не
   двумя полями. Расстояния между соседними портами считает сервер -- через
   проливы и каналы, а не по прямой через сушу. */
let PORTS=null, PORTS_BUSY=false, PORT_WX={};

async function loadPorts(){
  if(PORTS_BUSY) return PORTS;
  PORTS_BUSY=true; renderPorts();
  try{ PORTS=await api('/api/my-ports'); }
  catch(e){ PORTS={ports:[],error:'net'}; }
  PORTS_BUSY=false; renderPorts();
  return PORTS;
}
async function portAction(qs){
  try{ PORTS=await api('/api/my-ports?'+qs); }catch(e){}
  renderPorts();
}
/* По умолчанию здесь просто список портов контракта -- ради него раздел и
   заведён. Всё остальное (расстояния, ETA, предупреждения, рекомендации
   по переходу) убрано под кнопку: нужно это не каждый раз, а список нужен
   всегда. */
let PORT_TOOLS=false, PORT_EDIT=null;
let PORT_SPEED=parseFloat(localStorage.getItem('navarea_portspeed'))||null;

/* Справка о гавани из World Port Index. Живёт файлом в приложении, поэтому
   раздел открывается и без сети -- на подходе к порту это обычное дело.
   Величина прилива тут средняя по порту: она отвечает на вопрос «насколько
   вообще ходит вода», а не заменяет таблицы приливов на дату. */
const PORT_WPI={};
function portWpiHtml(w){
  const p=w.port||{};
  const rows=[];
  if(p.type_text)    rows.push([tr('Гавань'), p.type_text+(p.size_text?', '+p.size_text:'')]);
  if(p.shelter_text) rows.push([tr('Укрытие'), p.shelter_text]);
  rows.push([tr('Средний прилив'), p.tide_m?(p.tide_m+' '+tr('м')):tr('не указан')]);
  if(w.distance_nm!=null) rows.push([tr('От точки порта'), w.distance_nm+' '+tr('миль')]);
  return `<div class="pwx">
    <div class="pwxh">${ico('anchor','xs')} ${esc(p.name||'')}${p.cc?', '+esc(p.cc):''}
      <span class="pwxs">World Port Index</span></div>
    ${rows.map(([k,v])=>`<div class="tres"><span class="tl">${esc(k)}</span>
      <span class="tv" style="font-size:13px">${esc(String(v))}</span></div>`).join('')}
    ${p.tide_m?`<div class="hint" style="margin:7px 0 0">${ico('alert','xs')} ${
      esc(tr('Это средняя величина прилива по справочнику. Для расчёта на дату и час нужны таблицы приливов порта.'))}</div>`:''}
  </div>`;
}
async function loadPortWpi(portId, lat, lon){
  if(PORT_WPI[portId]){ delete PORT_WPI[portId]; renderPorts(); return; }
  try{
    const r=await api('/api/port-info?lat='+lat+'&lon='+lon+'&lang='+LANG);
    const near=(r.nearest||[])[0];
    if(near) PORT_WPI[portId]={port:near, distance_nm:near.distance_nm};
  }catch(e){}
  renderPorts();
}

function renderPorts(){
  const box=$('#portsBox'); if(!box) return;
  const hint=$('#portsHint');
  if(hint) hint.innerHTML=ico('alert','xs')+' '+
    esc(tr('Порты захода в этом контракте. Список подставляется в погоду, проверку рейса и в ответы ассистента.'));

  if(PORTS_BUSY&&!PORTS){ box.innerHTML='<div class="sk card"></div><div class="sk card"></div>'; return; }
  if(!PORTS){ box.innerHTML=''; return; }
  if(PORTS.error==='premium_required'){ box.innerHTML=''; gate('#v-ports','voyage'); return; }

  const list=PORTS.ports||[];
  if(!list.length){
    box.innerHTML=`<div class="empty">${ico('anchor')}${esc(tr('Портов пока нет. Добавь первый порт захода выше.'))}</div>`;
    return;
  }

  let h='';
  list.forEach((p,i)=>{
    if(PORT_TOOLS&&i>0){
      h+=`<div class="pleg">${ico('route','xs')}
        <span>${p.leg_nm!=null?p.leg_nm+' '+tr('миль'):tr('расстояние не посчитано')}
        ${p.legs&&p.legs.length?' · '+esc(p.legs.join(', ')):''}
        ${(PORT_SPEED&&p.leg_nm!=null)?' · '+hhmm(p.leg_nm/PORT_SPEED):''}</span></div>`;
    }
    h+=`<div class="pcard">
      <span class="num">${i+1}</span>
      <span class="tx" data-pedit="${p.id}">
        <span class="t1">${esc(p.name)}</span>
        <span class="t2">${esc(p.country||'')}${p.eta?' · ETA '+esc(p.eta):''}</span>
        ${p.note?`<span class="t2">${esc(p.note)}</span>`:''}
        ${PORT_TOOLS&&p.lat!=null
          ? `<span class="t3">${ico('wave','xs')}<a data-pwx="${i}">${esc(tr('Погода в порту'))} →</a></span>
             <span class="t3">${ico('anchor','xs')}<a data-pinfo="${p.id}">${esc(tr('Гавань и приливы'))} →</a></span>`
          : (p.lat==null?`<span class="t3">${esc(tr('порт не найден в справочнике'))}</span>`:'')}
      </span>
      <span class="acts">
        <button class="pact" data-pup="${p.id}" aria-label="Выше">↑</button>
        <button class="pact" data-pdn="${p.id}" aria-label="Ниже">↓</button>
        <button class="pact del" data-pdel="${p.id}" aria-label="Удалить">×</button>
      </span>
    </div>`;
    if(PORT_TOOLS&&PORT_WX[p.id]) h+=portWxHtml(PORT_WX[p.id], p.id);
    if(PORT_WPI[p.id]) h+=portWpiHtml(PORT_WPI[p.id]);
  });

  h+=`<button class="showall" id="portTools">${
    PORT_TOOLS?esc(tr('Свернуть инструменты рейса')):esc(tr('Инструменты рейса'))}</button>`;

  if(PORT_TOOLS){
    if(PORTS.total_nm){
      h+=`<div class="ptotal"><span>${esc(tr('Весь переход'))}</span>
        <b>${PORTS.total_nm} ${esc(tr('миль'))}</b></div>`;
      if(PORT_SPEED){
        h+=`<div class="ptotal"><span>${esc(tr('В пути на'))} ${PORT_SPEED} ${esc(tr('узлах'))}</span>
          <b>${Math.round(PORTS.total_nm/PORT_SPEED/24*10)/10} ${esc(tr('сут'))}</b></div>`;
      }
    }
    h+=`<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
      <button class="btn g" style="flex:1;min-width:150px" id="portSpeed">${
        esc(tr('Скорость для ETA'))}${PORT_SPEED?' · '+PORT_SPEED:''}</button>
      <button class="btn g" style="flex:1;min-width:150px" id="portsWx">${esc(tr('Погода по всем портам'))}</button>
    </div>
    <button class="btn wide" style="margin-top:8px" id="portsCheck">${
      esc(tr('Проверить предупреждения по рейсу'))}</button>
    <button class="btn g wide" style="margin-top:8px" id="portsPassage">${
      esc(tr('Рекомендации по переходу'))}</button>
    <div id="portsVoy"></div>`;
  }

  box.innerHTML=h;
  box.querySelectorAll('[data-pup]').forEach(b=>b.onclick=()=>{ hap(); portAction('action=move&dir=up&id='+b.dataset.pup); });
  box.querySelectorAll('[data-pdn]').forEach(b=>b.onclick=()=>{ hap(); portAction('action=move&dir=down&id='+b.dataset.pdn); });
  box.querySelectorAll('[data-pdel]').forEach(b=>b.onclick=()=>{
    if(!confirm(tr('Убрать порт из рейса?'))) return;
    hap('medium'); portAction('action=del&id='+b.dataset.pdel);
  });
  box.querySelectorAll('[data-pedit]').forEach(el=>el.onclick=()=>{
    const p=list.find(x=>x.id===+el.dataset.pedit); if(p) openPortEditor(p);
  });
  box.querySelectorAll('[data-pwx]').forEach(a=>a.onclick=()=>{
    const p=list[+a.dataset.pwx]; hap('medium'); loadPortWeather(p);
  });
  box.querySelectorAll('[data-pinfo]').forEach(a=>a.onclick=()=>{
    const id=+a.dataset.pinfo;
    const p=list.find(x=>x.id===id);
    if(!p||p.lat==null) return;
    hap('medium'); loadPortWpi(id, p.lat, p.lon);
  });
  bindWxMaps(box);

  const tg=$('#portTools');
  if(tg) tg.onclick=()=>{ PORT_TOOLS=!PORT_TOOLS; hap(); renderPorts(); };
  const sp=$('#portSpeed');
  if(sp) sp.onclick=()=>{
    const opts=[];
    for(let v=6;v<=22;v++) opts.push({v:String(v),t:v+' '+tr('узлов'),
      s:PORTS.total_nm?Math.round(PORTS.total_nm/v/24*10)/10+' '+tr('сут')+' '+tr('на весь переход'):''});
    pickOpen('Скорость для расчёта ETA', opts, String(PORT_SPEED||''), v=>{
      PORT_SPEED=+v; localStorage.setItem('navarea_portspeed',v); renderPorts();
    });
  };
  const wx=$('#portsWx');
  if(wx) wx.onclick=async()=>{
    hap('medium');
    for(const p of list){ if(p.lat!=null&&!PORT_WX[p.id]) await loadPortWeather(p); }
  };
  const chk=$('#portsCheck');
  if(chk) chk.onclick=()=>{
    if(list.length<2){ alert(tr('Нужны хотя бы два порта.')); return; }
    hap('medium'); askOpenRoute(list[0].name, list[list.length-1].name);
  };
  const pass=$('#portsPassage');
  if(pass) pass.onclick=()=>{
    if(list.length<2){ alert(tr('Нужны хотя бы два порта.')); return; }
    hap('medium');
    askFromHome('Дай рекомендации по океанскому переходу '+list[0].name+' — '+
      list[list.length-1].name+' по Ocean Passages for the World: рекомендованный путь, '+
      'сезонные соображения, течения и ветры, чего избегать.');
  };
  applyLang();
}

/* Правка порта: время прихода и заметка. Открывается тапом по названию. */
function openPortEditor(p){
  hap('medium');
  PORT_EDIT=p.id;
  $('#tName').textContent=p.name;
  { const b=$('#tBackTitle'); if(b) b.textContent=tr('Мои порты'); }
  $('#tDesc').textContent=p.country||'';
  $('#tIcon').innerHTML=ico('anchor','lg');
  $('#tFields').innerHTML=`
    <div class="fld"><label>${esc(tr('Планируемый приход'))}</label>
      <button type="button" class="datefield" id="peEta" data-iso="${esc(portEtaIso(p.eta))}">
        <span class="dv ${p.eta?'':'none'}">${p.eta?esc(p.eta):esc(tr('Не задана'))}</span>
        <span class="dico">${ico('clock','sm')}</span>
      </button></div>
    <div class="fld"><label>${esc(tr('Заметка'))}</label>
      <input class="tinput" id="peNote" value="${esc(p.note||'')}"
        placeholder="${esc(tr('Груз, агент, бункеровка'))}"></div>`;
  $('#tResults').innerHTML=`<button class="btn wide" id="peSave">${esc(tr('Сохранить'))}</button>`;
  $('#peEta').onclick=()=>{
    const b=$('#peEta');
    dpOpen(b.dataset.iso||'', 'Планируемый приход', iso=>{
      b.dataset.iso=iso;
      const v=b.querySelector('.dv');
      v.className='dv'+(iso?'':' none');
      v.textContent=iso?dpHuman(iso):tr('Не задана');
    });
  };
  $('#peSave').onclick=()=>{
    const iso=$('#peEta').dataset.iso||'';
    const note=$('#peNote').value.trim();
    hap('medium');
    portAction('action=edit&id='+p.id+'&eta='+encodeURIComponent(iso?dpHuman(iso):'')
      +'&note='+encodeURIComponent(note));
    closeTool();
  };
  $('#tBack').textContent=tr('Отмена');
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
  curTool=null;
  applyLang();
}
/* Обратный разбор «10 Июл 2028» в ISO -- чтобы календарь открылся на той
   же дате, что уже записана. */
function portEtaIso(text){
  if(!text) return '';
  const m=/^(\d{1,2})\s+([^\s]+)\s+(\d{4})/.exec(String(text));
  if(!m) return '';
  const i=DP_MON_SHORT.findIndex(x=>tr(x)===m[2]||x===m[2]);
  if(i<0) return '';
  return dpIso(+m[3], i, +m[1]);
}

/* ---- Погода в порту: свои цифры плюс карты Windy и Ventusky ---- */
async function loadPortWeather(p){
  const redraw=()=>{ if(S.view==='cyc') renderCyclones(); else renderPorts(); };
  PORT_WX[p.id]={loading:true}; redraw();
  try{
    PORT_WX[p.id]=await api('/api/port-weather?q='+encodeURIComponent(p.name)
      +(p.lat!=null?'&lat='+p.lat+'&lon='+p.lon:''));
  }catch(e){ PORT_WX[p.id]={error:'net'}; }
  redraw();
}
function portWxHtml(w, id){
  if(w.loading) return '<div class="sk card" style="height:96px;margin-bottom:9px"></div>';
  if(w.error) return `<div class="hint" style="margin-bottom:9px">${ico('alert','xs')} ${
    esc(tr('Погоду сейчас получить не удалось. Карты ниже работают отдельно.'))}</div>`;
  return `<div class="wxcard">
    <div class="wxhead"><span class="nm">${esc(w.place||'')}</span><span class="at">${esc(w.at||'')}</span></div>
    <div class="wxgrid">
      ${wxCell(w.wind_kn,'уз','ветер', w.wind_kn>=22?'warn':'', w.wind_from)}
      ${wxCell(w.gust_kn,'уз','порывы', w.gust_kn>=34?'hot':'')}
      ${wxCell(w.wave_m,'м','волна', w.wave_m>=2.5?'warn':'')}
      ${wxCell(w.swell_m,'м','зыбь')}
      ${wxCell(w.visibility_nm,'мили','видимость', w.visibility_nm!=null&&w.visibility_nm<2?'hot':'')}
      ${wxCell(w.pressure_hpa,'гПа','давление')}
    </div>
    <div class="wksm" style="margin-top:9px">${esc(tr(w.beaufort_name||''))}${
      w.beaufort!=null?' · '+w.beaufort+' '+esc(tr('баллов')):''}${
      w.sea_state?' · '+esc(tr(w.sea_state)):''}</div>
    <div class="wxmaps">${(w.maps||[]).map(m=>
      `<button class="wxmap" data-wxopen="${esc(m.url)}">${ico('map','xs')}${esc(m.name)}</button>`).join('')}
      ${(w.maps||[]).some(m=>m.embed)
        ? `<button class="wxmap" data-wxembed="${esc((w.maps.find(m=>m.embed)||{}).embed||'')}">${
            ico('radar','xs')}${esc(tr('Карта прямо здесь'))}</button>` : ''}
    </div>
    <div id="wxe${id}"></div>
  </div>`;
}
/* Кнопки погодных карт. Windy умеет встраиваться прямо в страницу,
   Ventusky открывается отдельным окном -- встраивание он не разрешает. */
function bindWxMaps(root){
  (root||document).querySelectorAll('[data-wxopen]').forEach(b=>b.onclick=()=>{
    hap('medium');
    const url=b.dataset.wxopen;
    try{ if(TG&&TG.openLink) return TG.openLink(url); }catch(e){}
    window.open(url,'_blank');
  });
  (root||document).querySelectorAll('[data-wxembed]').forEach(b=>b.onclick=()=>{
    hap('medium');
    const card=b.closest('.wxcard'); if(!card) return;
    const holder=card.querySelector('[id^="wxe"]'); if(!holder) return;
    if(holder.firstChild){ holder.innerHTML=''; b.classList.remove('on'); return; }
    b.classList.add('on');
    const wrap=document.createElement('div');
    wrap.className='wxwrap';
    const f=document.createElement('iframe');
    f.className='wxembed'; f.src=b.dataset.wxembed;
    f.setAttribute('loading','lazy');
    f.setAttribute('referrerpolicy','no-referrer');
    const x=document.createElement('button');
    x.className='wxclose'; x.textContent='×'; x.setAttribute('aria-label','Закрыть карту');
    x.onclick=()=>{ hap(); holder.innerHTML=''; b.classList.remove('on'); };
    wrap.appendChild(f); wrap.appendChild(x);
    holder.appendChild(wrap);
    const note=document.createElement('div');
    note.className='wxnote';
    note.textContent=tr('Полная карта со шкалой времени открывается кнопкой Windy выше');
    holder.appendChild(note);
  });
}

function wxCell(v,unit,label,cls,extra){
  const val=(v===null||v===undefined)?'—':(v+(unit?' '+tr(unit):''));
  return `<div class="wxcell ${cls||''}">
    <div class="v">${esc(String(val))}${extra?` <span style="font-size:11px">${esc(extra)}</span>`:''}</div>
    <div class="k">${esc(tr(label))}</div></div>`;
}

/* ================= Справка =================
   Вопросы сгруппированы по разделам и свёрнуты: на экране видно только
   заголовки, чтобы человек нашёл своё, а не читал всё подряд. */
const FAQ=[
 {t:'С чего начать',i:'compass',items:[
  {q:'Что вообще умеет WatchKeeper?',
   a:'Три вещи. Показывает действующие предупреждения NAVAREA и береговые по твоим районам и маршруту. Считает то, что считает вахтенный: запас под килём, проседание, расхождение с целью, ETA, якорную стоянку. И отвечает на вопросы обычными словами через Ask AI, сам подставляя данные судна, позицию и погоду.'},
  {q:'С чего начать после установки?',
   a:'Заполни карточку судна в разделе «Моё судно» — осадка, скорость и габариты потом подставляются в расчёты сами. Отметь звёздочкой свои районы NAVAREA. Добавь порты захода в «Мои порты». Всё остальное заработает само.'},
  {q:'Работает ли приложение без связи?',
   a:'Расчёты, справочники и тренажёры — да, полностью. Предупреждения, станции и зоны сохраняются на устройстве и показываются последними сохранёнными. Погода, ассистент и проверка маршрута требуют связи: они ходят на сервер.'},
  {q:'Заменяет ли бот приём MSI по ГМССБ?',
   a:'Нет и не может. Официальный источник — NAVTEX, приёмник Inmarsat SafetyNET и штатное оборудование ГМССБ. Бот — вспомогательный инструмент: он помогает не пропустить и разобраться, но решение принимает судоводитель по официальным пособиям.'}]},

 {t:'Предупреждения и карта',i:'globe',items:[
  {q:'Откуда берутся предупреждения?',
   a:'Из открытых источников координаторов районов: NGA (США), UKHO (Великобритания), гидрографические службы Перу и Испании. Если подключён Sealagom, данные идут оттуда сразу по всем 21 району.'},
  {q:'Как часто обновляются данные?',
   a:'Бот опрашивает источники каждые 30 минут (настраивается). Время последнего обновления по каждому району видно в списке районов.'},
  {q:'Почему у предупреждения нет точки на карте?',
   a:'Координаты разбираются из текста сообщения. Если в тексте их нет или они записаны непривычным способом, точка не появится. Текст при этом доступен целиком.'},
  {q:'Что значит «точная геометрия»?',
   a:'Метка на карточке: район пришёл от источника готовой фигурой, а не разобран нами из текста. Такой контур точнее.'},
  {q:'Как следить только за своими районами?',
   a:'Отметь районы звёздочкой. Они попадут в избранное на главной, и по ним будут приходить уведомления о новых предупреждениях.'}]},

 {t:'Расчёты',i:'sliders',items:[
  {q:'Откуда берутся числа в расчётах?',
   a:'Часть подставляется из карточки судна: осадка, скорость, коэффициент полноты, длина, надводный габарит. Такие поля помечены словом «само». Остальное вводится руками.'},
  {q:'Можно ли доверять расчётам?',
   a:'Это справочные расчёты по общепринятым формулам. Они не заменяют судовую документацию, таблицы манёвренных характеристик и информацию об остойчивости. Решение принимает судоводитель.'},
  {q:'Почему проседание считается по-разному?',
   a:'Формулы для открытой воды и для стеснённого фарватера дают разный результат — во втором случае проседание заметно больше. Выбор акватории есть прямо в расчёте.'},
  {q:'Расчёты платные?',
   a:'Нет. Всё, от чего зависит безопасность — запас под килём, проседание, расхождение, точка перекладки, якорь, габарит под мостом — бесплатно навсегда.'}]},

 {t:'Ask AI',i:'compass',items:[
  {q:'Чем ассистент отличается от обычного чат-бота?',
   a:'Он умеет брать данные сам. Спросишь про погоду на переходе — сам проложит маршрут через проливы, разложит время прихода по точкам и возьмёт прогноз именно на эти часы. Спросишь про предупреждения — сам отберёт те, что задевают твой маршрут.'},
  {q:'Что такое «Сценарии»?',
   a:'Готовые запросы по разделам: навигация, ECDIS, МППСС, погода, ГМССБ, вахта, груз, аварийные случаи. В шаблон уже подставлены твои данные — видно, что подставилось, а что ассистент спросит.'},
  {q:'Что такое режимы ответа?',
   a:'Форма, в которой придёт ответ: коротко, для вахты, чек-листом, расчётом с проверкой, аварийным порядком действий, брифингом, записью в журнал, радиофразеологией. Выбирается кнопкой слева над перепиской.'},
  {q:'Ассистент может ошибаться?',
   a:'Да, как любая языковая модель. Он не выдумывает живые данные — погода и предупреждения приходят из источников, — но формулировки правил и выводы стоит проверять по МППСС, конвенциям и судовым инструкциям.'},
  {q:'Есть ли лимит вопросов?',
   a:'На бесплатном тарифе — пять вопросов в сутки. На Premium ограничения нет.'}]},

 {t:'Тренажёры и ГМССБ',i:'radar',items:[
  {q:'Тренажёр ЦИВ выходит в эфир?',
   a:'Нет. Ничего не передаётся. Все подтверждения, задержки и ответы береговых станций имитируются внутри приложения.'},
  {q:'Как пользоваться роликом на станции?',
   a:'Поворот выбирает поле или пункт меню, нажатие открывает его на изменение. На дежурном экране ролик переключается между CH, TX и RX; нажал — крутишь значение.'},
  {q:'Что делает кнопка BRILL?',
   a:'Переключает яркость и контраст экрана: день, ночь (приглушённый красный, чтобы не сбивать адаптацию глаз) и зелёный люминофорный режим.'},
  {q:'Зачем нужен режим экзамена?',
   a:'Даёт обстановку, а ты выбираешь, каким вызовом отвечать. После ответа показывает разбор: почему бедствие, а не срочность, и наоборот.'},
  {q:'Проверки EPIRB и SART — что записывается?',
   a:'Отметки чек-листа, результат самопроверки и дата замены батареи. История хранится в приложении, её можно очистить.'}]},

 {t:'Подписка',i:'star',items:[
  {q:'Что входит в Premium?',
   a:'Неограниченное число районов, береговые предупреждения, проверка маршрута, карточка судна, чек-листы и сертификаты, история за 30 дней, вопросы к ассистенту без лимита, расширенные расчёты.'},
  {q:'Как оплатить?',
   a:'Звёздами Telegram прямо в приложении: «Моё судно» → «Что входит в Premium» → «Оформить». Откроется окно оплаты Telegram. Карт и переводов не нужно.'},
  {q:'Что такое звёзды Telegram?',
   a:'Внутренняя валюта Telegram. Покупаются в самом приложении Telegram и тратятся на цифровые товары и услуги. Подписка продлевается сама каждые 30 дней.'},
  {q:'Как отменить подписку?',
   a:'«Моё судно» → «Настройки» → «Доступ» → выключить «Автопродление». Оплаченный период доработает до конца. То же самое делает команда /cancel_subscription в чате с ботом.'},
  {q:'Что остаётся бесплатным?',
   a:'Два района с уведомлениями, карта всех действующих предупреждений, все расчёты безопасности, справочники, станции ГМССБ, тренажёры и пять вопросов ассистенту в сутки.'}]},

 {t:'Данные и приватность',i:'flag',items:[
  {q:'Что бот знает обо мне?',
   a:'Идентификатор Telegram, отмеченные районы, карточку судна, сертификаты и чек-листы, порты рейса — то, что ты сам ввёл. Настройки интерфейса и последние расчёты хранятся только на устройстве.'},
  {q:'Передаётся ли моя позиция?',
   a:'Только когда ты сам её запросил кнопкой или включил слежение, и только на время работы приложения. Она нужна для погоды, расстояний и экрана станции. Геопозицию можно выключить совсем в настройках.'},
  {q:'Как удалить свои данные?',
   a:'Напиши в поддержку из настроек — удалю карточку судна, сертификаты и порты. Локальные данные стираются кнопкой «Очистить сохранённые данные».'}]},

 {t:'Если что-то не работает',i:'alert',items:[
  {q:'Приложение открылось пустым или без данных',
   a:'Скорее всего нет связи с сервером — вверху появится полоса «Нет связи». Расчёты и справочники продолжат работать. Проверь интернет и потяни экран вниз.'},
  {q:'Не приходят уведомления о предупреждениях',
   a:'Проверь, отмечены ли районы звёздочкой и включён ли переключатель в настройках. Уведомления приходят сообщением от бота в чат.'},
  {q:'Позиция не определяется',
   a:'В глубине корпуса GPS телефона часто не ловит. Выйди на крыло мостика или введи координаты вручную. Проверь, что доступ к геопозиции разрешён.'},
  {q:'Кнопка оплаты ничего не открывает',
   a:'Оплата работает только внутри Telegram: приложение должно быть открыто кнопкой в чате с ботом, а не по ссылке в браузере.'},
  {q:'Нашёл ошибку или есть предложение',
   a:'Настройки → Написать в поддержку. Переписка идёт прямо здесь, я отвечаю в этом же чате.'}]}
];
const FAQ_OPEN={}, FAQ_ANS={};
let FAQ_Q='';

function renderFaq(){
  const box=$('#faqBox'); if(!box) return;
  const q=FAQ_Q.trim().toLowerCase();

  const cats=FAQ.map((c,ci)=>{
    const items=c.items.filter(it=>!q||
      (it.q+' '+it.a).toLowerCase().indexOf(q)!==-1);
    return {c,ci,items};
  }).filter(x=>x.items.length);

  if(!cats.length){
    box.innerHTML=`<div class="faqempty">${esc(tr('Ничего не нашлось. Спроси в поддержке, отвечу и добавлю в справку.'))}</div>`;
    bindFaq(); return;
  }

  box.innerHTML=cats.map(({c,ci,items})=>{
    const open=q?true:!!FAQ_OPEN[ci];
    return `<div class="faqcat ${open?'on':''}">
      <button class="faqhead" data-fc="${ci}">
        ${ico(c.i,'sm')}<span>${esc(tr(c.t))}</span>
        <span class="cnt">${items.length}</span><span class="ar">›</span>
      </button>
      <div class="faqitems">${items.map(it=>{
        const key=ci+'|'+c.items.indexOf(it);
        return `<button class="faqq ${FAQ_ANS[key]?'on':''}" data-fq="${esc(key)}">
          <span class="q">${esc(tr(it.q))}</span>
          <span class="a">${esc(tr(it.a))}</span>
        </button>`;
      }).join('')}</div>
    </div>`;
  }).join('');
  bindFaq();
  applyLang();
}
function bindFaq(){
  document.querySelectorAll('[data-fc]').forEach(b=>b.onclick=()=>{
    const i=b.dataset.fc; FAQ_OPEN[i]=!FAQ_OPEN[i]; hap(); renderFaq();
  });
  document.querySelectorAll('[data-fq]').forEach(b=>b.onclick=()=>{
    const k=b.dataset.fq; FAQ_ANS[k]=!FAQ_ANS[k]; hap(); renderFaq();
  });
}

/* ================= Поддержка =================
   Переписка с создателем бота внутри приложения. Сообщение сразу уходит
   ему в Telegram, ответ приходит и сюда, и обычным сообщением от бота. */
let SUP=null, SUP_BUSY=false;

async function loadSupport(){
  if(SUP_BUSY) return SUP;
  SUP_BUSY=true; renderSupport();
  try{ SUP=await api('/api/support?action=seen'); }
  catch(e){ SUP={messages:[],error:'net'}; }
  SUP_BUSY=false; renderSupport(); paintBell();
  return SUP;
}
async function supSend(text){
  text=(text||'').trim();
  if(!text) return;
  SUP=SUP||{messages:[]};
  SUP.messages.push({author:'user',text:text,at:new Date().toISOString()});
  renderSupport();
  try{ SUP=await api('/api/support?action=send&text='+encodeURIComponent(text)); }
  catch(e){}
  renderSupport();
}
function renderSupport(){
  const box=$('#supBox'); if(!box) return;
  const hint=$('#supHint');
  if(hint) hint.innerHTML=ico('alert','xs')+' '+
    esc(tr('Пишешь напрямую создателю бота. Ответ придёт сюда и сообщением в чат.'));

  const msgs=(SUP&&SUP.messages)||[];
  if(SUP&&SUP.error==='unauthorized'){
    box.innerHTML=`<div class="empty">${ico('alert')}${
      esc(tr('Поддержка работает только внутри Telegram. Открой приложение кнопкой в чате с ботом.'))}</div>`;
    return;
  }
  if(!msgs.length){
    box.innerHTML=`<div class="askintro">
      <div class="ai">${ico('compass','lg')}</div>
      <div class="at">${esc(tr('Чем помочь?'))}</div>
      <div class="as">${esc(tr('Опиши, что не работает или чего не хватает. Прочту и отвечу.'))}</div>
    </div>`;
    return;
  }
  box.innerHTML=msgs.map(m=>
    `<div class="supmsg ${m.author==='user'?'me':'owner'}">
       <div class="who">${esc(tr(m.author==='user'?'Ты':'Поддержка'))} · ${esc(ago(m.at))}</div>
       ${esc(m.text)}
     </div>`).join('');
  try{ box.scrollTop=box.scrollHeight; }catch(e){}
  applyLang();
}
function bindSupportInput(){
  const inp=$('#supInput'), btn=$('#supSend');
  const go=()=>{ const v=inp?inp.value:''; if(inp) inp.value=''; hap('medium'); supSend(v); };
  if(btn) btn.onclick=go;
  if(inp) inp.onkeydown=e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); go(); } };
}

/* Ответ приходит не по нажатию кнопки, а когда его напишут, поэтому пока
   раздел открыт -- тихо перечитываем переписку. Раньше ответ появлялся
   только после перезахода в приложение.
   Опрос идёт лишь на своём экране и при видимой вкладке: в рейсе канал
   спутниковый, гонять запросы в фоне незачем. */
let SUP_POLL=null;
function supPollStart(){
  supPollStop();
  SUP_POLL=setInterval(async()=>{
    if(S.view!=='support'||document.hidden){ supPollStop(); return; }
    if(SUP_BUSY) return;
    try{
      const fresh=await api('/api/support?action=seen');
      const was=(SUP&&SUP.messages||[]).length;
      SUP=fresh;
      if((fresh.messages||[]).length>was){ hap('medium'); paintBell(); }
      renderSupport();
    }catch(e){}
  }, 7000);
}
function supPollStop(){ if(SUP_POLL){ clearInterval(SUP_POLL); SUP_POLL=null; } }


/* ================= Панель создателя бота =================
   Всё, что раньше жило только командами в чате: кто платит, кто пользуется,
   сколько звёзд пришло, что спрашивают в поддержке. Команды остались, но
   набирать /refund с номером операции на телефоне почти невозможно.

   Данные отдаёт сервер и только владельцу, по подписи Telegram. Разделы
   разнесены по вкладкам: на экране телефона одновременно помещается
   десяток цифр, а не сорок. */
let ADM=null, ADM_SEC='over', ADM_TAB='all', ADM_Q='', ADM_OPEN=null;
let ADM_BUSY=false, ADM_TYPING=false, ADM_CARD=null, ADM_THREAD=null, ADM_SRC=null;

const ADM_SECS=[
  {v:'over',   t:'Обзор',   i:'gauge'},
  {v:'people', t:'Люди',    i:'compass'},
  {v:'money',  t:'Деньги',  i:'star'},
  {v:'talk',   t:'Связь',   i:'archive'},
  {v:'sys',    t:'Система', i:'sliders'}
];

async function loadAdmin(){
  try{ ADM=await api('/api/admin'); }
  catch(e){ ADM={error:'network'}; }
  renderAdmin();
}
async function loadAdminUsers(){
  const q=encodeURIComponent(ADM_Q||'');
  const only=ADM_TAB==='all'?'':ADM_TAB;
  try{
    const r=await api('/api/admin?action=users&q='+q+'&only='+only);
    if(r&&r.users){ ADM=ADM||{}; ADM.users=r.users; }
  }catch(e){}
  renderAdmin();
}
function admSay(text, cls){
  const el=$('#admState'); if(!el) return;
  el.className='buystate'+(cls?' '+cls:'');
  el.textContent=text||'';
}

/* Действие владельца: выдать, снять, вернуть, написать. Список после
   каждого перечитываем целиком: цифры в шапке меняются вместе со строкой,
   и обновлять одну строку было бы враньём. */
async function admAct(qs, okText, keepCard){
  if(ADM_BUSY) return null;
  ADM_BUSY=true; hap('medium'); admSay(tr('Выполняю…'));
  let r=null;
  try{ r=await api('/api/admin?'+qs); }
  catch(e){ r={error:'network'}; }
  ADM_BUSY=false;

  if(!r||r.error){
    admSay((r&&r.error==='forbidden'?tr('Нет доступа.'):tr('Не получилось.'))
           +((r&&r.detail)?(' '+r.detail):''),'no');
    return r;
  }
  const openId=keepCard&&ADM_CARD?ADM_CARD.user_id:null;
  await loadAdmin();
  if(openId) await admOpenUser(openId);
  admSay(okText,'ok');
  return r;
}

/* ---- Мелкие кирпичики оформления ---- */
function admName(u){
  const n=[(u.first_name||'').trim(), u.username?('@'+u.username):''].filter(Boolean).join(' ');
  return n||('id '+u.user_id);
}
function admCells(list){
  return '<div class="admgrid">'+list.map(c=>
    `<div class="admcell ${c.hot?'hot':''}"><b>${c.v}</b><span>${esc(tr(c.t))}</span></div>`).join('')+'</div>';
}
/* Столбики за 30 дней. Рисуем сами, без библиотеки графиков: в рейсе
   приложение открывается без сети, а тянуть 200 КБ ради тридцати
   прямоугольников незачем. */
function admBars(rows, key, color){
  if(!rows||!rows.length) return '';
  const max=Math.max(1,...rows.map(r=>r[key]||0));
  const w=100/rows.length;
  return `<svg class="admchart" viewBox="0 0 100 30" preserveAspectRatio="none">`+
    rows.map((r,i)=>{
      const v=r[key]||0, h=v?Math.max(1.2, v/max*28):0.4;
      return `<rect x="${(i*w+w*0.15).toFixed(2)}" y="${(29-h).toFixed(2)}"
        width="${(w*0.7).toFixed(2)}" height="${h.toFixed(2)}" rx="0.5"
        fill="${v?color:'currentColor'}" opacity="${v?1:.18}"></rect>`;
    }).join('')+`</svg>`;
}
function admSum(rows, key){ return (rows||[]).reduce((a,r)=>a+(r[key]||0),0); }

/* ---- Обзор ---- */
function admOverview(){
  const s=ADM.summary||{}, bal=ADM.balance||{}, g=ADM.growth||[];
  const stars=(bal.stars==null)?null:bal.stars;
  const need=Math.max(0,((ADM.withdraw||{}).min||1000)-(stars||0));

  const attention=[];
  if(s.support_open) attention.push({t:'Обращения без ответа', v:s.support_open, go:'talk'});
  if(s.expiring_week) attention.push({t:'Подписка кончается на неделе', v:s.expiring_week, go:'money'});
  if(s.cancelled) attention.push({t:'Отключили автопродление', v:s.cancelled, go:'people'});

  return `
    <div class="dpanel"><h4>Сейчас</h4>
      ${stars===null
        ? `<div class="tres warn"><span class="tl">${esc(tr('Баланс не пришёл'))}</span>
             <span class="tv" style="font-size:12px">${esc(bal.error||'')}</span></div>`
        : `<div class="admhead">
             <div><div class="admbig">${stars} ⭐</div>
               <div class="admsub">${esc(tr('на балансе бота'))}</div></div>
             <div class="admhead-r"><div class="admmid">${s.mrr_stars||0} ⭐</div>
               <div class="admsub">${esc(tr('в месяц с текущих подписок'))}</div></div>
           </div>
           ${need>0?`<div class="hint" style="padding:8px 0 0">${
             esc(tr('До вывода не хватает')+' '+need+' ⭐')}</div>`:''}`}
      ${admCells([
        {v:s.users||0,        t:'человек всего'},
        {v:s.active_week||0,  t:'заходили за неделю'},
        {v:s.paid_now||0,     t:'платят сейчас'},
        {v:(s.conversion||0)+'%', t:'дошли до оплаты'},
        {v:s.new_week||0,     t:'пришли за неделю'},
        {v:s.stars_30d||0,    t:'звёзд за 30 дней'}
      ])}
    </div>

    ${attention.length?`<div class="dpanel"><h4>Требует внимания</h4>
      ${attention.map(a=>`<div class="sw" data-adm-go="${a.go}">
        <div style="min-width:0"><div class="t">${ico('alert','sm')}${esc(tr(a.t))}</div></div>
        <span class="rtag am">${a.v}</span></div>`).join('')}
    </div>`:`<div class="dpanel"><h4>Требует внимания</h4>
      <div class="hint" style="padding:10px 0">${ico('anchor','xs')} ${
        esc(tr('Ничего не ждёт ответа: обращений нет, подписки в ближайшую неделю не кончаются.'))}</div>
    </div>`}

    <div class="dpanel"><h4>Тридцать дней</h4>
      <div class="admline"><span>${esc(tr('Новые люди'))}</span><b>${admSum(g,'users')}</b></div>
      ${admBars(g,'users','var(--ok)')}
      <div class="admline" style="margin-top:12px"><span>${esc(tr('Звёзды'))}</span><b>${admSum(g,'stars')}</b></div>
      ${admBars(g,'stars','var(--amber)')}
      <div class="admdates"><span>${esc(String((g[0]||{}).date||'').slice(5))}</span>
        <span>${esc(String((g[g.length-1]||{}).date||'').slice(5))}</span></div>
    </div>`;
}

/* ---- Люди ---- */
function admUserRow(u){
  const paid=u.is_premium&&u.premium_until&&new Date(u.premium_until)>new Date();
  // Владелец идёт первым случаем: доступ у него из настроек бота, а не из
  // базы, и без пометки он выглядел бы как бесплатный тариф.
  const tag=u.owner
    ? `<span class="rtag am">${tr('владелец')}</span>`
    : paid
      ? `<span class="rtag ${u.premium_source==='granted'?'':'ok'}">${
          u.premium_source==='granted'?tr('выдан'):tr('оплачен')}</span>`
      : (u.paid_stars?`<span class="rtag">${u.paid_stars} ⭐</span>`
                     :`<span class="rtag">${tr('бесплатный')}</span>`);
  const bits=['id '+u.user_id];
  if(paid) bits.push(tr('до')+' '+subDate(u.premium_until));
  if(u.sub_cancelled&&paid) bits.push(tr('без автопродления'));
  if(u.paid_stars&&(paid||u.owner)) bits.push(u.paid_stars+' ⭐');
  bits.push(u.last_seen_at?(tr('заходил')+' '+ago(u.last_seen_at)):tr('в приложение не заходил'));

  return `<div class="sw" data-adm-user="${u.user_id}">
      <div style="min-width:0"><div class="t">${esc(admName(u))}</div>
        <div class="d">${esc(bits.join(' · '))}</div></div>
      ${tag}
    </div>`;
}
function admPeople(){
  if(ADM_CARD) return admCardView();
  const users=(ADM.users||[]);
  return `
    <div class="dpanel"><h4>Люди</h4>
      <div class="admseg">
        <button data-adm-tab="all" class="${ADM_TAB==='all'?'on':''}">${esc(tr('Все'))}</button>
        <button data-adm-tab="paid" class="${ADM_TAB==='paid'?'on':''}">${esc(tr('С Premium'))}</button>
        <button data-adm-tab="active" class="${ADM_TAB==='active'?'on':''}">${esc(tr('Активные'))}</button>
      </div>
      <div class="sbox" style="margin-bottom:9px">
        <input id="admQ" placeholder="${esc(tr('Найти по id, имени или @нику'))}"
               autocomplete="off" value="${esc(ADM_Q)}">
      </div>
      ${users.length?users.map(admUserRow).join('')
        :`<div class="hint" style="padding:14px 0">${esc(tr('Никого не нашлось.'))}</div>`}
      <div class="buystate" id="admState"></div>
      <div class="hint" style="margin:4px 0 0">${ico('alert','xs')} ${
        esc(tr('Нажми на человека, чтобы открыть карточку: платежи, устройства, районы и переписка.'))}</div>
    </div>`;
}

/* Карточка одного человека. Открывается вместо списка, а не под строкой:
   на телефоне раскрывающийся блок уводит список за край экрана, и назад
   приходится листать вслепую. */
function admCardView(){
  const u=ADM_CARD;
  const paid=u.is_premium&&u.premium_until&&new Date(u.premium_until)>new Date();
  const pays=(u.payments||[]), dev=(u.devices||[]), sup=(u.support||[]);
  const spent=pays.filter(p=>!p.refunded_at).reduce((a,p)=>a+(p.stars_amount||0),0);

  return `
    <div class="dpanel">
      <button class="btn g wide" id="admBack" style="margin-bottom:11px">← ${esc(tr('К списку'))}</button>
      <div class="admhead">
        <div><div class="admmid">${esc(admName(u))}</div>
          <div class="admsub">id ${u.user_id}${u.owner?(' · '+esc(tr('владелец'))):''}</div></div>
        <span class="rtag ${paid?'ok':''}">${paid
          ? (u.premium_source==='granted'?tr('выдан'):tr('оплачен')) : tr('бесплатный')}</span>
      </div>
      ${admCells([
        {v:spent,                t:'звёзд заплатил'},
        {v:pays.length,          t:'платежей'},
        {v:(u.areas||0),         t:'районов'},
        {v:dev.length,           t:'устройств'}
      ])}
      <div class="tres"><span class="tl">${esc(tr('Пришёл'))}</span>
        <span class="tv" style="font-size:13px">${esc(subDate(u.created_at))}</span></div>
      <div class="tres"><span class="tl">${esc(tr('Был в приложении'))}</span>
        <span class="tv" style="font-size:13px">${u.last_seen_at?esc(ago(u.last_seen_at)):esc(tr('ни разу'))}</span></div>
      ${paid?`<div class="tres"><span class="tl">${esc(tr('Premium до'))}</span>
        <span class="tv" style="font-size:13px">${esc(subDate(u.premium_until))}${
          u.sub_cancelled?(' · '+esc(tr('без автопродления'))):''}</span></div>`:''}
      ${u.vessel?`<div class="tres"><span class="tl">${esc(tr('Судно'))}</span>
        <span class="tv" style="font-size:13px">${esc(u.vessel)}</span></div>`:''}
      <div class="admacts" style="margin-top:11px">
        <button class="btn g" data-grant="${u.user_id}" data-days="7">+7 ${tr('дн')}</button>
        <button class="btn g" data-grant="${u.user_id}" data-days="30">+30 ${tr('дн')}</button>
        <button class="btn g" data-grant="${u.user_id}" data-days="365">+365 ${tr('дн')}</button>
        ${paid?`<button class="btn g" data-revoke="${u.user_id}">${tr('Снять Premium')}</button>`:''}
      </div>
      <div class="buystate" id="admState"></div>
    </div>

    <div class="dpanel"><h4>Написать</h4>
      <textarea id="admMsg" class="admtext" rows="3"
        placeholder="${esc(tr('Сообщение придёт в чат с ботом и ляжет в переписку поддержки'))}"></textarea>
      <button class="btn wide" id="admSend" style="margin-top:9px">${esc(tr('Отправить'))}</button>
    </div>

    ${pays.length?`<div class="dpanel"><h4>Платежи</h4>
      ${pays.map(admPayRow).join('')}</div>`:''}

    ${sup.length?`<div class="dpanel"><h4>Переписка</h4>
      ${sup.slice(-6).map(m=>`<div class="supmsg ${m.author==='user'?'me':'owner'}">
        <div class="who">${esc(tr(m.author==='user'?'Он':'Я'))} · ${esc(ago(m.created_at))}</div>
        ${esc(m.text)}</div>`).join('')}</div>`:''}

    ${dev.length?`<div class="dpanel"><h4>Устройства</h4>
      ${dev.map(d=>`<div class="tres"><span class="tl mono">${esc(String(d.device_id).slice(0,12))}…</span>
        <span class="tv" style="font-size:12px">${esc(ago(d.last_seen))}</span></div>`).join('')}
      <div class="hint" style="margin:6px 0 0">${ico('alert','xs')} ${
        esc(tr('Одно устройство на несколько аккаунтов бывает у сменщиков и курсантов. Пробный период получает только первый из них.'))}</div>
    </div>`:''}`;
}

/* ---- Деньги ---- */
function admPayRow(p){
  const gone=!!p.refunded_at;
  const who=p.first_name||p.username?admName(p):('id '+p.user_id);
  return `<div class="admpay ${gone?'gone':''}">
      <div class="pw"><span>${esc(who)}</span><span>${p.stars_amount} ⭐</span></div>
      <div class="pd">id ${p.user_id} · ${esc(String(p.created_at||'').slice(0,16).replace('T',' '))}${
        p.is_recurring?(' · '+tr('автопродление')):''}${gone?(' · '+tr('возвращено')):''}</div>
      <div class="pc">${esc(p.charge_id||'')}</div>
      ${gone?'':`<div class="admacts" style="margin:9px 0 0">
        <button class="btn g" data-refund="${p.user_id}" data-charge="${esc(p.charge_id||'')}">${
          tr('Вернуть звёзды')}</button></div>`}
    </div>`;
}
function admMoney(){
  const s=ADM.summary||{}, bal=ADM.balance||{}, w=ADM.withdraw||{};
  const stars=(bal.stars==null)?null:bal.stars;
  const need=Math.max(0,(w.min||1000)-(stars||0));
  const pct=Math.min(100, Math.round(((stars||0)/(w.min||1000))*100));
  const pays=(ADM.payments||[]), exp=(ADM.expiring||[]);

  return `
    <div class="dpanel"><h4>Звёзды</h4>
      ${stars===null
        ? `<div class="tres warn"><span class="tl">${esc(tr('Баланс не пришёл'))}</span>
             <span class="tv" style="font-size:12px">${esc(bal.error||'')}</span></div>`
        : `<div class="admbig">${stars} ⭐</div>
           <div class="hint" style="padding:6px 0 0">${
             esc(tr('Это баланс бота в Telegram. Деньги за подписки приходят сюда.'))}</div>
           <div class="admbar"><i style="width:${pct}%"></i></div>
           <div class="hint" style="padding:0">${need>0
             ? esc(tr('До вывода не хватает')+' '+need+' ⭐ '+tr('из')+' '+(w.min||1000))
             : esc(tr('Минимума для вывода хватает.'))}</div>`}
      ${admCells([
        {v:s.stars_total||0,    t:'получено всего'},
        {v:s.stars_30d||0,      t:'за 30 дней'},
        {v:s.refunded_stars||0, t:'возвращено'},
        {v:s.mrr_stars||0,      t:'ждём в месяц'},
        {v:s.payers||0,         t:'платили хоть раз'},
        {v:(s.conversion||0)+'%', t:'дошли до оплаты'}
      ])}
    </div>

    <div class="dpanel"><h4>Вывод</h4>
      <div class="tres"><span class="tl">${esc(tr('Минимум для вывода'))}</span>
        <span class="tv">${w.min||1000} ⭐</span></div>
      <div class="tres"><span class="tl">${esc(tr('Выдержка каждой звезды'))}</span>
        <span class="tv">${w.hold_days||21} ${esc(tr('дн'))}</span></div>
      <div class="tres"><span class="tl">${esc(tr('Срок прошли, по моему учёту'))}</span>
        <span class="tv">${w.ripe_estimate||0} ⭐</span></div>
      <div class="hint" style="margin:9px 0 0">${ico('alert','xs')} ${esc(tr(
        'Вывод идёт только через Fragment и только в TON. У Bot API такого метода нет, кнопкой из бота его не вызвать. Telegram держит каждую звезду 21 день на случай возврата покупателю.'))}</div>
      <button class="btn wide" id="admFragment" style="margin-top:9px">${esc(tr('Открыть Fragment'))}</button>
    </div>

    ${exp.length?`<div class="dpanel"><h4>Кончается на неделе</h4>
      ${exp.map(u=>`<div class="sw" data-adm-user="${u.user_id}">
        <div style="min-width:0"><div class="t">${esc(admName(u))}</div>
          <div class="d">${esc(tr('до')+' '+subDate(u.premium_until))}${
            u.sub_cancelled?(' · '+esc(tr('автопродление выключено'))):''}</div></div>
        <span class="rtag ${u.sub_cancelled?'':'ok'}">${u.sub_cancelled?tr('уйдёт'):tr('продлится')}</span>
      </div>`).join('')}
      <div class="hint" style="margin:4px 0 0">${ico('alert','xs')} ${esc(tr(
        'У кого автопродление выключено, подписка после этой даты просто закончится.'))}</div>
    </div>`:''}

    <div class="dpanel"><h4>Платежи</h4>
      ${pays.length?pays.map(admPayRow).join('')
        :`<div class="hint" style="padding:14px 0">${esc(tr('Платежей пока нет.'))}</div>`}
      <div class="buystate" id="admState"></div>
      <div class="hint" style="margin:4px 0 0">${ico('alert','xs')} ${esc(tr(
        'Возврат отдаёт звёзды покупателю целиком и снимает Premium. Отменить возврат нельзя.'))}</div>
    </div>`;
}

/* ---- Связь: поддержка и объявления ---- */
function admTalk(){
  if(ADM_THREAD) return admThreadView();
  const th=(ADM.threads||[]), nt=(ADM.notices||[]);
  return `
    <div class="dpanel"><h4>Обращения</h4>
      ${th.length?th.map(t=>`<div class="sw" data-adm-thread="${t.user_id}">
        <div style="min-width:0"><div class="t">${esc(t.first_name||('id '+t.user_id))}${
          t.username?(' @'+esc(t.username)):''}</div>
          <div class="d">${esc(tr('сообщений')+' '+t.total+' · '+ago(t.last_at))}</div></div>
        <span class="rtag ${t.unread?'am':''}">${t.unread?t.unread:'→'}</span>
      </div>`).join('')
        :`<div class="hint" style="padding:14px 0">${esc(tr('Обращений пока нет.'))}</div>`}
    </div>

    <div class="dpanel"><h4>Написать всем в колокольчик</h4>
      <input id="admNtTitle" class="admtext" placeholder="${esc(tr('Заголовок'))}" autocomplete="off">
      <textarea id="admNtBody" class="admtext" rows="3" style="margin-top:8px"
        placeholder="${esc(tr('Что изменилось в боте'))}"></textarea>
      <div class="admseg" style="margin:9px 0">
        <button data-adm-kind="release" class="on">${esc(tr('Обновление'))}</button>
        <button data-adm-kind="news">${esc(tr('Новость'))}</button>
      </div>
      <button class="btn wide" id="admPublish">${esc(tr('Опубликовать'))}</button>
      <div class="buystate" id="admState"></div>
      <div class="hint" style="margin:9px 0 0">${ico('alert','xs')} ${esc(tr(
        'Запись появится у всех в колокольчике и подсветится как непрочитанная. Сообщением в чат она не уходит и никого не разбудит на вахте.'))}</div>
    </div>

    ${nt.length?`<div class="dpanel"><h4>Что уже опубликовано</h4>
      ${nt.map(n=>`<div class="tres"><span class="tl">${esc(n.title)}</span>
        <span class="tv" style="font-size:12px">${esc(ago(n.created_at))}</span></div>`).join('')}
    </div>`:''}`;
}
function admThreadView(){
  const t=ADM_THREAD;
  return `
    <div class="dpanel">
      <button class="btn g wide" id="admBack" style="margin-bottom:11px">← ${esc(tr('К обращениям'))}</button>
      <div class="admmid">${esc(t.name||('id '+t.user_id))}</div>
      <div class="admsub" style="margin-bottom:11px">id ${t.user_id}</div>
      ${(t.messages||[]).map(m=>`<div class="supmsg ${m.author==='user'?'me':'owner'}">
        <div class="who">${esc(tr(m.author==='user'?'Он':'Я'))} · ${esc(ago(m.created_at))}</div>
        ${esc(m.text)}</div>`).join('')}
      <textarea id="admMsg" class="admtext" rows="3" style="margin-top:11px"
        placeholder="${esc(tr('Ответ придёт в чат с ботом'))}"></textarea>
      <button class="btn wide" id="admSend" style="margin-top:9px">${esc(tr('Ответить'))}</button>
      <div class="buystate" id="admState"></div>
    </div>`;
}

/* ---- Система ---- */
function admSys(){
  const w=ADM.warnings||{};
  return `
    <div class="dpanel"><h4>Бот</h4>
      <div class="tres"><span class="tl">${esc(tr('Сборка'))}</span>
        <span class="tv mono" style="font-size:13px">${esc(ADM.build||'')}</span></div>
      <div class="tres"><span class="tl">${esc(tr('База'))}</span>
        <span class="tv" style="font-size:13px">${esc(ADM.database||'')}</span></div>
      <div class="tres"><span class="tl">${esc(tr('Сервер поднят'))}</span>
        <span class="tv" style="font-size:13px">${ADM.uptime_h||0} ${esc(tr('ч'))}</span></div>
      <div class="tres"><span class="tl">${esc(tr('Тарифы'))}</span>
        <span class="tv" style="font-size:13px">${esc(tr(ADM.paywall?'включены':'выключены, всё открыто'))}</span></div>
      <div class="tres"><span class="tl">${esc(tr('Цена подписки'))}</span>
        <span class="tv">${ADM.price_stars||0} ⭐</span></div>
      <div class="tres"><span class="tl">${esc(tr('Пробный период'))}</span>
        <span class="tv" style="font-size:13px">${ADM.trial_days||0} ${esc(tr('дн'))}</span></div>
      ${ADM.test_env?`<div class="tres warn"><span class="tl">${esc(tr('Тестовая среда Telegram'))}</span>
        <span class="tv" style="font-size:13px">${esc(tr('включена'))}</span></div>`:''}
    </div>

    <div class="dpanel"><h4>Предупреждения в базе</h4>
      ${admCells([
        {v:w.active_warnings||0, t:'действующих'},
        {v:w.total_warnings||0,  t:'всего'},
        {v:(ADM.summary||{}).areas_marked||0, t:'районов отмечено'}
      ])}
    </div>

    <div class="dpanel"><h4>Источники</h4>
      <button class="btn wide" id="admSources">${esc(tr('Опросить источники сейчас'))}</button>
      <div class="buystate" id="admState"></div>
      ${ADM_SRC?`<div style="margin-top:11px">${ADM_SRC.map(s=>
        `<div class="tres ${s.ok?'':'warn'}"><span class="tl">${esc(s.area)} · ${esc(s.source)}</span>
         <span class="tv" style="font-size:13px">${s.ok?(s.count+' '+esc(tr('сообщ.'))):esc(s.reason||'')}</span>
        </div>`).join('')}</div>`
        :`<div class="hint" style="margin:9px 0 0">${ico('alert','xs')} ${esc(tr(
          'Обход занимает несколько секунд: бот стучится в каждую службу и показывает, сколько сообщений она отдала прямо сейчас.'))}</div>`}
    </div>`;
}

/* ---- Сборка экрана и обработчики ---- */
function renderAdmin(){
  const box=$('#admBox'); if(!box) return;

  if(!ADM){ box.innerHTML='<div class="sk card"></div><div class="sk card"></div>'; return; }
  if(ADM.error==='forbidden'){
    box.innerHTML=`<div class="empty">${ico('alert')}${
      esc(tr('Раздел только для создателя бота.'))}</div>`;
    return;
  }
  if(ADM.error){
    box.innerHTML=`<div class="empty">${ico('alert')}${
      esc(tr('Нет связи с сервером. Открой раздел ещё раз.'))}</div>`;
    return;
  }

  const nav=`<div class="admnav">${ADM_SECS.map(s=>
    `<button data-adm-sec="${s.v}" class="${ADM_SEC===s.v?'on':''}">${ico(s.i,'sm')}<span>${esc(tr(s.t))}</span></button>`
    ).join('')}</div>`;

  let body='';
  if(ADM_SEC==='over')   body=admOverview();
  if(ADM_SEC==='people') body=admPeople();
  if(ADM_SEC==='money')  body=admMoney();
  if(ADM_SEC==='talk')   body=admTalk();
  if(ADM_SEC==='sys')    body=admSys();
  box.innerHTML=nav+body;

  box.querySelectorAll('[data-adm-sec]').forEach(b=>b.onclick=()=>{
    ADM_SEC=b.dataset.admSec; ADM_CARD=null; ADM_THREAD=null; hap(); renderAdmin();
  });
  box.querySelectorAll('[data-adm-go]').forEach(b=>b.onclick=()=>{
    ADM_SEC=b.dataset.admGo; hap(); renderAdmin();
  });
  const back=$('#admBack');
  if(back) back.onclick=()=>{ ADM_CARD=null; ADM_THREAD=null; hap(); renderAdmin(); };

  const fr=$('#admFragment');
  if(fr) fr.onclick=()=>{
    hap('medium');
    // Fragment живёт вне Telegram, поэтому openLink, а не openTelegramLink.
    const url=(ADM.withdraw||{}).fragment||'https://fragment.com/stars';
    try{ TG.openLink(url); }catch(e){ window.open(url,'_blank'); }
  };

  box.querySelectorAll('[data-adm-tab]').forEach(b=>b.onclick=()=>{
    ADM_TAB=b.dataset.admTab; ADM_OPEN=null; hap(); loadAdminUsers();
  });
  const q=$('#admQ');
  if(q){
    let t=null;
    q.oninput=()=>{ ADM_TYPING=true; clearTimeout(t);
      t=setTimeout(()=>{ ADM_Q=q.value; ADM_OPEN=null; loadAdminUsers(); },350); };
    q.onblur=()=>{ ADM_TYPING=false; };
    // Список перерисовывается на каждую букву вместе с полем ввода. Без
    // возврата фокуса на телефоне после первой же буквы закрывалась
    // клавиатура, и набрать что-то длиннее «55» было невозможно.
    if(ADM_TYPING){
      q.focus();
      try{ q.setSelectionRange(q.value.length, q.value.length); }catch(e){}
    }
  }

  box.querySelectorAll('[data-adm-user]').forEach(el=>el.onclick=()=>{
    hap(); admOpenUser(parseInt(el.dataset.admUser,10));
  });
  box.querySelectorAll('[data-adm-thread]').forEach(el=>el.onclick=()=>{
    hap(); admOpenThread(parseInt(el.dataset.admThread,10));
  });

  box.querySelectorAll('[data-grant]').forEach(b=>b.onclick=e=>{
    e.stopPropagation();
    admAct('action=grant&user_id='+b.dataset.grant+'&days='+b.dataset.days,
           tr('Premium выдан, человек получил сообщение.'), true);
  });
  box.querySelectorAll('[data-revoke]').forEach(b=>b.onclick=e=>{
    e.stopPropagation();
    if(!confirm(tr('Снять Premium? Деньги при этом не возвращаются.'))) return;
    admAct('action=revoke&user_id='+b.dataset.revoke, tr('Premium снят.'), true);
  });
  box.querySelectorAll('[data-refund]').forEach(b=>b.onclick=e=>{
    e.stopPropagation();
    if(!confirm(tr('Вернуть звёзды покупателю? Premium будет снят, отменить возврат нельзя.'))) return;
    admAct('action=refund&user_id='+b.dataset.refund+'&charge_id='+encodeURIComponent(b.dataset.charge),
           tr('Звёзды возвращены, Premium снят.'), true);
  });

  const send=$('#admSend');
  if(send) send.onclick=async()=>{
    const ta=$('#admMsg'); const text=ta?ta.value.trim():'';
    if(!text){ admSay(tr('Сначала напиши текст.'),'no'); return; }
    const uid=(ADM_THREAD?ADM_THREAD.user_id:(ADM_CARD?ADM_CARD.user_id:0));
    if(!uid) return;
    if(ta) ta.value='';
    await admAct('action=message&user_id='+uid+'&text='+encodeURIComponent(text),
                 tr('Отправлено.'), !ADM_THREAD);
    if(ADM_THREAD) admOpenThread(uid);
  };

  const pub=$('#admPublish');
  if(pub) pub.onclick=async()=>{
    const t=$('#admNtTitle'), b=$('#admNtBody');
    const title=t?t.value.trim():'', body=b?b.value.trim():'';
    if(!title){ admSay(tr('Нужен заголовок.'),'no'); return; }
    const kind=(box.querySelector('[data-adm-kind].on')||{}).dataset
      ? box.querySelector('[data-adm-kind].on').dataset.admKind : 'release';
    if(t) t.value=''; if(b) b.value='';
    await admAct('action=notice&kind='+kind+'&title='+encodeURIComponent(title)
                 +'&body='+encodeURIComponent(body), tr('Опубликовано, запись ушла в колокольчик.'));
  };
  box.querySelectorAll('[data-adm-kind]').forEach(b=>b.onclick=()=>{
    box.querySelectorAll('[data-adm-kind]').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); hap();
  });

  const src=$('#admSources');
  if(src) src.onclick=async()=>{
    hap('medium'); src.disabled=true; src.textContent=tr('Опрашиваю…');
    try{ const r=await api('/api/admin?action=sources'); ADM_SRC=r.sources||[]; }
    catch(e){ ADM_SRC=[]; }
    renderAdmin();
  };

  applyLang();
}

async function admOpenUser(id){
  try{
    const r=await api('/api/admin?action=user&user_id='+id);
    if(r&&r.card){ ADM_CARD=r.card; ADM_SEC='people'; ADM_THREAD=null; }
  }catch(e){}
  renderAdmin();
}
async function admOpenThread(id){
  try{
    const r=await api('/api/admin?action=thread&user_id='+id);
    const who=(ADM.threads||[]).find(t=>t.user_id===id)||{};
    ADM_THREAD={user_id:id, messages:r.messages||[],
                name:[(who.first_name||'').trim(), who.username?('@'+who.username):''].filter(Boolean).join(' ')};
    ADM_SEC='talk'; ADM_CARD=null;
    paintBell();
  }catch(e){}
  renderAdmin();
}


/* ================= Тренажёр ЦИВ (DSC) =================
   Экранная копия Furuno FS-1575: дисплей, клавиатура, кнопка бедствия
   под крышкой. Ничего в эфир не уходит -- вся связь имитируется, включая
   задержки на подтверждение, как на настоящей станции. */
/* Справочник ЦИВ зашит в приложение: тренажёр статичен, ходить за ним на
   сервер незачем -- и он продолжает работать в рейсе без связи. С сервера
   данные подхватываются только если там окажется более свежая версия. */
const DSC_BUILTIN={"freqs":[{"band":"MF","dsc":2187.5,"rt":2182.0,"nbdp":2174.5,"note":"Средние волны. Дальность порядка 150 миль днём, ночью больше."},{"band":"HF 4","dsc":4207.5,"rt":4125.0,"nbdp":4177.5,"note":"Ночью и на рассвете, дальность до 300 миль."},{"band":"HF 6","dsc":6312.0,"rt":6215.0,"nbdp":6268.0,"note":"Круглосуточно, средние дистанции."},{"band":"HF 8","dsc":8414.5,"rt":8291.0,"nbdp":8376.5,"note":"Самый универсальный диапазон, работает днём и ночью."},{"band":"HF 12","dsc":12577.0,"rt":12290.0,"nbdp":12520.0,"note":"День, большие дистанции."},{"band":"HF 16","dsc":16804.5,"rt":16420.0,"nbdp":16695.0,"note":"День, максимальная дальность."}],"nature":[{"id":"fire","t":"Fire, explosion","ru":"Пожар, взрыв"},{"id":"flooding","t":"Flooding","ru":"Поступление воды"},{"id":"collision","t":"Collision","ru":"Столкновение"},{"id":"grounding","t":"Grounding","ru":"Посадка на мель"},{"id":"listing","t":"Listing, danger of capsizing","ru":"Крен, опасность опрокидывания"},{"id":"sinking","t":"Sinking","ru":"Затопление"},{"id":"adrift","t":"Disabled and adrift","ru":"Потеря хода, дрейф"},{"id":"undesign","t":"Undesignated distress","ru":"Бедствие без уточнения"},{"id":"abandon","t":"Abandoning ship","ru":"Оставление судна"},{"id":"piracy","t":"Piracy / armed robbery","ru":"Пиратское нападение"},{"id":"mob","t":"Man overboard","ru":"Человек за бортом"}],"calls":[{"id":"distress","t":"Distress Alert","ru":"Вызов бедствия","cat":"Distress","needs":["nature","position"],"why":"Подаётся только при непосредственной опасности для судна или людей. Станция сама подставляет позицию от приёмника и передаёт по всем диапазонам. Ждём подтверждения от берегового центра, не от судов."},{"id":"relay","t":"Distress Relay","ru":"Ретрансляция бедствия","cat":"Distress","needs":["nature","position","mmsi_opt"],"why":"Передаём за другое судно: приняли сигнал бедствия, а берег его не подтвердил. Свой сигнал бедствия при этом не подаём -- иначе спасатели будут искать нас, а не терпящего бедствие."},{"id":"urgency","t":"Urgency Call","ru":"Срочность (PAN PAN)","cat":"Urgency","needs":[],"why":"Серьёзная ситуация, но непосредственной опасности гибели нет: потеря хода в стороне от судоходства, тяжёлый больной на борту."},{"id":"safety","t":"Safety Call","ru":"Безопасность (SECURITE)","cat":"Safety","needs":[],"why":"Навигационные и метеорологические предупреждения: плавающий объект, неработающий буй, шторм."},{"id":"individual","t":"Individual Call","ru":"Индивидуальный вызов","cat":"Routine","needs":["mmsi","freq"],"why":"Вызов конкретного судна или береговой станции по её MMSI. Указываем рабочую частоту, на которой будем говорить."},{"id":"allships","t":"All Ships Call","ru":"Вызов всем судам","cat":"Safety","needs":["freq"],"why":"Всем, кто в зоне слышимости. В обычной обстановке применяется только с категорией срочности или безопасности."},{"id":"group","t":"Group Call","ru":"Групповой вызов","cat":"Routine","needs":["mmsi","freq"],"why":"Судам одной группы: флот компании, суда в конвое. Групповой MMSI начинается с нуля и заранее прописан в станции."},{"id":"test","t":"Test Call","ru":"Тестовый вызов","cat":"Safety","needs":["mmsi"],"why":"Проверка работоспособности ЦИВ на ВЧ и ПВ. Направляется береговой станции, она отвечает подтверждением. На 2187.5 кГц проверка делается именно тестовым вызовом, а не вызовом бедствия."},{"id":"position","t":"Position Request","ru":"Запрос позиции","cat":"Routine","needs":["mmsi"],"why":"Запрос координат другого судна. Оно может ответить автоматически или отклонить запрос -- это его право."},{"id":"polling","t":"Polling","ru":"Опрос присутствия","cat":"Routine","needs":["mmsi"],"why":"Проверка, находится ли станция в зоне связи. Ответ приходит автоматически, без участия вахтенного на той стороне."}],"lessons":{"ack":"Подтверждение (ACK) означает, что вызов принят. При бедствии подтверждать имеет право береговой центр -- судно подтверждает только если берег молчит и судно способно помочь.","freq":"Диапазон выбирают по дальности и времени суток. Ночью проходят низкие частоты (2, 4 МГц), днём высокие (12, 16 МГц). 8 МГц работает почти всегда -- с него и начинают.","rt":"После вызова ЦИВ переходим на парную радиотелефонную частоту того же диапазона и говорим уже голосом. ЦИВ -- только для того, чтобы привлечь внимание.","distress":"Кнопка бедствия закрыта крышкой и требует удержания около пяти секунд -- защита от случайного нажатия. Если подал по ошибке, не выключай станцию: сообщи голосом на 2182 кГц, что тревога ложная, и отмени её.","mmsi":"MMSI из девяти цифр. У судна первые три -- код страны, у береговой станции первые две цифры нули, у группы -- один ноль в начале.","test":"Тестовый вызов не тревожит спасателей и не поднимает никого по тревоге. Именно им проверяют ЦИВ, как требует ежедневная проверка по ГМССБ."},"exam":[{"id":"e1","situation":"В машинном отделении пожар, экипаж не справляется, судно теряет ход. Твои действия по ЦИВ.","expect":{"call":"distress","nature":"fire"},"explain":"Непосредственная опасность для судна и людей -- это вызов бедствия с указанием характера «пожар, взрыв»."},{"id":"e2","situation":"Судно село на мель, поступления воды нет, крена нет, опасности для людей нет, но сняться самостоятельно не можешь.","expect":{"call":"urgency"},"explain":"Прямой угрозы гибели нет, значит бедствие подавать рано. Это срочность (PAN PAN). Если начнёт поступать вода или появится крен -- переходим на бедствие."},{"id":"e3","situation":"Приняли вызов бедствия с соседнего судна на 8414.5 кГц. Прошло пять минут, береговая станция не подтвердила приём.","expect":{"call":"relay"},"explain":"Передаём ретрансляцию бедствия. Свой вызов бедствия подавать нельзя -- у нас самих ничего не случилось, и спасатели пойдут не туда."},{"id":"e4","situation":"Обнаружили в море полузатопленный контейнер, представляющий опасность для судоходства.","expect":{"call":"safety"},"explain":"Навигационная опасность для других судов -- категория безопасности (SECURITE), обычно вызовом всем судам."},{"id":"e5","situation":"Нужно проверить работу ЦИВ на ПВ, как того требует ежедневная проверка ГМССБ.","expect":{"call":"test"},"explain":"Для этого есть тестовый вызов береговой станции. Вызов бедствия для проверки не применяют ни при каких обстоятельствах."},{"id":"e6","situation":"Человек упал за борт, судно развернулось на циркуляции, идёт поиск.","expect":{"call":"distress","nature":"mob"},"explain":"Жизни человека угрожает непосредственная опасность -- вызов бедствия с характером «человек за бортом»."},{"id":"e7","situation":"Нужно связаться с агентом через береговую станцию Lyngby Radio для передачи заявки на снабжение.","expect":{"call":"individual"},"explain":"Обычная деловая связь -- индивидуальный вызов береговой станции с указанием рабочей частоты."},{"id":"e8","situation":"На борту тяжелобольной, нужна консультация врача, но судно на ходу и опасности нет.","expect":{"call":"urgency"},"explain":"Медицинская консультация без угрозы гибели судна -- срочность (PAN PAN), обычно с пометкой MEDICO."},{"id":"e9","situation":"Судно атаковано вооружёнными лицами при подходе к якорной стоянке.","expect":{"call":"distress","nature":"piracy"},"explain":"Пиратское нападение -- отдельный вид бедствия по ITU-R M.493, подаётся вызов бедствия."},{"id":"e10","situation":"Нужно узнать, где сейчас находится судно компании, идущее тем же районом.","expect":{"call":"position"},"explain":"Запрос позиции. Судно вправе отклонить запрос, это нормально."}],"note":"Тренажёр. Ничего в эфир не уходит. Перед экзаменом и работой на судне сверяйся с ALRS Volume 5 и инструкцией своей станции."};
let DSC=DSC_BUILTIN;

/* ---- Каналы ПВ/КВ ----
   Дуплексные радиотелефонные каналы по Приложению 17 Регламента радиосвязи:
   в каждой полосе частота передачи судна и приёма от берега идут с шагом
   3 кГц от начала полосы. Плюс 2182 кГц -- симплексная частота бедствия
   и вызова на ПВ, с неё станция и начинает. */
function buildChannels(){
  const out=[{ch:'2182',tx:2182.0,rx:2182.0,band:'MF'}];
  [[401,4065,4357,27,'4 MHz'],[601,6200,6501,8,'6 MHz'],
   [801,8195,8719,32,'8 MHz'],[1201,12230,13077,40,'12 MHz'],
   [1601,16360,17242,41,'16 MHz']].forEach(g=>{
    for(let i=0;i<g[3];i++) out.push({ch:String(g[0]+i),tx:g[1]+3*i,rx:g[2]+3*i,band:g[4]});
  });
  return out;
}
const CHANS=buildChannels();

/* Частоты обычной (не бедственной) связи ЦИВ: межсудовые вызывные
   и парные им радиотелефонные. */
const ROUTINE_FREQS=[
  {band:'MF',     dsc:2177.0,  rt:2170.0},
  {band:'HF 4',   dsc:4208.0,  rt:4146.0},
  {band:'HF 6',   dsc:6312.5,  rt:6224.0},
  {band:'HF 8',   dsc:8415.0,  rt:8297.0},
  {band:'HF 12',  dsc:12577.5, rt:12353.0},
  {band:'HF 16',  dsc:16805.0, rt:16528.0}
];

/* Частоты, которые станция держит на приёме постоянно (экран WATCH KEEPING).
   Верхняя строка -- бедствие, ниже -- береговые вызывные ЦИВ. */
const WATCH_DISTRESS=[2187.5];
const WATCH_ROUTINE=[2177.0,4219.5,6331.0,8436.5,12657.0,19703.5];

/* Береговые станции для адресной книги */
const ADDR_BOOK=[
  {n:'ODESSA RADIO',    m:'002734411'},
  {n:'ISTANBUL TURK',   m:'002710000'},
  {n:'LYNGBY RADIO',    m:'002191000'},
  {n:'ROGALAND RADIO',  m:'002570300'},
  {n:'FALMOUTH MRCC',   m:'002320014'},
  {n:'OLYMPIA RADIO',   m:'002371000'},
  {n:'MADRID RADIO',    m:'002241022'},
  {n:'GROUP FLEET',     m:'023712000'}
];

const MSG_TYPES=[
  {id:'individual', t:'INDIVIDUAL MSG'},
  {id:'group',      t:'GROUP MSG'},
  {id:'pstn',       t:'PSTN MSG'},
  {id:'area',       t:'AREA MSG'},
  {id:'position',   t:'POSITION MSG'},
  {id:'test',       t:'TEST MSG'},
  {id:'special',    t:'SPECIAL MSG'}
];
const SPECIAL_MSGS=[
  {t:'DISTRESS RELAY',   call:'relay'},
  {t:'POLLING',          call:'polling'},
  {t:'NEUTRAL CRAFT',    call:'safety'},
  {t:'MEDICAL TRANSPORT',call:'urgency'}
];
const PRIORITIES=['ROUTINE','SAFETY','URGENCY'];
const COMM_MODES=['TELEPHONE','NBDP-ARQ','NBDP-FEC'];

/* ---- Дерево MENU, как на самом приборе ----
   Номера пунктов и порядок сверены с фотографиями FS-2575C: INTERCOM
   стоит четвёртым без номера и недоступен -- он и на станции серый,
   пока не подключён второй пост. */
const MENU_TREE=[
  {n:'1', t:'TEST', items:[
    {t:'DAILY TEST',   act:'dailytest'},
    {t:'TX SELF TEST', act:'txtest'},
    {t:'TONE TEST',    act:'tonetest'}]},
  {n:'2', t:'USER CH', items:[
    {t:'MF/HF CH',  v:'2182',  act:'userch'},
    {t:'MF/HF CH',  v:'821',   act:'userch'},
    {t:'MF/HF CH',  v:'1221',  act:'userch'},
    {t:'ADD NEW CH', act:'info', info:['Свои каналы заводят под связь с','конкретной береговой станцией или','флотом компании. На тренажёре список','фиксированный.']}]},
  {n:'3', t:'LOG', items:[
    {t:'TRANSMITTED',       act:'log', kind:'tx'},
    {t:'RECEIVED ORDINARY', act:'log', kind:'rx'},
    {t:'RECEIVED DISTRESS', act:'log', kind:'dist'}]},
  {n:'',  t:'INTERCOM', dim:true, items:[]},
  {n:'5', t:'SYSTEM', items:[
    {t:'SQ FREQ', v:'1000Hz', act:'info', info:['Частота тонального шумоподавителя.','Ниже 1000 Гц слышнее слабые сигналы,','выше -- меньше шума в динамике.']},
    {t:'KEY ASSIGN',     sub:true, act:'info', info:['Назначение цифровых клавиш на','быстрые команды дежурного экрана.']},
    {t:'PRINT',          sub:true, act:'info', info:['Печать журнала на судовой принтер.','По ГМССБ распечатка вызовов бедствия','хранится вместе с радиожурналом.']},
    {t:'POSITION SETUP', sub:true, act:'position'},
    {t:'DATE/TIME',      act:'datetime'},
    {t:'TIMEOUT',        sub:true, act:'info', info:['Время, через которое станция сама','возвращается на дежурный экран.']},
    {t:'RX SETUP',       sub:true, act:'info', info:['Настройки приёмника: АРУ, аттенюатор,','режим полосы.']},
    {t:'EXTERNAL ALARM', sub:true, act:'info', info:['Вынос тревоги на мостик и в каюту','капитана -- обязателен по ГМССБ.']},
    {t:'NETWORK',        act:'info', info:['Обмен с судовой сетью: приёмник GPS,','ЭКНИС, судовой журнал.']}]},
  {n:'6', t:'DSC', items:[
    {t:'ADDRESS BOOK', act:'addr'},
    {t:'MSG FILE',     act:'compose'},
    {t:'ACK SETTINGS', sub:true, act:'ack'},
    {t:'SPECIAL MSG',  sub:true, act:'special'},
    {t:'ROUTINE SCAN', act:'scan'}]},
  {n:'7', t:'AUDIO', items:[
    {t:'SPEAKER',   v:'ON',  act:'info', info:['Динамик дежурного приёма. Выключать','его на вахте нельзя.']},
    {t:'HANDSET',   v:'ON',  act:'info', info:['Трубка. Разговор после вызова ЦИВ','идёт именно по ней.']},
    {t:'SIDE TONE', v:'OFF', act:'info', info:['Самопрослушивание своей передачи.']},
    {t:'AF LEVEL',  v:'5',   act:'info', info:['Уровень низкой частоты. Ручкой VOLUME','на панели он же и крутится.']}]},
  {n:'8', t:'ALARM', items:[
    {t:'DISTRESS ALARM', v:'ON',  act:'info', info:['Тревога при приёме бедствия.','Отключить её штатно нельзя.']},
    {t:'ROUTINE ALARM',  v:'ON',  act:'info', info:['Звук при обычном вызове в свой адрес.']},
    {t:'BUZZER',         v:'ON',  act:'info', info:['Зуммер нажатия клавиш.']}]},
  {n:'9', t:'SERVICE', items:[
    {t:'SYSTEM INFO',   act:'sysinfo'},
    {t:'SELF CHECK',    act:'txtest'},
    {t:'DEFAULT SET',   sub:true, act:'info', info:['Сброс к заводским настройкам.','MMSI при этом не стирается.']}]}
];

/* ---- Состояние тренажёра ---- */
let DS={
  screen:'home',
  // дежурный экран
  chi:0, tx:2182.0, rx:2182.0, homeSel:0, homeEdit:false,
  // меню
  mCol:0, mSel:0, mSub:0,
  // информационный экран и журналы
  info:null, addrSel:0,
  // сообщение
  call:null, nature:null, mmsi:'', band:3,
  log:[], busy:false, armed:false, hold:0,
  // сканирование
  scan:{on:false, i:0, hit:-1, msg:'', timer:null},
  exam:null, examIdx:0, examScore:0, examTotal:0
};

/* Составление сообщения: и обычного, и бедствия */
let CM={pick:true, type:0, spec:0, sel:0, edit:false,
        to:'', prio:0, mode:0, fi:0};
let DM={sel:0, edit:false, nature:7, mode:0, fi:0};

/* ---- Яркость экрана (кнопка BRILL) ---- */
const BRILL_MODES=['day','night','green'];
const BRILL_NAME={day:'DAY',night:'NIGHT',green:'GREEN'};
let BRILL = localStorage.getItem('navarea_brill')||'day';
let BRILL_TIP=0;

/* ---- Звук ----
   Web Audio, без единого файла: тон формируется на месте. Посылка ЦИВ на
   ПВ/КВ -- это частотная манипуляция двумя тонами 1615 и 1785 Гц, её и
   воспроизводим; сигнал тревоги -- двухтональный 2200/1300 Гц по 250 мс,
   как он звучит в эфире на 2182 кГц. */
let DSC_SND = localStorage.getItem('navarea_dscsnd')!=='0';
let AC=null, MUTED=false;
function actx(){
  if(AC!==null) return AC;
  try{ AC=new (window.AudioContext||window.webkitAudioContext)(); }
  catch(e){ AC=false; }
  return AC;
}
function tone(freq,at,dur,vol,type){
  const c=actx(); if(!c) return;
  const t0=c.currentTime+at;
  const o=c.createOscillator(), g=c.createGain();
  o.type=type||'sine';
  o.frequency.setValueAtTime(freq,t0);
  g.gain.setValueAtTime(0.0001,t0);
  g.gain.exponentialRampToValueAtTime(Math.max(0.0002,vol),t0+0.006);
  g.gain.setValueAtTime(Math.max(0.0002,vol),t0+Math.max(0.01,dur-0.008));
  g.gain.exponentialRampToValueAtTime(0.0001,t0+dur);
  o.connect(g); g.connect(c.destination);
  o.start(t0); o.stop(t0+dur+0.02);
}
function snd(kind){
  if(!DSC_SND||MUTED) return;
  const c=actx(); if(!c) return;
  if(c.state==='suspended'){ try{ c.resume(); }catch(e){} }
  const v=Math.max(.03, Math.min(.34, (KNOB.vol/10)*0.3));
  if(kind==='key'){ tone(1400,0,.018,v*.22,'square'); return; }
  if(kind==='tx'){        // уходящая посылка ЦИВ
    for(let i=0;i<36;i++) tone(i%2?1785:1615, i*0.021, .02, v*.55,'square');
    return;
  }
  if(kind==='rx'){        // приём чужой посылки, следом сигнал вызова
    for(let i=0;i<24;i++) tone(i%2?1615:1785, i*0.021, .02, v*.45,'square');
    tone(880,.55,.1,v*.6); tone(1320,.68,.14,v*.6);
    return;
  }
  if(kind==='ack'){ tone(880,0,.1,v*.6); tone(1320,.13,.16,v*.6); return; }
  if(kind==='alarm'){     // двухтональный сигнал тревоги
    for(let i=0;i<8;i++) tone(i%2?1300:2200, i*.25, .24, v*.7);
    return;
  }
  if(kind==='tone'){ tone(1000,0,1.1,v*.55); return; }
  if(kind==='err'){ tone(260,0,.2,v*.5,'square'); return; }
}

async function loadDSC(){
  // Данные уже есть (зашиты), поэтому запрос к серверу необязателен:
  // если он не отвечает или файла там нет -- работаем на встроенных.
  try{
    const fresh=await api('/api/dsc');
    if(fresh&&Array.isArray(fresh.calls)&&fresh.calls.length) DSC=fresh;
  }catch(e){}
  return DSC;
}

const dscBand = ()=> (DSC&&DSC.freqs[DS.band]) || {band:'HF 8',dsc:8414.5,rt:8291.0};
const curChan = ()=> CHANS[DS.chi]||CHANS[0];
function dscPrint(line){ DS.log.push(line); if(DS.log.length>16) DS.log.shift(); drawDSC(); }
function dscClear(){ DS.log=[]; }

/* Смена экрана в одном месте: заодно гасим сканирование, иначе таймер
   продолжает крутиться уже на другом экране. */
function setScreen(s){
  if(s!=='watch') scanStop();
  DS.screen=s;
}

/* ================= Дисплей ================= */
function sBars(){
  const n=Math.round((KNOB.rf/99)*8);
  return Array.from({length:8},(_,i)=>i<Math.max(1,n)?1:0);
}
function lcdTop(right){
  const c=curChan();
  const r = right!==undefined ? right
    : `<span class="ssb">SSB</span> TX ${DS.tx.toFixed(1)}/RX ${DS.rx.toFixed(2)} kHz`;
  return `<div class="lcdtop"><span>⚓ ✉ ✉</span><span>${r}</span></div>`;
}
function lcdFoot(extra){
  return `<div class="lcdfoot">
    <span><span class="k">⏎</span>:<b>SELECT</b></span>
    <span><span class="k">CANCEL</span>:<b>BACK</b></span>
    <span><span class="k">MENU</span>:<b>CLOSE</b></span>
    ${extra||''}</div>`;
}
function gpsLat(){ return geoFresh()?geoFmtLat(GEO.lat):((VES&&VES.active&&VES.active.lat)||"12°41.1831'N"); }
function gpsLon(){ return geoFresh()?geoFmtLon(GEO.lon):((VES&&VES.active&&VES.active.lon)||"074°09.2407'W"); }
function utcHM(){
  const n=new Date();
  return String(n.getUTCHours()).padStart(2,'0')+':'+String(n.getUTCMinutes()).padStart(2,'0');
}
function myMmsi(){ return (VES&&VES.active&&VES.active.mmsi)?VES.active.mmsi:'210210000'; }

function drawDSC(){
  const box=$('#lcd'); if(!box||!DSC) return;
  const alert=(DS.screen==='log'&&DS.log.some(l=>/DISTRESS|MAYDAY/.test(l)));
  box.className='lcd br-'+BRILL+(alert?' alert':'');

  { const v=$('#volVal'); if(v) v.textContent=Math.round(KNOB.vol);
    const r=$('#rfVal'); if(r) r.textContent=Math.round(KNOB.rf); }

  if(BRILL_TIP>Date.now()){
    box.innerHTML=`${lcdTop()}
      <div style="flex:1;display:flex;align-items:center;justify-content:center;
                  flex-direction:column;gap:8px">
        <div style="font-size:15px;font-weight:800;letter-spacing:2px">BRILLIANCE</div>
        <div style="font-size:26px;font-weight:800;color:#fff">${BRILL_NAME[BRILL]}</div>
        <div style="font-size:9.4px;color:#9db6d4">${esc(tr('BRILL — ещё раз, чтобы сменить'))}</div>
      </div>`;
    return;
  }

  const fn={home:lcdHome, menu:lcdMenu, info:lcdInfo, addr:lcdAddr,
            compose:lcdCompose, distress:lcdDistress, watch:lcdWatch,
            mmsi:lcdMmsi, log:lcdLog, calls:lcdCalls}[DS.screen];
  box.innerHTML=(fn||lcdHome)();
}

/* ---- дежурный экран: CH / TX / RX ---- */
function lcdHome(){
  const c=curChan(), b=dscBand();
  const sel=i=>DS.homeSel===i?(DS.homeEdit?' edit':' sel'):'';
  return `${lcdTop()}
    <div class="lrow1">
      <div class="ldist">DIST-<br>RESS</div>
      <div class="lch${sel(0)}"><span class="l">CH</span><span class="n">${esc(c.ch)}</span>
        <span class="bd">${esc(c.band)}</span></div>
      <div class="lnb">NB</div>
      <div class="lmenu">
        <div class="mi"><b>1</b>RX FREQ</div>
        <div class="mi"><b>4</b>DAILY TEST</div>
        <div class="mi"><b>7</b>TEST CALL</div>
      </div>
    </div>
    <div class="lfreq${sel(1)}"><span class="lb">TX</span><span class="v">${DS.tx.toFixed(1)}</span><span class="u">kHz</span></div>
    <div class="lfreq${sel(2)}"><span class="lb">RX</span><span class="v">${DS.rx.toFixed(2)}</span><span class="u">kHz</span></div>
    <div class="lmode"><span>SSB</span><span>MID</span><span>FAST</span><span>SIMP</span>${MUTED?'<span>MUTE</span>':''}</div>
    <div class="lmeter">S<div class="lbars">${sBars().map(x=>`<i class="${x?'on':''}"></i>`).join('')}</div></div>
    <div class="lmeter">IC<div class="lbars">${[1,1,1,0,0,0,0,0].map(x=>`<i class="${x?'on':''}"></i>`).join('')}</div><span style="margin-left:4px">0.0A</span></div>
    <div class="lag"><span class="attb">ATT</span><span>AF ${Math.round(KNOB.vol)} · RF GAIN ${Math.round(KNOB.rf)}</span></div>
    <div class="lgps"><span>LAT ${esc(gpsLat())}<br>LON ${esc(gpsLon())}</span><b>GPS DATA<br>${utcHM()} UTC</b></div>
    <div class="lmem">${Array(8).fill('<i></i>').join('')}</div>
    <div class="lcdfoot" style="margin-top:5px">
      <span>${esc(tr(DS.homeEdit?'Крути — меняется значение':'Крути — выбор CH/TX/RX'))}</span>
      <span><span class="k">⏎</span>:<b>${DS.homeEdit?'OK':'EDIT'}</b></span>
    </div>`;
}

/* ---- MENU ---- */
function lcdMenu(){
  const sec=MENU_TREE[DS.mSel]||MENU_TREE[0];
  const left=MENU_TREE.map((m,i)=>
    `<div class="lmi ${m.dim?'dim':''} ${i===DS.mSel?'sel':''} ${(i===DS.mSel&&DS.mCol===0)?'act':''}">
       <span class="nn">${esc(m.n)}</span>${esc(m.t)}${m.items.length?' ▸':''}</div>`).join('');
  const right=(sec.items||[]).map((it,i)=>
    `<div class="lmr ${(DS.mCol===1&&i===DS.mSub)?'sel':''}">
       <span class="sq"></span><span class="nm">${esc(it.t)}</span>
       ${it.v?`<span class="vl">: ${esc(it.v)}</span>`:''}
       ${it.sub?'<span class="ar">▸</span>':''}</div>`).join('');
  return `${lcdTop()}
    <div class="lmenuwrap">
      <div class="lmcol"><div class="lmcap">MENU</div>${left}</div>
      <div class="lmpanel"><div class="ph">${esc(sec.t)}</div>${right||
        `<div class="lmr dim"><span class="nm">${esc(tr('Раздел недоступен'))}</span></div>`}</div>
    </div>
    ${lcdFoot()}`;
}

/* ---- информационный экран пункта меню ---- */
function lcdInfo(){
  const inf=DS.info||{t:'',lines:[]};
  return `${lcdTop()}
    <div class="lhead">${esc(inf.t)}</div>
    <div class="llog">${(inf.lines||[]).map(l=>esc(tr(l))).join('\n')}</div>
    ${lcdFoot()}`;
}

/* ---- адресная книга ---- */
function lcdAddr(){
  return `${lcdTop()}
    <div class="lhead">ADDRESS BOOK</div>
    <div class="laddr">${ADDR_BOOK.map((a,i)=>
      `<div class="it ${i===DS.addrSel?'sel':''}">
         <span style="flex:1">${esc(a.n)}</span><span class="mm">${esc(a.m)}</span></div>`).join('')}</div>
    ${lcdFoot()}`;
}

/* ---- COMPOSE MESSAGE (OTHER DSC MSG) ---- */
function composeRows(){
  const t=MSG_TYPES[CM.type];
  const f=ROUTINE_FREQS[CM.fi]||ROUTINE_FREQS[0];
  const rows=[
    {k:'MSG TYPE', v:t.t, ed:'type'},
    {k:'TO',       v:CM.to?CM.to:'- - - - - - - - -', ed:'to'},
    {k:'PRIORITY', v:PRIORITIES[CM.prio], ed:'prio'},
    {k:'COMM MODE',v:COMM_MODES[CM.mode], ed:'mode'},
    {k:'COMM FREQ',v:f.rt.toFixed(1)+'kHz', ed:'freq'},
    {k:'DSC FREQ', v:f.dsc.toFixed(1)+'kHz', ed:'freq'}
  ];
  if(t.id==='special') rows.splice(1,0,{k:'CONTENT', v:SPECIAL_MSGS[CM.spec].t, ed:'spec'});
  if(t.id==='area') rows[1]={k:'AREA', v:'ALL SHIPS', ed:null};
  if(t.id==='position') rows[2]={k:'PRIORITY', v:'ROUTINE', ed:null};
  return rows;
}
function lcdCompose(){
  const rows=composeRows();
  let pop='';
  if(CM.pick){
    pop=`<div class="lpop"><div class="ph">MESSAGE FILE</div>
      ${MSG_TYPES.map((m,i)=>
        `<div class="it ${i===CM.type?'sel':''}">${esc(m.t)}</div>`).join('')}</div>`;
  } else if(CM.edit&&rows[CM.sel]&&rows[CM.sel].ed==='spec'){
    pop=`<div class="lpop" style="top:20px"><div class="ph">SPECIAL MSG</div>
      ${SPECIAL_MSGS.map((m,i)=>
        `<div class="it ${i===CM.spec?'sel':''}">${esc(m.t)}</div>`).join('')}</div>`;
  }
  const goSel = !CM.pick && CM.sel===rows.length;
  return `${lcdTop()}
    <div class="lhead">COMPOSE MESSAGE</div>
    <div class="lcomp">
      ${rows.map((r,i)=>
        `<div class="lcrow ${(!CM.pick&&i===CM.sel)?(CM.edit?'edit':'sel'):''} ${r.ed?'':'dim'}">
           <span class="k">${esc(r.k)}</span><span class="v">: ${esc(r.v)}</span></div>`).join('')}
      ${pop}
    </div>
    <div class="lcdfoot">
      <span><span class="k">CANCEL</span>:<b>BACK</b></span>
      <span class="go ${goSel?'on':''}">GO TO CALL</span>
    </div>`;
}

/* ---- COMPOSE MESSAGE: DISTRESS ALERT ---- */
function distressRows(){
  const nat=(DSC.nature||[])[DM.nature]||{t:'Undesignated distress'};
  const b=DSC.freqs[0];
  return [
    {k:'MSG TYPE', v:'DISTRESS ALERT', ed:null},
    {k:'NATURE',   v:nat.t.toUpperCase(), ed:'nature'},
    {k:'LAT',      v:gpsLat(), ed:null},
    {k:'LON/UTC',  v:gpsLon()+' / '+utcHM(), ed:null},
    {k:'COMM MODE',v:COMM_MODES[DM.mode]+' / '+b.rt.toFixed(1)+'kHz', ed:'mode'},
    {k:'DSC FREQ', v:(DSC.freqs[DM.fi]||b).dsc.toFixed(1)+' kHz', ed:'freq'}
  ];
}
function lcdDistress(){
  const rows=distressRows();
  const nat=(DSC.nature||[]);
  const pop = (DM.edit&&rows[DM.sel]&&rows[DM.sel].ed==='nature')
    ? `<div class="lpop" style="top:16px"><div class="ph">NATURE OF DISTRESS</div>
       ${nat.map((n,i)=>`<div class="it ${i===DM.nature?'sel':''}">${esc(n.t)}</div>`).join('')}</div>`
    : '';
  return `${lcdTop()}
    <div class="lhead red">COMPOSE MESSAGE</div>
    <div class="lcomp">
      ${rows.map((r,i)=>
        `<div class="lcrow ${i===DM.sel?(DM.edit?'edit':'sel'):''} ${r.ed?'':'dim'}">
           <span class="k">${esc(r.k)}</span><span class="v">: ${esc(r.v)}</span></div>`).join('')}
      ${pop}
    </div>
    <div class="lnote"><b>PRESS DISTRESS BUTTON</b>TO SEND DISTRESS ALERT.</div>
    <div class="lcdfoot"><span><span class="k">CANCEL</span>:<b>BACK</b></span></div>`;
}

/* ---- WATCH KEEPING / сканирование ---- */
function lcdWatch(){
  const sc=DS.scan;
  const cell=(f,idx)=>{
    const on = sc.on && sc.i===idx;
    const hit = sc.hit===idx;
    return `<i class="${hit?'hit':(on?'on':'')}">${on||hit?'<b>▸</b>':' '}${f.toFixed(1)}</i>`;
  };
  const dist=WATCH_DISTRESS.map((f,i)=>cell(f,i)).join('')+'<i></i><i></i>';
  const rout=WATCH_ROUTINE.map((f,i)=>cell(f,i+1)).join('');
  return `${lcdTop('MMSI:'+esc(myMmsi()))}
    <div class="lhead">WATCH KEEPING</div>
    <div class="lwk">
      <div class="lwkcap"><span>DISTRESS</span><span>WR</span></div>
      <div class="lwktab">${dist}</div>
      <div class="lwkcap" style="margin-top:3px"><span>ROUTINE</span><span>RX</span></div>
      <div class="lwktab">${rout}</div>
      <div class="lgps" style="margin-top:4px">
        <span>LAT: ${esc(gpsLat())}<br>LON: ${esc(gpsLon())}</span>
        <b>GPS DATA<br>${utcHM()} (UTC)</b></div>
      <div class="lmeter">RF GAIN
        <div class="lbars">${sBars().map(x=>`<i class="${x?'on':''}"></i>`).join('')}</div>
        <span style="margin-left:4px">${Math.round(KNOB.rf)}</span></div>
      <div class="lscanmsg">${esc(sc.msg||(sc.on?tr('СКАНИРОВАНИЕ…'):tr('SCAN — начать сканирование')))}</div>
    </div>
    ${lcdFoot()}`;
}

/* ---- ввод MMSI ---- */
function lcdMmsi(){
  return `${lcdTop()}
    <div class="lhead">ENTER MMSI</div>
    <div class="llog" style="display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px">
      <div style="font-size:20px;letter-spacing:3px;color:#fff">${esc(DS.mmsi.padEnd(9,'_'))}</div>
      <div style="opacity:.8;font-size:10px">${DS.mmsi.length===9?'<span class="blink">PRESS ⏎ TO SEND</span>':'9 digits required'}</div>
    </div>
    ${lcdFoot()}`;
}

/* ---- ход вызова ---- */
function lcdLog(){
  const b=DS.freq||dscBand();
  return `${lcdTop((DS.busy?'TX ':'RX ')+b.band+' · '+b.dsc+' kHz')}
    <div class="llog">${DS.log.map(esc).join('\n')}</div>
    ${lcdFoot()}`;
}

/* ---- список видов вызова (режим экзамена и клавиша 4) ---- */
function lcdCalls(){
  return `${lcdTop()}
    <div class="lhead">SELECT CALL TYPE</div>
    <div class="lmenuscreen">${(DSC.calls||[]).map((c,i)=>
      `<div class="it ${i===DS.mSub?'sel':''}">${i===DS.mSub?'▸':' '} ${esc(c.t)}</div>`).join('')}</div>
    ${lcdFoot()}`;
}

/* ================= Сканирование ================= */
function scanStop(){
  if(DS.scan.timer){ clearInterval(DS.scan.timer); DS.scan.timer=null; }
  DS.scan.on=false;
}
function scanStart(){
  scanStop();
  DS.scan.on=true; DS.scan.i=0; DS.scan.hit=-1; DS.scan.msg='';
  DS.scan.timer=setInterval(()=>{
    // если ушли с экрана -- останавливаемся сами
    if(DS.screen!=='watch'||S.view!=='dsc'){ scanStop(); return; }
    DS.scan.i=(DS.scan.i+1)%(1+WATCH_ROUTINE.length);
    // изредка на одной из частот появляется чужой вызов
    if(Math.random()<0.07){
      const idx=DS.scan.i;
      DS.scan.hit=idx;
      const from=ADDR_BOOK[Math.floor(Math.random()*ADDR_BOOK.length)];
      DS.scan.msg = idx===0
        ? 'DISTRESS ALERT RECEIVED · '+from.m
        : 'ROUTINE CALL · '+from.n+' '+from.m;
      snd(idx===0?'alarm':'rx');
      hap(idx===0?'heavy':'medium');
      scanStop();
      DS.scan.msg += ' · '+tr('CANCEL — продолжить');
      showLesson(idx===0?'ack':'freq');
    }
    drawDSC();
  }, 900);
  drawDSC();
}

/* ================= Имитация обмена ================= */
function wait(ms){ return new Promise(r=>setTimeout(r,ms)); }

/* Какой вид вызова получается из того, что набрано в COMPOSE.
   Срочность и безопасность на настоящей станции задаются не типом
   сообщения, а полем PRIORITY -- этому и учим. */
function composeCallId(){
  const t=MSG_TYPES[CM.type];
  if(t.id==='special') return SPECIAL_MSGS[CM.spec].call;
  if(t.id==='test')     return 'test';
  if(t.id==='position') return 'position';
  const p=PRIORITIES[CM.prio];
  if(p==='URGENCY') return 'urgency';
  if(p==='SAFETY')  return 'safety';
  if(t.id==='group') return 'group';
  if(t.id==='area')  return 'allships';
  return 'individual';
}
const callById = id => (DSC.calls||[]).find(c=>c.id===id);

function composeSend(){
  const id=composeCallId(), c=callById(id);
  if(!c){ snd('err'); return; }
  const needsMmsi = ['individual','group','test','position','polling'].includes(id);
  if(needsMmsi && CM.to.length!==9){
    snd('err'); hap('heavy');
    DS.info={t:'ERROR',lines:['Не задан адрес вызова.','Поле TO -- девять цифр MMSI.','','У судна первые три цифры -- код страны,','у береговой станции первые две нули,','у группы -- ноль в начале.']};
    setScreen('info'); drawDSC(); return;
  }
  DS.mmsi=CM.to;
  DS.band = Math.min(DSC.freqs.length-1, CM.fi);
  DS.nature=null;
  // Обычный вызов идёт на межсудовой вызывной частоте, а не на бедственной:
  // 2177.0 вместо 2187.5 и так далее по диапазонам.
  runCall(c, ROUTINE_FREQS[CM.fi]||ROUTINE_FREQS[0]);
}

async function runCall(c, freq){
  if(!c||DS.busy) return;
  DS.busy=true; setScreen('log'); dscClear();
  const b=freq||dscBand();
  DS.freq=b;                       // на этой паре идёт весь обмен и заголовок экрана
  hap('medium'); snd('tx');

  const isDistress = c.id==='distress';
  dscPrint(c.t.toUpperCase());
  dscPrint(`FREQ ${b.dsc} kHz`);
  if(DS.mmsi) dscPrint(`TO   ${DS.mmsi}`);
  if(DS.nature) dscPrint(`NATURE ${DS.nature.t}`);
  dscPrint('POS  '+gpsLat()+' '+gpsLon()+(geoFresh()?'':'  ('+tr('нет данных GPS')+')'));
  dscPrint('');
  dscPrint(isDistress?'TRANSMITTING DISTRESS...':'TRANSMITTING...');

  await wait(1200);
  dscPrint(isDistress?'DISTRESS SENT':'CALL SENT');
  dscPrint('WAITING FOR ACK...');
  await wait(isDistress?2200:1600);
  snd(isDistress?'alarm':'ack');

  if(c.id==='distress'){
    dscPrint('');
    dscPrint('RCC ACK RECEIVED');
    dscPrint('FROM 002734411 ODESSA RADIO');
    dscPrint(`SWITCH TO ${b.rt} kHz`);
    dscPrint('SPEAK: MAYDAY x3, SHIP NAME,');
    dscPrint('CALLSIGN, MMSI, POSITION,');
    dscPrint('NATURE, ASSISTANCE, POB');
    showLesson('rt');
  } else if(c.id==='relay'){
    dscPrint(''); dscPrint('RELAY ACK RECEIVED'); dscPrint('RCC ACKNOWLEDGED');
    showLesson('ack');
  } else if(c.id==='test'){
    dscPrint(''); dscPrint('TEST ACK RECEIVED');
    dscPrint(`FROM ${DS.mmsi||'002371000'}`);
    dscPrint('DSC OPERATION NORMAL');
    showLesson('test');
  } else if(c.id==='position'){
    dscPrint(''); dscPrint('POSITION RECEIVED');
    dscPrint('44-12.8N 033-51.6E'); dscPrint('AT '+utcHM()+' UTC');
  } else if(c.id==='polling'){
    dscPrint(''); dscPrint('POLLING ACK RECEIVED'); dscPrint('STATION IN RANGE');
  } else if(c.id==='allships'||c.id==='safety'||c.id==='urgency'){
    dscPrint(''); dscPrint('CALL COMPLETED');
    dscPrint(`SWITCH TO ${b.rt} kHz`);
    dscPrint(c.id==='urgency'?'SPEAK: PAN PAN x3':'SPEAK: SECURITE x3');
    showLesson('rt');
  } else {
    dscPrint(''); dscPrint('ACK RECEIVED');
    dscPrint(`SWITCH TO ${b.rt} kHz`);
    showLesson('rt');
  }

  DS.busy=false; drawDSC();
  if(DS.exam) checkExam(c);
}

/* ---- ежедневная проверка и самотест ---- */
async function dailyTest(){
  if(DS.busy) return;
  DS.busy=true; setScreen('log'); dscClear(); snd('tx'); hap('medium');
  DS.freq=DSC.freqs[0];
  dscPrint('DAILY TEST');
  dscPrint('TEST CALL TO COAST STATION');
  dscPrint('002734411 ODESSA RADIO');
  dscPrint(`FREQ ${DSC.freqs[0].dsc} kHz`);
  dscPrint(''); dscPrint('TRANSMITTING...');
  await wait(1400);
  dscPrint('WAITING FOR ACK...');
  await wait(1800);
  snd('ack');
  dscPrint(''); dscPrint('TEST ACK RECEIVED');
  dscPrint('DSC OPERATION NORMAL');
  dscPrint('RESULT: PASS');
  DS.busy=false; drawDSC();
  showLesson('test');
}
async function txSelfTest(){
  if(DS.busy) return;
  DS.busy=true; setScreen('log'); dscClear(); hap('medium');
  DS.freq=DSC.freqs[0];
  const steps=[['TX SELF TEST','']," ",['SYNTHESIZER','OK'],['PA MODULE','OK'],
               ['ANTENNA TUNER','OK'],['VSWR','1.3 : 1'],['DSC MODEM','OK'],
               ['BATTERY','26.4 V'],[' ',''],['RESULT','PASS']];
  for(const s of steps){
    dscPrint(Array.isArray(s)?(s[0].padEnd(16,' ')+s[1]):s);
    await wait(320);
  }
  snd('ack');
  DS.busy=false; drawDSC();
}

/* ================= Кнопка бедствия ================= */
function armDistress(){ DS.armed=true; hap('medium'); snd('key'); renderDSC(); }
function holdDistress(down){
  const btn=$('#dbtn'); if(!btn) return;
  if(down){
    btn.classList.add('arming');
    DS.hold=setTimeout(async()=>{
      btn.classList.remove('arming');
      DS.armed=false;
      hap('heavy');
      if(DS.screen==='distress'){
        // экран составления уже открыт -- это и есть подача тревоги
        const c=callById('distress');
        DS.call=c; DS.nature=(DSC.nature||[])[DM.nature]||null;
        DS.mmsi=''; DS.band=DM.fi;
        renderDSC();
        runCall(c, DSC.freqs[DM.fi]||DSC.freqs[0]);
      } else {
        openDistressCompose();
        renderDSC();
        showLesson('distress');
      }
    },2000);
  } else {
    clearTimeout(DS.hold); btn.classList.remove('arming');
  }
}
function openDistressCompose(){
  DM.sel=1; DM.edit=false; DM.fi=0;
  setScreen('distress');
}

/* ================= Пояснения ================= */
function showTip(c){
  const el=$('#dsctip'); if(!el||!c) return;
  el.innerHTML=`<b>${esc(c.ru)}</b>${esc(c.why)}`;
}
function showLesson(key){
  const el=$('#dsctip'); if(!el||!DSC) return;
  const t=(DSC.lessons||{})[key]; if(!t) return;
  el.innerHTML=`<b>${esc(tr('Как это работает'))}</b>${esc(t)}`;
}
function showText(title,text){
  const el=$('#dsctip'); if(!el) return;
  el.innerHTML=`<b>${esc(tr(title))}</b>${esc(tr(text))}`;
}

/* ================= Экзамен ================= */
function startExam(){
  DS.exam=(DSC.exam||[]).slice().sort(()=>Math.random()-0.5);
  DS.examIdx=0; DS.examScore=0; DS.examTotal=DS.exam.length;
  setScreen('home'); dscClear(); hap('medium'); renderDSC();
  showText('Режим экзамена','Прочти обстановку и подай тот вызов, который положен: '+
    'DISTRESS MSG — бедствие, OTHER DSC MSG — всё остальное. Срочность и безопасность '+
    'задаются полем PRIORITY, а не отдельным типом сообщения.');
}
function stopExam(){ DS.exam=null; renderDSC(); }
function checkExam(c){
  if(!DS.exam) return;
  const task=DS.exam[DS.examIdx]; if(!task) return;
  const okCall=c.id===task.expect.call;
  const okNat=!task.expect.nature||(DS.nature&&DS.nature.id===task.expect.nature);
  const ok=okCall&&okNat;
  if(ok) DS.examScore++;
  const el=$('#examVerdict');
  if(el){
    el.className='verdict '+(ok?'ok':'no');
    el.innerHTML=`<b>${ok?tr('Верно'):tr('Неверно')}</b>${esc(task.explain)}`;
  }
  hap(ok?'light':'heavy');
  setTimeout(()=>{
    DS.examIdx++;
    DS.nature=null; DS.mmsi=''; CM.to=''; CM.prio=0; CM.pick=true; CM.type=0;
    setScreen('home');
    renderDSC();
  },3600);
}

/* ================= Отрисовка раздела ================= */
function renderDSC(){
  const box=$('#dscBox'); if(!box) return;
  if(!DSC){ box.innerHTML='<div class="sk card"></div>'; return; }

  let exam='';
  if(DS.exam){
    const task=DS.exam[DS.examIdx];
    if(task){
      exam=`<div class="examhead">
        <div class="n">${esc(tr('Задание'))} ${DS.examIdx+1} / ${DS.examTotal} · ${esc(tr('верно'))}: ${DS.examScore}</div>
        <div class="q">${esc(task.situation)}</div></div>
        <div id="examVerdict"></div>`;
    } else {
      const pct=Math.round(DS.examScore/DS.examTotal*100);
      exam=`<div class="examhead"><div class="n">${esc(tr('Экзамен завершён'))}</div>
        <div class="q">${esc(tr('Верных ответов'))}: ${DS.examScore} ${esc(tr('из'))} ${DS.examTotal} (${pct}%)</div></div>`;
    }
  }

  box.innerHTML=exam+`
    <div class="radio">
      <div class="rplates">
        <div class="rplate">MF/HF<br>CONTROL UNIT</div>
        <div class="rplate">MMSI ${esc(myMmsi())}</div>
      </div>
      <div class="rhdr">
        <div class="rnameplate">CONTROL UNIT TYPE FS-2575C<br>SER.NO. 106667</div>
        <div class="rfuruno">FURUNO</div>
      </div>
      <div class="rbody">
        <div class="rscreen">
          <div class="lcd" id="lcd"></div>
          <div class="rsoft"><i></i><i></i><i></i></div>
        </div>

        <div class="rctrls">
          <div class="rleft">
            <div class="rspeaker"><i></i><i></i><i></i><i></i></div>
            <div class="rklabel">HANDSET</div>
            <div class="rknob" id="knobVol"></div>
            <div class="rklabel">VOLUME · <b id="volVal">5</b></div>
            <div class="rknob" id="knobRf"></div>
            <div class="rklabel">RF GAIN · <b id="rfVal">28</b><br>PUSH TO ATT</div>
          </div>

          <div class="rmid">
            <div class="rleds">
              <div class="rled"><i class="amber"></i><span>ALARM</span></div>
              <div class="rled"><i class="${DS.busy?'green':''}"></i><span>OVEN</span></div>
            </div>
            <div class="rdistwrap">
              ${DS.armed
                ? `<div class="rdistcover"><div class="rdistbtn arming" id="dbtn">DISTRESS</div></div>
                   <div class="rpwroff">PWR OFF</div>
                   <div class="rdistcap">${esc(tr('Удерживай 2 секунды'))}</div>`
                : `<div class="rdistcover" id="dlid"><div class="rdistbtn" style="opacity:.45">DISTRESS</div></div>
                   <div class="rpwroff">PWR OFF</div>
                   <div class="rdistcap">${esc(tr('Крышка кнопки бедствия — открыть'))}</div>`}
            </div>
          </div>

          <div class="rright">
            <div class="rkgrid">
              <button class="rkey ${DS.scan.on?'on':''}" data-dk="scan"><div class="kt">SCAN</div></button>
              <button class="rkey" data-dk="2182"><div class="kt">2182</div></button>
              <button class="rkey" data-dk="band"><div class="kt">RT/CH</div></button>
              <button class="rkey" data-dk="1"><div class="kt">1</div></button>
              <button class="rkey" data-dk="2"><div class="kt">2</div><div class="ks">NB</div></button>
              <button class="rkey" data-dk="3"><div class="kt">3</div><div class="ks">SQ</div></button>
              <button class="rkey" data-dk="4"><div class="kt">4</div></button>
              <button class="rkey" data-dk="5"><div class="kt">5</div><div class="ks">NR</div></button>
              <button class="rkey" data-dk="6"><div class="kt">6</div></button>
              <button class="rkey" data-dk="7"><div class="kt">7</div></button>
              <button class="rkey" data-dk="8"><div class="kt">8</div><div class="ks">NF</div></button>
              <button class="rkey" data-dk="9"><div class="kt">9</div></button>
              <button class="rkey" data-dk="up"><div class="kt">◄</div></button>
              <button class="rkey" data-dk="0"><div class="kt">0</div><div class="ks">TUNE</div></button>
              <button class="rkey" data-dk="down"><div class="kt">►</div></button>
            </div>
            <div class="rfngrid">
              <button class="rkey" data-dk="tab"><div class="kt">TAB</div></button>
              <button class="rkey ${DS.screen==='menu'?'on':''}" data-dk="menu"><div class="kt">MENU</div></button>
              <button class="rkey ${MUTED?'on':''}" data-dk="mute"><div class="kt">🔇</div></button>
              <button class="rkey warn" data-dk="cancel"><div class="kt">CANCEL</div></button>
            </div>
            <div class="rbigknob" id="dkEnter"><span class="kdial"></span><span class="cap">PUSH TO ENTER</span></div>
          </div>
        </div>
      </div>

      <div class="rcompose">
        <button class="rcbtn ${DS.screen==='distress'?'on':''}" data-dk="distmsg">DISTRESS<br>MSG</button>
        <button class="rcbtn ${DS.screen==='compose'?'on':''}" data-dk="othermsg">OTHER<br>DSC MSG</button>
        <button class="rcbtn" data-dk="brill">BRILL</button>
      </div>
      <div class="rbracket">COMPOSE DSC MSG</div>
    </div>
    <div class="rfooter">BATTERY MONITOR</div>

    <div class="rlegend2">
      <span><b>${esc(tr('Ролик'))}</b> — ${esc(tr('крутить: выбор, нажать: ввод'))}</span>
      <span><b>MENU</b> — ${esc(tr('разделы станции'))}</span>
      <span><b>BRILL</b> — ${esc(tr('день / ночь / зелёный'))}</span>
      <span><b>SCAN</b> — ${esc(tr('вахтенный приём'))}</span>
    </div>

    <div class="dsctip" id="dsctip"><b>${esc(tr('Тренажёр'))}</b>${esc((DSC.note||''))}</div>
    <div style="display:flex;gap:9px;margin-top:13px">
      ${DS.exam
        ? `<button class="btn g" style="flex:1" id="examStop">${esc(tr('Выйти из экзамена'))}</button>`
        : `<button class="btn" style="flex:1" id="examStart">${esc(tr('Режим экзамена'))}</button>`}
    </div>`;

  drawDSC();

  document.querySelectorAll('[data-dk]').forEach(b=>b.onclick=()=>dscKey(b.dataset.dk));
  const lid=$('#dlid'); if(lid) lid.onclick=armDistress;
  const ent=$('#dkEnter');
  if(ent) ent.onclick=()=>{
    // если ручку крутили, это было листание, а не нажатие
    if(ent._turned){ ent._turned=false; return; }
    dscKey('send');
  };
  const db=$('#dbtn');
  if(db){
    db.onmousedown=()=>holdDistress(true); db.onmouseup=()=>holdDistress(false);
    db.ontouchstart=(e)=>{e.preventDefault();holdDistress(true)};
    db.ontouchend=()=>holdDistress(false);
    db.onmouseleave=()=>holdDistress(false);
  }
  const es=$('#examStart'); if(es) es.onclick=startExam;
  const ex=$('#examStop'); if(ex) ex.onclick=stopExam;
  bindStationKnobs();
  applyLang();
}

/* ================= Ролик: выбор и ввод =================
   Один и тот же поворот означает разное на разных экранах, поэтому
   разбор собран в двух местах: dscTurn -- поворот, dscEnter -- нажатие. */
function dscTurn(dir){
  const s=DS.screen;

  if(s==='home'){
    if(DS.homeEdit){
      if(DS.homeSel===0){                       // канал
        DS.chi=(DS.chi+dir+CHANS.length)%CHANS.length;
        const c=curChan(); DS.tx=c.tx; DS.rx=c.rx;
      } else if(DS.homeSel===1){                // частота передачи
        DS.tx=Math.max(1600,Math.min(27500, +(DS.tx+dir*0.1).toFixed(1)));
      } else {                                  // частота приёма
        DS.rx=Math.max(1600,Math.min(27500, +(DS.rx+dir*0.1).toFixed(1)));
      }
    } else {
      DS.homeSel=(DS.homeSel+dir+3)%3;
    }
    drawDSC(); return;
  }

  if(s==='menu'){
    if(DS.mCol===0){
      DS.mSel=(DS.mSel+dir+MENU_TREE.length)%MENU_TREE.length;
      DS.mSub=0;
    } else {
      const n=(MENU_TREE[DS.mSel].items||[]).length||1;
      DS.mSub=(DS.mSub+dir+n)%n;
    }
    drawDSC(); return;
  }

  if(s==='addr'){
    DS.addrSel=(DS.addrSel+dir+ADDR_BOOK.length)%ADDR_BOOK.length;
    drawDSC(); return;
  }

  if(s==='calls'){
    const n=(DSC.calls||[]).length||1;
    DS.mSub=(DS.mSub+dir+n)%n;
    showTip(DSC.calls[DS.mSub]);
    drawDSC(); return;
  }

  if(s==='compose'){
    if(CM.pick){
      CM.type=(CM.type+dir+MSG_TYPES.length)%MSG_TYPES.length;
    } else if(CM.edit){
      const row=composeRows()[CM.sel]||{};
      if(row.ed==='spec') CM.spec=(CM.spec+dir+SPECIAL_MSGS.length)%SPECIAL_MSGS.length;
      else if(row.ed==='prio') CM.prio=(CM.prio+dir+PRIORITIES.length)%PRIORITIES.length;
      else if(row.ed==='mode') CM.mode=(CM.mode+dir+COMM_MODES.length)%COMM_MODES.length;
      else if(row.ed==='freq') CM.fi=(CM.fi+dir+ROUTINE_FREQS.length)%ROUTINE_FREQS.length;
      else if(row.ed==='type'){ CM.pick=true; CM.edit=false; }
    } else {
      const n=composeRows().length+1;           // +1 -- строка GO TO CALL
      CM.sel=(CM.sel+dir+n)%n;
    }
    drawDSC(); return;
  }

  if(s==='distress'){
    if(DM.edit){
      const row=distressRows()[DM.sel]||{};
      if(row.ed==='nature') DM.nature=(DM.nature+dir+(DSC.nature||[]).length)%((DSC.nature||[]).length||1);
      else if(row.ed==='mode') DM.mode=(DM.mode+dir+COMM_MODES.length)%COMM_MODES.length;
      else if(row.ed==='freq') DM.fi=(DM.fi+dir+DSC.freqs.length)%DSC.freqs.length;
    } else {
      const rows=distressRows();
      let i=DM.sel;
      do{ i=(i+dir+rows.length)%rows.length; }while(!rows[i].ed);
      DM.sel=i;
    }
    drawDSC(); return;
  }

  if(s==='watch'){ if(dir>0) scanStart(); else scanStop(); drawDSC(); return; }
}

function dscEnter(){
  const s=DS.screen;

  if(s==='home'){
    DS.homeEdit=!DS.homeEdit;
    snd('key'); drawDSC();
    showText(DS.homeEdit?'Ввод значения':'Выбор поля',
      DS.homeEdit
        ? 'Крути ролик: вправо — больше, влево — меньше. Нажми ещё раз, чтобы зафиксировать.'
        : 'Крути ролик, чтобы перейти между CH, TX и RX. Нажатие открывает поле на изменение.');
    return;
  }

  if(s==='menu'){
    if(DS.mCol===0){
      const sec=MENU_TREE[DS.mSel];
      if(sec.dim||!(sec.items||[]).length){ snd('err'); return; }
      DS.mCol=1; DS.mSub=0; drawDSC(); return;
    }
    runMenuItem(MENU_TREE[DS.mSel], (MENU_TREE[DS.mSel].items||[])[DS.mSub]);
    return;
  }

  if(s==='addr'){
    // выбранная станция подставляется адресатом в обычное сообщение
    CM.to=ADDR_BOOK[DS.addrSel].m;
    CM.pick=false; CM.sel=1; CM.edit=false;
    setScreen('compose'); drawDSC();
    showText('Адрес подставлен','Позывной из книги ушёл в поле TO. Дальше выбери приоритет, режим связи и рабочую частоту.');
    return;
  }

  if(s==='calls'){
    const c=(DSC.calls||[])[DS.mSub];
    if(!c) return;
    DS.call=c;
    if(c.id==='distress'){ openDistressCompose(); renderDSC(); return; }
    if(c.needs&&c.needs.includes('mmsi')){ setScreen('mmsi'); DS.mmsi=''; drawDSC(); showTip(c); return; }
    runCall(c); return;
  }

  if(s==='compose'){
    if(CM.pick){
      CM.pick=false; CM.sel=0; CM.edit=false;
      if(MSG_TYPES[CM.type].id==='test') CM.prio=1;
      drawDSC();
      showText('Тип сообщения',
        'Срочность (PAN PAN) и безопасность (SECURITE) на станции задаются полем PRIORITY, '+
        'а не отдельным типом сообщения. Тип отвечает только за то, кому уходит вызов.');
      return;
    }
    const rows=composeRows();
    if(CM.sel===rows.length){ composeSend(); return; }   // строка GO TO CALL
    const row=rows[CM.sel];
    if(!row||!row.ed){ snd('err'); return; }
    if(row.ed==='type'){ CM.pick=true; drawDSC(); return; }
    if(row.ed==='to'){
      CM.edit=true; CM.to=''; setScreen('mmsi'); DS.mmsi=''; drawDSC();
      showLesson('mmsi'); return;
    }
    CM.edit=!CM.edit; snd('key'); drawDSC(); return;
  }

  if(s==='distress'){
    const row=distressRows()[DM.sel];
    if(!row||!row.ed){ snd('err'); return; }
    DM.edit=!DM.edit; snd('key'); drawDSC(); return;
  }

  if(s==='mmsi'){
    if(DS.mmsi.length!==9){ snd('err'); return; }
    if(CM.edit){                       // адрес набирали для COMPOSE
      CM.to=DS.mmsi; CM.edit=false;
      setScreen('compose'); drawDSC(); return;
    }
    runCall(DS.call||callById('test'));
    return;
  }

  if(s==='watch'){ DS.scan.on?scanStop():scanStart(); drawDSC(); return; }
  if(s==='info'||s==='log'){ setScreen('home'); drawDSC(); return; }
}

/* ---- что делает выбранный пункт меню ---- */
function runMenuItem(sec,it){
  if(!it){ snd('err'); return; }
  snd('key');
  const act=it.act||'info';

  if(act==='dailytest'){ dailyTest(); return; }
  if(act==='txtest'){ txSelfTest(); return; }
  if(act==='tonetest'){
    snd('tone');
    DS.info={t:'TONE TEST',lines:['1000 Hz · 1 s','','Контрольный тон подаётся в тракт','низкой частоты. Если его не слышно','в динамике и в трубке -- неисправен','усилитель, а не приёмник.']};
    setScreen('info'); drawDSC(); return;
  }
  if(act==='scan'){ setScreen('watch'); scanStart(); renderDSC(); return; }
  if(act==='addr'){ setScreen('addr'); DS.addrSel=0; drawDSC(); return; }
  if(act==='compose'){ openCompose(); return; }
  if(act==='special'){
    openCompose(); CM.pick=false; CM.type=6; CM.sel=1; CM.edit=true; drawDSC();
    showText('Особые сообщения','Здесь живёт ретрансляция бедствия: её подают за другое судно, когда берег не подтвердил его тревогу. Свой вызов бедствия при этом не подаётся.');
    return;
  }
  if(act==='ack'){
    DS.info={t:'ACK SETTINGS',lines:[
      'DISTRESS ACK      MANUAL',
      'ROUTINE ACK       AUTO',
      'POSITION REQ      MANUAL',
      'POLLING           AUTO','',
      'Подтверждение бедствия всегда ручное:',
      'первым его даёт береговой центр, а не',
      'судно. Автоматический ответ на чужое',
      'бедствие правилами запрещён.']};
    setScreen('info'); drawDSC(); return;
  }
  if(act==='position'){
    DS.info={t:'POSITION SETUP',lines:[
      'SOURCE            GPS (auto)',
      'LAT               '+gpsLat(),
      'LON               '+gpsLon(),
      'UTC               '+utcHM(),'',
      'Если приёмник отказал, позицию вводят',
      'вручную и обновляют не реже чем раз',
      'в четыре часа -- иначе в тревоге уйдут',
      'старые координаты.']};
    setScreen('info'); drawDSC(); return;
  }
  if(act==='datetime'){
    const d=new Date();
    DS.info={t:'DATE/TIME',lines:[
      'DATE              '+String(d.getUTCDate()).padStart(2,'0')+'.'+
        String(d.getUTCMonth()+1).padStart(2,'0')+'.'+d.getUTCFullYear(),
      'TIME              '+utcHM()+' UTC',
      'SOURCE            GPS','',
      'В журнал ЦИВ время пишется всемирное.',
      'Судовое время в радиожурнале не',
      'используется.']};
    setScreen('info'); drawDSC(); return;
  }
  if(act==='sysinfo'){
    DS.info={t:'SYSTEM INFO',lines:[
      'MODEL             FS-2575C',
      'SER.NO.           106667',
      'MMSI              '+myMmsi(),
      'TX POWER          250 W',
      'PROGRAM           2451003-01.05','',
      'Тренажёр. Ничего в эфир не уходит.']};
    setScreen('info'); drawDSC(); return;
  }
  if(act==='userch'){
    const c=CHANS.find(x=>x.ch===it.v)||CHANS[0];
    DS.chi=CHANS.indexOf(c); DS.tx=c.tx; DS.rx=c.rx;
    setScreen('home'); DS.homeEdit=false; drawDSC();
    showText('Канал выбран','CH '+c.ch+' · TX '+c.tx.toFixed(1)+' / RX '+c.rx.toFixed(1)+' кГц.');
    return;
  }
  if(act==='log'){
    const kind=it.kind;
    const lines = kind==='dist'
      ? ['Записей нет.','','Принятые вызовы бедствия хранятся','отдельно и не стираются вахтенным.']
      : kind==='tx'
        ? (DS.log.length?DS.log.slice():['Записей нет.','','Здесь останется всё, что станция','передала за рейс.'])
        : ['Записей нет.','','Обычные принятые вызовы хранятся','до заполнения памяти, потом','затираются самыми старыми.'];
    DS.info={t:it.t,lines:lines};
    setScreen('info'); drawDSC(); return;
  }

  DS.info={t:it.t,lines:(it.info||['Настройка станции.'])};
  setScreen('info'); drawDSC();
}

function openCompose(){
  CM.pick=true; CM.sel=0; CM.edit=false;
  setScreen('compose'); renderDSC();
}

/* ================= Клавиатура ================= */
function dscKey(k){
  if(!DSC) return;
  hap();
  if(k!=='send') snd('key');

  if(k==='menu'){
    if(DS.screen==='menu'){ setScreen('home'); }
    else { setScreen('menu'); DS.mCol=0; DS.mSub=0; }
    renderDSC(); return;
  }

  if(k==='cancel'){
    if(DS.screen==='menu'&&DS.mCol===1){ DS.mCol=0; drawDSC(); return; }
    if(DS.screen==='compose'){
      if(CM.edit){ CM.edit=false; drawDSC(); return; }
      if(!CM.pick){ CM.pick=true; drawDSC(); return; }
    }
    if(DS.screen==='distress'&&DM.edit){ DM.edit=false; drawDSC(); return; }
    if(DS.screen==='watch'&&DS.scan.hit>=0){ DS.scan.hit=-1; DS.scan.msg=''; scanStart(); return; }
    if(DS.screen==='home'&&DS.homeEdit){ DS.homeEdit=false; drawDSC(); return; }
    setScreen('home'); DS.nature=null; DS.mmsi=''; dscClear();
    renderDSC(); return;
  }

  if(k==='send'){ dscEnter(); return; }
  if(k==='up'){ dscTurn(-1); return; }
  if(k==='down'){ dscTurn(1); return; }

  if(k==='tab'){
    if(DS.screen==='menu'){ DS.mCol=DS.mCol?0:1; drawDSC(); return; }
    if(DS.screen==='home'){ DS.homeSel=(DS.homeSel+1)%3; DS.homeEdit=false; drawDSC(); return; }
    return;
  }

  if(k==='scan'){
    setScreen('watch');
    DS.scan.on?scanStop():scanStart();
    renderDSC();
    showText('Вахтенный приём','Станция обязана непрерывно слушать частоты бедствия. SCAN проходит их по кругу: '+
      'верхняя строка — 2187.5 кГц, ниже береговые вызывные ЦИВ. Приём вызова сканирование останавливает.');
    return;
  }

  if(k==='2182'){
    DS.chi=0; DS.tx=2182.0; DS.rx=2182.0; DS.band=0;
    setScreen('home'); DS.homeEdit=false; DS.homeSel=0;
    renderDSC();
    showText('2182 кГц','Симплексная частота бедствия и вызова на ПВ. После вызова ЦИВ на 2187.5 разговор идёт голосом именно здесь.');
    return;
  }

  if(k==='band'){
    // RT/CH -- переключение между работой по каналу и по частоте
    DS.homeSel = DS.homeSel===0?1:0;
    DS.homeEdit=false;
    setScreen('home'); renderDSC();
    showText('RT/CH','Слева от экрана выбирается либо готовый канал (CH), либо частоты вручную (TX и RX). Ролик крутит то, что подсвечено.');
    return;
  }

  if(k==='brill'){
    BRILL=BRILL_MODES[(BRILL_MODES.indexOf(BRILL)+1)%BRILL_MODES.length];
    localStorage.setItem('navarea_brill',BRILL);
    BRILL_TIP=Date.now()+900;
    drawDSC();
    setTimeout(drawDSC,950);
    showText('Яркость экрана','День — полная яркость и контраст. Ночь — приглушённый красный, чтобы не сбивать адаптацию глаз на тёмном мостике. Зелёный — старый люминофорный режим, привычный по прежним станциям.');
    return;
  }

  if(k==='mute'){
    MUTED=!MUTED; renderDSC();
    showText(MUTED?'Динамик выключен':'Динамик включён',
      MUTED?'На вахте так делать нельзя: дежурный приём должен быть слышен.':'Дежурный приём снова слышен.');
    return;
  }

  if(k==='distmsg'){ openDistressCompose(); renderDSC(); showTip(callById('distress')); return; }
  if(k==='othermsg'){ openCompose(); showLesson('freq'); return; }

  if(/^[0-9]$/.test(k)){
    // На дежурном экране цифры 1/4/7 -- те же ярлыки, что подписаны
    // на самом экране, как на настоящей станции.
    if(DS.screen==='home'){
      if(k==='1'){ DS.homeSel=2; DS.homeEdit=true; drawDSC(); return; }
      if(k==='4'){ dailyTest(); return; }
      if(k==='7'){
        openCompose(); CM.pick=false; CM.type=5; CM.sel=1; CM.prio=1;
        drawDSC(); showLesson('test'); return;
      }
    }
    if(DS.screen==='menu'){
      const i=MENU_TREE.findIndex(m=>m.n===k);
      if(i>=0){ DS.mSel=i; DS.mCol=0; DS.mSub=0; drawDSC(); }
      return;
    }
    if(DS.screen==='mmsi'){
      if(DS.mmsi.length<9) DS.mmsi+=k;
      drawDSC(); if(DS.mmsi.length===3) showLesson('mmsi');
      return;
    }
    // из любого другого места цифра начинает набор адреса
    setScreen('mmsi'); DS.mmsi=k; drawDSC();
  }
}



/* ================= Позиция с устройства =================
   Берём координаты у самого телефона, чтобы не набирать их руками.
   Telegram отдаёт своё хранилище позиции только начиная с Bot API 8.0
   (LocationManager), поэтому сначала пробуем его, а если его нет --
   обычный navigator.geolocation. На судне GPS телефона обычно ловит,
   но в глубине корпуса может и не поймать: тогда честно говорим об этом,
   а не подставляем последнюю известную точку молча. */

/* ---- Настройки, живущие на устройстве ----
   Всё хранится локально: это предпочтения конкретного телефона, а не
   судовые данные, и синхронизировать их между устройствами незачем. */
let HAPTIC   = localStorage.getItem('navarea_haptic')!=='0';
let GEO_WATCH= localStorage.getItem('navarea_geowatch')!=='0';
let COORD_FMT= localStorage.getItem('navarea_coordfmt')||'dm';   // dm | dec
/* ---- Время ----
   Три источника, между которыми переключается вся шапка:
     utc   -- всемирное координированное, им ведётся радиожурнал;
     ship  -- судовое, его переводят приказом по судну, поэтому смещение
              задаёт сам вахтенный, а не операционная система;
     phone -- то, что показывает телефон (часто это порт приписки или
              последняя сеть, к которой он цеплялся).
   Судовое смещение хранится в часах и может быть дробным: есть пояса
   в полчаса и в три четверти часа. */
let TIME_MODE = localStorage.getItem('navarea_timemode')
  || (localStorage.getItem('navarea_timeutc')==='0' ? 'phone' : 'utc');
let SHIP_TZ = parseFloat(localStorage.getItem('navarea_shiptz'));
if(isNaN(SHIP_TZ)) SHIP_TZ = -(new Date().getTimezoneOffset())/60;
const TIME_LABEL={utc:'UTC',ship:'СУД',phone:'ТЛФ'};

/* Момент «сейчас» в выбранном времени, уже сдвинутый: дальше у него
   читаются UTC-поля, поэтому одна и та же формула годится всем трём. */
function nowIn(mode){
  const n=new Date();
  const m=mode||TIME_MODE;
  if(m==='utc')  return n;
  if(m==='ship') return new Date(n.getTime()+SHIP_TZ*3600000);
  return new Date(n.getTime()-n.getTimezoneOffset()*60000);
}
function clockHM(mode){
  const d=nowIn(mode);
  return String(d.getUTCHours()).padStart(2,'0')+':'+String(d.getUTCMinutes()).padStart(2,'0');
}
/* Время в произвольном поясе -- для списка выбора пояса */
function clockHM0(h){
  const d=new Date(Date.now()+h*3600000);
  return String(d.getUTCHours()).padStart(2,'0')+':'+String(d.getUTCMinutes()).padStart(2,'0');
}
function tzText(h){
  const s=h<0?'−':'+', a=Math.abs(h);
  const hh=Math.floor(a), mm=Math.round((a-hh)*60);
  return 'UTC'+s+hh+(mm?(':'+String(mm).padStart(2,'0')):'');
}
/* Совместимость с прежним кодом: где раньше спрашивали «это UTC?» */
let TIME_UTC = TIME_MODE==='utc';
let WATCH_ROLE = localStorage.getItem('navarea_watch')||'2nd';
let NTF = (()=>{ try{ return Object.assign({warn:true,cert:true,gmdss:true},
  JSON.parse(localStorage.getItem('navarea_ntf')||'{}')); }catch(e){ return {warn:true,cert:true,gmdss:true}; } })();
function saveNtf(){ try{ localStorage.setItem('navarea_ntf',JSON.stringify(NTF)); }catch(e){} }

let GEO={lat:null, lon:null, at:0, acc:null, cog:null, sog:null,
         busy:false, err:null, watchId:null, guard:null, cancel:null};

/* ---- Курс и скорость относительно грунта ----
   Приёмник телефона отдаёт heading и speed далеко не всегда: на многих
   устройствах они пустые, пока не включена навигация. Поэтому считаем сами,
   как это делает любой навигатор -- по смещению между двумя обсервациями:
   чем быстрее меняется место, тем выше скорость, направление смещения и
   есть курс.

   Слишком короткие и слишком длинные промежутки отбрасываем: за одну
   секунду смещение тонет в погрешности приёмника, а за полчаса судно
   успевает отвернуть, и «курс» получится ни о чём. Значения сглаживаем,
   иначе на волне цифры скачут на несколько узлов. */
let GEO_PREV=null;

function setCogSog(c){
  if(!c) return;
  // если устройство само даёт курс и скорость -- берём их, они точнее
  if(typeof c.speed==='number'&&!isNaN(c.speed)&&c.speed>=0)
    GEO.sog=+(c.speed*1.94384).toFixed(1);
  if(typeof c.heading==='number'&&!isNaN(c.heading)) GEO.cog=c.heading;
}

function trackFromFix(lat, lon, at, acc){
  const prev=GEO_PREV;
  GEO_PREV={lat:lat, lon:lon, at:at||Date.now(), acc:acc||null};
  if(!prev) return;

  const dt=(GEO_PREV.at-prev.at)/1000;              // секунд между обсервациями
  if(dt<3||dt>900) return;

  const nm=haversineNm(prev.lat,prev.lon,lat,lon);
  const metres=nm*1852;
  // Смещение должно быть заметно больше погрешности места, иначе это шум
  const need=Math.max(12,(prev.acc||20)+(acc||20));
  if(metres<need) return;

  const sog=nm/(dt/3600);
  if(sog>60) return;                                 // явный выброс приёмника

  const cog=bearingDeg(prev.lat,prev.lon,lat,lon);
  // сглаживание: новое значение весит треть, чтобы цифры не прыгали
  GEO.sog = GEO.sog==null ? +sog.toFixed(1) : +(GEO.sog*0.65+sog*0.35).toFixed(1);
  GEO.cog = GEO.cog==null ? Math.round(cog) : Math.round(smoothAngle(GEO.cog,cog,0.35));
}

function bearingDeg(a1,o1,a2,o2){
  const r=Math.PI/180;
  const dl=(o2-o1)*r, p1=a1*r, p2=a2*r;
  const y=Math.sin(dl)*Math.cos(p2);
  const x=Math.cos(p1)*Math.sin(p2)-Math.sin(p1)*Math.cos(p2)*Math.cos(dl);
  return (Math.atan2(y,x)/r+360)%360;
}
/* Углы усредняем через кратчайшую дугу: иначе на переходе через ноль
   курс 359° и 001° дали бы 180° -- ровно противоположный. */
function smoothAngle(old,next,k){
  let d=((next-old+540)%360)-180;
  return (old+d*k+360)%360;
}

/* Слежение за позицией можно выключить совсем: на судне интернет платный,
   а GPS телефона сажает батарею. Настройка живёт на устройстве. */
let GEO_ON = localStorage.getItem('navarea_geo_off')!=='1';

function setGeoEnabled(on){
  GEO_ON=on;
  localStorage.setItem('navarea_geo_off', on?'0':'1');
  if(!on){
    stopGeoWatch();
    GEO.lat=null; GEO.lon=null; GEO.at=0; GEO.err=null;
    if(typeof drawDSC==='function'&&typeof DSC!=='undefined'&&DSC) drawDSC();
    if(typeof map!=='undefined'&&map) drawMyPos();
  }
  renderGeoBtn();
}

/* Непрерывное слежение -- нужно, чтобы метка на карте ехала вместе с судном.
   Включается только когда карта открыта, чтобы не жечь батарею впустую. */
function startGeoWatch(){
  if(!GEO_ON||!GEO_WATCH||GEO.watchId!==null||!navigator.geolocation) return;
  try{
    GEO.watchId=navigator.geolocation.watchPosition(
      p=>{
        GEO.lat=p.coords.latitude; GEO.lon=p.coords.longitude;
        GEO.acc=p.coords.accuracy||null; GEO.at=Date.now(); GEO.err=null;
        // Курс и скорость приходят от того же приёмника. Дают их не все
        // устройства и только на ходу, поэтому в сводке они появляются
        // сами, а при отсутствии показывается прочерк, а не выдуманное число.
        setCogSog(p.coords);
        trackFromFix(GEO.lat, GEO.lon, GEO.at, GEO.acc);
        renderGeoBtn();
        if(S.view==='dash') renderSnapshot();
        if(typeof map!=='undefined'&&map) drawMyPos();
      },
      ()=>{},
      {enableHighAccuracy:true, maximumAge:15000, timeout:20000}
    );
  }catch(e){}
}
function stopGeoWatch(){
  if(GEO.watchId!==null&&navigator.geolocation){
    try{ navigator.geolocation.clearWatch(GEO.watchId); }catch(e){}
  }
  GEO.watchId=null;
}

function geoFmtLat(d){
  if(typeof COORD_FMT!=='undefined'&&COORD_FMT==='dec') return d.toFixed(4)+'°';
  const s=d<0?'S':'N'; d=Math.abs(d);
  const deg=Math.floor(d), min=(d-deg)*60;
  return String(deg).padStart(2,'0')+'-'+min.toFixed(1).padStart(4,'0')+s;
}
function geoFmtLon(d){
  if(typeof COORD_FMT!=='undefined'&&COORD_FMT==='dec') return d.toFixed(4)+'°';
  const s=d<0?'W':'E'; d=Math.abs(d);
  const deg=Math.floor(d), min=(d-deg)*60;
  return String(deg).padStart(3,'0')+'-'+min.toFixed(1).padStart(4,'0')+s;
}
const geoFresh = ()=> GEO.lat!==null && (Date.now()-GEO.at) < 5*60*1000;

function requestPosition(){
  return new Promise(resolve=>{
    if(!GEO_ON){ GEO.err='геопозиция выключена в настройках'; renderGeoBtn(); resolve(null); return; }

    // Повторное нажатие отменяет незавершённый запрос. Раньше кнопка
    // крутилась бесконечно: если система так и не ответила (например,
    // человек не решил, дать ли доступ), busy никто не сбрасывал.
    if(GEO.busy){ cancelPositionRequest(); resolve(null); return; }

    GEO.busy=true; GEO.err=null; renderGeoBtn();

    let finished=false;
    const done=(ok,err)=>{
      if(finished) return;
      finished=true;
      if(GEO.guard){ clearTimeout(GEO.guard); GEO.guard=null; }
      GEO.busy=false; GEO.err=ok?null:(err||'нет данных');
      renderGeoBtn();
      if(typeof renderSettings==='function'&&S.view==='settings') renderSettings();
      if(typeof map!=='undefined'&&map&&ok) drawMyPos();
      resolve(ok?{lat:GEO.lat,lon:GEO.lon}:null);
    };
    GEO.cancel=()=>done(false,'запрос отменён');

    // Страховка: система иногда не отвечает вовсе, ни успехом, ни отказом
    GEO.guard=setTimeout(()=>done(false,'устройство не ответило, попробуй ещё раз'), 20000);

    // 1. Telegram LocationManager (Bot API 8.0+)
    try{
      const lm=TG&&TG.LocationManager;
      if(lm&&typeof lm.init==='function'){
        lm.init(()=>{
          if(!lm.isLocationAvailable){ browserGeo(done); return; }
          lm.getLocation(loc=>{
            if(loc&&typeof loc.latitude==='number'){
              GEO.lat=loc.latitude; GEO.lon=loc.longitude;
              GEO.acc=loc.horizontal_accuracy||null; GEO.at=Date.now();
              done(true);
            } else browserGeo(done);
          });
        });
        return;
      }
    }catch(e){}

    browserGeo(done);
  });
}

function cancelPositionRequest(){
  if(GEO.guard){ clearTimeout(GEO.guard); GEO.guard=null; }
  if(typeof GEO.cancel==='function'){ const c=GEO.cancel; GEO.cancel=null; c(); }
  else { GEO.busy=false; renderGeoBtn(); }
}

function browserGeo(done){
  if(!navigator.geolocation){ done(false,'устройство не отдаёт позицию'); return; }
  navigator.geolocation.getCurrentPosition(
    p=>{
      GEO.lat=p.coords.latitude; GEO.lon=p.coords.longitude;
      GEO.acc=p.coords.accuracy||null; GEO.at=Date.now();
      setCogSog(p.coords);
      trackFromFix(GEO.lat, GEO.lon, GEO.at, GEO.acc);
      done(true);
    },
    err=>{
      const msg = err && err.code===1 ? 'доступ к геопозиции запрещён'
                : err && err.code===3 ? 'спутники не поймались, попробуй у окна или на крыле мостика'
                : 'позиция недоступна';
      done(false,msg);
    },
    {enableHighAccuracy:true, timeout:15000, maximumAge:60000}
  );
}

/* Кнопка позиции в шапке: показывает состояние и текущие координаты */
function renderGeoBtn(){
  const b=$('#geoBtn'); if(!b) return;
  b.className='geobtn'+(!GEO_ON?' off':'')+(GEO.busy?' busy':'')+(geoFresh()?' on':'')+(GEO.err?' err':'');
  // Огонёк состояния: зелёный пульс -- место есть, красный -- нет,
  // жёлтый -- идёт определение.
  const state = GEO.busy ? 'wait' : (GEO_ON&&geoFresh()&&!GEO.err ? '' : 'off');
  b.innerHTML=ico('target','sm')+`<b id="liveDot" class="${state}"></b>`;
  b.title=!GEO_ON?tr('Геопозиция выключена'):(geoFresh()?(geoFmtLat(GEO.lat)+' '+geoFmtLon(GEO.lon)):tr('Моя позиция'));
  const t=$('#geoText');
  if(t){
    if(GEO.busy) t.textContent=tr('Определяю…');
    else if(GEO.err) t.textContent=GEO.err;
    else if(GEO.lat!==null) t.textContent=geoFmtLat(GEO.lat)+'  '+geoFmtLon(GEO.lon);
    else t.textContent=tr('Позиция не запрошена');
  }
}

/* Подставляет позицию в открытый инструмент: заполняет пары полей
   широта/долгота, какие бы имена у них ни были. */
async function fillPositionInto(pairs){
  const p = geoFresh() ? {lat:GEO.lat,lon:GEO.lon} : await requestPosition();
  if(!p) return false;
  pairs.forEach(([latKey,lonKey])=>{
    const la=document.querySelector(`[data-k="${latKey}"]`);
    const lo=document.querySelector(`[data-k="${lonKey}"]`);
    if(la){ la.value=geoFmtLat(p.lat); toolVals[latKey]=la.value; }
    if(lo){ lo.value=geoFmtLon(p.lon); toolVals[lonKey]=lo.value; }
  });
  if(typeof curTool!=='undefined'&&curTool) saveCalcVals(curTool.id,toolVals);
  if(typeof runTool==='function') runTool();
  hap('medium');
  return true;
}

/* Ищет в полях открытого инструмента пары широта/долгота.
   Имена у полей разные (la/lo, la1/lo1, lat/lon), поэтому сопоставляем
   по порядку: каждая широта со следующей за ней долготой. */
function coordPairsOf(tool){
  if(!tool||!tool.fields) return [];
  const lats=tool.fields.filter(f=>f.t==='coord'&&/^(la|lat)/.test(f.k)).map(f=>f.k);
  const lons=tool.fields.filter(f=>f.t==='coord'&&/^(lo|lon)/.test(f.k)).map(f=>f.k);
  const out=[];
  for(let i=0;i<Math.min(lats.length,lons.length);i++) out.push([lats[i],lons[i]]);
  return out;
}

/* ================= Ручки станции =================
   Крутятся пальцем и реально меняют показания на экране, как на судовой
   станции: VOLUME -- громкость, RF GAIN -- усиление приёмника (оно же
   двигает S-метр), большая ручка -- энкодер выбора пунктов меню.
   Считаем угол от центра ручки до пальца, поэтому крутить можно с любой
   стороны, а не только тянуть вверх-вниз. */
const KNOB={vol:5, rf:28, ent:0, entAngle:0, entAt:0};   // ent -- накопленный поворот энкодера

/* Насколько ручка отзывчива. Энкодер сознательно сделан вязким: на
   стеклянном экране палец проходит полсотни пикселей незаметно, и на
   прежних настройках список пролетал целиком от одного движения. */
const ENC_STEP=55;      // градусов на один щелчок -- шаг листания
const ENC_GAP=55;       // мс -- минимум между щелчками, чтобы не частило

function knobAngle(el, x, y){
  const r=el.getBoundingClientRect();
  return Math.atan2(y-(r.top+r.height/2), x-(r.left+r.width/2))*180/Math.PI;
}

function makeKnob(el, opts){
  if(!el||el._knob) return;
  el._knob=true;
  const sens = opts.sens||1.8;          // градусов на пиксель при движении вверх-вниз
  const wheel = opts.wheel||8;          // градусов на щелчок колеса мыши
  let prev=null, startY=0, mode=null, lastHap=0;

  const begin=(x,y)=>{
    prev=knobAngle(el,x,y); startY=y; mode=null;
    el.classList.add('turning');
    if(opts.onStart) opts.onStart();
  };

  const move=(x,y)=>{
    if(prev===null) return;
    // Определяем, как человек крутит: по кругу или тянет вверх-вниз.
    // Пальцем на телефоне вертикальное движение выходит естественнее,
    // мышью удобнее вращать -- поддерживаем оба, выбирая по первому
    // заметному движению.
    if(mode===null){
      const dy=Math.abs(y-startY);
      const a=knobAngle(el,x,y); let da=a-prev;
      if(da>180) da-=360; if(da<-180) da+=360;
      if(dy>10&&Math.abs(da)<12) mode='drag';
      else if(Math.abs(da)>=6) mode='turn';
    }

    let delta=0;
    if(mode==='drag'){
      delta=(startY-y)*sens;    // вверх -- больше
      startY=y;
    } else {
      const a=knobAngle(el,x,y);
      let d=a-prev;
      if(d>180) d-=360; if(d<-180) d+=360;
      if(Math.abs(d)<1) return;
      prev=a; delta=d;
    }
    if(!delta) return;
    opts.onTurn(delta);

    // Отдача не чаще, чем раз в 60 мс: иначе на плавном повороте
    // телефон тарахтит без остановки.
    const now=Date.now();
    if(!opts.quiet&&now-lastHap>60){ hap(); lastHap=now; }
  };

  const end=()=>{
    prev=null; mode=null;
    el.classList.remove('turning');
    if(opts.onEnd) opts.onEnd();
  };

  el.addEventListener('pointerdown',e=>{ e.preventDefault(); el.setPointerCapture&&el.setPointerCapture(e.pointerId); begin(e.clientX,e.clientY); },{passive:false});
  el.addEventListener('pointermove',e=>{ if(prev!==null){ e.preventDefault(); move(e.clientX,e.clientY); } },{passive:false});
  el.addEventListener('pointerup',end,{passive:true});
  el.addEventListener('pointercancel',end,{passive:true});
  el.addEventListener('touchstart',e=>{ if(e.touches[0]) begin(e.touches[0].clientX,e.touches[0].clientY); },{passive:true});
  el.addEventListener('touchmove',e=>{ if(e.touches[0]&&prev!==null){ e.preventDefault(); move(e.touches[0].clientX,e.touches[0].clientY); } },{passive:false});
  el.addEventListener('touchend',end,{passive:true});
  // колесо мыши -- на настольном браузере привычнее всего
  el.addEventListener('wheel',e=>{ e.preventDefault(); opts.onTurn(e.deltaY>0?-wheel:wheel); },{passive:false});
}

function knobRotate(el, deg){
  if(el) el.style.transform='rotate('+deg+'deg)';
}

function knobBubble(el,text){
  if(!el) return;
  let b=el.querySelector('.knobval');
  if(!b){ b=document.createElement('span'); b.className='knobval'; el.appendChild(b); }
  b.textContent=text;
}

function bindStationKnobs(){
  const vol=$('#knobVol'), rf=$('#knobRf'), ent=$('#dkEnter');

  // Громкость и усиление -- наоборот, отзывчивые: их крутят до нужного
  // значения на слух, и длинное протягивание пальцем только раздражает.
  makeKnob(vol,{onTurn:d=>{
    KNOB.vol=Math.max(0,Math.min(10,KNOB.vol+d/20));
    knobRotate(vol, (KNOB.vol/10)*270-135);
    knobBubble(vol, Math.round(KNOB.vol));
    drawDSC();
  }});
  knobRotate(vol,(KNOB.vol/10)*270-135);

  makeKnob(rf,{onTurn:d=>{
    KNOB.rf=Math.max(0,Math.min(99,KNOB.rf+d/2.8));
    knobRotate(rf, (KNOB.rf/99)*270-135);
    knobBubble(rf, Math.round(KNOB.rf));
    drawDSC();
  }});
  knobRotate(rf,(KNOB.rf/99)*270-135);

  // Большая ручка -- энкодер без упоров: крутится сколько угодно, а список
  // листается щелчками. Угол поворота и счётчик щелчков живут раздельно,
  // иначе ручка отскакивала назад после каждого щелчка.
  //
  // Щелчок отрабатывает не чаще ENC_GAP: на прежних настройках одно
  // движение пальцем пролистывало всё меню насквозь, и попасть в нужную
  // строку было невозможно.
  makeKnob(ent,{sens:1.1, wheel:28, quiet:true, onTurn:d=>{
    KNOB.entAngle=(KNOB.entAngle||0)+d;
    KNOB.ent=(KNOB.ent||0)+d;
    const dial=ent.querySelector('.kdial');
    knobRotate(dial||ent, KNOB.entAngle);
    ent._turned=true;

    const now=Date.now();
    if(now-KNOB.entAt<ENC_GAP){
      // копим поворот, но щелчок пока придержим
      KNOB.ent=Math.max(-ENC_STEP*2,Math.min(ENC_STEP*2,KNOB.ent));
      return;
    }
    if(KNOB.ent>=ENC_STEP){ KNOB.ent=0; KNOB.entAt=now; hap(); dscTurn(1); }
    else if(KNOB.ent<=-ENC_STEP){ KNOB.ent=0; KNOB.entAt=now; hap(); dscTurn(-1); }
  }});
  { const dial=ent&&ent.querySelector('.kdial');
    if(dial) knobRotate(dial, KNOB.entAngle||0);
    // видно, что ручка «нажата» и крутит значение, а не выбирает поле
    if(ent) ent.classList.toggle('pushed',
      (DS.screen==='home'&&DS.homeEdit)||
      (DS.screen==='compose'&&CM.edit)||
      (DS.screen==='distress'&&DM.edit)); }
}



/* ================= Визуализация тракта сигнала =================
   Показываем, куда физически уходит сигнал при проверке и при боевом
   включении. Для EPIRB это спутниковый тракт COSPAS-SARSAT, для SART --
   вид отметки с мостика проходящего судна.

   Числа не выдуманы: высоты орбит (GEO 35 890 км, MEO около 20 000 км,
   LEO около 850 км), посылка маяка раз в ~50 секунд, доставка тревоги
   в спасательный центр в пределах 15 минут -- это требования и параметры
   системы COSPAS-SARSAT. */

const SAT_STAGES=[
  {k:'idle',   t:'Маяк в дежурном режиме', d:'Сигнал не излучается'},
  {k:'burst',  t:'Посылка на 406 МГц',     d:'Маяк передаёт короткими посылками примерно раз в 50 секунд'},
  {k:'sat',    t:'Принято спутником',      d:'MEOSAR: спутники GPS, Galileo, ГЛОНАСС и BeiDou несут поисковые ретрансляторы'},
  {k:'lut',    t:'Ретрансляция на MEOLUT', d:'Наземная станция измеряет частоту и время посылок, вычисляет место'},
  {k:'mcc',    t:'Передано в MCC',         d:'Координационный центр системы сверяет данные и опознаёт маяк по номеру'},
  {k:'rcc',    t:'Тревога у спасателей',   d:'Норматив системы: тревога доходит до спасательного центра в пределах 15 минут'}
];

function satSvg(stage, isTest){
  const on = (k)=> SAT_STAGES.findIndex(s=>s.k===stage) >= SAT_STAGES.findIndex(s=>s.k===k);
  const beam = on('burst');
  const relay = on('lut');
  const col = isTest ? '#5ba6e8' : '#ff8a3d';   // тест синим, боевой оранжевым

  return `<svg viewBox="0 0 340 300">
    <defs>
      <radialGradient id="vzEarth" cx="50%" cy="35%">
        <stop offset="0%" stop-color="#2d7cb8"/><stop offset="60%" stop-color="#154a76"/><stop offset="100%" stop-color="#0a2a45"/>
      </radialGradient>
      <linearGradient id="vzUp" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="${col}" stop-opacity="0"/>
        <stop offset="50%" stop-color="${col}" stop-opacity=".9"/>
        <stop offset="100%" stop-color="${col}" stop-opacity=".2"/>
      </linearGradient>
      <linearGradient id="vzDown" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#3fc97f" stop-opacity=".15"/>
        <stop offset="100%" stop-color="#3fc97f" stop-opacity=".85"/>
      </linearGradient>
    </defs>

    <ellipse cx="170" cy="330" rx="300" ry="235" fill="none" stroke="#1e4468" stroke-width="1" stroke-dasharray="3 5"/>
    <ellipse cx="170" cy="330" rx="230" ry="180" fill="none" stroke="#1e4468" stroke-width="1" stroke-dasharray="3 5"/>
    <ellipse cx="170" cy="330" rx="160" ry="128" fill="none" stroke="#1e4468" stroke-width="1" stroke-dasharray="3 5"/>
    <text x="12" y="52" font-size="7.5" fill="#4d7ba8" font-family="monospace">GEO 35 890 км</text>
    <text x="12" y="105" font-size="7.5" fill="#4d7ba8" font-family="monospace">MEO ~20 000 км</text>
    <text x="12" y="158" font-size="7.5" fill="#4d7ba8" font-family="monospace">LEO ~850 км</text>

    <ellipse cx="170" cy="330" rx="150" ry="118" fill="url(#vzEarth)"/>
    <path d="M60 268 q40 -14 82 -4 t76 8" fill="none" stroke="#3d8fc9" stroke-width="1" opacity=".4"/>
    <path d="M45 292 q55 -12 110 -2 t105 6" fill="none" stroke="#3d8fc9" stroke-width="1" opacity=".3"/>

    ${beam?`<path class="vzbeam" d="M150 250 L206 118" stroke="url(#vzUp)" stroke-width="3" fill="none"/>`:''}
    ${relay?`<path class="vzbeam2" d="M206 118 L272 244" stroke="url(#vzDown)" stroke-width="2.5" fill="none" stroke-dasharray="5 4"/>`:''}

    <g transform="translate(268,60)">
      <rect x="-9" y="-5" width="18" height="10" rx="2" fill="#c9d2dc"/>
      <rect x="-19" y="-3" width="8" height="6" fill="#3d6fa5"/><rect x="11" y="-3" width="8" height="6" fill="#3d6fa5"/>
      <text x="0" y="18" font-size="7" fill="#8fb4d8" text-anchor="middle" font-family="monospace">GEO</text>
    </g>
    <g transform="translate(206,118)">
      ${on('sat')?`<circle r="15" fill="${col}" opacity=".16"><animate attributeName="r" values="12;19;12" dur="1.8s" repeatCount="indefinite"/></circle>`:''}
      <rect x="-9" y="-5" width="18" height="10" rx="2" fill="${on('sat')?'#ffd8a0':'#c9d2dc'}"/>
      <rect x="-19" y="-3" width="8" height="6" fill="${on('sat')?'#c07a20':'#3d6fa5'}"/>
      <rect x="11" y="-3" width="8" height="6" fill="${on('sat')?'#c07a20':'#3d6fa5'}"/>
      <text x="0" y="20" font-size="7" fill="${on('sat')?'#ffc372':'#8fb4d8'}" text-anchor="middle" font-family="monospace" font-weight="700">MEO</text>
    </g>
    <g transform="translate(96,150)">
      <rect x="-8" y="-4" width="16" height="9" rx="2" fill="#c9d2dc"/>
      <rect x="-17" y="-2" width="7" height="5" fill="#3d6fa5"/><rect x="10" y="-2" width="7" height="5" fill="#3d6fa5"/>
      <text x="0" y="17" font-size="7" fill="#8fb4d8" text-anchor="middle" font-family="monospace">LEO</text>
    </g>

    <g transform="translate(150,250)">
      ${beam?`<circle r="16" fill="${col}" opacity=".18"><animate attributeName="r" values="10;22;10" dur="1.6s" repeatCount="indefinite"/></circle>`:''}
      <circle r="9" fill="${col}" opacity=".3"/>
      <path d="M-9 2 l3 5 h12 l3 -5 z" fill="${col}"/>
      <rect x="-2" y="-8" width="4" height="10" rx="1" fill="${col}"/>
      <text x="0" y="24" font-size="7" fill="${col}" text-anchor="middle" font-family="monospace" font-weight="700">EPIRB 406</text>
    </g>

    <g transform="translate(272,244)">
      <path d="M-8 6 h16 l-3 -6 h-10 z" fill="#9db6d4"/>
      <path d="M0 0 a8 8 0 0 1 8 -8" fill="none" stroke="${relay?'#3fc97f':'#4d7ba8'}" stroke-width="2"/>
      <circle cx="0" cy="0" r="2.5" fill="${relay?'#3fc97f':'#4d7ba8'}"/>
      <text x="0" y="20" font-size="7" fill="${relay?'#7de3a8':'#6d90b4'}" text-anchor="middle" font-family="monospace" font-weight="700">MEOLUT</text>
    </g>
  </svg>`;
}

/* Цепочка этапов под картинкой */
function satChain(stage, isTest){
  const idx=SAT_STAGES.findIndex(s=>s.k===stage);
  return `<div class="satchain">`+SAT_STAGES.slice(1).map((s,i)=>{
    const done=idx>=i+1, now=idx===i+1;
    return `<div class="satstep ${done?'done':''} ${now?'now':''}">
      <i></i><div><div class="ss">${esc(tr(s.t))}</div>
      ${now?`<div class="sd">${esc(tr(s.d))}</div>`:''}</div></div>`;
  }).join('')+`</div>`+
  (isTest&&idx>0?`<div class="hint" style="margin-top:9px">${ico('alert','xs')} ${esc(tr('При самопроверке сигнал в эту цепочку не уходит: маяк лишь проверяет собственные узлы. Схема показана, чтобы было видно, что происходит при настоящем срабатывании.'))}</div>`:'');
}

/* ---- Вид с мостика проходящего судна (SART) ---- */
function bridgeViewSvg(active){
  // Вид с настоящего судового мостика: подволок с плафонами, репитеры над
  // окнами, панорамное остекление со стойками и дворниками, наклонный пульт
  // с ЭКНИС, радаром, коннингом и станцией ГМССБ, телеграф и штурвал.
  const sartDots = active
    ? `<g fill="#ffb020">
         <circle cx="136" cy="170" r="1.1"/><circle cx="139" cy="166.5" r="1.1"/>
         <circle cx="142" cy="163" r="1.1"/><circle cx="144.5" cy="160" r="1.1"/>
       </g>`
    : '';
  const raftGlow = active
    ? `<circle cx="0" cy="-10" r="6" fill="#ff8a3d" opacity=".25">
         <animate attributeName="r" values="3;9;3" dur="1.6s" repeatCount="indefinite"/></circle>`
    : '';

  return `<svg viewBox="0 0 340 260">
   <defs>
     <linearGradient id="bvSky" x1="0" y1="0" x2="0" y2="1">
       <stop offset="0%" stop-color="#8fb8d8"/><stop offset="55%" stop-color="#cfe0ee"/><stop offset="100%" stop-color="#e8f0f6"/>
     </linearGradient>
     <linearGradient id="bvSea" x1="0" y1="0" x2="0" y2="1">
       <stop offset="0%" stop-color="#3f7ba8"/><stop offset="100%" stop-color="#1d4a6e"/>
     </linearGradient>
     <linearGradient id="bvDeck" x1="0" y1="0" x2="0" y2="1">
       <stop offset="0%" stop-color="#3a444e"/><stop offset="100%" stop-color="#222a32"/>
     </linearGradient>
   </defs>

   <rect x="0" y="0" width="340" height="26" fill="#dfe4e8"/>
   <line x1="0" y1="26" x2="340" y2="26" stroke="#b8c0c8"/>
   <g fill="#f4f7f9" stroke="#c4ccd4" stroke-width=".6">
     <rect x="34" y="7" width="34" height="7" rx="1.5"/>
     <rect x="152" y="7" width="34" height="7" rx="1.5"/>
     <rect x="270" y="7" width="34" height="7" rx="1.5"/>
   </g>
   <g>
     <rect x="120" y="16" width="96" height="12" rx="1.5" fill="#2a333c"/>
     <circle cx="136" cy="22" r="4.2" fill="#e8ecef" stroke="#8a939c" stroke-width=".6"/>
     <circle cx="156" cy="22" r="4.2" fill="#e8ecef" stroke="#8a939c" stroke-width=".6"/>
     <rect x="170" y="18" width="14" height="8" rx="1" fill="#1a1f25"/>
     <text x="177" y="24.5" font-size="4.5" fill="#ff8a3d" text-anchor="middle" font-family="monospace">14.2</text>
     <circle cx="200" cy="22" r="4.2" fill="#e8ecef" stroke="#8a939c" stroke-width=".6"/>
   </g>

   <path d="M8 30 h324 v98 h-324 z" fill="url(#bvSky)"/>
   <rect x="8" y="92" width="324" height="36" fill="url(#bvSea)"/>
   <line x1="8" y1="92" x2="332" y2="92" stroke="#6d9dc0" stroke-width=".8"/>
   <path d="M8 100 q26 -3 52 0 t52 0 t52 0 t52 0 t52 0 t56 0 v28 h-324 z" fill="#2f6b96" opacity=".45"/>
   <path d="M8 112 q30 -3 60 0 t60 0 t60 0 t60 0 t76 0 v16 h-324 z" fill="#24587e" opacity=".5"/>

   <g transform="translate(214,86)">
     <ellipse cx="0" cy="7" rx="9" ry="2.6" fill="#e0611a"/>
     <path d="M-9 7 q9 -7 18 0" fill="#ff8a3d"/>
     <rect x="-.8" y="-8" width="1.6" height="11" fill="#1c2126"/>
     <circle cx="0" cy="-10" r="2.2" fill="#ff8a3d"/>
     ${raftGlow}
   </g>
   <text x="214" y="108" font-size="6" fill="#0d3350" text-anchor="middle" font-family="monospace">${esc(tr('плот · 4 мили'))}</text>

   <g fill="#c8d0d6">
     <rect x="72" y="28" width="7" height="102"/>
     <rect x="150" y="28" width="7" height="102"/>
     <rect x="228" y="28" width="7" height="102"/>
   </g>
   <rect x="8" y="28" width="324" height="102" fill="none" stroke="#b0b9c1" stroke-width="3"/>
   <g stroke="#5a646e" stroke-width="1.2" fill="none">
     <path d="M30 126 l14 -30"/><path d="M108 126 l14 -30"/><path d="M186 126 l14 -30"/><path d="M264 126 l14 -30"/>
   </g>

   <path d="M0 130 L340 130 L340 152 L0 152 Z" fill="#5a6a78"/>
   <path d="M0 152 L340 152 L340 260 L0 260 Z" fill="url(#bvDeck)"/>
   <path d="M14 152 L326 152 L318 196 L22 196 Z" fill="#2c4a68"/>

   <rect x="30" y="158" width="58" height="32" rx="2" fill="#0d1c2a" stroke="#7f8b96"/>
   <rect x="33" y="161" width="52" height="26" fill="#16304a"/>
   <path d="M36 182 q12 -8 24 -3 t22 -6" stroke="#5ba6e8" stroke-width=".8" fill="none"/>
   <text x="59" y="194.5" font-size="4.6" fill="#9db6d4" text-anchor="middle" font-family="monospace">ECDIS</text>

   <rect x="100" y="156" width="66" height="36" rx="2" fill="#0a1410" stroke="#7f8b96"/>
   <circle cx="133" cy="174" r="15.5" fill="#04140c"/>
   <circle cx="133" cy="174" r="10.5" fill="none" stroke="rgba(70,220,140,.28)" stroke-width=".6"/>
   <circle cx="133" cy="174" r="5.5" fill="none" stroke="rgba(70,220,140,.28)" stroke-width=".6"/>
   ${sartDots}
   <circle cx="133" cy="174" r="1.3" fill="#fff"/>
   <text x="133" y="195" font-size="4.6" fill="#9db6d4" text-anchor="middle" font-family="monospace">RADAR X</text>

   <rect x="178" y="158" width="52" height="32" rx="2" fill="#0d1c2a" stroke="#7f8b96"/>
   <rect x="181" y="161" width="46" height="26" fill="#122a3f"/>
   <text x="204" y="194.5" font-size="4.6" fill="#9db6d4" text-anchor="middle" font-family="monospace">CONNING</text>

   <rect x="242" y="156" width="72" height="36" rx="2" fill="#3a4650" stroke="#7f8b96"/>
   <g fill="#1e262e">
     <rect x="247" y="160" width="28" height="9" rx="1"/>
     <rect x="247" y="172" width="28" height="9" rx="1"/>
   </g>
   <circle cx="292" cy="164" r="3.4" fill="#e8503a"/>
   <g fill="#8a939c">
     <rect x="282" y="172" width="7" height="5" rx="1"/><rect x="292" y="172" width="7" height="5" rx="1"/>
     <rect x="302" y="172" width="7" height="5" rx="1"/>
   </g>
   <text x="278" y="188" font-size="4.4" fill="#cfd6dc" text-anchor="middle" font-family="monospace">GMDSS</text>

   <g transform="translate(60,214)">
     <rect x="-16" y="-8" width="32" height="30" rx="3" fill="#4a5560"/>
     <circle cx="0" cy="2" r="9" fill="#2a333c" stroke="#7f8b96"/>
     <rect x="-2" y="-5" width="4" height="10" rx="1.5" fill="#c8d0d6"/>
     <text x="0" y="27" font-size="4.6" fill="#9aa5ae" text-anchor="middle" font-family="monospace">TELEGRAPH</text>
   </g>
   <g transform="translate(170,216)">
     <circle r="14" fill="none" stroke="#5a646e" stroke-width="3.5"/>
     <circle r="4" fill="#4a5560"/>
     <g stroke="#5a646e" stroke-width="2">
       <line x1="0" y1="-14" x2="0" y2="-18"/><line x1="0" y1="14" x2="0" y2="18"/>
       <line x1="-14" y1="0" x2="-18" y2="0"/><line x1="14" y1="0" x2="18" y2="0"/>
     </g>
     <text x="0" y="30" font-size="4.6" fill="#9aa5ae" text-anchor="middle" font-family="monospace">HELM</text>
   </g>
   <path d="M250 200 q16 -6 22 8" stroke="#2a333c" stroke-width="1.6" fill="none"/>
   <circle cx="272" cy="209" r="3" fill="#1a1f25"/>
  </svg>`;
}

/* ================= Живые органы управления EPIRB / SART =================
   Не картинка, а работающий прибор: кнопка TEST нажимается и удерживается,
   индикаторы загораются в том порядке, что описан в руководстве, у SART
   поворотный переключатель имеет три положения.

   Важное различие, которое и надо усвоить на тренажёре: TEST -- это
   самопроверка, сигнал никуда не уходит. Боевое включение (ON/DISTRESS)
   поднимает спасательные службы, поэтому в тренажёре оно доступно, но
   сопровождается предупреждением и ведёт себя иначе -- индикаторы горят
   постоянно, а не гаснут после проверки. */
let EQLIVE={
  epirb:{mode:'off', holding:false, phase:'', gnss:false, strobe:false, tx:false, verdict:null, timer:null},
  sart:{mode:'off', phase:'', led:false, verdict:null, timer:null}
};

function eqReset(kind){
  const st=EQLIVE[kind];
  if(st.timer){ clearTimeout(st.timer); st.timer=null; }
  if(kind==='epirb') Object.assign(st,{mode:'off',holding:false,phase:'',gnss:false,strobe:false,tx:false,verdict:null});
  else Object.assign(st,{mode:'off',phase:'',led:false,verdict:null});
}

/* ---- EPIRB: удержание кнопки TEST ----
   По руководству Tron 60AIS: удержание TEST -> поиск позиции GNSS ->
   передача на 121.5 / AIS / 406 МГц -> один проблеск = норма. */
function epirbTestStart(){
  const st=EQLIVE.epirb;
  if(st.mode==='on') return;                 // в боевом режиме тест не запускается
  st.holding=true; st.verdict=null; st.phase='hold';
  hap('medium'); renderGmdss('epirb');

  st.timer=setTimeout(()=>{
    if(!st.holding){ return; }               // отпустил раньше -- теста нет
    st.mode='test'; st.phase='gnss'; st.gnss=true;
    hap(); renderGmdss('epirb');

    st.timer=setTimeout(()=>{
      st.phase='tx'; st.tx=true; st.gnss=false;
      renderGmdss('epirb');

      st.timer=setTimeout(()=>{
        st.phase='flash'; st.tx=false; st.strobe=true;
        renderGmdss('epirb');

        st.timer=setTimeout(async()=>{
          st.strobe=false; st.phase='done'; st.verdict='pass'; st.mode='off';
          hap('medium');
          try{ GMEQ=await api('/api/gmdss?action=log_test&kind=epirb&result=pass'); }catch(e){}
          renderGmdss('epirb');
        },900);
      },1600);
    },1400);
  },1200);
}

function epirbTestStop(){
  const st=EQLIVE.epirb;
  if(st.phase==='hold'){                     // не додержал
    st.holding=false; st.phase=''; 
    if(st.timer){ clearTimeout(st.timer); st.timer=null; }
    renderGmdss('epirb');
    return;
  }
  st.holding=false;
}

/* ---- EPIRB: боевое включение ---- */
function epirbActivate(){
  const st=EQLIVE.epirb;
  if(st.mode==='on'){ eqReset('epirb'); renderGmdss('epirb'); return; }
  if(!confirm(tr('Это боевое включение. На настоящем приборе оно поднимает спасательные службы. Продолжить в тренажёре?'))) return;
  eqReset('epirb');
  st.mode='on'; st.phase='active'; st.strobe=true; st.tx=true; st.gnss=true;
  hap('heavy'); renderGmdss('epirb');
}

/* ---- SART: поворотный переключатель OFF / TEST / ON ---- */
function sartSetMode(mode){
  const st=EQLIVE.sart;
  if(mode==='on'&&st.mode!=='on'){
    if(!confirm(tr('Это боевое включение. На настоящем приборе SART начнёт отвечать на радары как сигнал бедствия. Продолжить в тренажёре?'))) return;
  }
  if(st.timer){ clearTimeout(st.timer); st.timer=null; }
  st.mode=mode; st.verdict=null;

  if(mode==='off'){ st.phase=''; st.led=false; renderGmdss('sart'); return; }

  if(mode==='test'){
    st.phase='warmup'; st.led=true; hap('medium'); renderGmdss('sart');
    st.timer=setTimeout(()=>{
      st.phase='responding'; renderGmdss('sart');
      st.timer=setTimeout(async()=>{
        st.phase='done'; st.verdict='pass'; st.led=false; st.mode='off';
        hap('medium');
        try{ GMEQ=await api('/api/gmdss?action=log_test&kind=sart&result=pass'); }catch(e){}
        renderGmdss('sart');
      },3200);
    },1200);
    return;
  }

  // боевой режим: отвечает постоянно, пока не выключат
  st.phase='active'; st.led=true; hap('heavy'); renderGmdss('sart');
}

/* ---- индикаторы: панель состояния прибора ---- */
/* Соответствие фазы прибора этапу спутникового тракта */
function satStageOf(){
  const st=EQLIVE.epirb;
  if(st.mode==='on') return 'rcc';                 // боевое: тревога идёт до конца
  if(st.phase==='tx') return 'sat';
  if(st.phase==='flash'||st.phase==='done') return 'lut';
  if(st.phase==='gnss') return 'burst';
  return 'idle';
}

function eqLedPanel(kind){
  const st=EQLIVE[kind];
  const led=(on,color,label,blink)=>
    `<div class="eqled"><i class="${on?'on '+color:''}${on&&blink?' blink':''}"></i><span>${esc(label)}</span></div>`;

  if(kind==='epirb'){
    return `<div class="eqleds">
      ${led(st.gnss,'green','GNSS',st.phase==='gnss')}
      ${led(st.tx,'amber','406 MHz TX',true)}
      ${led(st.strobe,'white','STROBE',true)}
      ${led(st.mode==='on','red','ACTIVE',true)}
    </div>`;
  }
  return `<div class="eqleds">
    ${led(st.led&&st.mode==='test','amber','TEST',true)}
    ${led(st.mode==='on','red','ACTIVE',true)}
    ${led(st.phase==='responding'||st.phase==='active','green','RADAR REPLY',true)}
  </div>`;
}

/* ---- подпись текущего состояния ---- */
const EQ_PHASE_TEXT={
  epirb:{
    '':'Прибор в дежурном режиме, на кронштейне',
    hold:'Удерживай кнопку TEST…',
    gnss:'Поиск спутниковой позиции. Зелёный индикатор загорится, когда позиция определена',
    tx:'Идёт передача тестового сигнала: 121.5 МГц, AIS и 406 МГц. Спасательные службы его не получают',
    flash:'Проблеск индикатора по итогу проверки',
    done:'Один проблеск — самопроверка пройдена. Если индикатор продолжает мигать, смотри код ошибки в руководстве',
    active:'БОЕВОЙ РЕЖИМ. На настоящем приборе сигнал уже принят спутниками COSPAS-SARSAT'
  },
  sart:{
    '':'Переключатель в положении OFF, транспондер на кронштейне',
    warmup:'Режим TEST включён, транспондер прогревается',
    responding:'Отвечает на облучение радаром. Смотри отклик на экране X-диапазонного радара ниже',
    done:'Тест пройден. Не держи в режиме TEST дольше пяти минут: расходует батарею и мешает чужим радарам',
    active:'БОЕВОЙ РЕЖИМ. Отвечает на все радары в зоне видимости как сигнал бедствия'
  }
};

/* ================= EPIRB / SART: проверка оборудования =================
   Чек-лист, пошаговая самопроверка (по руководству Jotron), история с
   PASS/FAIL и напоминание о сроке батареи. Данные лежат на сервере (см.
   /api/gmdss), потому что это не личные настройки телефона, а судовой
   журнал проверок -- должен остаться, даже если человек сменит телефон. */
let GMEQ=null;
let EQSTEP={epirb:-1, sart:-1};   // текущий шаг самопроверки, -1 = не начата
let EQCHECK={epirb:[], sart:[]};
let EQCHK_OPEN={epirb:false, sart:false};  // отмеченные пункты чек-листа (несохранённые)

async function loadGmdss(){
  try{
    GMEQ=await api('/api/gmdss');
    localStorage.setItem('navarea_gmdss_cache', JSON.stringify(GMEQ));
  }catch(e){
    try{ GMEQ=JSON.parse(localStorage.getItem('navarea_gmdss_cache')||'null'); }catch(e2){}
  }
  if(GMEQ&&GMEQ.equipment){
    EQCHECK.epirb=(GMEQ.equipment.epirb&&GMEQ.equipment.epirb.checklist)||[];
    EQCHECK.sart=(GMEQ.equipment.sart&&GMEQ.equipment.sart.checklist)||[];
  }
  return GMEQ;
}

const EQ_META={
  epirb:{name:'Tron 60AIS', sub:'EPIRB · float-free bracket',
    svg:`<svg viewBox="0 0 100 150"><defs>
      <linearGradient id="eqbody" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#ff8a3d"/><stop offset="50%" stop-color="#ff6a1f"/><stop offset="100%" stop-color="#d9540f"/>
      </linearGradient>
      <linearGradient id="eqdome" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#eef2f5"/><stop offset="100%" stop-color="#c3cdd6"/>
      </linearGradient></defs>
      <rect x="47" y="6" width="6" height="34" rx="3" fill="#1c2126"/><circle cx="50" cy="6" r="4" fill="#2a3038"/>
      <path d="M32 46 Q32 30 50 30 Q68 30 68 46 Z" fill="url(#eqdome)" stroke="#9aa5b0" stroke-width="1"/>
      <circle cx="50" cy="38" r="5" fill="#ffd23d" opacity=".9"/>
      <rect x="28" y="46" width="44" height="80" rx="10" fill="url(#eqbody)" stroke="#b4430a" stroke-width="1.5"/>
      <rect x="28" y="70" width="44" height="10" fill="#111417"/>
      <text x="50" y="78" font-size="6" fill="#fff" text-anchor="middle" font-family="monospace" font-weight="700">SOLAS</text>
      <circle cx="50" cy="98" r="9" fill="#1c2126"/><circle cx="50" cy="98" r="6.5" fill="#3a4148"/>
      <text x="50" y="100" font-size="5" fill="#dfe4e8" text-anchor="middle" font-family="monospace" font-weight="700">TEST</text>
      <circle cx="50" cy="114" r="3" fill="#3fc97f"/>
      <rect x="20" y="126" width="60" height="10" rx="4" fill="#1c2126"/>
      <rect x="22" y="120" width="8" height="14" rx="2" fill="#2a3038"/><rect x="70" y="120" width="8" height="14" rx="2" fill="#2a3038"/>
    </svg>`},
  sart:{name:'Tron SART20', sub:'Radar SART · X-диапазон',
    svg:`<svg viewBox="0 0 90 190"><defs>
      <linearGradient id="sqbody" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#ff8a3d"/><stop offset="50%" stop-color="#ff6a1f"/><stop offset="100%" stop-color="#d9540f"/>
      </linearGradient></defs>
      <rect x="41" y="4" width="4" height="60" rx="2" fill="#1c2126"/><circle cx="43" cy="4" r="3.5" fill="#2a3038"/>
      <path d="M25 64 Q25 44 43 44 Q61 44 61 64 Z" fill="#e8ecef" stroke="#9aa5b0" stroke-width="1"/>
      <rect x="21" y="64" width="44" height="88" rx="8" fill="url(#sqbody)" stroke="#b4430a" stroke-width="1.5"/>
      <circle cx="43" cy="96" r="15" fill="#161a1e" stroke="#000" stroke-width="1"/><circle cx="43" cy="96" r="11" fill="#2a3038"/>
      <rect x="41" y="86" width="4" height="10" rx="2" fill="#ffb020"/>
      <text x="43" y="118" font-size="5.5" fill="#dfe4e8" text-anchor="middle" font-family="monospace" font-weight="700">OFF·TEST·ON</text>
      <rect x="21" y="128" width="44" height="9" fill="#111417"/>
      <text x="43" y="135" font-size="5.5" fill="#fff" text-anchor="middle" font-family="monospace" font-weight="700">X-BAND</text>
      <rect x="15" y="152" width="56" height="9" rx="4" fill="#1c2126"/>
    </svg>`}
};
const EQ_STATUS_LABEL={ok:'В порядке',watch:'Планируй замену',soon:'Скоро истекает',expired:'Просрочено',unknown:'Срок не указан'};


/* Кнопка TEST у EPIRB: нажать и удерживать, как на приборе */
function epirbControls(){
  const st=EQLIVE.epirb;
  return `<div class="eqctl">
    <button class="eqbtn test ${st.phase==='hold'?'holding':''}" id="epirbTest">TEST</button>
    <button class="eqbtn arm ${st.mode==='on'?'on':''}" id="epirbOn">${st.mode==='on'?'OFF':'ON'}</button>
  </div>`;
}

/* Поворотный переключатель SART: три положения */
function sartControls(){
  const m=EQLIVE.sart.mode;
  return `<div class="eqsw">
    ${['off','test','on'].map(x=>
      `<button class="swpos ${m===x?'on':''} ${x}" data-sart="${x}">${x.toUpperCase()}</button>`).join('')}
  </div>`;
}

function renderGmdss(kind){
  const box=$('#'+kind+'Box'); if(!box||!GMEQ) return;
  const eq=(GMEQ.equipment&&GMEQ.equipment[kind])||{};
  const meta=EQ_META[kind];
  const checklist=GMEQ[kind+'_checklist']||[];
  const steps=GMEQ[kind+'_steps']||[];
  const history=eq.history||[];
  const done=EQCHECK[kind]||[];
  const pct=checklist.length?Math.round(done.length/checklist.length*100):0;
  const status=eq.status||'unknown';

  const live=EQLIVE[kind];
  const phaseTxt=(EQ_PHASE_TEXT[kind]||{})[live.phase]||'';

  let h=`<div class="eqhero ${live.mode==='on'?'alarm':''}">
      <div class="eqdev">${meta.svg}${kind==='epirb'?epirbControls():sartControls()}</div>
      <div class="eqinfo">
        <div class="nm">${esc(meta.name)}</div>
        <div class="md">${esc(tr(meta.sub))}</div>
        <div class="eqstatus ${status}">● ${esc(tr(EQ_STATUS_LABEL[status]))}${eq.battery_expires?' · '+esc(String(eq.battery_expires).slice(0,10)):''}</div>
        ${eqLedPanel(kind)}
      </div>
    </div>
    ${phaseTxt?`<div class="eqphase ${live.mode==='on'?'alarm':''}">${esc(tr(phaseTxt))}</div>`:''}
    ${live.verdict==='pass'?`<div class="verdict ok"><b>PASS</b>${esc(tr('Самопроверка пройдена. Отметка добавлена в историю.'))}</div>`:''}

    <div class="eqfield" style="margin-top:15px">
      <label>${esc(tr('Дата замены батареи'))}</label>
      <button type="button" class="datefield" id="${kind}Expires" data-iso="${esc(eq.battery_expires||'')}">
        <span class="dv ${eq.battery_expires?'':'none'}">${eq.battery_expires
          ? esc(dpHuman(eq.battery_expires))
          : esc(tr('Не задана'))}</span>
        <span class="dico">${ico('clock','sm')}</span>
      </button>
    </div>

    `;

  // ---- Сначала визуализация, потом порядок проверки, потом чек-лист ----
  // Так человек сперва видит, что вообще происходит с сигналом, и только
  // затем идёт по пунктам осмотра.
  if(kind==='epirb'){
    const stg=satStageOf(), isTest=live.mode!=='on';
    h+=`<div class="sech" style="margin-top:17px"><h3>${esc(tr('Куда уходит сигнал'))}</h3></div>
        <div class="satwrap">${satSvg(stg,isTest)}</div>
        ${satChain(stg,isTest)}`;
  }
  if(kind==='sart'){
    const act = live.phase==='responding'||live.phase==='active';
    h+=`<div class="sech" style="margin-top:17px"><h3>${esc(tr('Вид с проходящего судна'))}</h3></div>
        <div class="bviewwrap">${bridgeViewSvg(act)}</div>
        <div class="hint" style="margin-top:9px">${ico('alert','xs')} ${esc(tr(act
          ? 'Так отметку видит вахтенный на мостике проходящего судна: цепочка точек от своего судна в сторону плота.'
          : 'Переведи переключатель в TEST или ON, чтобы увидеть, как отметка появляется на чужом радаре.'))}</div>

        <div class="sech" style="margin-top:17px"><h3>Radar Preview</h3></div>
        <div class="hint">${ico('alert','xs')} ${esc(tr('Линия из 12 точек с интервалом 0.64 мили. Ближе 1 мили точки становятся дугами, затем полными окружностями.'))}</div>
        <div class="ppiwrap"><div class="ppiratio"><svg id="sartPpi" viewBox="0 0 300 300"></svg></div></div>
        <div class="rngbtns">
          <button class="rngbtn" data-rng="far">6-8 ${esc(tr('миль'))}</button>
          <button class="rngbtn on" data-rng="mid">1-2 ${esc(tr('мили'))}</button>
          <button class="rngbtn" data-rng="close">&lt;0.2 ${esc(tr('мили'))}</button>
        </div>`;
  }

  h+=`<div class="sech" style="margin-top:19px"><h3>${esc(tr('Порядок самопроверки'))}</h3></div>
      <div class="hint">${ico('alert','xs')} ${esc(tr(kind==='epirb'
        ? 'Нажми и удерживай TEST на приборе выше. Индикаторы отработают тот же порядок, что и на настоящем.'
        : 'Переведи переключатель на приборе выше в положение TEST.'))}</div>
      <div class="eqsteps">`;
  steps.forEach(st=>{
    h+=`<div class="eqstep"><div class="num"></div><div class="txt">
          <div class="st">${esc(tr(st.t))}</div>
          <div class="sd">${esc(tr(st.d))}</div></div></div>`;
  });
  h+=`</div>`;

  // ---- Чек-лист: три главных пункта, остальное под кнопкой ----
  // Первые три -- то, что чаще всего и оказывается причиной отказа:
  // просроченная батарея, заклинивший бракет, повреждённая антенна.
  const MAIN=3;
  const openAll=EQCHK_OPEN[kind];
  const shown=openAll?checklist:checklist.slice(0,MAIN);
  h+=`<div class="sech" style="margin-top:19px"><h3>${esc(tr('Ежемесячная проверка'))}</h3>
        <a class="cnt2">${done.length}/${checklist.length}</a></div>
      <div class="eqprogress"><i style="width:${pct}%"></i></div>`;
  shown.forEach(it=>{
    const on=done.includes(it.k);
    h+=`<div class="eqchk ${on?'on':''}" data-chk="${it.k}">
          <div class="box">${on?ico('back','sm'):''}</div>
          <div class="t">${esc(tr(it.t))}</div>
        </div>`;
  });
  if(checklist.length>MAIN){
    const hidden=checklist.length-MAIN;
    const hiddenDone=checklist.slice(MAIN).filter(it=>done.includes(it.k)).length;
    h+=`<button class="showall" data-eqmore="${kind}">${openAll
      ? esc(tr('Свернуть'))
      : esc(tr('Показать остальные'))+' · '+hidden+(hiddenDone?(' · '+esc(tr('отмечено'))+' '+hiddenDone):'')}</button>`;
  }
  h+=`<button class="btn wide" id="${kind}SaveChk" style="margin-top:8px">${esc(tr('Сохранить отметки'))}</button>`;

  h+=`<div class="sech" style="margin-top:19px"><h3>${esc(tr('История проверок'))}</h3>
        ${history.length?`<a id="${kind}ClearHist">${esc(tr('Очистить'))}</a>`:''}</div>`;
  h+= history.length
    ? history.slice(0,15).map(x=>`<div class="eqhist">
          <span class="dot ${x.result}"></span>
          <span class="dt">${esc(String(x.at).slice(0,16).replace('T',' '))}</span>
          <span class="rs ${x.result}">${x.result==='pass'?'PASS':'FAIL'}</span>
        </div>`).join('')
    : `<div class="empty">${ico('clock')}${esc(tr('Проверок пока нет'))}</div>`;

  box.innerHTML=h;
  applyLang();
  bindGmdssEvents(kind);
  if(kind==='sart') drawSartPpi('mid');
}

function bindGmdssEvents(kind){
  // органы управления прибора
  const et=$('#epirbTest');
  if(et){
    et.onmousedown=epirbTestStart; et.onmouseup=epirbTestStop; et.onmouseleave=epirbTestStop;
    et.ontouchstart=(e)=>{e.preventDefault();epirbTestStart()}; et.ontouchend=epirbTestStop;
  }
  const eo=$('#epirbOn'); if(eo) eo.onclick=epirbActivate;
  document.querySelectorAll('[data-sart]').forEach(b=>b.onclick=()=>sartSetMode(b.dataset.sart));

  document.querySelectorAll('[data-eqmore]').forEach(b=>b.onclick=()=>{
    const k=b.dataset.eqmore; EQCHK_OPEN[k]=!EQCHK_OPEN[k]; hap(); renderGmdss(k);
  });
  document.querySelectorAll('[data-chk]').forEach(el=>el.onclick=()=>{
    hap(); const k=el.dataset.chk;
    EQCHECK[kind]=EQCHECK[kind].includes(k)?EQCHECK[kind].filter(x=>x!==k):EQCHECK[kind].concat([k]);
    renderGmdss(kind);
  });

  const sv=$('#'+kind+'SaveChk');
  if(sv) sv.onclick=async()=>{
    hap('medium');
    try{ GMEQ=await api('/api/gmdss?action=save_checklist&kind='+kind+'&checked='+encodeURIComponent(JSON.stringify(EQCHECK[kind]))); renderGmdss(kind); }
    catch(e){}
  };

  // Дата батареи -- свой календарь: раздел перерисовывается только после
  // «Готово», поэтому окно больше не захлопывается на выборе года и месяца.
  const exp=$('#'+kind+'Expires');
  if(exp) exp.onclick=()=>{
    dpOpen(exp.dataset.iso||'', 'Дата замены батареи', async iso=>{
      try{ GMEQ=await api('/api/gmdss?action=save_equipment&kind='+kind
             +'&battery_expires='+encodeURIComponent(iso)); }
      catch(e){}
      renderGmdss(kind);
    });
  };

  const st=$('#'+kind+'StartTest');
  if(st) st.onclick=()=>{ hap('medium'); EQSTEP[kind]=0; renderGmdss(kind); };

  const nx=$('#'+kind+'NextStep');
  if(nx) nx.onclick=async()=>{
    hap('medium');
    const steps=(GMEQ[kind+'_steps']||[]).length;
    EQSTEP[kind]++;
    if(EQSTEP[kind]>=steps){
      try{ GMEQ=await api('/api/gmdss?action=log_test&kind='+kind+'&result=pass'); }catch(e){}
    }
    renderGmdss(kind);
  };
  const fl=$('#'+kind+'FailStep');
  if(fl) fl.onclick=async()=>{
    hap('heavy');
    try{ GMEQ=await api('/api/gmdss?action=log_test&kind='+kind+'&result=fail'); }catch(e){}
    EQSTEP[kind]=-1; renderGmdss(kind);
  };
  const ta=$('#'+kind+'TestAgain');
  if(ta) ta.onclick=()=>{ hap(); EQSTEP[kind]=-1; renderGmdss(kind); };

  const ch=$('#'+kind+'ClearHist');
  if(ch) ch.onclick=async()=>{
    hap('medium');
    if(!confirm(tr('Удалить всю историю проверок?'))) return;
    try{ GMEQ=await api('/api/gmdss?action=clear_history&kind='+kind); renderGmdss(kind); }catch(e){}
  };

  document.querySelectorAll('[data-rng]').forEach(b=>b.onclick=()=>{
    hap();
    document.querySelectorAll('[data-rng]').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); drawSartPpi(b.dataset.rng);
  });
}

/* ---- радарная отметка SART: проверено рендером, соответствует
   IMO SN.1/Circ.197 -- 12 точек с интервалом 0.64 мили вдоль пеленга,
   переходящие в дуги и окружности ближе одной мили. ---- */
function sartPolar(cx,cy,r,angleDeg){
  const a=(angleDeg-90)*Math.PI/180;
  return [cx+r*Math.cos(a), cy+r*Math.sin(a)];
}
function drawSartPpi(mode){
  const svg=$('#sartPpi'); if(!svg) return;
  const cx=150, cy=150, R=140, bearing=35;
  const maxNm = mode==='far'?8:(mode==='mid'?2:0.3);
  let rings='';
  [0.25,0.5,0.75,1].forEach(f=>{ rings+=`<circle cx="${cx}" cy="${cy}" r="${R*f}" fill="none" stroke="rgba(70,220,140,.22)"/>`; });
  let blips='';
  if(mode==='far'||mode==='mid'){
    for(let i=1;i<=12;i++){
      const nm=i*0.64;
      if(nm>maxNm+0.01) continue;
      const r=(nm/maxNm)*R*0.94;
      const [x,y]=sartPolar(cx,cy,r,bearing);
      const sz = mode==='far' ? 3.2 : (3.5+i*0.55);
      blips+=`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${sz}" fill="#ffb020" style="filter:drop-shadow(0 0 4px rgba(255,176,32,.8))"/>`;
    }
  } else {
    const r=R*0.32; const [x,y]=sartPolar(cx,cy,r,bearing);
    [10,20,30].forEach(sz=>{
      blips+=`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${sz}" fill="none" stroke="#ffb020" stroke-width="2.4" style="filter:drop-shadow(0 0 4px rgba(255,176,32,.7))"/>`;
    });
  }
  svg.innerHTML=`
    <circle cx="${cx}" cy="${cy}" r="${R}" fill="none"/>
    ${rings}
    <defs><linearGradient id="sartsweepg" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0%" stop-color="rgba(70,220,140,0)"/><stop offset="100%" stop-color="rgba(70,220,140,.9)"/>
    </linearGradient></defs>
    <line class="sweepline" x1="${cx}" y1="${cy}" x2="${cx}" y2="${cy-R}" stroke="url(#sartsweepg)" stroke-width="2"/>
    ${blips}
    <circle cx="${cx}" cy="${cy}" r="3" fill="#fff" style="filter:drop-shadow(0 0 5px #fff)"/>`;
}

let VES=null, vesSearchTimer=null;

async function loadVessel(){
  try{ VES=await api('/api/vessel'); localStorage.setItem('navarea_vessel',JSON.stringify(VES)); }
  catch(e){ try{ VES=JSON.parse(localStorage.getItem('navarea_vessel')||'null'); }catch(e2){} }
  renderVessel();
  return VES;
}

/* значения из карточки судна для полей расчёта */
function vesselPrefill(toolId){
  return (VES&&VES.prefill&&VES.prefill[toolId])||{};
}
const activeVessel=()=>(VES&&VES.active)||{};

function renderVessel(){
  const box=$('#vesselBox'); if(!box) return;
  if(!VES){ box.innerHTML='<div class="sk card"></div><div class="sk card"></div>'; return; }
  if(VES.error){
    box.innerHTML=`<div class="empty">${ico('ship')}Открой приложение из чата с ботом, чтобы карточка судна привязалась к тебе.</div>`;
    return;
  }
  const v=VES.active||{};
  const list=VES.vessels||[];

  if(!list.length){ renderVesselEmpty(box); return; }

  const row=(l,val,u)=>val?`<div class="tres"><span class="tl">${esc(l)}</span><span class="tv mono">${esc(val)}${u?' '+u:''}</span></div>`:'';
  const section=(sec)=>{
    const rows=sec.fields.map(f=>row(f.l,v[f.k],f.u)).filter(Boolean);
    if(!rows.length) return '';
    return `<div class="dpanel"><h4>${ico(sec.icon,'xs')} ${esc(sec.title)}</h4>${rows.join('')}</div>`;
  };

  const switcher = list.length>1
    ? `<div class="chips" style="margin-bottom:12px">${list.map(x=>
        `<button class="chip ${x._id===VES.active_id?'on':''}" data-sel="${esc(x._id)}">${esc(x.name||'Без названия')}</button>`).join('')}
       <button class="chip" data-addship>+ Судно</button></div>`
    : '';

  box.innerHTML=switcher+`
    <div class="vhero">
      <svg class="vwave" viewBox="0 0 800 40" preserveAspectRatio="none">
        <path d="M0 20 q50 -12 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v24 h-800 z" fill="#4d93d6"/>
      </svg>
      <div class="vin">
        <div class="vname">${esc(v.name||'Без названия')}</div>
        <div class="vmeta">
          ${v.type?`<span class="dchip">${ico('ship','xs')}${esc(v.type)}</span>`:''}
          ${v.flag?`<span class="dchip">${ico('flag','xs')}${esc(v.flag)}</span>`:''}
          ${v.imo?`<span class="dchip">IMO ${esc(v.imo)}</span>`:''}
          ${v.built?`<span class="dchip">${esc(v.built)} г.</span>`:''}
        </div>
      </div>
    </div>

    <div class="vkey">
      ${v.loa?`<div class="vk"><div class="vkv mono">${esc(v.loa)}</div><div class="vkl">длина, м</div></div>`:''}
      ${v.beam?`<div class="vk"><div class="vkv mono">${esc(v.beam)}</div><div class="vkl">ширина, м</div></div>`:''}
      ${v.draft_max?`<div class="vk"><div class="vkv mono">${esc(v.draft_max)}</div><div class="vkl">осадка, м</div></div>`:''}
      ${v.dwt?`<div class="vk"><div class="vkv mono">${esc(v.dwt)}</div><div class="vkl">дедвейт, т</div></div>`:''}
    </div>

    ${(VES.sections||[]).map(section).join('')}

    <div class="dpanel"><h4>${ico('archive','xs')} Документы</h4>
      <div id="docList"></div>
      <button class="btn g wide" id="addDoc" style="margin-top:9px">Добавить документ</button>
    </div>

    <button class="btn wide" id="editVessel">Изменить данные</button>
    <button class="btn g wide" id="delVessel" style="margin-top:9px">Удалить судно</button>
    <div class="hint" style="margin-top:13px">${ico('alert','xs')} Эти значения подставляются в расчёты как исходные — можно менять на месте, карточка от этого не изменится.</div>`;

  renderDocs();
  const eb=$('#editVessel'); if(eb) eb.onclick=()=>openVesselForm(VES.active_id);
  const db_=$('#delVessel'); if(db_) db_.onclick=async()=>{
    hap('medium');
    if(!confirm('Удалить это судно из профиля?')) return;
    try{ VES=await api('/api/vessel?action=delete&id='+encodeURIComponent(VES.active_id)); renderVessel(); }catch(e){}
  };
  document.querySelectorAll('[data-sel]').forEach(b=>b.onclick=async()=>{
    hap();
    try{ VES=await api('/api/vessel?action=select&id='+encodeURIComponent(b.dataset.sel)); renderVessel(); }catch(e){}
  });
  const add=box.querySelector('[data-addship]'); if(add) add.onclick=()=>openVesselSearch();
  const ad=$('#addDoc'); if(ad) ad.onclick=openDocForm;
  applyLang();
}

function renderVesselEmpty(box){
  box.innerHTML=`
    <div class="vhero">
      <svg class="vwave" viewBox="0 0 800 40" preserveAspectRatio="none">
        <path d="M0 20 q50 -12 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v24 h-800 z" fill="#4d93d6"/>
      </svg>
      <div class="vin">${ico('ship','lg')}
        <div class="vt">Судно не заведено</div>
        <div class="vs">Заполни карточку один раз — длина, ширина, осадка, Cb и остальное сами подставятся в расчёты запаса под килём, проседания, якорной стоянки и прохода под мостом.</div>
      </div>
    </div>
    <button class="btn wide" id="findVessel" style="margin-top:13px">Найти судно по названию</button>
    <button class="btn g wide" id="manualVessel" style="margin-top:9px">Заполнить вручную</button>
    <div class="hint" style="margin-top:13px">${ico('alert','xs')} ${esc((VES.provider||{}).note||'')}</div>`;
  const f=$('#findVessel'); if(f) f.onclick=openVesselSearch;
  const m=$('#manualVessel'); if(m) m.onclick=()=>openVesselForm('');
  applyLang();
}

/* --- поиск судна с автодополнением --- */
function openVesselSearch(){
  hap('medium');
  const prov=(VES&&VES.provider)||{};
  $('#tName').textContent='Поиск судна';
  $('#tDesc').textContent=prov.title||'';
  $('#tIcon').innerHTML=ico('search','lg');
  { const b=$('#tBackTitle'); if(b) b.textContent='Поиск судна'; }
  $('#tFields').innerHTML=`
    <div class="fld">
      <label>Название, IMO или MMSI</label>
      <div class="sbox"><input class="tinput" id="vsQ" placeholder="Например Cape" autocomplete="off" style="border:none;background:none;padding:0"></div>
    </div>
    <div class="hint">${ico('alert','xs')} ${esc(prov.note||'')}</div>`;
  $('#tResults').innerHTML=`<div id="vsList"></div>
    <button class="btn wide" id="vsManual" style="margin-top:11px">Заполнить вручную</button>`;
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
  curTool=null;

  const inp=$('#vsQ');

  /* Внешнего справочника судов в открытом доступе нет, поэтому подсказываем
     тем, что реально помогает: судами, которые пользователь уже заводил
     (часто это тот же пароход после отпуска или систер-шип), и типовыми
     сериями -- выбрал класс, размерения подставились, останется поправить. */
  async function vsRender(q){
    let r;
    try{ r=await api('/api/vessel?action=suggest&q='+encodeURIComponent(q||'')); }
    catch(e){ $('#vsList').innerHTML=`<div class="hint">Нет связи с сервером.</div>`; return; }

    const hist=r.history||[], pres=r.presets||[];
    let h='';
    if(hist.length){
      h+=`<div class="sech" style="margin:4px 0 9px"><h3 style="font-size:13px">Мои суда</h3></div>`+
        hist.map(x=>`<div class="vsrow" data-mine="${esc(x.id)}">
            <div class="vsi">${ico('ship','sm')}</div>
            <div style="flex:1;min-width:0">
              <div class="vsn">${esc(x.name)}</div>
              <div class="vsd">${esc(x.sub||'')}</div>
            </div><span class="rtag am">в профиле</span></div>`).join('');
    }
    if(pres.length){
      h+=`<div class="sech" style="margin:15px 0 9px"><h3 style="font-size:13px">Типовые серии</h3></div>`+
        pres.map(x=>`<div class="vsrow" data-preset="${esc(x.id)}">
            <div class="vsi">${ico('ship','sm')}</div>
            <div style="flex:1;min-width:0">
              <div class="vsn">${esc(x.title)}</div>
              <div class="vsd">${esc(x.type)} · размерения подставятся</div>
            </div><span class="rtag">шаблон</span></div>`).join('');
    }
    $('#vsList').innerHTML = h || `<div class="hint">${ico('search','xs')} Ничего не нашлось. Можно заполнить карточку вручную.</div>`;

    document.querySelectorAll('[data-mine]').forEach(el=>el.onclick=()=>{
      hap('medium'); openVesselForm(el.dataset.mine);
    });
    document.querySelectorAll('[data-preset]').forEach(el=>el.onclick=async()=>{
      hap('medium');
      try{
        const res=await api('/api/vessel?action=preset&preset='+encodeURIComponent(el.dataset.preset));
        const card=res.values||{};
        if(inp.value.trim()) card.name=inp.value.trim();
        openVesselForm('', card);
      }catch(e){ openVesselForm('',{name:inp.value.trim()}); }
    });
    applyLang();
  }

  vsRender('');
  inp.oninput=()=>{
    clearTimeout(vesSearchTimer);
    vesSearchTimer=setTimeout(()=>vsRender(inp.value.trim()),240);
  };
  const mv=$('#vsManual'); if(mv) mv.onclick=()=>openVesselForm('',{name:inp.value.trim()});
  applyLang();
}

/* --- форма карточки по разделам --- */
function openVesselForm(vid, preset){
  if(!VES) return;
  hap('medium');
  const base=vid ? (VES.vessels||[]).find(x=>x._id===vid)||{} : (preset||{});
  $('#tName').textContent=vid?'Изменить судно':'Карточка судна';
  $('#tDesc').textContent='Заполняется один раз, подставляется во все расчёты';
  $('#tIcon').innerHTML=ico('ship','lg');
  { const b=$('#tBackTitle'); if(b) b.textContent='Карточка судна'; }

  $('#tFields').innerHTML=(VES.sections||[]).map((sec,i)=>`
    <div class="vsec ${i===0?'open':''}" data-sec="${sec.id}">
      <div class="vsech">${ico(sec.icon,'sm')}<span>${esc(tr(sec.title))}</span>
        <span class="vsarrow">${ico('back','xs')}</span></div>
      <div class="vsbody">${sec.fields.map(f=>
        `<div class="fld"><label>${esc(tr(f.l))}${f.u?' · '+esc(tr(f.u)):''}</label>
         <input class="vinput" data-k="${f.k}" inputmode="${f.t==='num'?'decimal':'text'}"
                autocomplete="off" ${f.ref?`data-ref="${f.ref}"`:''}
                value="${esc(base[f.k]||'')}">
         ${f.ref?`<div class="sugg" data-sugg="${f.k}"></div>`:''}</div>`).join('')}</div>
    </div>`).join('');

  $('#tResults').innerHTML=`<button class="btn wide" id="saveVessel">Сохранить</button>`;
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
  curTool=null;

  document.querySelectorAll('.vsech').forEach(h=>h.onclick=()=>{
    h.parentElement.classList.toggle('open'); hap();
  });
  bindVesselSuggest();

  $('#saveVessel').onclick=async()=>{
    const q=[];
    document.querySelectorAll('.vinput').forEach(el=>{
      if(el.value.trim()) q.push(encodeURIComponent(el.dataset.k)+'='+encodeURIComponent(el.value.trim()));
    });
    if(!q.length){ return; }
    hap('medium');
    try{
      VES=await api('/api/vessel?action=save'+(vid?'&id='+encodeURIComponent(vid):'')+'&'+q.join('&'));
      localStorage.setItem('navarea_vessel',JSON.stringify(VES));
      renderVessel(); closeTool();
    }catch(e){
      $('#tResults').innerHTML=`<div class="tres warn"><span class="tl">Не удалось сохранить</span><span class="tv">нет связи</span></div>`;
    }
  };
  applyLang();
}

/* --- документы судна --- */
function renderDocs(){
  const el=$('#docList'); if(!el||!VES) return;
  const docs=VES.docs||[];
  el.innerHTML = docs.length
    ? docs.map(d=>`<div class="tres"><span class="tl">${esc(d.title)}
        ${d.note?`<br><span style="font-size:11px;opacity:.7">${esc(d.note)}</span>`:''}</span>
        <span class="tv" style="font-size:12.5px">${esc(d.edition||'')}</span>
        <button class="rcopy" data-deldoc="${esc(d.id)}" style="margin-left:9px">${ico('archive','sm')}</button></div>`).join('')
    : `<div class="hint" style="margin:0">${ico('archive','xs')} Список судовых документов с номером редакции — чтобы под рукой было, что и когда корректировалось.</div>`;
  document.querySelectorAll('[data-deldoc]').forEach(b=>b.onclick=async ev=>{
    ev.stopPropagation(); hap('medium');
    try{ VES=await api('/api/vessel?action=doc_del&doc='+encodeURIComponent(b.dataset.deldoc)); renderVessel(); }catch(e){}
  });
}

function openDocForm(){
  hap('medium');
  const types=(VES&&VES.doc_types)||[];
  $('#tName').textContent='Документ судна';
  $('#tDesc').textContent='Название, редакция и заметка';
  $('#tIcon').innerHTML=ico('archive','lg');
  { const b=$('#tBackTitle'); if(b) b.textContent='Документ судна'; }
  $('#tFields').innerHTML=`
    <div class="fld"><label>Документ</label>
      <select class="tinput" id="docTitle">
        ${types.map(t=>`<option>${esc(t)}</option>`).join('')}
        <option>Другой</option>
      </select></div>
    <div class="fld"><label>Своё название (если выбрано «Другой»)</label>
      <input class="tinput" id="docOther" placeholder="Например Ballast Water Plan"></div>
    <div class="fld"><label>Редакция или дата</label>
      <input class="tinput" id="docEd" placeholder="Например Rev. 3, 2025"></div>
    <div class="fld"><label>Заметка</label>
      <input class="tinput" id="docNote" placeholder="Например где хранится"></div>`;
  $('#tResults').innerHTML=`<button class="btn wide" id="docSave">Сохранить</button>`;
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
  curTool=null;

  $('#docSave').onclick=async()=>{
    let title=$('#docTitle').value;
    if(title==='Другой') title=$('#docOther').value.trim();
    if(!title){ return; }
    hap('medium');
    try{
      VES=await api('/api/vessel?action=doc_add&title='+encodeURIComponent(title)+
        '&edition='+encodeURIComponent($('#docEd').value.trim())+
        '&note='+encodeURIComponent($('#docNote').value.trim()));
      renderVessel(); closeTool();
    }catch(e){}
  };
  applyLang();
}

/* ---- Экран инструментов ---- */
let curTool=null, toolVals={};

/* Что пользователь вводил в каждом расчёте. Раньше при выходе всё
   сбрасывалось на значения по умолчанию, и длинные наборы (CPA, ECDIS,
   дифферент) приходилось набивать заново. */
const CALC_MEM='navarea_calc_vals';
function loadCalcVals(id){
  try{ return (JSON.parse(localStorage.getItem(CALC_MEM)||'{}'))[id]||null; }catch(e){ return null; }
}
function saveCalcVals(id,vals){
  try{
    const all=JSON.parse(localStorage.getItem(CALC_MEM)||'{}');
    all[id]=vals;
    localStorage.setItem(CALC_MEM,JSON.stringify(all));
  }catch(e){}
}

/* ---- Инструменты: сначала разделы, потом список ----
   Раньше все категории со всеми плитками шли одной лентой вниз, и до
   нижних приходилось долго крутить. Теперь сверху компактная сетка
   разделов, а список открывается внутри выбранного. */
let TOOL_CAT=null;

function renderTools(){
  const favT=JSON.parse(localStorage.getItem('navarea_favtools')||'[]');

  // выбран раздел -- показываем только его
  if(TOOL_CAT){
    const cat=TOOL_CATS[TOOL_CAT]||{t:TOOL_CAT,i:'sliders'};
    const list=TOOLS.filter(t=>t.cat===TOOL_CAT);
    $('#toollist').innerHTML=
      `<button class="backrow" id="toolsBack">${ico('back','sm')}<span>${esc(tr('Все разделы'))}</span></button>
       <div class="sech"><h3>${esc(tr(cat.t))}</h3><a class="cnt2">${list.length}</a></div>
       <div class="grid2">${list.map(toolCard).join('')}</div>`;
    bindToolCards();
    const b=$('#toolsBack'); if(b) b.onclick=()=>{TOOL_CAT=null;hap();renderTools();};
    applyLang();
    return;
  }

  let h='';

  // то, что под рукой: избранное и частое -- одной короткой лентой
  const quick=[];
  favT.forEach(id=>{ const t=TOOLS.find(x=>x.id===id); if(t&&!quick.includes(t)) quick.push(t); });
  topUsed('tool',6).forEach(id=>{ const t=TOOLS.find(x=>x.id===id); if(t&&!quick.includes(t)) quick.push(t); });
  if(quick.length){
    h+=`<div class="sech"><h3>${esc(tr('Под рукой'))}</h3></div>`+
       `<div class="grid2">${quick.slice(0,4).map(toolCard).join('')}</div>`;
  }

  // GMDSS -- отдельной категорией, как просили: тренажёр ЦИВ, проверка
  // EPIRB и SART, справочник радиостанций MF/HF собраны вместе, а не
  // раскиданы отдельными вкладками сверху.
  h+=`<div class="sech" style="margin-top:16px"><h3>GMDSS</h3></div><div class="catgrid">`;
  GMDSS_CARDS.forEach(c=>{
    h+=`<button class="catcard" data-gview="${c.v}">
          <span class="ci">${ico(c.i)}</span>
          <span class="cn">${esc(tr(c.t))}</span>
        </button>`;
  });
  h+=`</div>`;

  // разделы-расчёты плитками
  h+=`<div class="sech" style="margin-top:16px"><h3>${esc(tr('Навигация и расчёты'))}</h3></div><div class="catgrid">`;
  Object.keys(TOOL_CATS).forEach(ck=>{
    const list=TOOLS.filter(t=>t.cat===ck);
    if(!list.length) return;
    const c=TOOL_CATS[ck];
    h+=`<button class="catcard" data-cat="${ck}">
          <span class="ci">${ico(c.i)}</span>
          <span class="cn">${esc(tr(c.t))}</span>
          <span class="cq">${list.length}</span>
        </button>`;
  });
  h+=`</div>`;

  $('#toollist').innerHTML=h;
  applyLang();
  bindToolCards();
  bindDraggableRows();
  document.querySelectorAll('[data-cat]').forEach(b=>b.onclick=()=>{
    TOOL_CAT=b.dataset.cat; hap(); renderTools();
    try{ window.scrollTo({top:0,behavior:'smooth'}); }catch(e){}
  });
  document.querySelectorAll('[data-gview]').forEach(b=>b.onclick=()=>{
    hap(); switchView(b.dataset.gview);
  });
}
const GMDSS_CARDS=[
  {v:'dsc',t:'Тренажёр ЦИВ',i:'radar'},
  {v:'epirb',t:'EPIRB Test',i:'buoy'},
  {v:'sart',t:'SART Test',i:'radar'},
  {v:'radio',t:'Радиостанции MF/HF',i:'radar'}
];

function bindToolCards(){
  document.querySelectorAll('[data-tool]').forEach(c=>c.onclick=ev=>{
    if(ev.target.closest('.gstar')) return;
    openTool(TOOLS.find(t=>t.id===c.dataset.tool));
  });
  document.querySelectorAll('[data-ftool]').forEach(b=>b.onclick=ev=>{
    ev.stopPropagation();hap('medium');
    const id=b.dataset.ftool;
    let f=JSON.parse(localStorage.getItem('navarea_favtools')||'[]');
    f=f.includes(id)?f.filter(x=>x!==id):f.concat([id]);
    localStorage.setItem('navarea_favtools',JSON.stringify(f));
    renderTools();
  });
}

function toolCard(t,i){
  const favT=JSON.parse(localStorage.getItem('navarea_favtools')||'[]');
  const f=favT.includes(t.id);
  return `<div class="gcard up" style="animation-delay:${Math.min((i||0)*40,300)}ms" data-tool="${t.id}">
    <div class="gtop" style="height:64px">
      <svg class="bgw" viewBox="0 0 800 32" preserveAspectRatio="none">
        <path d="M0 16 q50 -10 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v20 h-800 z" fill="#4d93d6"/>
      </svg>
      <div class="gi">${ico(t.icon)}</div>
      <button class="gstar ${f?'on':''}" data-ftool="${t.id}">${ico('star')}</button>
    </div>
    <div class="gbody">
      <div class="gname" style="min-height:auto">${esc(t.name)}</div>
      <div class="gsub" style="margin-top:4px;display:block;line-height:1.35">${esc(t.desc)}</div>
    </div>
  </div>`;
}

function openTool(t){
  if(!t) return;
  bump('tool',t.id);
  curTool=t; hap('medium');
  rememberCalc(t.id);

  // Известные параметры судна подставляются вместо значений по умолчанию:
  // открывая запас под килём, вводить нужно только текущую глубину и прилив.
  const pre=vesselPrefill(t.id);
  const saved=loadCalcVals(t.id)||{};
  toolVals={};
  t.fields.forEach(f=>{
    // приоритет: что вводил сам -> данные судна -> значение по умолчанию
    if(saved[f.k]!==undefined && saved[f.k]!=='') toolVals[f.k]=saved[f.k];
    else if(pre[f.k]!==undefined && pre[f.k]!=='') toolVals[f.k]=pre[f.k];
    else toolVals[f.k]=(f.def!==undefined?f.def:'');
  });

  $('#tName').textContent=tr(t.name);
  { const b=$('#tBackTitle'); if(b) b.textContent=tr(t.name); }
  $('#tDesc').textContent=tr(t.desc);
  $('#tIcon').innerHTML=ico(t.icon,'lg');
  const shipName=(activeVessel().name)||'';
  $('#tFields').innerHTML=t.fields.map(f=>{
    const fromShip = pre[f.k]!==undefined && pre[f.k]!=='';
    const tag = fromShip ? `<span class="fromship">${ico('ship','xs')}${esc(shipName||'из карточки')}</span>` : '';
    if(f.t==='sel'){
      return `<div class="fld"><label>${esc(f.l)}${tag}</label>
        <select class="tinput" data-k="${f.k}">
          ${f.opts.map(o=>`<option ${o===f.def?'selected':''}>${esc(o)}</option>`).join('')}
        </select></div>`;
    }
    const im=f.t==='num'?'decimal':'text';
    return `<div class="fld"><label>${esc(f.l)}${f.u?` · ${esc(f.u)}`:''}${tag}</label>
      <input class="tinput${fromShip?' fromship-in':''}" data-k="${f.k}" inputmode="${im}"
             value="${esc(String(toolVals[f.k]||''))}"></div>`;
  }).join('');

  // В расчётах с координатами -- кнопка подстановки позиции с устройства
  { const pairs=coordPairsOf(t);
    if(pairs.length){
      $('#tFields').insertAdjacentHTML('afterbegin',
        `<button class="geouse" id="useGeo">${ico('target','xs')}${esc(tr('Подставить мою позицию'))}</button>`);
      const ug=$('#useGeo');
      if(ug) ug.onclick=async()=>{
        ug.textContent=tr('Определяю…');
        const ok=await fillPositionInto(pairs);
        ug.innerHTML=ico('target','xs')+esc(ok?tr('Позиция подставлена'):(GEO.err||tr('Позиция недоступна')));
      };
    }
  }

  document.querySelectorAll('.tinput').forEach(el=>{
    const ev=el.tagName==='SELECT'?'onchange':'oninput';
    el[ev]=()=>{
      toolVals[el.dataset.k]=el.value;
      if(curTool) saveCalcVals(curTool.id,toolVals);
      runTool();
    };
  });
  runTool();
  applyLang();
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
}
/* На числовой клавиатуре телефона десятичный разделитель -- запятая, а JS
   понимает только точку: "1424,7" превращалось в NaN и весь расчёт молча
   ломался. Приводим ввод к машинному виду перед вычислением.
   Если в строке есть и точка, и запятая -- запятая считается разделителем
   тысяч ("1,424.7") и просто убирается. */
function numFix(s){
  if(typeof s!=='string') return s;
  const t=s.trim();
  if(t.indexOf(',')===-1) return t;
  return (t.indexOf('.')!==-1) ? t.replace(/,/g,'') : t.replace(/,/g,'.');
}
function normVals(v){
  const out={};
  Object.keys(v||{}).forEach(k=>{ out[k]=numFix(v[k]); });
  return out;
}

function runTool(){
  if(!curTool) return;
  let rows;
  try{ rows=curTool.calc(normVals(toolVals))||[]; }
  catch(e){ rows=[{l:'Ошибка',v:'Проверь введённые данные'}]; }
  const __al=1;
  // Строка может нести не пару «название и значение», а рисунок: так
  // расчёт расхождения показывает планшет, где видно саму геометрию.
  $('#tResults').innerHTML=rows.map(r=>
    r.svg ? `<div class="tplot">${r.svg}</div>`
     : `<div class="tres ${r.hi?'hi':''} ${r.warn?'warn':''}">
       <span class="tl">${esc(tr(r.l))}</span>
       <span class="tv mono">${esc(tr(String(r.v)))}</span>
     </div>`).join('');
  applyLang();
}
function closeTool(){
  $('#tool').classList.remove('on');
  document.body.style.overflow='';
  curTool=null; hap();
}

$('#tBack').onclick=()=>{ if(curCL) saveCL(); closeTool(); $('#tBack').textContent='Назад к инструментам'; };
/* Тап по пустому месту убирает клавиатуру: на телефоне она иначе висит
   поверх результата, и пересчитанные цифры не видно. */
document.addEventListener('pointerdown', ev=>{
  const a=document.activeElement;
  if(!a) return;
  const tag=a.tagName;
  if(tag!=='INPUT'&&tag!=='TEXTAREA'&&tag!=='SELECT') return;
  if(ev.target===a||(ev.target.closest&&ev.target.closest('input,textarea,select,.sugg'))) return;
  a.blur();
}, true);

$('#tBackTop').innerHTML=ico('back');
$('#tBackTop').onclick=()=>{ if(typeof curCL!=='undefined'&&curCL) saveCL(); closeTool(); };
{ const gb=$('#geoBtn');
  if(gb) gb.onclick=async()=>{
    hap('medium');
    const p=await requestPosition();
    if(p){
      // свежая позиция сразу видна на экране станции и в текущем расчёте
      if(typeof drawDSC==='function'&&DSC) drawDSC();
      if(typeof curTool!=='undefined'&&curTool){
        const pairs=coordPairsOf(curTool);
        if(pairs.length) fillPositionInto(pairs);
      }
    }
    renderGeoBtn();
  };
}
$('#langBtn').onclick=()=>{
  LANG=(LANG==='en')?'ru':'en';
  tr._keys=null;
  localStorage.setItem('navarea_lang',LANG);
  hap('medium');
  // Перерисовываем текущий раздел и шапку, а не только подменяем текст:
  // строки, собранные в коде из кусков (дата, приветствие), иначе
  // остались бы на прежнем языке.
  try{ renderClock(); switchView(S.view); }catch(e){}
  applyLang();
};
$('#toolsHint').innerHTML=ico('alert','xs')+' Все расчёты выполняются прямо в приложении и работают без связи.';
renderTools();
loadBridge();
renderRefs();
loadHistory();

/* Статичные иконки в разметке. Через проверку: разметка со временем
   меняется, а одна пропавшая строка обрывала весь остаток скрипта --
   и внешне это выглядело как «половина приложения не работает». */
function setIco(sel,name,size,mode){
  const el=$(sel); if(!el) return;
  if(mode==='prepend') el.insertAdjacentHTML('afterbegin', ico(name,size));
  else el.innerHTML=ico(name,size);
}
setIco('#fbtn','sliders');
setIco('#offIco','radar','sm');
setIco('#pfromBox','anchor','sm','prepend');
setIco('#ptoBox','flag','sm','prepend');
document.querySelectorAll('.tab[data-i]').forEach(t=>{
  const ic=t.querySelector('.ic'); if(ic) ic.innerHTML=ico(t.dataset.i);
});

/* ---- Главный экран: часы и кнопки ---- */
renderClock();
setInterval(()=>{ if(S.view==='dash') renderClock(); }, 20000);
{ const o=$('#askOpen'), g=$('#askGo'), a=$('#askAll');
  const open=()=>{ hap('medium'); switchGroup('ask'); setTimeout(()=>{ const i=$('#askInput'); if(i) i.focus(); },120); };
  if(o) o.onclick=open;
  if(g) g.onclick=open;
  if(a) a.onclick=()=>{ hap(); switchGroup('ask'); };
  const n=$('#notifBtn');
  if(n) n.onclick=()=>{ hap('medium'); switchView('notif'); };
  const nc=$('#notifClear'); if(nc) nc.onclick=()=>{ hap(); markNotifSeen(); };
  const ar=$('#admReload');
  if(ar) ar.onclick=()=>{ hap(); ADM=null; renderAdmin(); loadAdmin(); };
}

/* Поиск по справке */
{ const fq=$('#faqQ');
  if(fq){ let t=null; fq.oninput=()=>{ clearTimeout(t); t=setTimeout(()=>{ FAQ_Q=fq.value; renderFaq(); },200); }; }
}
/* Добавление порта: тот же поиск портов, что в проверке маршрута */
{ const inp=$('#pnew');
  if(inp){
    setupPort('#pnew','#snew', name=>portAction('action=add&name='+encodeURIComponent(name)));
    inp.onkeydown=e=>{
      if(e.key!=='Enter') return;
      e.preventDefault();
      const v=inp.value.trim(); if(!v) return;
      inp.value=''; hap('medium');
      portAction('action=add&name='+encodeURIComponent(v));
    };
  }
}
/* Уведомления подтягиваем при запуске, чтобы колокольчик был честным */
loadNotifications(true);
setInterval(()=>{ if(S.view!=='notif') loadNotifications(true); }, 180000);

/* ---- Клавиатура ----
   В WebView под Android видимая область сжимается, и всё, что закреплено
   снизу, всплывает над клавиатурой. Нижнее меню при этом наезжает на поле
   ввода. Поэтому на время набора текста уводим его вниз.
   Признака «клавиатура открыта» в браузере нет, поэтому смотрим сразу на
   два: фокус в поле ввода и заметно сжавшуюся видимую область. */
(function(){
  const isField=el=>el&&(el.tagName==='INPUT'||el.tagName==='TEXTAREA'||el.isContentEditable);
  let focused=false, shrunk=false;
  const apply=()=>document.body.classList.toggle('kbd', focused&&shrunk);

  document.addEventListener('focusin', e=>{ if(isField(e.target)){ focused=true; apply(); } });
  document.addEventListener('focusout', ()=>{
    // короткая пауза: при переходе между двумя полями фокус на миг пропадает
    setTimeout(()=>{ if(!isField(document.activeElement)){ focused=false; apply(); } }, 120);
  });

  const vv=window.visualViewport;
  if(vv){
    let base=vv.height;
    const onResize=()=>{
      base=Math.max(base, vv.height);
      shrunk=(base-vv.height)>140;
      apply();
    };
    vv.addEventListener('resize', onResize);
    onResize();
  } else {
    // старые WebView без visualViewport: полагаемся только на фокус
    shrunk=true;
  }
})();
document.querySelectorAll('#corr .cat').forEach((c,i)=>
  c.insertAdjacentHTML('afterbegin', ico(['gauge','gauge','wave','compass'][i]||'gauge')));

/* открыть сразу нужную вкладку, если пришли по ссылке вида /app#tools */
const wantTab=(location.hash||'').replace('#','');
if(['dash','areas','map','tools','radio','voy'].includes(wantTab)) switchView(wantTab);

renderGeoBtn();   // иначе кнопка позиции пустая до первого нажатия
loadAccess();
if(loadCache())render();
setTimeout(applyLang,60);
load(false);
setInterval(()=>{if(S.view==='dash'||S.view==='areas')load(false)},120000);

/* Самопроверка: через пару секунд после загрузки смотрим, доехал ли скрипт
   до конца. Если какая-то часть не определилась -- значит выполнение
   оборвалось, и мы показываем, где именно, вместо молчаливой поломки. */
setTimeout(function(){
  try{
    var need=['switchGroup','switchView','render','renderTools','renderRadio','renderSubtabs','openTool'];
    var missing=[];
    for(var i=0;i<need.length;i++){
      var ok=false;
      try{ ok=(eval('typeof '+need[i])==='function'); }catch(e){}
      if(!ok) missing.push(need[i]);
    }
    if(missing.length){
      var el=document.getElementById('errbar');
      if(el){
        el.innerHTML='<span class="x" onclick="this.parentNode.classList.remove(\'on\')">×</span>'+
          '<b>Часть приложения не загрузилась</b>Не определено: '+missing.join(', ')+
          '. Панель работает в упрощённом режиме. Пришли этот текст разработчику.';
        el.classList.add('on');
      }
    }
  }catch(e){}
}, 2500);
</script>
</body>
</html>
"""
