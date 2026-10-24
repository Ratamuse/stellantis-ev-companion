#!/usr/bin/env python3
"""stellantis-ev-companion : page web compagnon de psa_car_controller pour les voitures electriques Stellantis
(Peugeot, Citroen, DS, Opel...) : arret de charge fiable, heures creuses, clim, preconditionnement selon la
meteo, historique, notifications.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import json
import os
import re
import html
import secrets
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONFIG_FILE = os.environ.get("CONFIG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))
with open(CONFIG_FILE, encoding="utf-8") as _f:
    CONFIG = json.load(_f)
VIN = CONFIG["vin"]
PSACC = CONFIG.get("psacc_url", "http://127.0.0.1:5000")
PORT = int(CONFIG.get("port", 8080))
BRAND, MODEL = CONFIG.get("brand", ""), CONFIG.get("model", "Ma voiture")
STATE_DIR = os.environ.get("STATE_DIRECTORY", os.path.dirname(os.path.abspath(__file__)))
CLIM_FILE = os.path.join(STATE_DIR, "clim.json")
AUTO_FILE = os.path.join(STATE_DIR, "auto_charge.json")
NOTIF_FILE = os.path.join(STATE_DIR, "notif.json")
PREHEAT_FILE = os.path.join(STATE_DIR, "preheat.json")
REPORT_FILE = os.path.join(STATE_DIR, "report.json")
CHARGE_LOG = os.path.join(STATE_DIR, "charges.json")
CAR_FILE = os.path.join(STATE_DIR, "car.json")
NTFY_SERVER = "https://ntfy.sh"
OFFPEAK = [tuple(p) for p in CONFIG.get("offpeak", [["22:00", "06:00"]])]  # plages heures creuses (debut, fin)
SWITCH_DELAY = 5  # minutes apres la fin d'une plage avant de viser la suivante
BATTERY_KWH = float(CONFIG.get("battery_kwh", 46))  # capacite utile, pour estimer une charge
DEPARTURES = CONFIG.get("departures", [])  # [{"days": [0..6], "time": "HH:MM", "place", "lat", "lon"}]
WEATHER = CONFIG.get("weather") or (DEPARTURES[0] if DEPARTURES else None)  # lieu de reference meteo
COMMUTE = CONFIG.get("commute")  # {"label": "Maison <-> Travail", "km": 25}, facultatif
APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_TYPES = {"svg": "image/svg+xml", "png": "image/png", "webp": "image/webp", "jpg": "image/jpeg"}
LATE_LIMIT = timedelta(minutes=10)  # au-dela (ex. Raspberry eteint), on saute ce declenchement

CHARGING = {"InProgress": "En charge", "Disconnected": "Débranchée", "Stopped": "En attente",
            "Finished": "Charge terminée", "Failure": "Erreur de charge"}
CLIM = {"Enabled": "Clim/chauffage en marche", "Disabled": "Clim/chauffage arrêté",
        "Finished": "Clim/chauffage terminé", "Failure": "Clim/chauffage en erreur"}

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<script>(function(){var t;try{t=localStorage.getItem('theme')}catch(e){}document.documentElement.dataset.theme=t==='light'?'light':'dark'})()</script>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07090d" id="tc">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>%MODEL%</title>
<style>
:root{--bg:#07090d;--card:rgba(255,255,255,.045);--line:rgba(255,255,255,.09);--txt:#f2f4f8;--mut:#8a93a3;
 --acc:#2fd3ff;--acc2:#6c5cff;--ok:#3ee08f;--err:#ff6b6b}
:root{--soft:rgba(255,255,255,.06);--soft2:rgba(255,255,255,.12);--field:rgba(255,255,255,.04);--sw:rgba(255,255,255,.16);--ring:rgba(255,255,255,.07);--ink:#fff;--toast:#161d2b;--glow:#1c2d4a;--scheme:dark;--shadow:none}
html[data-theme=light]{--bg:#f2f3f5;--card:#fff;--line:rgba(0,0,0,.09);--txt:#15181d;--mut:#6b7280;--acc:#0a8fd6;--acc2:#5b4bff;--ok:#15803d;--err:#c62828;--soft:rgba(0,0,0,.05);--soft2:rgba(0,0,0,.1);--field:#fff;--sw:rgba(0,0,0,.18);--ring:rgba(0,0,0,.08);--ink:#15181d;--toast:#fff;--glow:#dfe8f5;--scheme:light;--shadow:0 2px 14px rgba(0,0,0,.07)}
.card{box-shadow:var(--shadow)}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;min-height:100vh;color:var(--txt);font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
 background:radial-gradient(900px 520px at 50% -160px,var(--glow) 0%,transparent 65%),var(--bg);background-attachment:fixed}
main{max-width:440px;margin:0 auto;padding:max(16px,env(safe-area-inset-top)) 16px 48px}
header{display:flex;align-items:center;justify-content:space-between;padding:4px 2px 14px}
.brand{display:flex;align-items:center;gap:12px}
.brand img{height:40px;display:block}
.word{text-transform:uppercase;font-weight:700;letter-spacing:.34em;font-size:12px;color:var(--mut)}
.model{font-size:26px;font-weight:300;letter-spacing:.02em;line-height:1}
.model b{font-weight:700}
.icon-btn{width:42px;height:42px;border-radius:50%;border:1px solid var(--line);background:var(--card);color:var(--txt);display:grid;place-items:center}
.icon-btn.spin svg{animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
svg.i{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:18px;margin-bottom:14px;
 -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px)}
.card h2{display:flex;align-items:center;gap:8px;margin:0 0 12px;font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}
.hero{display:flex;flex-direction:column;align-items:center;padding:22px 14px 18px}
.heroRow{display:flex;align-items:center;justify-content:space-between;gap:4px;width:100%}
.vcol{display:flex;flex-direction:column;align-items:center;gap:8px;width:74px;flex:none}
.vval{font-size:30px;font-weight:300;line-height:1;white-space:nowrap}
.vval small{font-size:13px;color:var(--mut);margin-left:2px}
.vbar{position:relative;width:16px;height:128px;border-radius:9px;background:var(--ring)}
.vfill{position:absolute;left:0;right:0;bottom:0;height:0;border-radius:9px;background:linear-gradient(0deg,var(--acc),var(--acc2));transition:height 1.2s ease,background .6s}
.vfill.km{background:linear-gradient(0deg,var(--acc2),var(--acc))}
.vmark{position:absolute;left:-6px;right:-6px;height:3px;margin-bottom:-1px;border-radius:2px;background:var(--ink);transition:bottom 1s}
.vlab{font-size:11.5px;color:var(--mut);text-align:center;line-height:1.25;min-height:2.5em}
.heroRow .car{flex:1;min-width:0;max-width:220px;width:100%;height:auto;margin:0;filter:drop-shadow(0 8px 10px rgba(0,0,0,.28));transition:filter .6s}
#hero.charging .vfill:not(.km){background:linear-gradient(0deg,#12b76a,#3ee08f);animation:bglow 2.6s ease-in-out infinite}
#hero.charging .car{animation:cglow 2.6s ease-in-out infinite}
#hero.unplugged .car{animation:rglow 3.2s ease-in-out infinite}
#hero.waiting .car{animation:wglow 3.2s ease-in-out infinite}
@keyframes wglow{0%,100%{filter:drop-shadow(0 0 4px rgba(47,140,255,.25))}50%{filter:drop-shadow(0 0 16px rgba(47,140,255,.85))}}
@keyframes rglow{0%,100%{filter:drop-shadow(0 0 4px rgba(255,77,77,.25))}50%{filter:drop-shadow(0 0 16px rgba(255,77,77,.8))}}
@keyframes bglow{0%,100%{box-shadow:0 0 4px rgba(62,224,143,.35)}50%{box-shadow:0 0 18px 5px rgba(62,224,143,.9)}}
@keyframes cglow{0%,100%{filter:drop-shadow(0 0 4px rgba(62,224,143,.25))}50%{filter:drop-shadow(0 0 16px rgba(62,224,143,.85))}}
.gauge{position:relative;width:220px;height:220px}
.gauge svg{position:relative;z-index:1}
.car{width:120px;height:auto;margin:-6px 0 2px;filter:drop-shadow(0 4px 6px rgba(0,0,0,.25))}
.gauge::before{content:"";position:absolute;inset:-22px;border-radius:50%;opacity:0;transition:opacity .8s;
 background:radial-gradient(circle closest-side,transparent 64%,rgba(62,224,143,.6) 79%,transparent 100%)}
.gauge.charging::before{animation:halo 2.6s ease-in-out infinite}
@keyframes halo{0%,100%{opacity:.25}50%{opacity:1}}
.gauge.charging #g stop:first-child{stop-color:#3ee08f}
.gauge.charging #g stop:last-child{stop-color:#12b76a}
.gauge svg{transform:rotate(-90deg);display:block}
.center{position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center}
.lvl{font-size:44px;font-weight:200;letter-spacing:-.03em;line-height:1}
.lvl small{font-size:22px;color:var(--mut);font-weight:300}
.lim{font-size:13px;color:var(--mut);margin-top:6px}
.pills{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:16px}
.pill{display:inline-flex;gap:6px;align-items:center;padding:7px 13px;border-radius:99px;background:var(--soft);color:var(--mut);font-size:13px}
.pill.on{background:rgba(47,211,255,.13);color:var(--acc)}
.pill:empty{display:none}
.range{margin-top:18px;padding-top:14px;border-top:1px solid var(--line);width:100%;text-align:center}
.rkm{font-size:30px;font-weight:300}
.rkm small{font-size:15px;color:var(--mut)}
.rsub{font-size:13px;color:var(--mut);margin-top:2px}
.head{display:flex;align-items:baseline;justify-content:space-between}
.value{font-size:38px;font-weight:200}
.value small{font-size:18px;color:var(--mut)}
.chips{display:flex;gap:8px;margin:12px 0 4px}
.chip{flex:1;padding:11px 0;border-radius:14px;border:1px solid var(--line);background:transparent;color:var(--txt);font-size:15px;transition:.15s}
.chip.sel{background:linear-gradient(135deg,var(--acc),var(--acc2));border-color:transparent;color:#fff;font-weight:600}
.chip:disabled{opacity:.3}
.days .chip{padding:10px 0;font-size:14px}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:6px;border-radius:6px;margin:14px 0 6px;outline:none;
 background:linear-gradient(90deg,var(--acc),var(--acc2) var(--p,60%),var(--soft2) var(--p,60%))}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:26px;height:26px;border-radius:50%;background:#fff;box-shadow:0 2px 12px rgba(0,0,0,.6)}
input[type=range]::-moz-range-thumb{width:26px;height:26px;border:0;border-radius:50%;background:#fff}
.line{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 0 4px;margin-top:10px;border-top:1px solid var(--line)}
.switch{position:relative;width:50px;height:30px;flex:none}
.switch input{position:absolute;opacity:0;width:0;height:0}
.switch span{position:absolute;inset:0;border-radius:30px;background:var(--sw);transition:.2s}
.switch span:before{content:"";position:absolute;width:24px;height:24px;left:3px;top:3px;border-radius:50%;background:#fff;transition:.2s}
.switch input:checked+span{background:var(--acc)}
.switch input:checked+span:before{transform:translateX(20px)}
input[type=time]{background:var(--field);border:1px solid var(--line);border-radius:12px;color:var(--txt);font-size:20px;padding:6px 10px;color-scheme:var(--scheme);font-family:inherit}
input[type=time]:disabled{opacity:.3}
.btn{width:100%;padding:15px;border:0;border-radius:16px;font-size:16px;font-weight:600;color:#fff;margin-top:14px;
 background:linear-gradient(135deg,var(--acc),var(--acc2));box-shadow:0 10px 28px rgba(60,140,255,.28);display:flex;gap:8px;align-items:center;justify-content:center}
.btn:active{transform:scale(.98)}
.btn.sm{font-size:14px;padding:13px 6px}
.btn.ghost{background:transparent;border:1px solid var(--line);box-shadow:none;color:var(--txt)}
.row{display:flex;gap:10px}
[hidden]{display:none!important}
.dep{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-top:1px solid var(--line);cursor:pointer;font-size:14px}
.dep:first-child{border-top:0}
.dep.off{opacity:.4;text-decoration:line-through}
.back{display:inline-block;color:var(--acc);text-decoration:none;margin:0 0 12px 4px;font-size:15px}
select{background:var(--field);border:1px solid var(--line);border-radius:12px;color:var(--txt);font-size:18px;padding:6px 8px;color-scheme:var(--scheme);font-family:inherit}
select:disabled{opacity:.3}
.txt{flex:1;min-width:0;background:var(--field);border:1px solid var(--line);border-radius:12px;color:var(--txt);font-size:16px;padding:9px 10px;font-family:inherit}
.num{width:82px;background:var(--field);border:1px solid var(--line);border-radius:12px;color:var(--txt);font-size:18px;padding:6px 8px;color-scheme:var(--scheme);font-family:inherit}
.topic{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:16px;background:var(--soft);border-radius:10px;padding:10px 12px;user-select:all;-webkit-user-select:all;word-break:break-all}
.seg{display:flex;gap:4px;padding:4px;border-radius:14px;background:var(--soft);margin-bottom:12px}
.seg button{flex:1;padding:10px 4px;border:0;border-radius:11px;background:transparent;color:var(--mut);font-size:14px}
.seg button.sel{background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;font-weight:600}
.row .btn{margin-top:0}
.hint{color:var(--mut);font-size:12.5px;margin-top:6px}
.next{color:var(--acc);font-size:13px;margin-top:10px;min-height:1em}
#toast{position:fixed;left:50%;bottom:calc(24px + env(safe-area-inset-bottom));transform:translate(-50%,140px);background:var(--toast);border:1px solid var(--line);
 padding:12px 18px;border-radius:14px;transition:transform .3s;max-width:90%;box-shadow:0 10px 30px rgba(0,0,0,.5)}
#toast.show{transform:translate(-50%,0)}
</style></head><body><main>

<header>
 <div class="brand">
  <img src="logo" alt="" onerror="this.remove();document.getElementById('word').hidden=false">
  <div><div class="word" id="word" hidden>%BRAND%</div><div class="model"><b>%MODEL%</b></div></div>
 </div>
 <div style="display:flex;gap:8px"><a class="icon-btn" href="historique" aria-label="Historique"><svg class="i" viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg></a>
 <a class="icon-btn" href="#reglages" aria-label="Réglages"><svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></a>
 <button class="icon-btn" id="theme" aria-label="Mode jour / nuit"><svg class="i" viewBox="0 0 24 24" id="themeic"></svg></button>
 <button class="icon-btn" id="refresh" aria-label="Actualiser"><svg class="i" viewBox="0 0 24 24"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg></button></div>
</header>

<div id="v_main">

<section class="card hero" id="hero">
 <div class="heroRow">
  <div class="vcol">
   <div class="vval"><span id="lvl">–</span><small>%</small></div>
   <div class="vbar"><div class="vfill" id="bfill"></div><div class="vmark" id="tick"></div></div>
   <div class="vlab" id="lim"></div>
  </div>
  <img class="car" src="car" alt="" onerror="this.remove();document.getElementById('carsvg').removeAttribute('hidden')">
  <svg class="car" id="carsvg" viewBox="0 0 240 110" hidden aria-hidden="true"><path d="M18 78q0-14 14-17l26-6 24-22q8-7 20-7h52q12 0 21 8l22 20 26 5q15 3 15 18v10q0 6-6 6H24q-6 0-6-6z" style="fill:var(--soft2);stroke:var(--mut)" stroke-width="2.5" stroke-linejoin="round"/><path d="M92 36q5-5 12-5h46q8 0 13 5l15 15H78z" style="fill:var(--soft);stroke:var(--mut)" stroke-width="2"/><circle cx="66" cy="90" r="15" style="fill:var(--bg);stroke:var(--mut)" stroke-width="4"/><circle cx="182" cy="90" r="15" style="fill:var(--bg);stroke:var(--mut)" stroke-width="4"/></svg>
  <div class="vcol">
   <div class="vval"><span id="kmv">–</span><small>km</small></div>
   <div class="vbar"><div class="vfill km" id="kfill"></div></div>
   <div class="vlab" id="klab">à ton rythme</div>
  </div>
 </div>
 <div class="pills"><span class="pill" id="chg"></span><span class="pill" id="cst"></span></div>
 <div class="range" id="rng" hidden></div>
</section>

<section class="card">
 <h2><svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>Début de la charge</h2>
 <div class="seg"><button id="m_auto">Heures creuses auto</button><button id="m_man">Heure choisie</button></div>
 <div id="p_auto">
  <div class="hint" id="ainfo"></div>
 </div>
 <div id="p_man" hidden>
  <div class="line" style="border:0;margin-top:0">
   <span>Commencer à</span>
   <input type="time" id="start" value="02:10">
  </div>
  <button class="btn" id="startset">Envoyer à la voiture</button>
 </div>
 <div class="next" id="startcur"></div>
 <div class="line" style="padding-top:14px">
  <span class="hint" style="margin:0">Besoin de rouler bientôt ?</span>
  <button class="btn ghost sm" id="startnow" style="width:auto;margin:0;padding:10px 14px">⚡ Charger maintenant</button>
 </div>
</section>

<section class="card">
 <h2><svg class="i" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>Fin de la charge</h2>
 <div class="head"><span class="hint">Arrêter à</span><span class="value"><span id="pv">80</span><small> %</small></span></div>
 <input type="range" id="pct" min="50" max="100" step="1" value="80">
 <div class="chips"><button class="chip" data-p="80">80 %</button><button class="chip" data-p="90">90 %</button><button class="chip" data-p="100">100 %</button></div>
 <div class="line" id="stopline">
  <span>Arrêter aussi à</span>
  <span class="row" style="align-items:center"><input type="time" id="hr" value="07:10" disabled>
  <label class="switch"><input type="checkbox" id="hon"><span></span></label></span>
 </div>
 <div class="next" id="stopauto" hidden></div>
 <div class="hint">Enregistré automatiquement. La charge s'arrête au premier des deux atteint.</div>
</section>


<section class="card">
 <h2><svg class="i" viewBox="0 0 24 24"><path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"/></svg>Clim / chauffage</h2>
 <div class="row">
  <button class="btn" id="con">Démarrer</button>
  <button class="btn ghost" id="coff">Arrêter</button>
 </div>
 <div class="hint">La voiture chauffe ou refroidit seule selon la température réglée.</div>
 <div class="line">
  <span>Programmer</span>
  <span class="row" style="align-items:center"><input type="time" id="ptime" value="07:30" disabled>
  <label class="switch"><input type="checkbox" id="pon"><span></span></label></span>
 </div>
 <div class="chips days">
  <button class="chip" data-d="0">L</button><button class="chip" data-d="1">M</button><button class="chip" data-d="2">M</button>
  <button class="chip" data-d="3">J</button><button class="chip" data-d="4">V</button><button class="chip" data-d="5">S</button><button class="chip" data-d="6">D</button>
 </div>
 <div class="hint">Aucun jour sélectionné = une seule fois</div>
 <div class="next" id="pnext"></div>
 <button class="btn" id="psave">Enregistrer la programmation</button>
</section>

</div>

<div id="v_set" hidden>
 <a class="back" href="#">&larr; Retour</a>
<section class="card">
 <h2><svg class="i" viewBox="0 0 24 24"><path d="M5 17h14M6 17l1.5-6h9L18 17M8 11l1.5-4h5L16 11"/><circle cx="8" cy="18" r="1.5"/><circle cx="16" cy="18" r="1.5"/></svg>Ma voiture</h2>
 <div class="row" style="gap:8px">
  <input type="text" id="c_brand" class="txt" placeholder="Marque (Peugeot…)" maxlength="30">
  <input type="text" id="c_model" class="txt" placeholder="Modèle (e-208…)" maxlength="30">
 </div>
 <div class="hint">Affiché en haut de la page. Pour ta propre photo, dépose car.png (ou .webp, .jpg) à côté de app.py.</div>
</section>

<section class="card">
 <h2><svg class="i" viewBox="0 0 24 24"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>Notifications</h2>
 <div class="line" style="border:0;margin-top:0;padding-top:0">
  <span>Rappel si pas branchée</span>
  <label class="switch"><input type="checkbox" id="n_plug"><span></span></label>
 </div>
 <div class="row" style="align-items:center;gap:8px;flex-wrap:wrap;margin-top:6px">
  <span class="hint" style="margin:0">à</span><input type="time" id="n_time" value="21:00">
  <span class="hint" style="margin:0">si batterie sous</span>
  <select id="n_lvl"><option>30</option><option>40</option><option>50</option><option>60</option><option>70</option><option>80</option></select>
  <span class="hint" style="margin:0">%</span>
 </div>
 <div class="line"><span>Fin de charge ou interruption</span><label class="switch"><input type="checkbox" id="n_done"><span></span></label></div>
 <div class="line"><span>Charge en heures pleines</span><label class="switch"><input type="checkbox" id="n_peak"><span></span></label></div>
 <div class="line" style="display:block">
  <div class="hint" style="margin:0 0 8px">Dans l'appli <b>ntfy</b>, abonne-toi à ce sujet :</div>
  <div class="topic" id="n_topic">–</div>
 </div>
 <button class="btn ghost" id="n_test">Envoyer une notification de test</button>
</section>

<section class="card">
 <h2><svg class="i" viewBox="0 0 24 24"><path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"/></svg>Préchauffage selon la météo</h2>
 <div class="line" style="border:0;margin-top:0;padding-top:0">
  <span>Aux heures de départ</span>
  <label class="switch"><input type="checkbox" id="ph_on"><span></span></label>
 </div>
 <div class="row" style="align-items:center;gap:8px;flex-wrap:wrap;margin-top:6px">
  <span class="hint" style="margin:0">s'il fait moins de</span>
  <select id="ph_cold"><option>0</option><option>2</option><option>3</option><option>5</option><option>7</option><option>8</option><option>9</option><option>10</option><option>11</option><option>12</option><option>13</option><option>14</option><option>15</option></select>
  <span class="hint" style="margin:0">°C ou plus de</span>
  <select id="ph_hot"><option>22</option><option>24</option><option>25</option><option>26</option><option>28</option><option>30</option></select>
  <span class="hint" style="margin:0">°C</span>
 </div>
 <div class="row" style="align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px">
  <span class="hint" style="margin:0">lancé</span>
  <select id="ph_lead"><option>15</option><option>20</option><option>25</option><option>30</option><option>40</option><option>45</option></select>
  <span class="hint" style="margin:0">min avant le départ</span>
 </div>
 <div class="line" style="display:block">
  <div class="hint" style="margin:0 0 4px">Prochains départs — touche un jour pour l'annuler :</div>
  <div id="ph_list"></div>
 </div>
 <div class="hint">Les départs (jours, heure, lieu) se règlent dans config.json.</div>
</section>

<section class="card">
 <h2><svg class="i" viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>Bilan mensuel</h2>
 <div class="line" style="border:0;margin-top:0;padding-top:0">
  <span>Le 1er du mois à 9 h</span>
  <label class="switch"><input type="checkbox" id="b_on"><span></span></label>
 </div>
 <div class="hint" style="margin:6px 0 8px">Comparaison avec une voiture essence :</div>
 <div class="row" style="align-items:center;gap:8px;flex-wrap:wrap">
  <input type="number" id="b_l100" min="2" max="20" step="0.1" class="num">
  <span class="hint" style="margin:0">L/100 km à</span>
  <input type="number" id="b_fuel" min="0.5" max="5" step="0.01" class="num">
  <span class="hint" style="margin:0">€/L</span>
 </div>
 <button class="btn ghost" id="b_now">Recevoir le bilan du mois en cours</button>
</section>
</div>

<div id="toast"></div>
</main><script>
const SUN='<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const MOON='<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
function setTheme(t){document.documentElement.dataset.theme=t;try{localStorage.setItem('theme',t)}catch(e){}
 document.getElementById('tc').content=t==='light'?'#f2f3f5':'#07090d';
 document.getElementById('themeic').innerHTML=t==='light'?MOON:SUN;}
setTheme(document.documentElement.dataset.theme);
document.getElementById('theme').onclick=()=>setTheme(document.documentElement.dataset.theme==='light'?'dark':'light');
const $=id=>document.getElementById(id);
const C=590.6,dayBtns=[...document.querySelectorAll('[data-d]')];
let toastT;
function toast(t,ok=true){const e=$('toast');e.textContent=t;e.style.color=ok?'var(--txt)':'var(--err)';
 e.classList.add('show');clearTimeout(toastT);toastT=setTimeout(()=>e.classList.remove('show'),2800);}
function showPct(v){v=+v;$('pct').value=v;$('pv').textContent=v;$('pct').style.setProperty('--p',((v-50)*2)+'%');
 document.querySelectorAll('[data-p]').forEach(b=>b.classList.toggle('sel',+b.dataset.p==v));
 $('tick').style.bottom=v+'%';$('tick').hidden=v>=100;
 $('lim').textContent=v<100?'limite '+v+' %':'sans limite';}
function showMode(isAuto){$('m_auto').classList.toggle('sel',isAuto);$('m_man').classList.toggle('sel',!isAuto);
 $('p_auto').hidden=!isAuto;$('p_man').hidden=isAuto;}
let saveT;
function saveEnd(){clearTimeout(saveT);saveT=setTimeout(()=>act('api/set',{percentage:+$('pct').value,
 stop_hour:$('hon').checked?$('hr').value:null},'Fin de charge enregistrée ✔'),600);}
function progUi(){const on=$('pon').checked;$('ptime').disabled=!on;dayBtns.forEach(b=>b.disabled=!on);}
function fill(s){
 $('lvl').textContent=s.level==null?'–':s.level;
 $('bfill').style.height=(s.level||0)+'%';
 $('chg').textContent=s.charging||'';$('hero').classList.toggle('charging',s.charging=='En charge');$('hero').classList.toggle('unplugged',s.status=='Disconnected');$('hero').classList.toggle('waiting',s.status=='Stopped');$('chg').classList.toggle('on',s.charging=='En charge');
 $('cst').textContent=s.clim_status||'';$('cst').classList.toggle('on',/en marche/.test(s.clim_status||''));
 const r=s.range,lv=s.level||0,est=r&&r.km!=null?r.km:(r?r.car_km:null);
 $('kmv').textContent=est==null?'–':est;
 $('kfill').style.height=Math.max(0,Math.min(100,(lv-5)/95*100))+'%';
 const full=est!=null&&lv>5?Math.round(est*95/(lv-5)):null;
 $('klab').innerHTML=(r&&r.km!=null?'à ton rythme':'selon la voiture')+(full?'<br>plein : '+full+' km':'');
 $('rng').hidden=!r;
 if(r){const car=r.car_km!=null?'voiture : '+r.car_km+' km':'';
  $('rng').innerHTML=r.km==null
   ?'<div class="rsub">Autonomie à ton rythme : encore quelques trajets à enregistrer ('+r.trips+'/2)</div><div class="rsub">'+car+'</div>'
   :'<div class="rsub">sous 90 km/h · entre '+r.low+' et '+r.high+' km · '+String(r.kwh100).replace('.',',')+' kWh/100'
    +(r.temp!=null?' à '+r.temp+' °C':'')+'</div>'
    +'<div class="rsub">'+(r.commutes!=null?'≈ '+r.commutes+' trajet'+(r.commutes>1?'s':'')+' '+r.commute_label+(car?' · ':''):'')+car+'</div>';}
 if(s.threshold!=null){showPct(s.threshold);
  $('hon').checked=!!s.stop_hour;$('hr').disabled=!s.stop_hour;if(s.stop_hour)$('hr').value=s.stop_hour;}
 if(s.start_hour)$('start').value=s.start_hour;
 $('startcur').textContent=s.start_hour?'Heure enregistrée dans la voiture : '+s.start_hour:'';
 showMode(s.auto.enabled);
 $('stopline').hidden=s.auto.enabled;$('stopauto').hidden=!s.auto.enabled;
 $('stopauto').textContent='Heures creuses auto : la charge s’arrête aussi à la fin de chaque plage ('
  +s.auto.plages.map(p=>p.split('–')[1]).join(' et ')+') et reprend à la suivante.';
 const n=s.notif;$('n_plug').checked=n.plug;$('n_time').value=n.plug_time;$('n_lvl').value=String(n.plug_level);
 $('n_time').disabled=$('n_lvl').disabled=!n.plug;$('n_done').checked=n.done;$('n_peak').checked=n.peak;$('n_topic').textContent=n.topic;
 if(document.activeElement!==$('c_brand'))$('c_brand').value=s.car.brand;if(document.activeElement!==$('c_model'))$('c_model').value=s.car.model;
 document.querySelector('.word').textContent=s.car.brand;document.getElementById('word').hidden=!s.car.brand;document.querySelector('.model b').textContent=s.car.model;document.title=s.car.model;
 const b=s.report;$('b_on').checked=b.enabled;
 if(document.activeElement!==$('b_l100'))$('b_l100').value=b.l100;if(document.activeElement!==$('b_fuel'))$('b_fuel').value=b.fuel;
 const ph=s.preheat;$('ph_on').checked=ph.enabled;$('ph_cold').value=String(ph.cold);$('ph_hot').value=String(ph.hot);
 $('ph_lead').value=String(ph.lead);['ph_cold','ph_hot','ph_lead'].forEach(id=>$(id).disabled=!ph.enabled);
 $('ph_list').innerHTML=ph.next.map(d=>{const t=d.temp==null?'–':String(d.temp).replace('.',',')+' °C';
  const ic=d.temp==null?'':d.temp<=ph.cold?' ❄️':d.temp>=ph.hot?' ☀️':'';
  const day=new Date(d.date+'T12:00').toLocaleDateString('fr-FR',{weekday:'short',day:'numeric',month:'short'});
  return '<div class="dep'+(d.skip?' off':'')+'" data-date="'+d.date+'" data-skip="'+(d.skip?1:0)+'"><span>'+day+' · '+d.time+' · '+d.place
   +'</span><span>'+(d.skip?'annulé':t+ic)+'</span></div>';}).join('');
 document.querySelectorAll('.dep').forEach(e=>e.onclick=()=>act('api/preheat_skip',{date:e.dataset.date,skip:e.dataset.skip=='0'},
  e.dataset.skip=='0'?'Préchauffage annulé pour ce jour':'Préchauffage rétabli pour ce jour'));
 $('ainfo').textContent='La page règle seule l’heure de début sur la prochaine plage creuse ('
  +s.auto.plages.join(' ou ')+'). Prochain début : '+s.auto.target+'.';
 const p=s.clim;$('pon').checked=p.enabled;if(p.time)$('ptime').value=p.time;
 dayBtns.forEach(b=>b.classList.toggle('sel',p.days.includes(+b.dataset.d)));progUi();
 $('pnext').textContent=p.enabled&&p.next?'Prochain démarrage '+p.next:'';}
async function call(url,body){const r=await fetch(url,body===undefined?{}:{method:'POST',
 headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const s=await r.json();if(s.error)throw new Error(s.error);return s;}
async function act(url,body,ok){toast('Envoi…');
 try{fill(await call(url,body));toast(ok);}catch(e){toast('Erreur : '+e.message,false);}}
async function refresh(){$('refresh').classList.add('spin');
 try{fill(await call('api/state'));}catch(e){toast('Erreur : '+e.message,false);}
 $('refresh').classList.remove('spin');}
$('pct').oninput=e=>showPct(e.target.value);
$('pct').onchange=saveEnd;
document.querySelectorAll('[data-p]').forEach(b=>b.onclick=()=>{showPct(b.dataset.p);saveEnd();});
$('hon').onchange=()=>{$('hr').disabled=!$('hon').checked;saveEnd();};
$('hr').onchange=saveEnd;
$('m_auto').onclick=()=>{showMode(true);act('api/charge_auto',{enabled:true},'Heures creuses auto activées ✔');};
$('m_man').onclick=()=>{showMode(false);act('api/charge_auto',{enabled:false},'Choisis l’heure puis envoie-la à la voiture');};
$('pon').onchange=progUi;
dayBtns.forEach(b=>b.onclick=()=>b.classList.toggle('sel'));
$('refresh').onclick=refresh;
function saveNotif(){act('api/notif',{plug:$('n_plug').checked,plug_time:$('n_time').value,plug_level:+$('n_lvl').value,
 done:$('n_done').checked,peak:$('n_peak').checked},'Notifications enregistrées ✔');}
['n_plug','n_time','n_lvl','n_done','n_peak'].forEach(id=>$(id).onchange=saveNotif);
['b_on','b_l100','b_fuel'].forEach(id=>$(id).onchange=()=>act('api/report',{enabled:$('b_on').checked,
 l100:+$('b_l100').value,fuel:+$('b_fuel').value},'Bilan mensuel enregistré ✔'));
$('b_now').onclick=()=>act('api/report_now',{},'Bilan envoyé ✔');
function savePreheat(){act('api/preheat',{enabled:$('ph_on').checked,cold:+$('ph_cold').value,hot:+$('ph_hot').value,
 lead:+$('ph_lead').value},'Préchauffage enregistré ✔');}
['ph_on','ph_cold','ph_hot','ph_lead'].forEach(id=>$(id).onchange=savePreheat);
['c_brand','c_model'].forEach(id=>$(id).onchange=()=>act('api/car',{brand:$('c_brand').value,model:$('c_model').value},'Nom de la voiture enregistré ✔'));
$('n_test').onclick=()=>act('api/notif_test',{},'Notification de test envoyée ✔');
$('startset').onclick=()=>act('api/charge_start',{time:$('start').value},'Heure de début envoyée ✔');
$('startnow').onclick=()=>{if(confirm('Lancer la charge tout de suite, en ignorant l’heure de début ?'))
 act('api/charge_start',{now:true},'Charge immédiate demandée ✔');};
$('con').onclick=()=>act('api/clim',{on:true},'Démarrage demandé ✔');
$('coff').onclick=()=>act('api/clim',{on:false},'Arrêt demandé ✔');
$('psave').onclick=()=>act('api/clim_prog',{enabled:$('pon').checked,time:$('ptime').value,
 days:dayBtns.filter(b=>b.classList.contains('sel')).map(b=>+b.dataset.d)},'Programmation enregistrée ✔');
function view(){const s=location.hash=='#reglages';$('v_main').hidden=s;$('v_set').hidden=!s;window.scrollTo(0,0);}
window.onhashchange=view;view();
showPct(80);refresh();
</script></body></html>"""

