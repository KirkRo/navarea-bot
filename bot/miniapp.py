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
<title>Watchkeeper</title>
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
   Проверено рендером в headless-браузере и сверено с фото реальной
   station. Сетка на клавиатуре -- flexbox, не CSS grid: так надёжнее
   на разных WebView внутри Telegram. */
.radio{
  background:linear-gradient(155deg,#48463f,#282621);
  border:1px solid #55534b;border-radius:12px;padding:12px 12px 14px;
  box-shadow:0 20px 46px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.05);
  max-width:400px;margin:0 auto;
}
.rplates{display:flex;justify-content:center;gap:8px;margin:0 0 9px;flex-wrap:wrap}
.rplate{
  background:#e9ecef;color:#15181c;font-size:9px;font-weight:800;letter-spacing:.3px;
  border-radius:3px;padding:5px 9px;text-align:center;line-height:1.25;
  border:1px solid #b8bec4;box-shadow:0 1px 2px rgba(0,0,0,.3);
}
.rhdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding:0 2px;gap:8px}
.rnameplate{
  background:#dfe3e6;color:#1a1d20;font-size:6.6px;font-weight:700;line-height:1.35;
  border-radius:2px;padding:3px 6px;border:1px solid #aab0b6;flex:1;min-width:0;
}
.rfuruno{
  flex:none;font-weight:800;font-size:13px;letter-spacing:1px;font-style:italic;
  background-image:linear-gradient(180deg,#e8ebee,#9ba1a8);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}

.rbody{display:flex;gap:8px}
.rleft{width:70px;flex:none;display:flex;flex-direction:column;align-items:center;gap:6px}
.rspeaker{width:100%;background:#1a1c1e;border-radius:5px;padding:6px 8px}
.rspeaker i{display:block;height:2.6px;background:#000;border-radius:2px;margin:2.6px 0}
.rknob{width:32px;height:32px;border-radius:50%;
  background:radial-gradient(circle at 35% 30%,#54595f,#1c1e20 72%);
  border:1px solid #61656b;position:relative;box-shadow:0 2px 4px rgba(0,0,0,.5)}
.rknob::after{content:'';position:absolute;top:3px;left:50%;width:2px;height:10px;
  background:#8a9096;transform:translateX(-50%);border-radius:1px}
.rklabel{font-size:6.3px;color:#a8aeb4;text-align:center;font-weight:700;letter-spacing:.2px;line-height:1.2}
.rleds{display:flex;flex-direction:column;gap:4px;align-items:center;margin-top:1px}
.rled{display:flex;align-items:center;gap:4px}
.rled i{width:5.5px;height:5.5px;border-radius:50%;background:#3a3d40;flex:none}
.rled i.amber{background:#ffb020;box-shadow:0 0 5px #ffb020}
.rled i.green{background:#3fc97f;box-shadow:0 0 5px #3fc97f}
.rled span{font-size:6px;color:#a8aeb4;font-weight:700}

.rdistwrap{width:100%;text-align:center;margin-top:2px}
.rdistcover{
  width:44px;height:32px;margin:0 auto;position:relative;cursor:pointer;
  background:linear-gradient(160deg,rgba(220,230,240,.1),rgba(220,230,240,.02));
  border:1.5px solid #62666c;border-radius:5px;
}
.rdistbtn{position:absolute;inset:5px;border-radius:3px;
  background:linear-gradient(160deg,#f0503e,#b8281a);border:1px solid #ff7a68;
  box-shadow:0 0 6px rgba(240,80,62,.55), inset 0 1px 1px rgba(255,255,255,.3)}
.rdistbtn.arming{animation:rarmpulse .45s infinite}
@keyframes rarmpulse{50%{background:linear-gradient(160deg,#ff7a68,#e0402c);box-shadow:0 0 14px rgba(255,90,68,.85)}}
.rpwroff{font-size:6px;color:#a8aeb4;font-weight:700;margin-top:4px;letter-spacing:.3px}
.rdistcap{font-size:5.6px;color:#8a9098;text-align:center;line-height:1.35;margin-top:4px;padding:0 1px}

/* --- экран --- */
.rscreen{flex:1;min-width:0}
.lcd{
  background:linear-gradient(175deg,#0f2440,#0a1a30);
  border:2px solid #05070a;border-radius:5px;padding:6px 7px;
  min-height:172px;display:flex;flex-direction:column;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  color:#dce8f4;font-size:8.4px;position:relative;overflow:hidden;
}
.lcd.alert{background:linear-gradient(175deg,#3a1210,#280a08)}
.lcdtop{display:flex;justify-content:space-between;align-items:center;font-size:6.8px;
  color:#8fa8c4;margin-bottom:3px;flex:none}
.lrow1{display:flex;gap:4px;align-items:stretch;margin-bottom:3px;flex:none}
.ldist{
  background:#1a2c48;color:#e8eef5;font-size:6.4px;font-weight:800;text-align:center;
  border-radius:2px;padding:3px 3px;line-height:1.2;flex:none;width:26px;
  display:flex;align-items:center;justify-content:center;border:1px solid #2c4468;
}
.ldist.alert{background:#c0281c;animation:rdblink 1s steps(2) infinite}
@keyframes rdblink{50%{opacity:.4}}
.lch{
  flex:1;min-width:0;background:linear-gradient(180deg,#e9dfc4,#d8cba4);color:#1a1408;
  border-radius:2px;padding:2px 6px;display:flex;align-items:baseline;gap:4px;
}
.lch .l{font-size:6.6px;font-weight:800}
.lch .n{font-size:16px;font-weight:800;letter-spacing:.3px}
.lnb{flex:none;width:15px;display:flex;align-items:center;justify-content:center;
  font-size:5.6px;font-weight:800;color:#9db6d4;border:1px solid #2c4468;border-radius:50%;}
.lmenu{flex:none;width:44px;display:flex;flex-direction:column;justify-content:space-around;gap:1px}
.lmenu .mi{display:flex;align-items:center;gap:2px;font-size:5.3px;color:#c2d4e8;line-height:1.05}
.lmenu .mi b{color:#fff;font-weight:800}
.lfreq{font-size:7.6px;display:flex;gap:5px;margin:2px 0;flex:none}
.lfreq .lb{color:#8fa8c4;width:15px}
.lfreq .v{color:#fff;font-weight:700}
.lfreq .u{color:#8fa8c4}
.lmode{font-size:6.1px;color:#9db6d4;display:flex;gap:6px;margin:3px 0 2px;font-weight:700;flex:none}
.lmeter{font-size:5.7px;color:#8fa8c4;display:flex;align-items:center;gap:3px;margin-bottom:2px;flex:none}
.lbars{display:flex;gap:1px}
.lbars i{width:2.4px;height:5.5px;background:#274568;border-radius:.5px;display:block}
.lbars i.on{background:#5ba6e8}
.lag{display:flex;justify-content:space-between;align-items:center;font-size:5.7px;color:#9db6d4;margin-bottom:3px;flex:none}
.lag .attb{border:1px solid #2c4468;border-radius:8px;padding:1px 6px;font-weight:800}
.lgps{background:#152540;border:1px solid #24406a;border-radius:2px;padding:3px 5px;
  display:flex;justify-content:space-between;font-size:5.9px;color:#cfe0f2;margin-bottom:3px;flex:none}
.lgps b{color:#fff;font-weight:800;display:block;font-size:5.7px;text-align:right;opacity:.85}
.lmem{display:flex;gap:2px;flex:none;margin-top:auto}
.lmem i{flex:1;height:7px;border:1px solid #24406a;border-radius:1px;display:block}

/* --- меню/список поверх того же экрана (навигация по MENU) --- */
.lmenuscreen{flex:1;overflow-y:auto;font-size:9.5px;line-height:1.7}
.lmenuscreen::-webkit-scrollbar{width:0}
.lmenuscreen .it{padding-left:2px}
.lmenuscreen .it.sel{background:rgba(93,166,232,.18);border-left:2px solid #5ba6e8;padding-left:6px;margin-left:-8px;color:#fff}
.llog{flex:1;overflow-y:auto;font-size:9px;line-height:1.6;white-space:pre-wrap;color:#dce8f4}
.llog::-webkit-scrollbar{width:0}
.blink{animation:lcdblink 1.1s steps(2) infinite}
@keyframes lcdblink{50%{opacity:.25}}

/* --- правая колонка: клавиатура --- */
.rright{width:126px;flex:none;display:flex;flex-direction:column;gap:5px}
.rkgrid{display:flex;flex-wrap:wrap;gap:4px}
.rkgrid .rkey{width:calc((100% - 8px)/3)}
.rfngrid{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}
.rfngrid .rkey{width:calc((100% - 4px)/2)}
.rkey{
  background:linear-gradient(180deg,#3d4249,#26292d);border:1px solid #4a4f55;border-radius:5px;
  padding:5px 2px;text-align:center;box-shadow:0 1.5px 0 #17181a, inset 0 1px 0 rgba(255,255,255,.08);
  cursor:pointer;transition:transform .08s;box-sizing:border-box;
}
.rkey:active{transform:translateY(1.5px);box-shadow:0 0 0 #17181a, inset 0 1px 0 rgba(255,255,255,.05)}
.rkey .kt{font-size:7.2px;font-weight:800;color:#e6eaee;line-height:1}
.rkey .ks{font-size:4.8px;font-weight:700;color:#8a9098;margin-top:1px}
.rkey.ok{background:linear-gradient(180deg,#2f6b46,#1f4a30);border-color:#3d7d54}
.rkey.ok .kt{color:#d8ffe6}
.rkey.warn{background:linear-gradient(180deg,#7a5a20,#5a4116);border-color:#8d6a28}
.rkey.warn .kt{color:#ffe9c2}
.rbigknob{
  width:48px;height:48px;border-radius:50%;margin:4px auto 0;cursor:pointer;
  background:radial-gradient(circle at 32% 28%,#565b62,#1c1e20 70%);
  border:1px solid #63686e;box-shadow:0 3px 6px rgba(0,0,0,.5);position:relative;
}
.rbigknob::after{content:'';position:absolute;top:5px;left:50%;width:3px;height:14px;
  background:#a2a8ae;transform:translateX(-50%);border-radius:1.5px}
.rbigknob .cap{position:absolute;bottom:-9px;left:50%;transform:translateX(-50%);
  font-size:5.1px;color:#a8aeb4;font-weight:700;white-space:nowrap}

.rcompose{display:flex;gap:7px;align-items:flex-end;margin-top:16px}
.rcbtn{
  flex:1;background:linear-gradient(180deg,#3d4249,#26292d);border:1px solid #4a4f55;border-radius:5px;
  padding:7px 3px;font-size:6.2px;font-weight:800;color:#dfe4e8;text-align:center;line-height:1.15;
  cursor:pointer;
}
.rbracket{border-top:1px solid #4a4f55;margin-top:3px;padding-top:2px;font-size:4.8px;
  color:#8a9098;text-align:center;font-weight:700;letter-spacing:.2px}

.rfooter{
  background:#e9ecef;color:#15181c;font-size:8px;font-weight:800;letter-spacing:.3px;
  border-radius:3px;padding:6px 12px;text-align:center;margin:10px auto 0;max-width:180px;
  border:1px solid #b8bec4;box-shadow:0 1px 2px rgba(0,0,0,.3);
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

  <div class="hdr">
    <div style="min-width:0">
      <div class="hello" id="hello">Спокойной вахты</div>
      <div class="hello" id="buildId" style="font-size:9.5px;opacity:.55;margin-top:1px"></div>
      <div class="h1">Watch<span>keeper</span></div>
    </div>
    <button class="geobtn" id="geoBtn" title="Позиция с устройства"></button>
      <button class="langbtn" id="langBtn">RU</button>
      <div class="avatar" id="themeBtn"><b id="liveDot"></b></div>
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
            <stop offset="0%" stop-color="#ffd08a" stop-opacity=".72"/>
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
          <!-- скалы у основания -->
          <path d="M336 136 l7-11 5 6 6-9 7 10 6-7 8 11z" fill="#0a1e33"/>
          <path d="M341 136 l5-7 4 4 5-6 5 7 4-4 5 6z" fill="#102b46"/>
          <!-- фундамент -->
          <path d="M345 128 h22 l-2 8 h-18z" fill="#16344f"/>
          <!-- башня: конус с сужением кверху -->
          <path d="M350.5 126 L353 84 h6 l2.5 42 z" fill="#e6ecf2"/>
          <path d="M356 126 L356 84 h3 l2.5 42 z" fill="#c2ced9"/>
          <!-- красные полосы -->
          <path d="M351.6 117 h13.2 l.5 8 h-14.2z" fill="#c9463a"/>
          <path d="M352.9 101 h10.5 l.4 8 h-11.3z" fill="#c9463a"/>
          <path d="M354.2 86 h7.8 l.4 7 h-8.6z" fill="#c9463a"/>
          <!-- галерея -->
          <path d="M350 84 h13 v3 h-13z" fill="#22415e"/>
          <path d="M351 79 h11 v5 h-11z" fill="#16344f" opacity=".9"/>
          <!-- фонарный отсек: стекло + свет -->
          <rect x="352.5" y="70" width="8" height="10" rx="1.5" fill="#3d5f80"/>
          <rect x="353.5" y="71" width="6" height="8" rx="1" fill="#ffd894" class="lamp"/>
          <circle cx="356.5" cy="75" r="5.5" fill="#ffca7a" opacity=".3" class="lamp"/>
          <!-- купол -->
          <path d="M351.5 70 l5-5 5 5z" fill="#22415e"/>
          <rect x="355.8" y="62" width="1.4" height="4" fill="#22415e"/>
          <!-- луч -->
          <polygon points="357,75 400,42 400,108" fill="url(#beam)" class="beamRay"/>
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

    <div id="histBox"></div>
    <div class="sech" style="margin-top:17px"><h3>Избранные районы</h3><a id="toAreas">Все →</a></div>
    <div id="favlist"></div>

    <div class="sech" style="margin-top:18px"><h3>Быстрые действия</h3></div>
    <div class="quick" id="quick"></div>

    <div id="lastVoyBox"></div>
    <div id="lastCalcBox"></div>
  </section>

  <!-- РАЙОНЫ -->
  <section id="v-areas" class="hidden">
    <div class="sech"><h3 id="areasTitle">Все районы</h3><a id="sortBtn">По количеству ⇅</a></div>
    <div id="arealist"><div class="sk card"></div><div class="sk card"></div><div class="sk card"></div></div>
  </section>

  <!-- КАРТА -->
  <section id="v-map" class="hidden">
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
    <div class="sech"><h3>Справочные зоны</h3></div>
    <div id="zonelist"></div>
  </section>

  <!-- ИНСТРУМЕНТЫ -->
  <section id="v-tools" class="hidden">
    <div class="hint" id="toolsHint"></div>
    <div id="toollist"></div>
  </section>

  <!-- ЧЕК-ЛИСТЫ И СЕРТИФИКАТЫ -->
  <section id="v-bridge" class="hidden">
    <div id="bridgeBox"></div>
  </section>

  <!-- СПРАВОЧНИКИ -->
  <section id="v-refs" class="hidden">
    <div id="refBox"></div>
  </section>

  <!-- РАДИО -->
  <section id="v-radio" class="hidden">
    <div class="sech"><h3>Тест MF/HF DSC</h3></div>
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
    <div id="vesselBox"><div class="sk card"></div><div class="sk card"></div></div>
  </section>

  <!-- НАСТРОЙКИ -->
  <section id="v-settings" class="hidden">
    <div id="settingsBox"></div>
  </section>

  <!-- ТРЕНАЖЁР ЦИВ -->
  <section id="v-dsc" class="hidden">
    <div class="sech"><h3>Тренажёр ЦИВ</h3></div>
    <div id="dscBox"><div class="sk card"></div></div>
  </section>

  <!-- EPIRB TEST -->
  <section id="v-epirb" class="hidden">
    <div class="sech"><h3>EPIRB Test</h3></div>
    <div id="epirbBox"><div class="sk card"></div></div>
  </section>

  <!-- SART TEST -->
  <section id="v-sart" class="hidden">
    <div class="sech"><h3>SART Test</h3></div>
    <div id="sartBox"><div class="sk card"></div></div>
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

<nav class="tabs">
  <button class="tab on" data-g="home" data-i="gauge">Главная</button>
  <button class="tab" data-g="tools" data-i="sliders">Инструменты</button>
  <button class="tab" data-g="map" data-i="map">Карта</button>
  <button class="tab" data-g="profile" data-i="compass">Профиль</button>
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
  desc:'Расхождение с целью по данным радара',
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
    {l:'CPA',v:F(r.cpa,2)+' миль',hi:1,warn:r.cpa<1&&!r.opening},
    {l:'TCPA',v:r.opening?'цель расходится':hm(r.tcpa)},
    {l:'Курс относительного движения',v:F(r.relCourse,1)+'°'},
    {l:'Скорость сближения',v:F(r.relSpeed,1)+' узлов'}];
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
 'Панель':'Dashboard','Районы':'Areas','Карта':'Chart','Мостик':'Bridge','Расчёты':'Tools',
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
 'Данные справочные. Официальный источник — оборудование GMDSS и NAVTEX, ECDIS и судовые пособия. Решение принимает судоводитель.':
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
 'Сертификатов пока нет. Добавь — и бот сам напомнит за 60, 30, 14, 7, 3 и 1 день до истечения.':
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
 'миль':'NM','миля':'NM','узлов':'kn','узла':'kn','м':'m','км':'km','фут':'ft',
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
 'Крышка кнопки бедствия — открыть':'Distress button cover — open',
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
  $('#liveDot').className=S.offline?'off':'';
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
function renderDash(){
  if(!S.stats||!S.stats.totals) return;
  const t=S.stats.totals;
  const num=$('#heroNum'); if(num) countUp(num,t.in_force);
  const hl=$('#hello'); if(hl) hl.textContent=S.offline?'Данные из кэша':'Инструменты вахтенного помощника';

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
  $('#favlist').innerHTML=fav.length?collapsible('fav',fav,areaCard)
    :`<div class="empty">${ico('star')}Отметь районы звёздочкой — они появятся здесь для быстрого доступа.</div>`;
  bindAreas();
  renderQuick(); renderLastVoyage(); renderLastCalcs();
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
function initMap(){
  if(map)return;
  map=L.map('map',{worldCopyJump:true,zoomControl:true}).setView([25,-30],3);
  setBase('dark');
  map.on('mousemove',e=>{$('#curpos').textContent=fmtPos(e.latlng.lat,e.latlng.lng)});
  map.on('click',e=>{$('#curpos').textContent=fmtPos(e.latlng.lat,e.latlng.lng)});
  document.querySelectorAll('input[name=base]').forEach(r=>r.onchange=()=>{setBase(r.value);hap()});
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
    try{ localStorage.setItem('navarea_lastvoy',JSON.stringify({
      from:r.from.label,to:r.to.label,distance:r.distance_nm,count:r.count,legs:legs})); }catch(e){}
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
/* ---- Четыре группы внизу, подразделы лентой сверху ---- */
const GROUPS={
  home:{t:'Главная',i:'gauge',subs:[
    {v:'dash',t:'Обзор',i:'gauge'},
    {v:'areas',t:'Районы',i:'globe'}]},
  tools:{t:'Инструменты',i:'sliders',subs:[
    {v:'tools',t:'Инструменты',i:'sliders'},
    {v:'bridge',t:'Чек-листы',i:'flag'},
    {v:'refs',t:'Справка',i:'archive'}]},
  map:{t:'Карта',i:'map',subs:[
    {v:'map',t:'Обстановка',i:'map'},
    {v:'voy',t:'Маршрут',i:'route'},
    {v:'zones',t:'Зоны',i:'wave'}]},
  profile:{t:'Профиль',i:'compass',subs:[
    {v:'ship',t:'Моё судно',i:'ship'},
    {v:'settings',t:'Настройки',i:'sliders'}]}
};
const ALL_VIEWS=['dash','areas','map','tools','bridge','refs','radio','dsc','epirb','sart','ship','settings','voy','zones'];
const VIEW_GROUP={};
Object.keys(GROUPS).forEach(g=>GROUPS[g].subs.forEach(x=>VIEW_GROUP[x.v]=g));
// GMDSS-разделы открываются карточками с главного экрана "Инструменты", а не
// отдельными вкладками сверху -- так их не пять в ряд, а по категориям, как
// просили: сначала общий раздел, оборудование ГМССБ внутри него отдельным блоком.
['radio','dsc','epirb','sart'].forEach(v=>VIEW_GROUP[v]='tools');
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

  const topCats=$('#cats'); if(topCats) topCats.classList.toggle('hidden', v!=='dash');
  const topSearch=$('#topSearch'); if(topSearch) topSearch.classList.toggle('hidden', v!=='dash'&&v!=='areas');
  try{window.scrollTo({top:0,behavior:'smooth'})}catch(e){}

  if(v==='tools') renderTools();
  if(v==='refs') renderRefs();
  if(v==='bridge'){ if(gate('#bridgeBox','bridge')) loadBridge(); }
  if(v==='ship'){ if(gate('#v-ship','vessel')) loadVessel(); }
  if(v==='settings') renderSettings();
  if(v==='dsc'){ renderDSC(); loadDSC().then(renderDSC); }
  if(v==='epirb'){ if(gate('#epirbBox','bridge')) loadGmdss().then(()=>renderGmdss('epirb')); }
  if(v==='sart'){ if(gate('#sartBox','bridge')) loadGmdss().then(()=>renderGmdss('sart')); }
  if(v==='radio') setTimeout(()=>{renderRadio();initRmap();if(rmap)rmap.invalidateSize()},70);
  if(v==='dash') loadHistory();
  if(v==='voy') gate('#v-voy','voyage');
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
    : `<div class="empty">${ico('clock')}Сертификатов пока нет. Добавь — и бот сам напомнит за 60, 30, 14, 7, 3 и 1 день до истечения.</div>`;

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
      <input class="tinput" id="cExp" type="date"></div>
    <div class="fld"><label>Заметка (необязательно)</label>
      <input class="tinput" id="cNote" placeholder="Где выдан, что нужно для продления"></div>`;
  $('#tResults').innerHTML=
    `<button class="btn wide" id="cSave">Сохранить сертификат</button>`;
  $('#cSave').onclick=async()=>{
    const n=$('#cName').value.trim(), e=$('#cExp').value;
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
    el.className='trialbar free';
    el.innerHTML=`<div class="ti">${ico('lighthouse')}</div>
      <div class="tt"><div class="t1">Бесплатный тариф</div>
        <div class="t2">Два района, базовые расчёты и справочники. Остальное — ${ACC.price_stars} ⭐ в месяц.</div></div>
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
    <div class="ls">Раздел входит в Premium — ${ACC?ACC.price_stars:100} ⭐ в месяц, около 2 долларов.
      Первые 14 дней после установки всё открыто.</div>
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
    <div class="hint">${ico('alert','xs')} Расчёты, от которых зависит безопасность, остаются бесплатными навсегда — брать за них деньги неправильно. Платно то, что экономит время и ведёт учёт.</div>`;
  $('#tResults').innerHTML = isPaid()
    ? `<div class="tres hi"><span class="tl">Сейчас у тебя</span><span class="tv">${esc(ACC?ACC.title:'')}</span></div>`
    : `<button class="btn wide" id="buyBtn">Оформить за ${price} ⭐ в месяц</button>`;
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
  curTool=null;
  applyLang();

  const bb=$('#buyBtn');
  if(bb) bb.onclick=()=>{
    hap('medium');
    try{ TG.close(); }catch(e){}
    // оплата идёт в чате: там Telegram сам открывает окно платежа по /subscribe
  };
}


/* ---- Профиль: настройки, подписка, о приложении ---- */
function renderSettings(){
  const box=$('#settingsBox'); if(!box) return;
  const dark=!document.body.classList.contains('light');
  const tier=ACC?ACC.title:'—';
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
    </div>

    <div class="dpanel"><h4>Доступ</h4>
      <div class="tres hi"><span class="tl">Текущий тариф</span><span class="tv">${esc(tier)}</span></div>
      ${(ACC&&ACC.paywall===false)
        ? `<div class="hint" style="margin:9px 0 0">${ico('alert','xs')} Идёт отладка, все разделы открыты бесплатно.</div>`
        : `<button class="btn wide" id="setPlans" style="margin-top:9px">Что входит в Premium · ${price} ⭐</button>`}
    </div>

    <div class="dpanel"><h4>Данные без связи</h4>
      <div class="tres"><span class="tl">Последняя синхронизация</span><span class="tv" style="font-size:13px">${esc(cached)}</span></div>
      <div class="hint" style="margin:9px 0 0">${ico('radar','xs')} Предупреждения, станции и справочники сохраняются на устройстве — в рейсе приложение открывается и работает без сети. Расчёты работают всегда.</div>
      <button class="btn g wide" id="setClear" style="margin-top:9px">Очистить сохранённые данные</button>
    </div>

    <div class="dpanel"><h4>О приложении</h4>
      <div class="tres"><span class="tl">Watchkeeper</span><span class="tv" style="font-size:13px">${APP_VERSION}</span></div>
      <div class="hint" style="margin:9px 0 0">${ico('alert','xs')} Данные справочные. Официальный источник — оборудование GMDSS и NAVTEX, ECDIS и судовые пособия. Решение принимает судоводитель.</div>
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

/* ================= Тренажёр ЦИВ (DSC) =================
   Экранная копия Furuno FS-1575: дисплей, клавиатура, кнопка бедствия
   под крышкой. Ничего в эфир не уходит -- вся связь имитируется, включая
   задержки на подтверждение, как на настоящей станции. */
/* Справочник ЦИВ зашит в приложение: тренажёр статичен, ходить за ним на
   сервер незачем -- и он продолжает работать в рейсе без связи. С сервера
   данные подхватываются только если там окажется более свежая версия. */
const DSC_BUILTIN={"freqs":[{"band":"MF","dsc":2187.5,"rt":2182.0,"nbdp":2174.5,"note":"Средние волны. Дальность порядка 150 миль днём, ночью больше."},{"band":"HF 4","dsc":4207.5,"rt":4125.0,"nbdp":4177.5,"note":"Ночью и на рассвете, дальность до 300 миль."},{"band":"HF 6","dsc":6312.0,"rt":6215.0,"nbdp":6268.0,"note":"Круглосуточно, средние дистанции."},{"band":"HF 8","dsc":8414.5,"rt":8291.0,"nbdp":8376.5,"note":"Самый универсальный диапазон, работает днём и ночью."},{"band":"HF 12","dsc":12577.0,"rt":12290.0,"nbdp":12520.0,"note":"День, большие дистанции."},{"band":"HF 16","dsc":16804.5,"rt":16420.0,"nbdp":16695.0,"note":"День, максимальная дальность."}],"nature":[{"id":"fire","t":"Fire, explosion","ru":"Пожар, взрыв"},{"id":"flooding","t":"Flooding","ru":"Поступление воды"},{"id":"collision","t":"Collision","ru":"Столкновение"},{"id":"grounding","t":"Grounding","ru":"Посадка на мель"},{"id":"listing","t":"Listing, danger of capsizing","ru":"Крен, опасность опрокидывания"},{"id":"sinking","t":"Sinking","ru":"Затопление"},{"id":"adrift","t":"Disabled and adrift","ru":"Потеря хода, дрейф"},{"id":"undesign","t":"Undesignated distress","ru":"Бедствие без уточнения"},{"id":"abandon","t":"Abandoning ship","ru":"Оставление судна"},{"id":"piracy","t":"Piracy / armed robbery","ru":"Пиратское нападение"},{"id":"mob","t":"Man overboard","ru":"Человек за бортом"}],"calls":[{"id":"distress","t":"Distress Alert","ru":"Вызов бедствия","cat":"Distress","needs":["nature","position"],"why":"Подаётся только при непосредственной опасности для судна или людей. Станция сама подставляет позицию от приёмника и передаёт по всем диапазонам. Ждём подтверждения от берегового центра, не от судов."},{"id":"relay","t":"Distress Relay","ru":"Ретрансляция бедствия","cat":"Distress","needs":["nature","position","mmsi_opt"],"why":"Передаём за другое судно: приняли сигнал бедствия, а берег его не подтвердил. Свой сигнал бедствия при этом не подаём -- иначе спасатели будут искать нас, а не терпящего бедствие."},{"id":"urgency","t":"Urgency Call","ru":"Срочность (PAN PAN)","cat":"Urgency","needs":[],"why":"Серьёзная ситуация, но непосредственной опасности гибели нет: потеря хода в стороне от судоходства, тяжёлый больной на борту."},{"id":"safety","t":"Safety Call","ru":"Безопасность (SECURITE)","cat":"Safety","needs":[],"why":"Навигационные и метеорологические предупреждения: плавающий объект, неработающий буй, шторм."},{"id":"individual","t":"Individual Call","ru":"Индивидуальный вызов","cat":"Routine","needs":["mmsi","freq"],"why":"Вызов конкретного судна или береговой станции по её MMSI. Указываем рабочую частоту, на которой будем говорить."},{"id":"allships","t":"All Ships Call","ru":"Вызов всем судам","cat":"Safety","needs":["freq"],"why":"Всем, кто в зоне слышимости. В обычной обстановке применяется только с категорией срочности или безопасности."},{"id":"group","t":"Group Call","ru":"Групповой вызов","cat":"Routine","needs":["mmsi","freq"],"why":"Судам одной группы: флот компании, суда в конвое. Групповой MMSI начинается с нуля и заранее прописан в станции."},{"id":"test","t":"Test Call","ru":"Тестовый вызов","cat":"Safety","needs":["mmsi"],"why":"Проверка работоспособности ЦИВ на ВЧ и ПВ. Направляется береговой станции, она отвечает подтверждением. На 2187.5 кГц проверка делается именно тестовым вызовом, а не вызовом бедствия."},{"id":"position","t":"Position Request","ru":"Запрос позиции","cat":"Routine","needs":["mmsi"],"why":"Запрос координат другого судна. Оно может ответить автоматически или отклонить запрос -- это его право."},{"id":"polling","t":"Polling","ru":"Опрос присутствия","cat":"Routine","needs":["mmsi"],"why":"Проверка, находится ли станция в зоне связи. Ответ приходит автоматически, без участия вахтенного на той стороне."}],"lessons":{"ack":"Подтверждение (ACK) означает, что вызов принят. При бедствии подтверждать имеет право береговой центр -- судно подтверждает только если берег молчит и судно способно помочь.","freq":"Диапазон выбирают по дальности и времени суток. Ночью проходят низкие частоты (2, 4 МГц), днём высокие (12, 16 МГц). 8 МГц работает почти всегда -- с него и начинают.","rt":"После вызова ЦИВ переходим на парную радиотелефонную частоту того же диапазона и говорим уже голосом. ЦИВ -- только для того, чтобы привлечь внимание.","distress":"Кнопка бедствия закрыта крышкой и требует удержания около пяти секунд -- защита от случайного нажатия. Если подал по ошибке, не выключай станцию: сообщи голосом на 2182 кГц, что тревога ложная, и отмени её.","mmsi":"MMSI из девяти цифр. У судна первые три -- код страны, у береговой станции первые две цифры нули, у группы -- один ноль в начале.","test":"Тестовый вызов не тревожит спасателей и не поднимает никого по тревоге. Именно им проверяют ЦИВ, как требует ежедневная проверка по ГМССБ."},"exam":[{"id":"e1","situation":"В машинном отделении пожар, экипаж не справляется, судно теряет ход. Твои действия по ЦИВ.","expect":{"call":"distress","nature":"fire"},"explain":"Непосредственная опасность для судна и людей -- это вызов бедствия с указанием характера «пожар, взрыв»."},{"id":"e2","situation":"Судно село на мель, поступления воды нет, крена нет, опасности для людей нет, но сняться самостоятельно не можешь.","expect":{"call":"urgency"},"explain":"Прямой угрозы гибели нет, значит бедствие подавать рано. Это срочность (PAN PAN). Если начнёт поступать вода или появится крен -- переходим на бедствие."},{"id":"e3","situation":"Приняли вызов бедствия с соседнего судна на 8414.5 кГц. Прошло пять минут, береговая станция не подтвердила приём.","expect":{"call":"relay"},"explain":"Передаём ретрансляцию бедствия. Свой вызов бедствия подавать нельзя -- у нас самих ничего не случилось, и спасатели пойдут не туда."},{"id":"e4","situation":"Обнаружили в море полузатопленный контейнер, представляющий опасность для судоходства.","expect":{"call":"safety"},"explain":"Навигационная опасность для других судов -- категория безопасности (SECURITE), обычно вызовом всем судам."},{"id":"e5","situation":"Нужно проверить работу ЦИВ на ПВ, как того требует ежедневная проверка ГМССБ.","expect":{"call":"test"},"explain":"Для этого есть тестовый вызов береговой станции. Вызов бедствия для проверки не применяют ни при каких обстоятельствах."},{"id":"e6","situation":"Человек упал за борт, судно развернулось на циркуляции, идёт поиск.","expect":{"call":"distress","nature":"mob"},"explain":"Жизни человека угрожает непосредственная опасность -- вызов бедствия с характером «человек за бортом»."},{"id":"e7","situation":"Нужно связаться с агентом через береговую станцию Lyngby Radio для передачи заявки на снабжение.","expect":{"call":"individual"},"explain":"Обычная деловая связь -- индивидуальный вызов береговой станции с указанием рабочей частоты."},{"id":"e8","situation":"На борту тяжелобольной, нужна консультация врача, но судно на ходу и опасности нет.","expect":{"call":"urgency"},"explain":"Медицинская консультация без угрозы гибели судна -- срочность (PAN PAN), обычно с пометкой MEDICO."},{"id":"e9","situation":"Судно атаковано вооружёнными лицами при подходе к якорной стоянке.","expect":{"call":"distress","nature":"piracy"},"explain":"Пиратское нападение -- отдельный вид бедствия по ITU-R M.493, подаётся вызов бедствия."},{"id":"e10","situation":"Нужно узнать, где сейчас находится судно компании, идущее тем же районом.","expect":{"call":"position"},"explain":"Запрос позиции. Судно вправе отклонить запрос, это нормально."}],"note":"Тренажёр. Ничего в эфир не уходит. Перед экзаменом и работой на судне сверяйся с ALRS Volume 5 и инструкцией своей станции."};
let DSC=DSC_BUILTIN, DS={
  screen:'home',       // 'home' -- дежурный экран (как в жизни), 'main' -- меню видов вызова,
                       // 'nature'/'band'/'mmsi' -- списки выбора, 'log' -- ход вызова
  sel:0,              // выбранная строка меню
  call:null,          // выбранный вид вызова
  nature:null,        // вид бедствия
  mmsi:'',            // набранный MMSI
  band:3,             // индекс диапазона, по умолчанию 8 МГц
  log:[],             // строки на дисплее
  busy:false,
  armed:false,        // крышка кнопки бедствия открыта
  hold:0,
  exam:null, examIdx:0, examScore:0, examTotal:0
};

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
function dscPrint(line){ DS.log.push(line); if(DS.log.length>14) DS.log.shift(); drawDSC(); }
function dscClear(){ DS.log=[]; }

/* ---- дисплей ----
   Дежурный экран ('home') собран по фото настоящей FS-2575C: рамка CH,
   строки TX/RX, GPS DATA и так далее. Остальные экраны -- меню выбора,
   ввод MMSI, ход вызова -- используют ту же рамку, но простое содержимое
   списком, как оно и есть на реальной станции при заходе в MENU. */
function lcdMenuList(){
  if(DS.screen==='main'){
    return (DSC.calls||[]).map((c,i)=>
      `<div class="it ${i===DS.sel?'sel':''}">${i===DS.sel?'▸':' '} ${esc(c.t)}</div>`).join('');
  }
  if(DS.screen==='nature'){
    return (DSC.nature||[]).map((n,i)=>
      `<div class="it ${i===DS.sel?'sel':''}">${i===DS.sel?'▸':' '} ${esc(n.t)}</div>`).join('');
  }
  if(DS.screen==='band'){
    return (DSC.freqs||[]).map((f,i)=>
      `<div class="it ${i===DS.sel?'sel':''}">${i===DS.sel?'▸':' '} ${f.band}  ${f.dsc} kHz</div>`).join('');
  }
  return '';
}

/* Шкала S-метра: чем больше усиление, тем больше делений. Это не
   имитация эфира, а отклик на ручку -- как на станции, где RF GAIN
   двигает уровень шума и сигнала. */
function sBars(){
  const n=Math.round((KNOB.rf/99)*8);
  return Array.from({length:8},(_,i)=>i<Math.max(1,n)?1:0);
}
function drawDSC(){
  const box=$('#lcd'); if(!box||!DSC) return;
  const b=dscBand();
  const alert=DS.screen==='log'&&DS.log.some(l=>/DISTRESS|MAYDAY/.test(l));
  box.className='lcd'+(alert?' alert':'');

  const mmsi=(VES&&VES.active&&VES.active.mmsi)?VES.active.mmsi:'210210000';
  const now=new Date(), hh=String(now.getUTCHours()).padStart(2,'0'), mm=String(now.getUTCMinutes()).padStart(2,'0');
  // Позиция с устройства, если она свежая -- как на станции, где
  // координаты приходят от приёмника, а не набираются руками.
  const lat = geoFresh() ? geoFmtLat(GEO.lat) : ((VES&&VES.active&&VES.active.lat)||'46-29.4N');
  const lon = geoFresh() ? geoFmtLon(GEO.lon) : ((VES&&VES.active&&VES.active.lon)||'030-44.3E');

  { const v=$('#volVal'); if(v) v.textContent=Math.round(KNOB.vol);
    const r=$('#rfVal'); if(r) r.textContent=Math.round(KNOB.rf); }

  if(DS.screen==='home'){
    box.innerHTML=`
      <div class="lcdtop"><span>⚓ ✉ ✉</span><span>MMSI:${esc(mmsi)}</span></div>
      <div class="lrow1">
        <div class="ldist">DIST-<br>RESS</div>
        <div class="lch"><span class="l">CH</span><span class="n">200</span></div>
        <div class="lnb">NB</div>
        <div class="lmenu">
          <div class="mi"><b>1</b>RX FREQ</div>
          <div class="mi"><b>4</b>DAILY TEST</div>
          <div class="mi"><b>7</b>TEST CALL</div>
        </div>
      </div>
      <div class="lfreq"><span class="lb">TX</span><span class="v">${b.dsc.toFixed(1)}</span><span class="u">kHz</span></div>
      <div class="lfreq"><span class="lb">RX</span><span class="v">${b.rt.toFixed(2)}</span><span class="u">kHz</span></div>
      <div class="lmode"><span>SSB</span><span>MID</span><span>FAST</span><span>SIMP</span></div>
      <div class="lmeter">S<div class="lbars">${sBars().map(x=>`<i class="${x?'on':''}"></i>`).join('')}</div></div>
      <div class="lmeter">IC<div class="lbars">${[1,1,1,0,0,0,0,0].map(x=>`<i class="${x?'on':''}"></i>`).join('')}</div><span style="margin-left:3px">0.0A</span></div>
      <div class="lag"><span class="attb">ATT</span><span>AF ${Math.round(KNOB.vol)} · RF GAIN ${Math.round(KNOB.rf)}</span></div>
      <div class="lgps"><span>LAT ${esc(String(lat))}<br>LON ${esc(String(lon))}</span><b>GPS DATA<br>${hh}:${mm} UTC</b></div>
      <div class="lmem">${Array(8).fill('<i></i>').join('')}</div>`;
    return;
  }

  if(DS.screen==='mmsi'){
    box.innerHTML=`
      <div class="lcdtop"><span>ENTER MMSI</span><span>${b.band}</span></div>
      <div class="llog" style="display:flex;align-items:center;justify-content:center;flex-direction:column;gap:10px">
        <div style="font-size:15px;letter-spacing:2px;color:#fff">${esc(DS.mmsi.padEnd(9,'_'))}</div>
        <div style="opacity:.8">${DS.mmsi.length===9?'<span class="blink">PRESS SEND</span>':'9 digits required'}</div>
      </div>`;
    return;
  }

  if(DS.screen==='log'){
    box.innerHTML=`
      <div class="lcdtop"><span>${DS.busy?'TX':'RX'}</span><span>${b.band} · ${b.dsc} kHz</span></div>
      <div class="llog">${DS.log.map(esc).join('\n')}</div>`;
    return;
  }

  // main / nature / band -- списки меню в той же рамке
  const titles={main:'SELECT CALL TYPE',nature:'NATURE OF DISTRESS',band:'SELECT FREQUENCY'};
  box.innerHTML=`
    <div class="lcdtop"><span>${titles[DS.screen]||'MENU'}</span><span>${b.band}</span></div>
    <div class="lmenuscreen">${lcdMenuList()}</div>`;
}

/* ---- имитация обмена ---- */
function wait(ms){ return new Promise(r=>setTimeout(r,ms)); }

async function dscSend(){
  if(DS.busy||!DSC) return;
  const b=dscBand();

  if(DS.screen==='main'){
    const c=DSC.calls[DS.sel];
    DS.call=c;
    if(c.needs.includes('nature')){ DS.screen='nature'; DS.sel=0; drawDSC(); showTip(c); return; }
    if(c.needs.includes('mmsi')){ DS.screen='mmsi'; DS.mmsi=''; drawDSC(); showTip(c); return; }
    return runCall(c);
  }
  if(DS.screen==='nature'){
    DS.nature=DSC.nature[DS.sel];
    return runCall(DS.call);
  }
  if(DS.screen==='mmsi'){
    if(DS.mmsi.length!==9) return;
    return runCall(DS.call);
  }
  if(DS.screen==='band'){
    DS.band=DS.sel; DS.screen='main'; DS.sel=0; drawDSC();
    showLesson('freq');
    return;
  }
}

async function runCall(c){
  if(!c) return;
  DS.busy=true; DS.screen='log'; dscClear();
  const b=dscBand();
  hap('medium');

  const isDistress = c.id==='distress';
  dscPrint(`${c.t.toUpperCase()}`);
  dscPrint(`FREQ ${b.dsc} kHz`);
  if(DS.mmsi) dscPrint(`TO   ${DS.mmsi}`);
  if(DS.nature) dscPrint(`NATURE ${DS.nature.t}`);
  dscPrint('POS  '+(geoFresh()?(geoFmtLat(GEO.lat)+' '+geoFmtLon(GEO.lon)):'46-29.4N 030-44.3E')
           +(geoFresh()?'':'  (нет данных GPS)'));
  dscPrint('');
  dscPrint(isDistress?'TRANSMITTING DISTRESS...':'TRANSMITTING...');

  await wait(1200);
  dscPrint(isDistress?'DISTRESS SENT':'CALL SENT');
  dscPrint('WAITING FOR ACK...');
  await wait(isDistress?2200:1600);

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
    dscPrint('');
    dscPrint('RELAY ACK RECEIVED');
    dscPrint('RCC ACKNOWLEDGED');
    showLesson('ack');
  } else if(c.id==='test'){
    dscPrint('');
    dscPrint('TEST ACK RECEIVED');
    dscPrint(`FROM ${DS.mmsi||'002371000'}`);
    dscPrint('DSC OPERATION NORMAL');
    showLesson('test');
  } else if(c.id==='position'){
    dscPrint('');
    dscPrint('POSITION RECEIVED');
    dscPrint('44-12.8N 033-51.6E');
    dscPrint('AT 1420 UTC');
  } else if(c.id==='polling'){
    dscPrint('');
    dscPrint('POLLING ACK RECEIVED');
    dscPrint('STATION IN RANGE');
  } else if(c.id==='allships'||c.id==='safety'||c.id==='urgency'){
    dscPrint('');
    dscPrint('CALL COMPLETED');
    dscPrint(`SWITCH TO ${b.rt} kHz`);
    dscPrint(c.id==='urgency'?'SPEAK: PAN PAN x3':'SPEAK: SECURITE x3');
    showLesson('rt');
  } else {
    dscPrint('');
    dscPrint('ACK RECEIVED');
    dscPrint(`SWITCH TO ${b.rt} kHz`);
    showLesson('rt');
  }

  DS.busy=false; drawDSC();
  if(DS.exam) checkExam(c);
}

/* ---- кнопка бедствия ---- */
function armDistress(){
  DS.armed=true; hap('medium'); renderDSC();
}
function holdDistress(down){
  const btn=$('#dbtn'); if(!btn) return;
  if(down){
    btn.classList.add('arming');
    DS.hold=setTimeout(async()=>{
      btn.classList.remove('arming');
      DS.call=(DSC.calls||[]).find(c=>c.id==='distress');
      DS.screen='nature'; DS.sel=0; DS.armed=false;
      hap('heavy'); renderDSC();
      showLesson('distress');
    },1800);
  } else {
    clearTimeout(DS.hold); btn.classList.remove('arming');
  }
}

/* ---- пояснения ---- */
function showTip(c){
  const el=$('#dsctip'); if(!el||!c) return;
  el.innerHTML=`<b>${esc(c.ru)}</b>${esc(c.why)}`;
}
function showLesson(key){
  const el=$('#dsctip'); if(!el||!DSC) return;
  const t=(DSC.lessons||{})[key]; if(!t) return;
  el.innerHTML=`<b>${esc(tr('Как это работает'))}</b>${esc(t)}`;
}

/* ---- экзамен ---- */
function startExam(){
  DS.exam=(DSC.exam||[]).slice().sort(()=>Math.random()-0.5);
  DS.examIdx=0; DS.examScore=0; DS.examTotal=DS.exam.length;
  DS.screen='main'; DS.sel=0; dscClear(); hap('medium'); renderDSC();
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
    DS.nature=null; DS.mmsi=''; DS.screen='main'; DS.sel=0;
    renderDSC();
  },3600);
}

/* ---- отрисовка раздела ---- */
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
        <div class="rplate">MMSI ${esc((VES&&VES.active&&VES.active.mmsi)||'210210000')}</div>
      </div>
      <div class="rhdr">
        <div class="rnameplate">CONTROL UNIT TYPE FS-2575C<br>SER.NO. 106667</div>
        <div class="rfuruno">FURUNO</div>
      </div>
      <div class="rbody">
        <div class="rleft">
          <div class="rspeaker"><i></i><i></i><i></i><i></i></div>
          <div class="rklabel">HANDSET</div>
          <div class="rknob" id="knobVol"></div>
          <div class="rklabel">VOLUME · <b id="volVal">5</b></div>
          <div class="rknob" id="knobRf"></div>
          <div class="rklabel">RF GAIN · <b id="rfVal">28</b><br>PUSH TO ATT</div>
          <div class="rleds">
            <div class="rled"><i class="amber"></i><span>ALARM</span></div>
            <div class="rled"><i class="${DS.busy?'green':''}"></i><span>OVEN</span></div>
          </div>
          <div class="rdistwrap">
            ${DS.armed
              ? `<div class="rdistcover"><div class="rdistbtn arming" id="dbtn"></div></div>
                 <div class="rpwroff">PWR OFF</div>
                 <div class="rdistcap">${esc(tr('Удерживай 2 секунды'))}</div>`
              : `<div class="rdistcover" id="dlid"><div class="rdistbtn" style="opacity:.45"></div></div>
                 <div class="rpwroff">PWR OFF</div>
                 <div class="rdistcap">${esc(tr('Keep pressed 4 sec for DISTRESS'))}</div>`}
          </div>
        </div>

        <div class="rscreen"><div class="lcd" id="lcd"></div></div>

        <div class="rright">
          <div class="rkgrid">
            <button class="rkey" data-dk="scan"><div class="kt">SCAN</div></button>
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
            <button class="rkey" data-dk="menu"><div class="kt">MENU</div></button>
            <button class="rkey" data-dk="mute"><div class="kt">🔇</div></button>
            <button class="rkey warn" data-dk="cancel"><div class="kt">CANCEL</div></button>
          </div>
          <div class="rbigknob" id="dkEnter"><span class="cap">PUSH TO ENTER</span></div>
        </div>
      </div>

      <div class="rcompose">
        <button class="rcbtn" data-dk="distmsg">DISTRESS<br>MSG</button>
        <button class="rcbtn" data-dk="othermsg">OTHER<br>DSC MSG</button>
        <button class="rcbtn" data-dk="brill">BRILL</button>
      </div>
      <div class="rbracket">COMPOSE DSC MSG</div>
    </div>
    <div class="rfooter">BATTERY MONITOR</div>

    <div class="dsctip" id="dsctip"><b>${esc(tr('Тренажёр'))}</b>${esc((DSC.note||''))}</div>
    <div style="display:flex;gap:9px;margin-top:13px">
      ${DS.exam
        ? `<button class="btn g" style="flex:1" id="examStop">${esc(tr('Выйти из экзамена'))}</button>`
        : `<button class="btn" style="flex:1" id="examStart">${esc(tr('Режим экзамена'))}</button>`}
    </div>`;

  drawDSC();

  document.querySelectorAll('[data-dk]').forEach(b=>b.onclick=()=>dscKey(b.dataset.dk));
  const lid=$('#dlid'); if(lid) lid.onclick=armDistress;
  const ent=$('#dkEnter'); if(ent) ent.onclick=()=>dscKey('send');
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

function dscKey(k){
  if(!DSC) return;
  hap();
  const lists={main:(DSC.calls||[]).length,nature:(DSC.nature||[]).length,band:(DSC.freqs||[]).length};
  const len=lists[DS.screen]||0;

  // На дежурном экране цифры 1/4/7 -- те же ярлыки, что подписаны на
  // самом экране (RX FREQ / DAILY TEST / TEST CALL), как на настоящей
  // станции. Остальные цифры уводят в набор MMSI, как обычно.
  if(DS.screen==='home'){
    if(k==='1'){ DS.screen='band'; DS.sel=DS.band; drawDSC(); return; }
    if(k==='4'||k==='7'){
      const t=(DSC.calls||[]).find(c=>c.id==='test');
      if(t){ DS.call=t; DS.screen='mmsi'; DS.mmsi=''; drawDSC(); showTip(t); return; }
    }
    if(k==='menu'||k==='2182'){ DS.screen='main'; DS.sel=0; drawDSC(); return; }
  }

  if(k==='up'){ DS.sel=(DS.sel-1+len)%(len||1); if(DS.screen==='main') showTip(DSC.calls[DS.sel]); drawDSC(); return; }
  if(k==='down'){ DS.sel=(DS.sel+1)%(len||1); if(DS.screen==='main') showTip(DSC.calls[DS.sel]); drawDSC(); return; }
  if(k==='menu'){ DS.screen='main'; DS.sel=0; DS.nature=null; DS.mmsi=''; dscClear(); drawDSC(); return; }
  if(k==='home'||k==='mute'||k==='tab'||k==='brill'){ DS.screen='home'; DS.nature=null; DS.mmsi=''; dscClear(); drawDSC(); return; }
  if(k==='band'||k==='2182'||k==='scan'){ DS.screen='band'; DS.sel=DS.band; drawDSC(); return; }
  if(k==='cancel'){
    DS.screen='home';
    DS.nature=null; DS.mmsi=''; dscClear(); drawDSC(); showLesson('distress'); return;
  }
  if(k==='del'){ if(DS.screen==='mmsi') DS.mmsi=DS.mmsi.slice(0,-1); drawDSC(); return; }
  if(k==='distmsg'){
    const dcall=(DSC.calls||[]).find(c=>c.id==='distress');
    if(dcall){ DS.call=dcall; DS.screen='nature'; DS.sel=0; drawDSC(); showTip(dcall); }
    return;
  }
  if(k==='othermsg'){ DS.screen='main'; DS.sel=0; drawDSC(); return; }
  if(k==='send'){ dscSend(); return; }
  if(/^[0-9]$/.test(k)){
    if(DS.screen!=='mmsi'){ DS.screen='mmsi'; DS.mmsi=''; }
    if(DS.mmsi.length<9) DS.mmsi+=k;
    drawDSC(); if(DS.mmsi.length===3) showLesson('mmsi');
  }
}



/* ================= Позиция с устройства =================
   Берём координаты у самого телефона, чтобы не набирать их руками.
   Telegram отдаёт своё хранилище позиции только начиная с Bot API 8.0
   (LocationManager), поэтому сначала пробуем его, а если его нет --
   обычный navigator.geolocation. На судне GPS телефона обычно ловит,
   но в глубине корпуса может и не поймать: тогда честно говорим об этом,
   а не подставляем последнюю известную точку молча. */
let GEO={lat:null, lon:null, at:0, acc:null, busy:false, err:null};

function geoFmtLat(d){
  const s=d<0?'S':'N'; d=Math.abs(d);
  const deg=Math.floor(d), min=(d-deg)*60;
  return String(deg).padStart(2,'0')+'-'+min.toFixed(1).padStart(4,'0')+s;
}
function geoFmtLon(d){
  const s=d<0?'W':'E'; d=Math.abs(d);
  const deg=Math.floor(d), min=(d-deg)*60;
  return String(deg).padStart(3,'0')+'-'+min.toFixed(1).padStart(4,'0')+s;
}
const geoFresh = ()=> GEO.lat!==null && (Date.now()-GEO.at) < 5*60*1000;

function requestPosition(){
  return new Promise(resolve=>{
    if(GEO.busy){ resolve(null); return; }
    GEO.busy=true; GEO.err=null; renderGeoBtn();

    const done=(ok,err)=>{
      GEO.busy=false; GEO.err=ok?null:(err||'нет данных');
      renderGeoBtn();
      resolve(ok?{lat:GEO.lat,lon:GEO.lon}:null);
    };

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

function browserGeo(done){
  if(!navigator.geolocation){ done(false,'устройство не отдаёт позицию'); return; }
  navigator.geolocation.getCurrentPosition(
    p=>{
      GEO.lat=p.coords.latitude; GEO.lon=p.coords.longitude;
      GEO.acc=p.coords.accuracy||null; GEO.at=Date.now();
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
  b.className='geobtn'+(GEO.busy?' busy':'')+(geoFresh()?' on':'')+(GEO.err?' err':'');
  b.innerHTML=ico('target','sm');
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
const KNOB={vol:5, rf:28, ent:0};   // ent -- накопленный поворот энкодера

function knobAngle(el, x, y){
  const r=el.getBoundingClientRect();
  return Math.atan2(y-(r.top+r.height/2), x-(r.left+r.width/2))*180/Math.PI;
}

function makeKnob(el, opts){
  if(!el||el._knob) return;
  el._knob=true;
  let prev=null;

  const start=(x,y)=>{ prev=knobAngle(el,x,y); };
  const move=(x,y)=>{
    if(prev===null) return;
    const a=knobAngle(el,x,y);
    let d=a-prev;
    if(d>180) d-=360; if(d<-180) d+=360;   // переход через 180 градусов
    if(Math.abs(d)<1) return;
    prev=a;
    opts.onTurn(d);
  };
  const end=()=>{ prev=null; };

  el.addEventListener('pointerdown',e=>{ e.preventDefault(); el.setPointerCapture&&el.setPointerCapture(e.pointerId); start(e.clientX,e.clientY); },{passive:false});
  el.addEventListener('pointermove',e=>{ if(prev!==null){ e.preventDefault(); move(e.clientX,e.clientY); } },{passive:false});
  el.addEventListener('pointerup',end,{passive:true});
  el.addEventListener('pointercancel',end,{passive:true});
  el.addEventListener('touchstart',e=>{ if(e.touches[0]) start(e.touches[0].clientX,e.touches[0].clientY); },{passive:true});
  el.addEventListener('touchmove',e=>{ if(e.touches[0]&&prev!==null){ e.preventDefault(); move(e.touches[0].clientX,e.touches[0].clientY); } },{passive:false});
  el.addEventListener('touchend',end,{passive:true});
}

function knobRotate(el, deg){
  if(el) el.style.transform='rotate('+deg+'deg)';
}

function bindStationKnobs(){
  const vol=$('#knobVol'), rf=$('#knobRf'), ent=$('#dkEnter');

  makeKnob(vol,{onTurn:d=>{
    KNOB.vol=Math.max(0,Math.min(10,KNOB.vol+d/28));
    knobRotate(vol, (KNOB.vol/10)*270-135);
    if(Math.random()<0.35) hap();
    drawDSC();
  }});
  knobRotate(vol,(KNOB.vol/10)*270-135);

  makeKnob(rf,{onTurn:d=>{
    KNOB.rf=Math.max(0,Math.min(99,KNOB.rf+d/3.6));
    knobRotate(rf, (KNOB.rf/99)*270-135);
    if(Math.random()<0.35) hap();
    drawDSC();
  }});
  knobRotate(rf,(KNOB.rf/99)*270-135);

  // Большая ручка: поворот листает список, нажатие -- подтверждение.
  makeKnob(ent,{onTurn:d=>{
    KNOB.ent+=d;
    const step=22;                       // столько градусов на один щелчок
    while(KNOB.ent>=step){ KNOB.ent-=step; dscKey('down'); }
    while(KNOB.ent<=-step){ KNOB.ent+=step; dscKey('up'); }
    knobRotate(ent, (KNOB.ent||0));
  }});
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
let EQCHECK={epirb:[], sart:[]};  // отмеченные пункты чек-листа (несохранённые)

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
      <input type="date" id="${kind}Expires" value="${esc(eq.battery_expires||'')}">
    </div>

    <div class="sech" style="margin-top:15px"><h3>${esc(tr('Ежемесячная проверка'))}</h3><a class="cnt2">${done.length}/${checklist.length}</a></div>
    <div class="eqprogress"><i style="width:${pct}%"></i></div>`;

  checklist.forEach(it=>{
    const on=done.includes(it.k);
    h+=`<div class="eqchk ${on?'on':''}" data-chk="${it.k}">
          <div class="box">${on?ico('back','sm'):''}</div>
          <div class="t">${esc(tr(it.t))}</div>
        </div>`;
  });
  h+=`<button class="btn wide" id="${kind}SaveChk" style="margin-top:6px">${esc(tr('Сохранить отметки'))}</button>`;

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

  if(kind==='sart'){
    h+=`<div class="sech" style="margin-top:19px"><h3>Radar Preview</h3></div>
        <div class="hint">${ico('alert','xs')} ${esc(tr('Линия из 12 точек с интервалом 0.64 мили. Ближе 1 мили точки становятся дугами, затем полными окружностями.'))}</div>
        <div class="ppiwrap"><div class="ppiratio"><svg id="sartPpi" viewBox="0 0 300 300"></svg></div></div>
        <div class="rngbtns">
          <button class="rngbtn" data-rng="far">6-8 ${esc(tr('миль'))}</button>
          <button class="rngbtn on" data-rng="mid">1-2 ${esc(tr('мили'))}</button>
          <button class="rngbtn" data-rng="close">&lt;0.2 ${esc(tr('мили'))}</button>
        </div>`;
  }

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

  const exp=$('#'+kind+'Expires');
  if(exp) exp.onchange=async()=>{
    hap('medium');
    try{ GMEQ=await api('/api/gmdss?action=save_equipment&kind='+kind+'&battery_expires='+encodeURIComponent(exp.value)); renderGmdss(kind); }
    catch(e){}
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
  $('#tResults').innerHTML=rows.map(r=>
    `<div class="tres ${r.hi?'hi':''} ${r.warn?'warn':''}">
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
  applyLang();
};
$('#toolsHint').innerHTML=ico('alert','xs')+' Все расчёты выполняются прямо в приложении и работают без связи.';
renderTools();
loadBridge();
renderRefs();
loadHistory();

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

/* открыть сразу нужную вкладку, если пришли по ссылке вида /app#tools */
const wantTab=(location.hash||'').replace('#','');
if(['dash','areas','map','tools','radio','voy'].includes(wantTab)) switchView(wantTab);

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
