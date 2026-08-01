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
.cats,.chips{display:flex;gap:9px;overflow-x:auto;padding:2px 0 12px;scrollbar-width:none;scroll-snap-type:x proximity}
.cats::-webkit-scrollbar,.chips::-webkit-scrollbar{display:none}
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
".hidden{display:none!important}
.legs{display:flex;align-items:flex-start;gap:7px;margin-top:9px;padding-top:9px;
  border-top:1px solid rgba(240,160,60,.22);font-size:11.5px;color:var(--muted);line-height:1.45}
.legs .ico{color:var(--amber);margin-top:2px}
.topback{
  position:sticky;top:0;z-index:60;display:flex;align-items:center;gap:9px;
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

/* ---- Моё судно ---- */
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
      <div class="h1">Watch<span>keeper</span></div>
    </div>
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

  <div class="trialbar hidden" id="trialbar"></div>
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

  <!-- ИНСТРУМЕНТЫ -->
  <section id="v-tools" class="hidden">
    <div class="sech"><h3>Мостик</h3></div>
    <div class="hint" id="toolsHint"></div>
    <div id="bridgeBox"></div>
    <div id="refBox" style="margin-top:19px"></div>
    <div class="sech" style="margin-top:19px"><h3>Расчёты</h3></div>
    <div id="toollist"></div>
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
    <div class="sech"><h3>Моё судно</h3></div>
    <div id="vesselBox"><div class="sk card"></div><div class="sk card"></div></div>
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
        <div class="dtitle" id="tName" style="font-size:20px;margin:0"></div>
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
  <button class="tab on" data-v="dash" data-i="gauge">Панель</button>
  <button class="tab" data-v="areas" data-i="globe">Районы</button>
  <button class="tab" data-v="map" data-i="map">Карта</button>
  <button class="tab" data-v="tools" data-i="sliders">Мостик</button>
  <button class="tab" data-v="radio" data-i="radar">Радио</button>
  <button class="tab" data-v="ship" data-i="ship">Судно</button>
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
      if(k.length<4) continue;
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
  r.results.forEach(w=>(w.shapes||[]).forEach(s=>
    shapeLayer(s.points,s.type,`<b>${esc(w.area_code)} №${esc(w.msg_number||'—')}</b><br>${w.distance_nm} миль от курса`,'#f0a03c',s.radius_nm).addTo(vmap)));
  vmap.fitBounds(line.getBounds(),{padding:[28,28]});
}

/* --- навигация --- */
function switchView(v){
  S.view=v;
  ['dash','areas','map','tools','radio','ship','voy'].forEach(x=>{
    const el=$('#v-'+x);
    if(x===v){el.classList.remove('hidden');el.style.animation='none';void el.offsetWidth;el.style.animation=''}
    else el.classList.add('hidden');
  });
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.v===v));
  const topCats=$('#cats'); if(topCats) topCats.classList.toggle('hidden', v!=='dash');
  const topSearch=$('#topSearch'); if(topSearch) topSearch.classList.toggle('hidden', v!=='dash'&&v!=='areas');
  try{window.scrollTo({top:0,behavior:'smooth'})}catch(e){}
  if(v==='tools'){renderTools();renderRefs();if(gate('#bridgeBox','bridge'))loadBridge();}
  if(v==='ship'){ if(gate('#v-ship','vessel')) loadVessel(); }
  setTimeout(applyLang,30);
  if(v==='radio')setTimeout(()=>{renderRadio();initRmap();if(rmap)rmap.invalidateSize()},70);
  if(v==='dash')loadHistory();
  if(v==='voy')gate('#v-voy','voyage');
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


/* ---- Моё судно ---- */
let VES=null;

async function loadVessel(){
  try{ VES=await api('/api/vessel'); localStorage.setItem('navarea_vessel',JSON.stringify(VES)); }
  catch(e){ try{ VES=JSON.parse(localStorage.getItem('navarea_vessel')||'null'); }catch(e2){} }
  renderVessel();
  return VES;
}

/* размерения судна подставляются в расчёты по умолчанию */
function vesselDefault(key){
  const v=(VES&&VES.vessel)||{};
  const map={dr:'draft',ad:'air_draft',cb:'cb',loa:'loa',hh:'hawse',s:'speed',c:'cons'};
  const src=map[key];
  return src&&v[src]?v[src]:null;
}

