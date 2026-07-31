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
<title>NAVAREA Monitor</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
:root{
  --bg:#0a1520; --bg2:#0d1c29;
  --surf:rgba(21,33,47,.82); --surf2:rgba(28,42,58,.7);
  --text:#f4f8fc; --muted:#7f96ac; --dim:#5b7086;
  --amber:#f0a03c; --amber2:#ff8b3d; --amber-soft:rgba(240,160,60,.13);
  --ok:#3fc97f; --hot:#ff6b4a; --sea:#4d93d6;
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
.wrap{padding:16px 15px 0;max-width:940px;margin:0 auto;position:relative;z-index:1}
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
.avatar b{
  position:absolute;top:-3px;right:-3px;width:11px;height:11px;border-radius:50%;
  background:var(--ok);border:2.5px solid var(--bg);animation:beat 2.4s infinite;
}
.avatar b.off{background:var(--hot);animation:none}
@keyframes beat{0%,100%{box-shadow:0 0 0 0 rgba(63,201,127,.55)}70%{box-shadow:0 0 0 8px rgba(63,201,127,0)}}

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
.cats{display:flex;gap:9px;overflow-x:auto;padding:2px 0 12px;scrollbar-width:none;scroll-snap-type:x proximity}
.cats::-webkit-scrollbar{display:none}
.cat{
  flex:none;width:74px;padding:11px 6px 9px;border-radius:var(--r-md);cursor:pointer;
  background:var(--surf);border:1px solid var(--line);text-align:center;scroll-snap-align:start;
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

/* ---- Нижняя навигация ---- */
.tabs{
  position:fixed;bottom:0;left:0;right:0;z-index:1000;display:flex;
  background:rgba(11,22,34,.93);border-top:1px solid var(--line);
  backdrop-filter:blur(22px);padding:7px 6px calc(7px + env(safe-area-inset-bottom));
}
body.light .tabs{background:rgba(255,255,255,.94)}
.tab{
  flex:1;border:none;background:none;cursor:pointer;color:var(--dim);
  font-size:10px;font-weight:650;font-family:inherit;padding:7px 2px 5px;
  border-radius:var(--r-sm);position:relative;transition:color .24s;
}
.tab .ic{display:block;font-size:20px;margin-bottom:3px;
  transition:transform .32s cubic-bezier(.34,1.7,.5,1)}
.tab.on{color:var(--amber)}
.tab.on .ic{transform:translateY(-3px) scale(1.16)}
.tab.on::after{
  content:'';position:absolute;bottom:1px;left:38%;right:38%;height:3px;border-radius:3px;
  background:linear-gradient(90deg,var(--amber),var(--amber2));
}

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

  <div class="hdr">
    <div style="min-width:0">
      <div class="hello">Спокойной вахты</div>
      <div class="h1">Обстановка <span id="hName">в море</span></div>
    </div>
    <div class="avatar" id="themeBtn"><b id="liveDot"></b></div>
  </div>

  <div class="srow">
    <div class="sbox">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input id="q" placeholder="Номер, координаты, текст…">
    </div>
    <button class="fbtn" id="fbtn"></button>
  </div>

  <div class="cats" id="cats"></div>

  <div class="offline" id="offline"><span id="offIco"></span>Нет связи. Показаны последние сохранённые данные.</div>

  <!-- ПАНЕЛЬ -->
  <section id="v-dash">
    <div class="hero" id="heroBox">
      <svg class="heroSvg" viewBox="0 0 400 186" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0e2f4d"/><stop offset="100%" stop-color="#15486f"/>
          </linearGradient>
          <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#186091"/><stop offset="100%" stop-color="#0a2540"/>
          </linearGradient>
          <radialGradient id="beam" cx="0" cy="0.5" r="1">
            <stop offset="0%" stop-color="#f0a03c" stop-opacity=".62"/>
            <stop offset="100%" stop-color="#f0a03c" stop-opacity="0"/>
          </radialGradient>
          <radialGradient id="moon" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%" stop-color="#fff4dc" stop-opacity=".9"/>
            <stop offset="100%" stop-color="#fff4dc" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <rect width="400" height="186" fill="url(#sky)"/>
        <circle cx="322" cy="40" r="30" fill="url(#moon)"/>
        <circle cx="322" cy="40" r="13" fill="#f6ead1" opacity=".5"/>
        <g class="gulls" opacity=".45">
          <path d="M64 44 q5 -5 10 0 q5 -5 10 0" stroke="#dbe9f6" stroke-width="1.6" fill="none"/>
          <path d="M100 33 q3.5 -3.5 7 0 q3.5 -3.5 7 0" stroke="#dbe9f6" stroke-width="1.3" fill="none"/>
          <path d="M138 50 q3 -3 6 0 q3 -3 6 0" stroke="#dbe9f6" stroke-width="1.1" fill="none"/>
        </g>
        <g class="lh">
          <polygon points="352,132 361,132 359,86 354,86" fill="#0f2b45"/>
          <rect x="352.5" y="78" width="8" height="8" rx="2" fill="#f0a03c" class="lamp"/>
          <polygon points="356,82 400,54 400,110" fill="url(#beam)" class="beamRay"/>
          <rect x="348" y="130" width="17" height="6" rx="2" fill="#0b2138"/>
        </g>
        <g class="ship">
          <path d="M0 124 h96 l-9 17 h-78 z" fill="#0c2540"/>
          <path d="M4 124 h88 l-2 4 h-84 z" fill="#123a5c"/>
          <rect x="10" y="108" width="11" height="16" fill="#f0a03c" opacity=".9"/>
          <rect x="24" y="113" width="10" height="11" fill="#4d93d6"/>
          <rect x="37" y="110" width="10" height="14" fill="#f0a03c" opacity=".72"/>
          <rect x="50" y="114" width="10" height="10" fill="#4d93d6"/>
          <rect x="66" y="99" width="20" height="25" rx="2.5" fill="#1d4668"/>
          <rect x="70" y="104" width="4" height="4" fill="#d6e9fb" opacity=".95"/>
          <rect x="77" y="104" width="4" height="4" fill="#d6e9fb" opacity=".95"/>
          <rect x="70" y="112" width="4" height="4" fill="#d6e9fb" opacity=".7"/>
          <rect x="82" y="84" width="2.5" height="15" fill="#8fa8c0"/>
          <circle cx="83" cy="83" r="2.5" fill="#f0a03c" class="lamp"/>
        </g>
        <path class="w1" d="M-400 140 q50 -9 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v60 h-800 z" fill="url(#sea)" opacity=".92"/>
        <path class="w2" d="M-400 152 q50 -8 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v50 h-800 z" fill="#0d3557" opacity=".9"/>
        <path class="w3" d="M-400 165 q50 -7 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v40 h-800 z" fill="#0a1f36"/>
      </svg>
      <div class="heroGrad"></div>
      <div class="heroIn">
        <span class="hchip" id="hchip">В эфире</span>
        <div class="hnum mono" id="heroNum">—</div>
        <div class="hsub">действующих предупреждений по твоим районам</div>
      </div>
      <button class="hbtn" id="heroBtn">Открыть карту →</button>
    </div>

    <div class="hull" id="hullBox">
      <div class="hullTop">
        <div class="hgrid" id="hgrid"></div>
      </div>
      <div class="hullBody"></div>
      <div class="hullPort"><i></i><i></i><i></i></div>
      <div class="hullWave">
        <svg viewBox="0 0 800 20" preserveAspectRatio="none">
          <path d="M0 10 q50 -8 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v14 h-800 z" fill="rgba(77,147,214,.3)"/>
        </svg>
      </div>
    </div>

    <div class="sech"><h3>Избранные районы</h3><a id="toAreas">Все →</a></div>
    <div id="favlist"></div>
  </section>

  <!-- РАЙОНЫ -->
  <section id="v-areas" class="hidden">
    <div class="sech"><h3 id="areasTitle">Все районы</h3><a id="sortBtn">По количеству ⇅</a></div>
    <div id="arealist"><div class="sk card"></div><div class="sk card"></div><div class="sk card"></div></div>
  </section>

  <!-- КАРТА -->
  <section id="v-map" class="hidden">
    <div class="mapwrap">
      <div id="map"></div>
      <div class="mapctl">
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
    <div class="sech"><h3>Справочные зоны</h3></div>
    <div id="zonelist"></div>
  </section>

  <!-- РЕЙС -->
  <section id="v-voy" class="hidden">
    <div class="sech"><h3>Планирование перехода</h3></div>
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
        <div class="cat" data-c="50">${ico('gauge')}<span class="cn">50 миль</span></div>
        <div class="cat on" data-c="150">${ico('gauge')}<span class="cn">150 миль</span></div>
        <div class="cat" data-c="300">${ico('wave')}<span class="cn">300 миль</span></div>
        <div class="cat" data-c="500">${ico('compass')}<span class="cn">500 миль</span></div>
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

<nav class="tabs">
  <button class="tab on" data-v="dash" data-i="gauge">Панель</button>
  <button class="tab" data-v="areas" data-i="globe">Районы</button>
  <button class="tab" data-v="map" data-i="map">Карта</button>
  <button class="tab" data-v="voy" data-i="ship">Рейс</button>
</nav>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
/* ---- Векторные иконки (вместо эмодзи) ---- */
const ICONS={
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
const hap=t=>{try{TG&&TG.HapticFeedback.impactOccurred(t||'light')}catch(e){}};

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
async function api(p){
  const sep=p.includes('?')?'&':'?';
  const r=await fetch(p+sep+'initData='+encodeURIComponent(INIT));
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
  const dur=680,t0=performance.now();
  (function s(t){
    const k=Math.min(1,(t-t0)/dur),e=1-Math.pow(1-k,3);
    el.textContent=Math.round(to*e);
    if(k<1) requestAnimationFrame(s);
  })(t0);
}

async function load(spin){
  try{
    const [st,wr]=await Promise.all([api('/api/stats'),api('/api/warnings?limit=3000')]);
    S.stats=st;S.warnings=wr.results||[];S.offline=false;
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
  $('#liveDot').className=S.offline?'off':'';
  render();
}

function render(){renderCats();renderDash();renderAreas();renderZones()}

/* --- плитки районов --- */
function renderCats(){
  if(!S.stats) return;
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

/* --- панель --- */
function renderDash(){
  if(!S.stats) return;
  const t=S.stats.totals;
  const num=$('#heroNum'); if(num) countUp(num,t.in_force);
  $('#hName').textContent=S.offline?'из кэша':'в море';

  const cells=[
    {v:t.in_force,k:'Действует',c:'a'},
    {v:t.added_today,k:'Сегодня',c:t.added_today?'h':''},
    {v:t.added_week,k:'За 7 дней',c:''},
    {v:t.archived,k:'В архиве',c:''}];
  $('#hgrid').innerHTML=cells.map((c,i)=>
    `<div class="hcell ${c.c} up" style="animation-delay:${i*70}ms">
       <div class="v mono" data-n="${c.v}">0</div><div class="k">${c.k}</div></div>`).join('');
  document.querySelectorAll('.hcell .v').forEach(el=>countUp(el,+el.dataset.n));

  const fav=(S.stats.areas||[]).filter(a=>S.favs.includes(a.code));
  $('#favlist').innerHTML=fav.length?`<div class="grid2">${fav.map(areaCard).join('')}</div>`
    :`<div class="empty">${ico('star')}Отметь районы звёздочкой — они появятся здесь для быстрого доступа.</div>`;
  bindAreas();
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
  if(!S.stats) return;
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
  $('#arealist').innerHTML=`<div class="grid2">${list.map(areaCard).join('')}</div>`;
  bindAreas();
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
function initMap(){
  if(map)return;
  map=L.map('map',{worldCopyJump:true,zoomControl:true}).setView([25,-30],3);
  setBase('dark');
  map.on('mousemove',e=>{$('#curpos').textContent=fmtPos(e.latlng.lat,e.latlng.lng)});
  map.on('click',e=>{$('#curpos').textContent=fmtPos(e.latlng.lat,e.latlng.lng)});
  document.querySelectorAll('input[name=base]').forEach(r=>r.onchange=()=>{setBase(r.value);hap()});
  const bind=(id,k)=>{const el=$(id);if(el)el.onchange=()=>{LY[k]=el.checked;drawMap();hap()}};
  bind('#lyAreas','areas');bind('#lyPoints','points');bind('#lyLabels','labels');
  drawZones();drawMap();
}
function shapeLayer(pts,type,popup,color,radiusNm){
  let l;
  if(type==='polygon'&&pts.length>=3) l=L.polygon(pts,{color:color,weight:2,fillOpacity:.16,fillColor:color});
  else if(type==='line'&&pts.length>=2) l=L.polyline(pts,{color:color,weight:3});
  else if(type==='circle'&&radiusNm) l=L.circle(pts[0],{radius:radiusNm*1852,color:color,weight:2,fillOpacity:.14});
  else l=L.circleMarker(pts[0],{radius:6,color:color,fillColor:color,fillOpacity:.85,weight:2});
  return l.bindPopup(popup);
}
function drawMap(){
  if(!map)return;
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
  const all=[];w.shapes.forEach(s=>s.points.forEach(p=>all.push(p)));
  if(all.length===1)map.setView(all[0],8);
  else map.fitBounds(L.latLngBounds(all),{padding:[45,45]});
}

/* --- рейс --- */
function setupPort(i,s){
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
          inp.value=d.dataset.p;sug.classList.remove('on');hap();
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
    $('#voyout').innerHTML=`
      <div class="voyhead up">
        <div class="big">На маршруте найдено ${r.count} активных ${w}</div>
        <div class="sm">${esc(r.from.label)} → ${esc(r.to.label)} · <span class="mono">${r.distance_nm}</span> миль · коридор ±<span class="mono">${r.corridor_nm}</span></div>
      </div>
      <div id="vmap"></div>
      ${r.results.length?r.results.map(warnCard).join('')
        :`<div class="empty">${ico('anchor')}По этому маршруту действующих предупреждений с координатами нет.</div>`}`;
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
  r.results.forEach(w=>(w.shapes||[]).forEach(s=>
    shapeLayer(s.points,s.type,`<b>${esc(w.area_code)} №${esc(w.msg_number||'—')}</b><br>${w.distance_nm} миль от курса`,'#f0a03c',s.radius_nm).addTo(vmap)));
  vmap.fitBounds(line.getBounds(),{padding:[28,28]});
}

/* --- навигация --- */
function switchView(v){
  S.view=v;
  ['dash','areas','map','voy'].forEach(x=>{
    const el=$('#v-'+x);
    if(x===v){el.classList.remove('hidden');el.style.animation='none';void el.offsetWidth;el.style.animation=''}
    else el.classList.add('hidden');
  });
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.v===v));
  try{window.scrollTo({top:0,behavior:'smooth'})}catch(e){}
  if(v==='map')setTimeout(()=>{initMap();map.invalidateSize();drawZones();drawMap()},70);
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{hap();switchView(t.dataset.v)});
$('#toAreas').onclick=()=>{hap();S.cat='all';renderCats();switchView('areas');renderAreas()};
$('#heroBtn').onclick=()=>{hap('medium');switchView('map')};
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
    sh.forEach(s=>shapeLayer(s.points,s.type,'',	'#f0a03c',s.radius_nm).addTo(dmap));
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

/* статичные иконки в разметке */
$('#themeBtn').insertAdjacentHTML('afterbegin', ico('compass','lg'));
$('#fbtn').innerHTML=ico('sliders');
$('#offIco').innerHTML=ico('radar','sm');
$('#hchip').insertAdjacentHTML('afterbegin', ico('radar','xs'));
$('#pfromBox').insertAdjacentHTML('afterbegin', ico('anchor','sm'));
$('#ptoBox').insertAdjacentHTML('afterbegin', ico('flag','sm'));
document.querySelectorAll('.tab[data-i]').forEach(t=>
  t.insertAdjacentHTML('afterbegin', ico(t.dataset.i)));
document.querySelectorAll('#corr .cat').forEach((c,i)=>
  c.insertAdjacentHTML('afterbegin', ico(['gauge','gauge','wave','compass'][i]||'gauge')));

if(loadCache())render();
load(false);
setInterval(()=>{if(S.view==='dash'||S.view==='areas')load(false)},120000);
</script>
</body>
</html>
"""