HISTORY = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<script>(function(){var t;try{t=localStorage.getItem('theme')}catch(e){}document.documentElement.dataset.theme=t==='light'?'light':'dark'})()</script>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07090d" id="tc">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Historique %MODEL%</title>
<style>
:root{--bg:#07090d;--card:rgba(255,255,255,.045);--line:rgba(255,255,255,.09);--txt:#f2f4f8;--mut:#8a93a3;
 --acc:#2fd3ff;--acc2:#6c5cff;--err:#ff6b6b}
:root{--soft:rgba(255,255,255,.06);--soft2:rgba(255,255,255,.12);--field:rgba(255,255,255,.04);--sw:rgba(255,255,255,.16);--ring:rgba(255,255,255,.07);--ink:#fff;--toast:#161d2b;--glow:#1c2d4a;--scheme:dark;--shadow:none}
html[data-theme=light]{--bg:#f2f3f5;--card:#fff;--line:rgba(0,0,0,.09);--txt:#15181d;--mut:#6b7280;--acc:#0a8fd6;--acc2:#5b4bff;--ok:#15803d;--err:#c62828;--soft:rgba(0,0,0,.05);--soft2:rgba(0,0,0,.1);--field:#fff;--sw:rgba(0,0,0,.18);--ring:rgba(0,0,0,.08);--ink:#15181d;--toast:#fff;--glow:#dfe8f5;--scheme:light;--shadow:0 2px 14px rgba(0,0,0,.07)}
.card{box-shadow:var(--shadow)}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;min-height:100vh;color:var(--txt);font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
 background:radial-gradient(900px 520px at 50% -160px,var(--glow) 0%,transparent 65%),var(--bg);background-attachment:fixed}
main{max-width:440px;margin:0 auto;padding:max(16px,env(safe-area-inset-top)) 16px 48px}
header{display:flex;align-items:center;gap:12px;padding:4px 2px 14px}
.title{font-size:26px;font-weight:300}
.title b{font-weight:700}
.icon-btn{width:42px;height:42px;border-radius:50%;border:1px solid var(--line);background:var(--card);color:var(--txt);display:grid;place-items:center;text-decoration:none;flex:none}
.icon-btn:disabled{opacity:.3}
svg.i{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:18px;margin-bottom:14px;
 -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px)}
.card h2{margin:0 0 12px;font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}
.month{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.month span{font-size:18px;font-weight:600;text-transform:capitalize}
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.odo{display:flex;justify-content:space-between;align-items:baseline;padding:0 4px 12px;color:var(--mut);font-size:14px}
.odo b{color:var(--txt);font-size:20px;font-weight:400}
.tile{background:var(--field);border:1px solid var(--line);border-radius:18px;padding:14px}
.tile .k{font-size:12px;color:var(--mut)}
.tile .v{font-size:28px;font-weight:200;line-height:1.2;margin-top:4px}
.tile .v small{font-size:14px;color:var(--mut)}
.tile .s{font-size:12px;color:var(--mut);margin-top:2px}
.seg{display:flex;gap:4px;padding:4px;border-radius:14px;background:var(--soft);margin-bottom:12px}
.seg button{flex:1;padding:9px 4px;border:0;border-radius:11px;background:transparent;color:var(--mut);font-size:13px}
.seg button.sel{background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;font-weight:600}
.chart{position:relative}
.chart svg{display:block;width:100%;height:auto;overflow:visible}
.chart .bar{cursor:pointer}
#tip{position:absolute;pointer-events:none;background:var(--toast);border:1px solid var(--line);border-radius:10px;padding:6px 10px;
 font-size:13px;white-space:nowrap;transform:translate(-50%,-100%);display:none}
.item{display:flex;justify-content:space-between;gap:10px;padding:12px 0;border-top:1px solid var(--line)}
.item:first-of-type{border-top:0;padding-top:2px}
.item .a{font-weight:600}
.item .b{font-size:13px;color:var(--mut)}
.item .r{text-align:right}
.empty{color:var(--mut);font-size:14px}
.note{color:var(--mut);font-size:12.5px;margin-top:10px}
</style></head><body><main>

<header>
 <a class="icon-btn" href="./" aria-label="Retour"><svg class="i" viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg></a>
 <div class="title">Historique <b>%MODEL%</b></div>
 <button class="icon-btn" id="theme" aria-label="Mode jour / nuit" style="margin-left:auto"><svg class="i" viewBox="0 0 24 24" id="themeic"></svg></button>
</header>

<section class="card">
 <div class="month">
  <button class="icon-btn" id="prev" aria-label="Mois précédent"><svg class="i" viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg></button>
  <span id="mname">–</span>
  <button class="icon-btn" id="next" aria-label="Mois suivant"><svg class="i" viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></svg></button>
 </div>
 <div class="odo"><span>Compteur</span><b><span id="s_odo">–</span> km</b></div>
 <div class="tiles">
  <div class="tile"><div class="k">Distance</div><div class="v"><span id="s_km">–</span><small> km</small></div><div class="s" id="s_trips"></div></div>
  <div class="tile"><div class="k">Consommation</div><div class="v"><span id="s_c">–</span><small> kWh/100</small></div><div class="s" id="s_kwh"></div></div>
  <div class="tile"><div class="k">Énergie chargée</div><div class="v"><span id="s_e">–</span><small> kWh</small></div><div class="s" id="s_ch"></div></div>
  <div class="tile"><div class="k">Coût des charges</div><div class="v"><span id="s_cost">–</span><small> €</small></div><div class="s" id="s_100"></div></div>
 </div>
</section>

<section class="card">
 <h2>Par mois</h2>
 <div class="seg"><button data-m="kwh100" class="sel">Conso</button><button data-m="km">Distance</button><button data-m="cost">Coût</button></div>
 <div class="chart"><svg id="chart" viewBox="0 0 400 170"></svg><div id="tip"></div></div>
</section>

<section class="card">
 <h2>Trajets du mois</h2>
 <div id="trips"></div>
 <div class="note" id="tnote"></div>
</section>

<section class="card">
 <h2>Charges du mois</h2>
 <div id="charges"></div>
 <div class="note" id="cnote"></div>
</section>

</main><script>
const SUN='<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const MOON='<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
function setTheme(t){document.documentElement.dataset.theme=t;try{localStorage.setItem('theme',t)}catch(e){}
 document.getElementById('tc').content=t==='light'?'#f2f3f5':'#07090d';
 document.getElementById('themeic').innerHTML=t==='light'?MOON:SUN;}
setTheme(document.documentElement.dataset.theme);
document.getElementById('theme').onclick=()=>setTheme(document.documentElement.dataset.theme==='light'?'dark':'light');
const $=id=>document.getElementById(id);
const MOIS=['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'];
const METRICS={kwh100:{u:'kWh/100 km',d:1},km:{u:'km',d:0},cost:{u:'€',d:2}};
let H=null,cur=null,metric='kwh100';
function fmt(v,d){return v==null?'–':Number(v).toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d});}
function mname(k){const p=k.split('-');return MOIS[+p[1]-1]+' '+p[0];}
const COURT=['janv','févr','mars','avr','mai','juin','juil','août','sept','oct','nov','déc'];
function short(k){return COURT[+k.split('-')[1]-1];}
function when(iso){const d=new Date(iso);return d.toLocaleDateString('fr-FR',{weekday:'short',day:'numeric',month:'short'})
 +' · '+d.toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'});}
function dur(min){if(min==null)return '–';min=Math.round(min);return min<60?min+' min':Math.floor(min/60)+' h '+String(min%60).padStart(2,'0');}
function plural(n,w){return n+' '+w+(n>1?'s':'');}

function render(){
 const keys=H.months.map(m=>m.month),i=keys.indexOf(cur),m=H.months[i]||{};
 $('mname').textContent=mname(cur);$('prev').disabled=i<=0;$('next').disabled=i>=keys.length-1;
 $('s_odo').textContent=fmt(m.odo,0);$('s_km').textContent=fmt(m.km,0);$('s_trips').textContent=plural(m.trips||0,'trajet');
 $('s_c').textContent=fmt(m.kwh100,1);$('s_kwh').textContent=m.kwh_used!=null?fmt(m.kwh_used,1)+' kWh consommés':'';
 $('s_e').textContent=fmt(m.kwh_charged,1);$('s_ch').textContent=plural(m.charges||0,'charge');
 $('s_cost').textContent=fmt(m.cost,2);$('s_100').textContent=m.cost100!=null?'≈ '+fmt(m.cost100,2)+' € / 100 km':'';
 chart();lists();}

function chart(){
 const svg=$('chart'),W=400,top=24,base=146,mon=H.months.slice(-12),M=METRICS[metric];
 const vals=mon.map(m=>m[metric]),max=Math.max(...vals.map(v=>v||0))||1;
 const slot=W/Math.max(mon.length,6),bw=Math.min(36,slot-8);
 let s='<line x1="0" x2="'+W+'" y1="'+base+'" y2="'+base+'" style="stroke:var(--soft2)"/>';
 mon.forEach((m,j)=>{const v=vals[j],x=j*slot+(slot-bw)/2,cx=x+bw/2,sel=m.month==cur;
  s+='<text x="'+cx+'" y="'+(base+18)+'" text-anchor="middle" font-size="12" style="fill:'+(sel?'var(--txt)':'var(--mut)')+'">'+short(m.month)+'</text>';
  if(v==null){s+='<rect class="bar" data-j="'+j+'" x="'+(j*slot)+'" y="'+top+'" width="'+slot+'" height="'+(base-top)+'" fill="transparent"/>';return;}
  const h=Math.max(3,(base-top)*v/max),y=base-h,r=Math.min(4,h);
  s+='<path d="M'+x+' '+base+'V'+(y+r)+'Q'+x+' '+y+' '+(x+r)+' '+y+'H'+(x+bw-r)+'Q'+(x+bw)+' '+y+' '+(x+bw)+' '+(y+r)+'V'+base+'Z" fill="url(#bg)" opacity="'+(sel?1:.4)+'"/>';
  if(sel)s+='<text x="'+cx+'" y="'+(y-7)+'" text-anchor="middle" font-size="12" font-weight="600" style="fill:var(--txt)">'+fmt(v,M.d)+'</text>';
  s+='<rect class="bar" data-j="'+j+'" x="'+(j*slot)+'" y="'+top+'" width="'+slot+'" height="'+(base-top)+'" fill="transparent"/>';});
 svg.innerHTML='<defs><linearGradient id="bg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#2fd3ff"/><stop offset="1" stop-color="#6c5cff"/></linearGradient></defs>'+s;
 svg.querySelectorAll('.bar').forEach(b=>{const m=mon[+b.dataset.j];
  b.onclick=()=>{cur=m.month;render();};
  b.onpointerenter=()=>{const t=$('tip'),r=svg.getBoundingClientRect(),k=r.width/W;
   t.textContent=mname(m.month)+' : '+(m[metric]==null?'pas de données':fmt(m[metric],M.d)+' '+M.u);
   t.style.left=(+b.getAttribute('x')+slot/2)*k+'px';t.style.top=(top*k)+'px';t.style.display='block';};
  b.onpointerleave=()=>$('tip').style.display='none';});}

function lists(){
 const tr=H.trips.filter(t=>t.month==cur).reverse(),ch=H.charges.filter(c=>c.month==cur).reverse();
 $('trips').innerHTML=tr.length?tr.map(t=>'<div class="item"><div><div class="a">'+fmt(t.km,1)+' km</div><div class="b">'+when(t.start)+' · '+dur(t.min)+'</div></div>'
  +'<div class="r"><div class="a"'+(t.km<10?' style="color:var(--mut);font-weight:400">≈ ':'>')+fmt(t.kwh100,1)+' kWh/100</div><div class="b">'+fmt(t.kwh,1)+' kWh · '+fmt(t.speed,0)+' km/h</div></div></div>').join('')
  :'<div class="empty">Aucun trajet ce mois-ci.</div>';
 $('charges').innerHTML=ch.length?ch.map(c=>'<div class="item"><div><div class="a">'+(c.start_level!=null?c.start_level:'?')+' → '+(c.end_level!=null?c.end_level:'?')+' %</div>'
  +'<div class="b">'+when(c.start)+(c.done?' · '+dur(c.min):' · fin non enregistrée')+'</div></div>'
  +'<div class="r"><div class="a">'+(c.cost!=null?fmt(c.cost,2)+' €':'–')+'</div><div class="b">'+(c.kwh!=null?fmt(c.kwh,1)+' kWh':'')+(c.hc!=null?' · HC '+c.hc+' %':'')+'</div></div></div>').join('')
  :'<div class="empty">Aucune charge ce mois-ci.</div>';
 $('tnote').textContent=(H.min_trip?'Trajets de plus de '+fmt(H.min_trip,0)+' km. ':'')
  +'Sous 10 km, la consommation d’un trajet seul est approximative (≈) : la batterie n’est mesurée qu’au pour cent près.';
 $('cnote').textContent='Coût TTC estimé : énergie entrée dans la batterie ÷ '+fmt(H.efficiency*100,0)+' % de rendement, au tarif heures creuses ('
  +fmt(H.night_price,4)+' €) ou pleines ('+fmt(H.day_price,4)+' €) selon l’heure.';}

document.querySelectorAll('[data-m]').forEach(b=>b.onclick=()=>{metric=b.dataset.m;
 document.querySelectorAll('[data-m]').forEach(x=>x.classList.toggle('sel',x==b));chart();});
$('prev').onclick=()=>{const k=H.months.map(m=>m.month);cur=k[k.indexOf(cur)-1]||cur;render();};
$('next').onclick=()=>{const k=H.months.map(m=>m.month);cur=k[k.indexOf(cur)+1]||cur;render();};
fetch('api/history').then(r=>r.json()).then(h=>{if(h.error)throw new Error(h.error);H=h;cur=h.months[h.months.length-1].month;render();})
 .catch(e=>{document.querySelector('main').insertAdjacentHTML('beforeend','<p class="empty">Erreur : '+e.message+'</p>');});
</script></body></html>"""


def psacc(path, **params):
    url = PSACC + path + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.loads(r.read().decode())


def parse_hhmm(s):
    h, m = (int(x) for x in s.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("heure invalide")
    return h, m


def fmt_hour(h):
    if not h:
        return None
    if isinstance(h, (list, tuple)):
        return "%02d:%02d" % (int(h[0]), int(h[1]))
    return str(h)[:5]


# ---- Programmation du preconditionnement ----

lock = threading.Lock()
prog = {"enabled": False, "time": "07:30", "days": [], "next": None}  # days : 0 = lundi ... 6 = dimanche
DAY_NAMES = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def next_occurrence(hhmm, after, days):
    """Prochain HH:MM apres `after`, un des jours `days` (aucun jour = prochaine occurrence)."""
    h, m = parse_hhmm(hhmm)
    t = after.replace(hour=h, minute=m, second=0, microsecond=0)
    for i in range(8):
        c = t + timedelta(days=i)
        if c > after and (not days or c.weekday() in days):
            return c


def save_prog():
    with open(CLIM_FILE, "w") as f:
        json.dump(prog, f)


def load_prog():
    try:
        with open(CLIM_FILE) as f:
            prog.update(json.load(f))
    except (OSError, ValueError):
        pass
    if prog.pop("daily", False) and not prog["days"]:  # ancien format "tous les jours"
        prog["days"] = list(range(7))


def clim_tick():
    with lock:
        if not (prog["enabled"] and prog["next"]):
            return
        due = datetime.fromisoformat(prog["next"])
        now = datetime.now()
        if now < due:
            return
        fire = now - due < LATE_LIMIT
        if prog["days"]:
            prog["next"] = next_occurrence(prog["time"], now, prog["days"]).isoformat()
        else:
            prog["enabled"], prog["next"] = False, None
        save_prog()
    if fire:
        try:
            print("Preconditionnement programme :", psacc("/preconditioning/%s/1" % VIN), flush=True)
        except Exception as e:
            print("Echec preconditionnement programme :", e, flush=True)


# ---- Debut de charge automatique sur les heures creuses ----

auto = {"enabled": False, "sent": None}  # sent = derniere heure de debut envoyee a la voiture
auto_retry = {"at": datetime.min}


def to_min(hhmm):
    h, m = parse_hhmm(hhmm)
    return h * 60 + m


def offpeak_target(now):
    """Debut de la prochaine plage creuse : on bascule SWITCH_DELAY apres la fin de chaque plage."""
    cur = now.hour * 60 + now.minute
    plages = sorted(OFFPEAK, key=lambda p: to_min(p[1]))
    for start, end in plages:
        if cur < to_min(end) + SWITCH_DELAY:
            return start
    return plages[0][0]


def save_auto():
    with open(AUTO_FILE, "w") as f:
        json.dump(auto, f)


def load_auto():
    try:
        with open(AUTO_FILE) as f:
            auto.update(json.load(f))
    except (OSError, ValueError):
        pass


def auto_tick():
    with lock:
        if not auto["enabled"] or datetime.now() < auto_retry["at"] or fresh["full"]:
            return  # batterie deja a la limite : on ne reprogramme pas un debut de charge inutile
        target = offpeak_target(datetime.now())
        if target == auto["sent"]:
            return
    h, m = parse_hhmm(target)
    try:
        res = psacc("/charge_hour", vin=VIN, hour=h, minute=m)
        check(res)
    except Exception as e:
        print("Echec programmation debut de charge %s :" % target, e, flush=True)
        auto_retry["at"] = datetime.now() + timedelta(minutes=10)
        return
    print("Debut de charge programme automatiquement a", target, flush=True)
    with lock:
        auto["sent"] = target
        save_auto()


def scheduler():
    while True:
        time.sleep(20)
        for tick in (fresh_tick, clim_tick, auto_tick, preheat_tick, report_tick):
            try:
                tick()
            except Exception as e:
                print("Erreur planificateur :", e, flush=True)


def prog_view():
    with lock:
        p = dict(prog)
    if p["next"]:
        d = datetime.fromisoformat(p["next"])
        delta = (d.date() - datetime.now().date()).days
        day = "aujourd'hui" if delta == 0 else "demain" if delta == 1 else DAY_NAMES[d.weekday()]
        p["next"] = "%s à %s" % (day, d.strftime("%H:%M"))
    return p


# ---- Etat et actions ----

def delayed_hour(value):
    """'PT22H30M' (format de l'API Stellantis) -> '22:30'."""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", str(value or ""))
    if not m or not any(m.groups()):
        return None
    return "%02d:%02d" % (int(m.group(1) or 0), int(m.group(2) or 0))


def vehicle():
    """Niveau batterie, charge et clim depuis le cache (ne reveille pas la voiture)."""
    v = {"level": None, "status": None, "charging": None, "start_hour": None, "clim_status": None}
    try:
        info = psacc("/get_vehicleinfo/" + VIN, from_cache=1)
    except Exception:
        return v
    for e in info.get("energy") or []:
        if e.get("type") == "Electric":
            ch = e.get("charging") or {}
            v["level"] = e.get("level")
            v["status"] = ch.get("status")
            v["charging"] = CHARGING.get(v["status"], v["status"])
            v["start_hour"] = delayed_hour(ch.get("next_delayed_time"))
            v["autonomy"] = e.get("autonomy")
    clim = ((info.get("preconditioning") or {}).get("air_conditioning") or {}).get("status")
    v["clim_status"] = CLIM.get(clim, clim)
    if fresh["at"] and fresh["status"] is not None:  # le cache de psacc n'a souvent pas l'etat de charge
        v["level"] = fresh["level"] if fresh["level"] is not None else v["level"]
        v["status"], v["charging"] = fresh["status"], CHARGING.get(fresh["status"], fresh["status"])
    return v


# ---- Surveillance de la charge avec des donnees fraiches ----
# Le cache de psa_car_controller perd souvent l'etat de charge ("charging status not available from api") :
# son arret a la limite ne se declenche alors pas. On interroge donc Stellantis directement et on arrete nous-memes.

fresh = {"at": None, "level": None, "status": None, "full": False}
guard = {"last_stop": None, "tries": 0, "reason": None, "resume": None}


def next_window_start(now):
    """Debut de la prochaine plage creuse strictement apres `now`."""
    cur = now.hour * 60 + now.minute
    starts = sorted(to_min(s) for s, _ in OFFPEAK)
    m = next((s for s in starts if s > cur), starts[0])
    return "%02d:%02d" % divmod(m, 60)


def stop_charge(reason, level, now, resume=None):
    """Arrete la charge en placant le debut differe a `resume` (HH:MM, plus tard) ou, a defaut, une heure dans
    le passe : la voiture attend alors le lendemain."""
    if guard["last_stop"] and now - guard["last_stop"] < timedelta(minutes=8):
        return  # laisser a la voiture le temps d'obeir
    guard["last_stop"] = now
    guard["tries"] += 1
    if guard["tries"] > 3:
        if guard["tries"] == 4:
            ntfy("⚠️ Impossible d'arrêter la charge", "Batterie à %s %%, la voiture ne répond pas à l'ordre d'arrêt (%s)."
                 % (level, reason), ["warning"], 4)
        return
    h, m = parse_hhmm(resume) if resume else ((now.hour - 1) % 24, 0)
    check(psacc("/charge_hour", vin=VIN, hour=h, minute=m))
    guard["reason"], guard["resume"] = reason, resume
    if resume:
        with lock:  # evite qu'auto_tick renvoie l'ancienne plage avant sa bascule (07:15 / 16:15)
            auto["sent"] = offpeak_target(now)
    print("Arret de la charge (%s) a %s %%%s" % (reason, level, ", reprise %s" % resume if resume else ""), flush=True)


def fresh_tick():
    now = datetime.now()
    every = timedelta(minutes=2 if fresh["status"] == "InProgress" else 5)
    if fresh["at"] and now - fresh["at"] < every:
        return
    fresh["at"] = now
    info = psacc("/get_vehicleinfo/" + VIN, from_cache=0)
    e = next((x for x in info.get("energy") or [] if x.get("type") == "Electric"), None)
    if not e:
        return
    ch = e.get("charging") or {}
    level, status = e.get("level"), ch.get("status")
    level = None if level is None else int(round(level))
    fresh.update(level=level, status=status)
    cc = psacc("/charge_control", vin=VIN)
    thr = cc.get("percentage_threshold", 100)
    fresh["full"] = level is not None and thr < 100 and level >= thr and status != "Disconnected"

    if status == "InProgress":
        stop = fmt_hour(cc.get("_stop_hour"))
        if stop:
            h, m = parse_hhmm(stop)
            late = (now.hour * 60 + now.minute - (h * 60 + m)) % 1440
        if fresh["full"]:
            stop_charge("limite %d %%" % thr, level, now)
        elif stop and late < 30:  # dans la demi-heure qui suit l'heure d'arret
            stop_charge("heure d'arrêt %s" % stop, level, now)
        elif auto["enabled"] and not ns["forced"] and ns["prev"] == "InProgress" and not is_offpeak(now):
            # la charge deborde de la plage creuse : on la suspend jusqu'au debut de la plage suivante
            # (une charge qui demarre en heures pleines est geree par notif_tick, qui la met en attente)
            stop_charge("fin des heures creuses", level, now, resume=next_window_start(now))
    else:
        guard["tries"] = 0

    notif_tick({"status": status, "level": level, "start_hour": delayed_hour(ch.get("next_delayed_time"))})


def state(cc=None):
    if cc is None:
        cc = psacc("/charge_control", vin=VIN)
    if "error" in cc or "percentage_threshold" not in cc:
        raise RuntimeError(cc.get("error", "psa_car_controller ne répond pas correctement"))
    with lock:
        auto_view = {"enabled": auto["enabled"], "target": offpeak_target(datetime.now()),
                     "plages": ["%s–%s" % p for p in OFFPEAK]}
    v = vehicle()
    try:
        rng = range_estimate(v["level"], v.get("autonomy"))
    except Exception as e:
        print("Estimation d'autonomie impossible :", e, flush=True)
        rng = None
    return dict(v, threshold=cc["percentage_threshold"], stop_hour=fmt_hour(cc.get("_stop_hour")),
                clim=prog_view(), auto=auto_view, notif=dict(notif), car=dict(car), preheat=preheat_view(), report={k: report[k] for k in ("enabled", "l100", "fuel")}, range=rng)


# ---- Autonomie estimee a partir des trajets passes ----

RESERVE = 5  # % de batterie gardes en reserve dans l'estimation
MAX_AVG_SPEED = 75  # trajets plus rapides en moyenne : sans doute de l'autoroute, exclus (on vise "sous 90 km/h")
cache = {}


def cached(key, ttl, fn):
    hit = cache.get(key)
    if hit and datetime.now() - hit[0] < ttl:
        return hit[1]
    value = fn()
    cache[key] = (datetime.now(), value)
    return value


def percentile(values, p):
    s = sorted(values)
    k = (len(s) - 1) * p
    i = int(k)
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * (k - i)


def range_estimate(level, car_km):
    """Km restants (jusqu'a RESERVE %) d'apres la consommation reelle des trajets des 90 derniers jours,
    corrigee par la temperature quand il y a assez de trajets pour mesurer son effet."""
    if level is None:
        return None
    trips = cached("trips", timedelta(minutes=10), lambda: psacc("/vehicles/trips"))
    try:
        soh = cached("soh", timedelta(hours=6), lambda: (psacc("/battery/soh/" + VIN) or {}).get("soh"))
    except Exception:
        soh = None  # sans SOH, on suppose la batterie neuve
    try:
        temps = forecast(WEATHER["place"], WEATHER["lat"], WEATHER["lon"]) if WEATHER else {}
    except Exception:
        temps = {}
    oldest = datetime.now().astimezone() - timedelta(days=90)
    pts = []  # (kWh/100 km, km, temperature)
    for t in trips if isinstance(trips, list) else []:
        start, km, c, speed = parse_date(t.get("start_at")), t.get("distance") or 0, t.get("consumption_km"), t.get("speed_average")
        if not start or start < oldest or km < 5 or c is None or not 8 <= c <= 35 or (speed or 0) > MAX_AVG_SPEED:
            continue
        pts.append((c, km, temps.get(start.strftime("%Y-%m-%dT%H:00"))))
    out = {"trips": len(pts), "car_km": car_km, "km": None}
    if len(pts) < 2:
        return out

    kwh100 = sum(c * km for c, km, _ in pts) / sum(km for _, km, _ in pts)  # moyenne ponderee par la distance
    now_temp = temps.get(datetime.now().strftime("%Y-%m-%dT%H:00"))
    with_t = [(tp, c) for c, _, tp in pts if tp is not None]
    if now_temp is not None and len(with_t) >= 8 and max(tp for tp, _ in with_t) - min(tp for tp, _ in with_t) >= 6:
        mx = sum(tp for tp, _ in with_t) / len(with_t)
        my = sum(c for _, c in with_t) / len(with_t)
        b = sum((tp - mx) * (c - my) for tp, c in with_t) / sum((tp - mx) ** 2 for tp, _ in with_t)
        cs = [c for _, c in with_t]
        kwh100 = min(max(my + b * (now_temp - mx), min(cs) * 0.9), max(cs) * 1.2)  # pas d'extrapolation folle
        out["temp"] = round(now_temp)

    usable = BATTERY_KWH * (soh or 100) / 100 * max(level - RESERVE, 0) / 100
    cs = [c for c, _, _ in pts]
    km = usable / kwh100 * 100
    out.update(km=round(km), kwh100=round(kwh100, 1),
               low=round(min(km, usable / percentile(cs, 0.8) * 100)),
               high=round(max(km, usable / percentile(cs, 0.2) * 100)),
               commutes=int(km // COMMUTE["km"]) if COMMUTE else None,
               commute_label=(COMMUTE or {}).get("label"))
    return out


def check(res):
    if isinstance(res, dict) and res.get("error"):
        raise RuntimeError(res["error"])
    if res is False:
        raise RuntimeError("commande refusée par psa_car_controller")


def set_charge(data):
    pct = int(data["percentage"])
    if not 50 <= pct <= 100:
        raise ValueError("pourcentage hors limites")
    h, m = 0, 0  # 0:00 = heure d'arret desactivee pour psa_car_controller
    if data.get("stop_hour"):
        h, m = parse_hhmm(data["stop_hour"])
        if (h, m) == (0, 0):
            m = 1
    return state(psacc("/charge_control", vin=VIN, percentage=pct, hour=h, minute=m))


def set_clim(data):
    check(psacc("/preconditioning/%s/%d" % (VIN, 1 if data.get("on") else 0)))
    return state()


def set_charge_start(data):
    """Charge immediate, ou charge differee qui demarre a l'heure donnee (programmation de la voiture)."""
    if data.get("now"):
        check(psacc("/charge_now/%s/1" % VIN))
        ns["forced"] = True  # pas d'alerte "heures pleines" pour une charge demandee
    else:
        h, m = parse_hhmm(data["time"])
        check(psacc("/charge_hour", vin=VIN, hour=h, minute=m))
    return state()


def set_prog(data):
    parse_hhmm(data["time"])
    with lock:
        prog["enabled"] = bool(data.get("enabled"))
        prog["time"] = data["time"]
        prog["days"] = sorted({int(d) for d in data.get("days", []) if 0 <= int(d) <= 6})
        prog["next"] = (next_occurrence(prog["time"], datetime.now(), prog["days"]).isoformat()
                        if prog["enabled"] else None)
        save_prog()
    return state()


def set_auto(data):
    with lock:
        auto["enabled"] = bool(data.get("enabled"))
        auto["sent"] = None  # a l'activation, envoie tout de suite la bonne heure
        auto_retry["at"] = datetime.min
        save_auto()
    if auto["enabled"]:
        auto_tick()
    return state()


# ---- Historique (trajets et charges enregistres par psa_car_controller) ----

def parse_date(s):
    try:
        return parsedate_to_datetime(s).astimezone()
    except (TypeError, ValueError):
        return None


def is_offpeak(dt):
    cur = dt.hour * 60 + dt.minute
    for start, end in OFFPEAK:
        a, b = to_min(start), to_min(end)
        if (a <= cur < b) if a < b else (cur >= a or cur < b):
            return True
    return False


def offpeak_share(start, stop):
    """Part du temps de charge en heures creuses, par pas de 5 min."""
    if not stop or stop <= start:
        return 1.0 if is_offpeak(start) else 0.0
    steps = hc = 0
    t = start
    while t < stop:
        steps += 1
        hc += is_offpeak(t)
        t += timedelta(minutes=5)
    return hc / steps


def history(_data=None):
    trips = psacc("/vehicles/trips")
    charges = psacc("/vehicles/chargings")
    settings = psacc("/settings")
    elec = settings.get("Electricity_config") or {}
    min_trip = (settings.get("General") or {}).get("minimum_trip_length")
    day = elec.get("day_price") or 0.0
    night = elec.get("night_price") or day
    eff = elec.get("charger_efficiency") or 0.9
    months = {}

    def month(dt):
        k = dt.strftime("%Y-%m")
        return months.setdefault(k, {"month": k, "km": 0.0, "kwh_used": 0.0, "trips": 0,
                                     "kwh_charged": 0.0, "cost": 0.0, "charges": 0})

    out_trips = []
    for t in trips if isinstance(trips, list) else []:
        start = parse_date(t.get("start_at"))
        if not start:
            continue
        m = month(start)
        m["km"] += t.get("distance") or 0
        if t.get("mileage"):
            m["odo"] = max(m.get("odo") or 0, t["mileage"])
        m["kwh_used"] += t.get("consumption") or 0
        m["trips"] += 1
        out_trips.append({"month": m["month"], "start": start.isoformat(), "km": t.get("distance"),
                          "kwh": t.get("consumption"), "kwh100": t.get("consumption_km"),
                          "min": t.get("duration"), "speed": t.get("speed_average")})

    # charges enregistrees par la page (completes), puis celles de psacc qui ne font pas doublon
    own = load_charge_log()
    records = [(datetime.fromisoformat(c["start"]), datetime.fromisoformat(c["stop"]), c) for c in own]
    own_starts = [r[0] for r in records]
    for c in charges if isinstance(charges, list) else []:
        start = parse_date(c.get("start_at"))
        if not start or any(abs((start - s).total_seconds()) < 7200 for s in own_starts):
            continue
        records.append((start, parse_date(c.get("stop_at")) if c.get("stop_at") else None, c))

    out_charges = []
    for start, stop, c in records:
        kwh = c.get("kw")
        if kwh is None and c.get("end_level") is not None and c.get("start_level") is not None:
            kwh = (c["end_level"] - c["start_level"]) / 100 * BATTERY_KWH
        share = offpeak_share(start, stop)
        cost = kwh / eff * (share * night + (1 - share) * day) if kwh is not None else None
        m = month(start)
        m["charges"] += 1
        m["kwh_charged"] += kwh or 0
        m["known"] = m.get("known") or kwh is not None
        m["cost"] += cost or 0
        out_charges.append({"month": m["month"], "start": start.isoformat(), "done": stop is not None,
                            "min": (stop - start).total_seconds() / 60 if stop else None,
                            "start_level": c.get("start_level"), "end_level": c.get("end_level"),
                            "kwh": kwh, "cost": cost, "hc": round(share * 100) if stop else None})

    current = month(datetime.now().astimezone())
    try:
        odo = (psacc("/get_vehicleinfo/" + VIN, from_cache=1).get("timed_odometer") or {}).get("mileage")
        if odo:
            current["odo"] = max(current.get("odo") or 0, odo)
    except Exception:
        pass
    for m in months.values():
        m["kwh100"] = m["kwh_used"] / m["km"] * 100 if m["km"] else None
        price = m["cost"] / m["kwh_charged"] if m["kwh_charged"] else night / eff
        m["cost100"] = m["kwh100"] * price if m["kwh100"] is not None else None  # euros pour 100 km
        if not m.pop("known", False):  # aucune charge complete ce mois-ci
            m["cost"] = m["kwh_charged"] = None

    return {"months": sorted(months.values(), key=lambda m: m["month"]),
            "trips": sorted(out_trips, key=lambda t: t["start"]),
            "charges": sorted(out_charges, key=lambda c: c["start"]),
            "day_price": day, "night_price": night, "efficiency": eff, "min_trip": min_trip}


# ---- Notifications sur le telephone (ntfy) ----

notif = {"topic": None, "plug": True, "plug_time": "21:00", "plug_level": 50, "done": True, "peak": True}
ns = {"prev": None, "start_level": None, "start_at": None, "forced": False, "plug_day": None}  # etat en memoire


def save_notif():
    with open(NOTIF_FILE, "w") as f:
        json.dump(notif, f)


def load_notif():
    try:
        with open(NOTIF_FILE) as f:
            notif.update(json.load(f))
    except (OSError, ValueError):
        pass
    if not notif["topic"]:  # sujet secret : quiconque le connait peut lire les notifications
        notif["topic"] = "ev-" + secrets.token_hex(8)
        save_notif()


def ntfy(title, message, tags=(), priority=3):
    body = json.dumps({"topic": notif["topic"], "title": title, "message": message,
                       "tags": list(tags), "priority": priority}).encode()
    req = urllib.request.Request(NTFY_SERVER, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()
    print("Notification :", title, flush=True)


def fr(x, decimals):
    return ("%.*f" % (decimals, x)).replace(".", ",")


def charge_summary(level):
    """' (+9 %, ≈ 4,1 kWh, ≈ 0,50 €)' pour la charge qui vient de se terminer."""
    if ns["start_level"] is None or level is None or level <= ns["start_level"]:
        return ""
    gained = level - ns["start_level"]
    kwh = gained / 100 * BATTERY_KWH
    try:
        elec = psacc("/settings").get("Electricity_config") or {}
        day = elec.get("day_price") or 0.0
        night = elec.get("night_price") or day
        share = offpeak_share(ns["start_at"], datetime.now())
        cost = kwh / (elec.get("charger_efficiency") or 0.9) * (share * night + (1 - share) * day)
        return " (+%d %%, ≈ %s kWh, ≈ %s €)" % (gained, fr(kwh, 1), fr(cost, 2))
    except Exception:
        return " (+%d %%, ≈ %s kWh)" % (gained, fr(kwh, 1))


def charge_ended(status, level, start_hour):
    cc = psacc("/charge_control", vin=VIN)
    thr = cc.get("percentage_threshold", 100)
    lvl = "?" if level is None else "%d %%" % level
    now = datetime.now()
    stop = fmt_hour(cc.get("_stop_hour"))
    if stop:
        h, m = parse_hhmm(stop)
        diff = abs(now.hour * 60 + now.minute - (h * 60 + m))
        near_stop = min(diff, 1440 - diff) <= 15
    else:
        near_stop = False
    if status == "Disconnected":
        ntfy("🔌 Débranchée pendant la charge", "Batterie à %s%s." % (lvl, charge_summary(level)), ["electric_plug"])
    elif level is not None and (level >= thr - 2 or level >= 98):
        ntfy("✅ Charge terminée", "Batterie à %s%s." % (lvl, charge_summary(level)), ["white_check_mark"])
    elif guard.get("reason") == "fin des heures creuses":
        ntfy("⏰ Fin des heures creuses", "Charge suspendue à %s%s. Reprise à %s." % (lvl, charge_summary(level), guard["resume"]),
             ["alarm_clock"])
    elif near_stop:
        ntfy("⏰ Charge arrêtée à l'heure prévue", "Batterie à %s%s." % (lvl, charge_summary(level)), ["alarm_clock"])
    elif not is_offpeak(now) and start_hour:
        ntfy("⏸️ Charge en attente", "Batterie à %s. La charge reprendra à %s." % (lvl, start_hour), ["pause_button"])
    else:
        ntfy("⚠️ Charge interrompue", "La charge s'est arrêtée à %s, avant la limite de %d %%%s."
             % (lvl, thr, charge_summary(level)), ["warning"], 4)


def load_charge_log():
    try:
        with open(CHARGE_LOG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def log_charge(level):
    """Enregistre la charge qui vient de finir : psacc n'en connait souvent que le debut."""
    if ns["start_at"] is None or ns["start_level"] is None or level is None or level <= ns["start_level"]:
        return
    with lock:
        log = load_charge_log()
        log.append({"start": ns["start_at"].astimezone().isoformat(timespec="seconds"),
                    "stop": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "start_level": ns["start_level"], "end_level": level})
        with open(CHARGE_LOG, "w") as f:
            json.dump(log, f)


def notif_tick(v):
    """Appele par fresh_tick avec l'etat frais de la voiture."""
    status, level, now = v["status"], v["level"], datetime.now()

    # rappel de branchement, une fois par soir
    today = now.date().isoformat()
    if notif["plug"] and status and ns["plug_day"] != today and now.strftime("%H:%M") >= notif["plug_time"]:
        ns["plug_day"] = today
        if status == "Disconnected" and level is not None and level < notif["plug_level"]:
            ntfy("🔌 Pense à brancher la voiture", "Batterie à %d %%, la voiture n'est pas branchée." % level,
                 ["electric_plug"], 4)

    # debut / fin de charge, detectes par changement d'etat
    if status is None:  # l'API ne donne pas toujours l'etat de charge
        return
    prev, ns["prev"] = ns["prev"], status
    if prev is None:  # premier passage apres demarrage : on observe seulement
        if status == "InProgress":
            ns["start_at"] = now
        return
    if status == "InProgress" and prev != "InProgress":
        ns["start_level"], ns["start_at"] = level, now
        if ns["forced"] or is_offpeak(now):
            return
        lvl = "?" if level is None else level
        target = None
        if auto["enabled"]:  # la voiture repasse en charge immediate a chaque branchement : on la remet en differe
            target = offpeak_target(now)
            try:
                h, m = parse_hhmm(target)
                check(psacc("/charge_hour", vin=VIN, hour=h, minute=m))
                print("Charge en heures pleines : mise en attente jusqu'a", target, "demandee", flush=True)
            except Exception as e:
                print("Echec mise en attente :", e, flush=True)
                target = None
        if notif["peak"] and target:
            ntfy("⏳ Charge en heures pleines → attente demandée",
                 "La voiture a commencé à charger (%s %%) en heures pleines. Je lui ai demandé d'attendre %s. "
                 "Si la LED reste verte, appuie sur le bouton de la trappe." % (lvl, target), ["hourglass"], 4)
        elif notif["peak"]:
            ntfy("⚡ Charge en heures pleines",
                 "La voiture charge maintenant (%s %%) en heures pleines. Pour attendre les heures creuses : "
                 "bouton de la trappe, ou « Heure choisie » sur la page." % lvl, ["zap"], 4)
    elif prev == "InProgress" and status != "InProgress":
        try:
            log_charge(level)
            if notif["done"]:
                charge_ended(status, level, v["start_hour"])
        finally:
            ns["forced"], ns["start_level"] = False, None
            guard["reason"] = guard["resume"] = None


def set_notif(data):
    plug_time = data.get("plug_time", notif["plug_time"])
    parse_hhmm(plug_time)
    plug_level = int(data.get("plug_level", notif["plug_level"]))
    if not 10 <= plug_level <= 90:
        raise ValueError("seuil hors limites")
    with lock:
        notif.update(plug=bool(data.get("plug")), plug_time=plug_time, plug_level=plug_level,
                     done=bool(data.get("done")), peak=bool(data.get("peak")))
        save_notif()
    return state()


def test_notif(_data):
    ntfy("🔔 Test", "Les notifications de ta voiture fonctionnent !", ["bell"])
    return state()


# ---- Prechauffage selon le planning de travail et la meteo ----

preheat = {"enabled": False, "cold": 5, "hot": 25, "lead": 30, "skip": [], "done": None}
weather_cache = {}  # lieu -> (heure de recuperation, {"2026-10-18T06:00": 4.2, ...})


def save_preheat():
    with open(PREHEAT_FILE, "w") as f:
        json.dump(preheat, f)


def load_preheat():
    try:
        with open(PREHEAT_FILE) as f:
            preheat.update(json.load(f))
    except (OSError, ValueError):
        pass


def departures(after, count):
    """Les `count` prochains departs (datetime, lieu, lat, lon) strictement apres `after`, d'apres config.json."""
    out = []
    for i in range(15):
        d = after.date() + timedelta(days=i)
        for dep in sorted(DEPARTURES, key=lambda x: x["time"]):
            if d.weekday() not in dep.get("days", range(7)):
                continue
            h, m = parse_hhmm(dep["time"])
            dt = datetime(d.year, d.month, d.day, h, m)
            if dt > after:
                out.append((dt, dep["place"], dep["lat"], dep["lon"]))
    return out[:count]

def forecast(place, lat, lon):
    cached = weather_cache.get(place)
    if cached and datetime.now() - cached[0] < timedelta(hours=1):
        return cached[1]
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
        {"latitude": lat, "longitude": lon, "hourly": "temperature_2m", "timezone": "Europe/Paris", "forecast_days": 4,
         "past_days": 92})  # le passe sert a connaitre la temperature de chaque trajet
    with urllib.request.urlopen(url, timeout=20) as r:
        hourly = json.loads(r.read().decode())["hourly"]
    temps = dict(zip(hourly["time"], hourly["temperature_2m"]))
    weather_cache[place] = (datetime.now(), temps)
    return temps


def temp_at(dt, place, lat, lon):
    """Temperature prevue a l'heure du depart (interpolee entre deux heures), None si hors prevision."""
    temps = forecast(place, lat, lon)
    h0 = dt.replace(minute=0)
    t0 = temps.get(h0.strftime("%Y-%m-%dT%H:00"))
    t1 = temps.get((h0 + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00"))
    if t0 is None:
        return None
    if t1 is None:
        return t0
    return t0 + (t1 - t0) * dt.minute / 60


def preheat_tick():
    if not preheat["enabled"]:
        return
    now = datetime.now()
    nxt = departures(now, 1)
    if not nxt:
        return
    dep, place, lat, lon = nxt[0]
    if now < dep - timedelta(minutes=preheat["lead"]) or preheat["done"] == dep.isoformat():
        return
    with lock:
        preheat["done"] = dep.isoformat()  # une seule decision par depart
        save_preheat()
    if dep.date().isoformat() in preheat["skip"]:
        print("Prechauffage annule pour", dep, flush=True)
        return
    when = "%s à %s" % (place, dep.strftime("%H:%M"))
    try:
        t = temp_at(dep, place, lat, lon)
    except Exception as e:
        print("Meteo indisponible :", e, flush=True)
        t = None
    if t is None:
        ntfy("⚠️ Météo indisponible", "Préchauffage non lancé (départ : %s)." % when, ["warning"])
        return
    t = round(t, 1)  # on decide sur la valeur affichee : 10,0 °C avec un seuil a 10 °C doit declencher
    if preheat["cold"] < t < preheat["hot"]:
        print("Prechauffage inutile : %.1f °C prevus (%s)" % (t, when), flush=True)
        ntfy("🌤️ Pas de préchauffage", "%s °C prévus à %s (seuils %d °C / %d °C)."
             % (fr(t, 1), when, preheat["cold"], preheat["hot"]), ["partly_sunny"], 2)
        return
    try:
        check(psacc("/preconditioning/%s/1" % VIN))
    except Exception as e:
        ntfy("⚠️ Échec du préchauffage", "%s °C prévus (%s), mais la voiture n'a pas répondu : %s" % (fr(t, 1), when, e),
             ["warning"], 4)
        return
    if t <= preheat["cold"]:
        ntfy("❄️ Préchauffage lancé", "%s °C prévus à %s." % (fr(t, 1), when), ["snowflake"])
    else:
        ntfy("☀️ Climatisation lancée", "%s °C prévus à %s." % (fr(t, 1), when), ["sunny"])


def preheat_view():
    with lock:
        p = {k: preheat[k] for k in ("enabled", "cold", "hot", "lead")}
        skip = set(preheat["skip"])
    p["next"] = []
    for dep, place, lat, lon in departures(datetime.now(), 6):
        try:
            t = temp_at(dep, place, lat, lon)
        except Exception:
            t = None
        p["next"].append({"date": dep.date().isoformat(), "time": dep.strftime("%H:%M"), "place": place,
                          "temp": None if t is None else round(t, 1), "skip": dep.date().isoformat() in skip})
    return p


def set_preheat(data):
    cold, hot, lead = int(data["cold"]), int(data["hot"]), int(data["lead"])
    if not (-10 <= cold < hot <= 40 and 5 <= lead <= 60):
        raise ValueError("réglages hors limites")
    with lock:
        preheat.update(enabled=bool(data.get("enabled")), cold=cold, hot=hot, lead=lead)
        save_preheat()
    return state()


def skip_preheat(data):
    day = date.fromisoformat(data["date"]).isoformat()
    today = date.today().isoformat()
    with lock:
        skip = {d for d in preheat["skip"] if d >= today}  # on oublie les jours passes
        skip.add(day) if data.get("skip") else skip.discard(day)
        preheat["skip"] = sorted(skip)
        save_preheat()
    return state()


# ---- Bilan mensuel envoye le 1er du mois ----

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre"]
report = {"enabled": True, "l100": 6.0, "fuel": 2.20, "last": None}  # voiture essence de comparaison


def save_report():
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f)


def load_report():
    try:
        with open(REPORT_FILE) as f:
            report.update(json.load(f))
    except (OSError, ValueError):
        pass


def month_title(key, partial=False):
    name = MONTHS[int(key[5:]) - 1]
    return "📊 Bilan %s%s %s%s" % ("d'" if name[0] in "aeiouéè" else "de ", name, key[:4], " (en cours)" if partial else "")


def send_report(key, partial=False):
    h = history()
    m = next((x for x in h["months"] if x["month"] == key), None)
    if not m or not m["km"]:
        ntfy(month_title(key, partial), "Aucun trajet enregistré ce mois-ci.", ["bar_chart"])
        return
    km, eff = m["km"], h["efficiency"]
    lines = ["%s km en %d trajet%s · %s kWh/100" % (fr(km, 0), m["trips"], "s" if m["trips"] > 1 else "",
                                                   fr(m["kwh100"], 1))]
    if m["cost"] is not None:
        cost, approx = m["cost"], ""
        lines.append("Recharges : %s kWh pour %s €" % (fr(m["kwh_charged"], 0), fr(cost, 2)))
    else:  # charges incompletes : estimation a partir de la consommation, au tarif heures creuses
        cost, approx = m["kwh_used"] / eff * h["night_price"], "≈ "
        lines.append("Électricité : ≈ %s € (estimation)" % fr(cost, 2))
    fuel = km * report["l100"] / 100 * report["fuel"]
    lines.append("Soit %s%s € aux 100 km" % (approx, fr(cost / km * 100, 2)))
    lines.append("En essence (%s L/100 à %s €) : %s € → %s%s € économisés"
                 % (fr(report["l100"], 1), fr(report["fuel"], 2), fr(fuel, 0), approx, fr(fuel - cost, 0)))
    ntfy(month_title(key, partial), "\n".join(lines), ["bar_chart"])


def report_tick():
    now = datetime.now()
    if not report["enabled"] or now.day != 1 or now.hour < 9:
        return
    prev = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    if report["last"] == prev:
        return
    with lock:
        report["last"] = prev  # un seul envoi, meme en cas d'erreur
        save_report()
    send_report(prev)


def set_report(data):
    l100, fuel = float(data["l100"]), float(data["fuel"])
    if not (2 <= l100 <= 20 and 0.5 <= fuel <= 5):
        raise ValueError("valeurs hors limites")
    with lock:
        report.update(enabled=bool(data.get("enabled")), l100=l100, fuel=fuel)
        save_report()
    return state()


def report_now(_data):
    send_report(datetime.now().strftime("%Y-%m"), partial=True)
    return state()


# ---- Nom de la voiture (Reglages) ----

car = {"brand": BRAND, "model": MODEL}  # valeurs de config.json, remplacees par celles saisies dans Reglages


def load_car():
    try:
        with open(CAR_FILE, encoding="utf-8") as f:
            car.update(json.load(f))
    except (OSError, ValueError):
        pass


def set_car(data):
    brand, model = str(data.get("brand", "")).strip()[:30], str(data.get("model", "")).strip()[:30]
    if not model:
        raise ValueError("indique au moins le modèle")
    with lock:
        car.update(brand=brand, model=model)
        with open(CAR_FILE, "w", encoding="utf-8") as f:
            json.dump(car, f, ensure_ascii=False)
    return state()


ROUTES = {"/api/car": set_car, "/api/report": set_report, "/api/report_now": report_now, "/api/preheat": set_preheat, "/api/preheat_skip": skip_preheat, "/api/notif": set_notif, "/api/notif_test": test_notif,"/api/set": set_charge, "/api/charge_start": set_charge_start, "/api/charge_auto": set_auto,
          "/api/clim": set_clim, "/api/clim_prog": set_prog}





def page(template):
    return template.replace("%MODEL%", html.escape(car["model"])).replace("%BRAND%", html.escape(car["brand"]))


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, bytes):
            raw = body
        else:
            raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/":
            self.send(200, page(PAGE), "text/html; charset=utf-8")
        elif self.path == "/historique":
            self.send(200, page(HISTORY), "text/html; charset=utf-8")
        elif self.path == "/api/history":
            try:
                self.send(200, history())
            except Exception as e:
                self.send(502, {"error": str(e)})
        elif self.path == "/car":
            self.send_image("car")
        elif self.path == "/logo":
            self.send_image("logo")
        elif self.path == "/api/state":
            try:
                self.send(200, state())
            except Exception as e:
                self.send(502, {"error": str(e)})
        else:
            self.send(404, {"error": "introuvable"})

    def send_image(self, name):
        """Images facultatives a deposer a cote de app.py : logo.(svg|png|webp|jpg), car.(png|webp|jpg)."""
        for ext, ctype in LOGO_TYPES.items():
            path = os.path.join(APP_DIR, name + "." + ext)
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    return self.send(200, f.read(), ctype)
        self.send(404, {"error": "pas d'image " + name})

    def do_POST(self):
        action = ROUTES.get(self.path)
        if not action:
            return self.send(404, {"error": "introuvable"})
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            self.send(200, action(data))
        except (ValueError, KeyError) as e:
            self.send(400, {"error": "requête invalide : %s" % e})
        except Exception as e:
            self.send(502, {"error": str(e)})


if __name__ == "__main__":
    load_prog()
    load_auto()
    load_notif()
    load_car()
    load_preheat()
    load_report()
    threading.Thread(target=scheduler, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