function renderVessel(){
  const box=$('#vesselBox'); if(!box) return;
  if(!VES){ box.innerHTML='<div class="sk card"></div><div class="sk card"></div>'; return; }
  if(VES.error){
    box.innerHTML=`<div class="empty">${ico('ship')}Открой приложение из чата с ботом, чтобы карточка судна привязалась к тебе.</div>`;
    return;
  }
  const v=VES.vessel||{};
  const filled=Object.keys(v).length;

  if(!filled){
    box.innerHTML=`
      <div class="vhero">
        <svg class="vwave" viewBox="0 0 800 40" preserveAspectRatio="none">
          <path d="M0 20 q50 -12 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v24 h-800 z" fill="#4d93d6"/>
        </svg>
        <div class="vin">${ico('ship','lg')}
          <div class="vt">Судно не заведено</div>
          <div class="vs">Заполни один раз — размерения сами подставятся в расчёты запаса под килём, проседания, якорной стоянки и прохода под мостом.</div>
        </div>
      </div>
      <button class="btn wide" id="editVessel" style="margin-top:13px">Заполнить карточку</button>
      <div class="hint" style="margin-top:13px">${ico('alert','xs')} ${esc(VES.note||'')}</div>`;
  } else {
    const row=(l,val,u)=>val?`<div class="tres"><span class="tl">${esc(l)}</span><span class="tv mono">${esc(val)}${u?' '+u:''}</span></div>`:'';
    box.innerHTML=`
      <div class="vhero">
        <svg class="vwave" viewBox="0 0 800 40" preserveAspectRatio="none">
          <path d="M0 20 q50 -12 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 v24 h-800 z" fill="#4d93d6"/>
        </svg>
        <div class="vin">
          <div class="vname">${esc(v.name||'Без названия')}</div>
          <div class="vmeta">
            ${v.type?`<span class="dchip">${ico('ship','xs')}${esc(v.type)}</span>`:''}
            ${VES.flag?`<span class="dchip">${ico('flag','xs')}${esc(VES.flag)}</span>`:''}
            ${v.imo?`<span class="dchip">IMO ${esc(v.imo)}</span>`:''}
          </div>
        </div>
      </div>
      <div class="dpanel" style="margin-top:13px"><h4>Опознавание</h4>
        ${row('MMSI',v.mmsi)}${row('Позывной',v.callsign)}${row('Флаг по MMSI',VES.flag)}
      </div>
      <div class="dpanel"><h4>Размерения</h4>
        ${row('Длина наибольшая',v.loa,'м')}${row('Ширина',v.beam,'м')}
        ${row('Осадка в грузу',v.draft,'м')}${row('Надводный габарит',v.air_draft,'м')}
        ${row('Коэффициент полноты',v.cb)}${row('Высота клюза',v.hawse,'м')}
      </div>
      <div class="dpanel"><h4>Эксплуатация</h4>
        ${row('Дедвейт',v.dwt,'т')}${row('Валовая вместимость',v.gt)}
        ${row('Скорость в грузу',v.speed,'узлов')}${row('Расход на ходу',v.cons,'т/сут')}
      </div>
      <button class="btn wide" id="editVessel">Изменить данные</button>
      <div class="hint" style="margin-top:13px">${ico('alert','xs')} Эти значения подставляются в расчёты как исходные — можно менять на месте, карточка от этого не изменится.</div>`;
  }
  const eb=$('#editVessel'); if(eb) eb.onclick=openVesselForm;
  applyLang();
}

function openVesselForm(){
  if(!VES) return;
  hap('medium');
  const v=VES.vessel||{};
  $('#tName').textContent='Карточка судна';
  { const b=$('#tBackTitle'); if(b) b.textContent='Карточка судна'; }
  $('#tDesc').textContent='Заполняется один раз, подставляется во все расчёты';
  $('#tIcon').innerHTML=ico('ship','lg');
  $('#tFields').innerHTML=(VES.fields||[]).map(f=>
    `<div class="fld"><label>${esc(f.l)}${f.u?' · '+esc(f.u):''}</label>
     <input class="vinput" data-k="${f.k}" inputmode="${f.t==='num'?'decimal':'text'}"
            value="${esc(v[f.k]||'')}"></div>`).join('');
  $('#tResults').innerHTML=`<button class="btn wide" id="saveVessel">Сохранить</button>`;
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
  curTool=null;

  $('#saveVessel').onclick=async()=>{
    const q=[];
    document.querySelectorAll('.vinput').forEach(el=>{
      if(el.value.trim()) q.push(encodeURIComponent(el.dataset.k)+'='+encodeURIComponent(el.value.trim()));
    });
    hap('medium');
    try{
      VES=await api('/api/vessel?action=save&'+q.join('&'));
      localStorage.setItem('navarea_vessel',JSON.stringify(VES));
      renderVessel(); closeTool();
    }catch(e){
      $('#tResults').innerHTML=`<div class="tres warn"><span class="tl">Не удалось сохранить</span><span class="tv">нет связи</span></div>`;
    }
  };
}

/* ---- Экран инструментов ---- */
let curTool=null, toolVals={};

function renderTools(){
  const favT=JSON.parse(localStorage.getItem('navarea_favtools')||'[]');
  let h='';
  if(favT.length){
    h+=`<div class="sech"><h3>Избранные инструменты</h3></div><div class="grid2">`+
       TOOLS.filter(t=>favT.includes(t.id)).map(toolCard).join('')+`</div>`;
  }
  Object.keys(TOOL_CATS).forEach(ck=>{
    const list=TOOLS.filter(t=>t.cat===ck);
    if(!list.length) return;
    h+=`<div class="sech" style="margin-top:17px"><h3>${TOOL_CATS[ck].t}</h3></div>
        <div class="grid2">${list.map(toolCard).join('')}</div>`;
  });
  $('#toollist').innerHTML=h;
  applyLang();
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
  curTool=t; hap('medium');
  toolVals={};
  t.fields.forEach(f=>{ toolVals[f.k]=(f.def!==undefined?f.def:''); });

  $('#tName').textContent=t.name;
  { const b=$('#tBackTitle'); if(b) b.textContent=t.name; }
  $('#tDesc').textContent=t.desc;
  $('#tIcon').innerHTML=ico(t.icon,'lg');
  $('#tFields').innerHTML=t.fields.map(f=>{
    if(f.t==='sel'){
      return `<div class="fld"><label>${esc(f.l)}</label>
        <select class="tinput" data-k="${f.k}">
          ${f.opts.map(o=>`<option ${o===f.def?'selected':''}>${esc(o)}</option>`).join('')}
        </select></div>`;
    }
    const im=f.t==='num'?'decimal':'text';
    return `<div class="fld"><label>${esc(f.l)}${f.u?` · ${esc(f.u)}`:''}</label>
      <input class="tinput" data-k="${f.k}" inputmode="${im}" value="${esc(String(f.def||''))}"></div>`;
  }).join('');

  document.querySelectorAll('.tinput').forEach(el=>{
    const ev=el.tagName==='SELECT'?'onchange':'oninput';
    el[ev]=()=>{ toolVals[el.dataset.k]=el.value; runTool(); };
  });
  runTool();
  applyLang();
  $('#tool').classList.add('on');
  document.body.style.overflow='hidden';
}
function runTool(){
  if(!curTool) return;
  let rows;
  try{ rows=curTool.calc(toolVals)||[]; }
  catch(e){ rows=[{l:'Ошибка',v:'Проверь введённые данные'}]; }
  const __al=1;
  $('#tResults').innerHTML=rows.map(r=>
    `<div class="tres ${r.hi?'hi':''} ${r.warn?'warn':''}">
       <span class="tl">${esc(r.l)}</span>
       <span class="tv mono">${esc(String(r.v))}</span>
     </div>`).join('');
  applyLang();
}
function closeTool(){
  $('#tool').classList.remove('on');
  document.body.style.overflow='';
  curTool=null; hap();
}

$('#tBack').onclick=()=>{ if(curCL) saveCL(); closeTool(); $('#tBack').textContent='Назад к инструментам'; };
$('#tBackTop').innerHTML=ico('back');
$('#tBackTop').onclick=()=>{ if(typeof curCL!=='undefined'&&curCL) saveCL(); closeTool(); };
$('#langBtn').onclick=()=>{
  LANG=(LANG==='en')?'ru':'en';
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
</script>
</body>
</html>
"""
