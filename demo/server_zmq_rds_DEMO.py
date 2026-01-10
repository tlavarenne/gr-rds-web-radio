#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import json
import threading
import zmq
import xmlrpc.client
from flask import Flask, jsonify, render_template_string, request, make_response

# -----------------------------
# ZMQ
# -----------------------------
ZMQ_RDS_ADDR       = "tcp://127.0.0.1:5556"   # JSON ps/rt
ZMQ_AUDIO_ADDR     = "tcp://127.0.0.1:5557"   # scope audio (float) 44.1k
ZMQ_RDS_SCOPE_ADDR = "tcp://127.0.0.1:5558"   # scope RDS (float)
ZMQ_CONST_ADDR     = "tcp://127.0.0.1:5559"   # constellation (I/Q)

# -----------------------------
# XMLRPC (GRC)
# -----------------------------
XMLRPC_URL = "http://127.0.0.1:8080"

# -----------------------------
# STATIONS (Paris demo)
# -----------------------------
STATIONS = [
    {
        "name": "France Inter",
        "freq": 87.8,
        "fichier": "FranceInter95_7_21janv2017.dat",
        "code":   "01100110101001010101010101010110",
    },
    {
        "name": "France Inter (alt)",
        "freq": 87.8,
        "fichier": "FranceInterALT95_7_21janv2017.dat",
        "code":   "01100110101001010101010101010110",
    },
    {
        "name": "France Musique",
        "freq": 91.7,
        "fichier": "FranceMusique91_6_21janv2017.dat",
        "code":   "01100110101001010101010101011001",
    },
    {
        "name": "France Bleu Paris",
        "freq": 107.1,
        "fichier": "FranceBleu102_6_21janv2017.dat",
        "code":   "01100110100101010101010101101001",
    },
]

# -----------------------------
# Flask
# -----------------------------
app = Flask(__name__)

# -----------------------------
# Shared STATE (in-memory)
# -----------------------------
STATE = {
    "ps": "",
    "rt": "",
    "t": 0.0,
    "last_rx": 0.0,
    "selected": None,
}

AUDIO = {"y": [], "sr": 0.0, "rms": 0.0, "peak": 0.0, "t": 0.0, "last_rx": 0.0}
RDS_SCOPE = {"y": [], "sr": 0.0, "rms": 0.0, "peak": 0.0, "t": 0.0, "last_rx": 0.0}
CONST = {"i": [], "q": [], "n": 0, "t": 0.0, "last_rx": 0.0}

# Small lock: we keep it simple (updates are fast)
_LOCK = threading.Lock()


def rpc_client():
    return xmlrpc.client.ServerProxy(XMLRPC_URL, allow_none=True)

def _limit_list(lst, nmax):
    if not isinstance(lst, list):
        return []
    if nmax <= 0:
        return []
    if len(lst) <= nmax:
        return lst
    return lst[-nmax:]

def zmq_json_sub_loop(addr, on_msg, recv_hwm=5):
    ctx = zmq.Context.instance()
    s = ctx.socket(zmq.SUB)
    s.setsockopt(zmq.SUBSCRIBE, b"")
    # drop old packets if we lag
    try:
        s.setsockopt(zmq.RCVHWM, recv_hwm)
    except Exception:
        pass
    s.connect(addr)

    while True:
        try:
            msg = s.recv()
            d = json.loads(msg.decode("utf-8", errors="ignore"))
            on_msg(d)
        except Exception:
            time.sleep(0.01)

# -----------------------------
# ZMQ callbacks (lightweight + limits)
# -----------------------------
def on_rds(d):
    with _LOCK:
        STATE["ps"] = d.get("ps", "") or ""
        STATE["rt"] = d.get("rt", "") or ""
        STATE["t"] = float(d.get("t", 0.0) or 0.0)
        STATE["last_rx"] = time.time()

def on_audio(d):
    with _LOCK:
        AUDIO["y"] = _limit_list(d.get("y", []) or [], 1400)  # cap
        AUDIO["sr"] = float(d.get("sr", 0.0) or 0.0)
        AUDIO["rms"] = float(d.get("rms", 0.0) or 0.0)
        AUDIO["peak"] = float(d.get("peak", 0.0) or 0.0)
        AUDIO["t"] = float(d.get("t", 0.0) or 0.0)
        AUDIO["last_rx"] = time.time()

def on_rds_scope(d):
    with _LOCK:
        RDS_SCOPE["y"] = _limit_list(d.get("y", []) or [], 1400)  # cap
        RDS_SCOPE["sr"] = float(d.get("sr", 0.0) or 0.0)
        RDS_SCOPE["rms"] = float(d.get("rms", 0.0) or 0.0)
        RDS_SCOPE["peak"] = float(d.get("peak", 0.0) or 0.0)
        RDS_SCOPE["t"] = float(d.get("t", 0.0) or 0.0)
        RDS_SCOPE["last_rx"] = time.time()

def on_const(d):
    with _LOCK:
        I = d.get("i", []) or []
        Q = d.get("q", []) or []
        # cap constellation points to keep draw cheap
        I = _limit_list(I, 1200)
        Q = _limit_list(Q, 1200)
        n = min(len(I), len(Q))

        CONST["i"] = I[:n]
        CONST["q"] = Q[:n]
        CONST["n"] = int(d.get("n", n) or n)
        CONST["t"] = float(d.get("t", 0.0) or 0.0)
        CONST["last_rx"] = time.time()

# -----------------------------
# Response helpers (no-store)
# -----------------------------
def json_nostore(payload):
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

# -----------------------------
# APIs
# -----------------------------
@app.route("/api/state")
def api_state():
    with _LOCK:
        return json_nostore(dict(STATE))

@app.route("/api/audio")
def api_audio():
    with _LOCK:
        return json_nostore(dict(AUDIO))

@app.route("/api/rds_scope")
def api_rds_scope():
    with _LOCK:
        return json_nostore(dict(RDS_SCOPE))

@app.route("/api/const")
def api_const():
    with _LOCK:
        return json_nostore(dict(CONST))

@app.route("/api/stations")
def api_stations():
    return json_nostore([{"name": x["name"], "freq": x["freq"]} for x in STATIONS])

@app.route("/api/select", methods=["POST"])
def api_select():
    data = request.get_json(force=True) or {}
    name = data.get("name", "")

    target = next((s for s in STATIONS if s["name"] == name), None)
    if target is None:
        return json_nostore({"ok": False, "error": "unknown station"}), 400

    try:
        rpc = rpc_client()
        # Important: set fichier puis code (comme tu fais)
        rpc.set_fichier(target["fichier"])
        rpc.set_code(target["code"])
        with _LOCK:
            STATE["selected"] = target["name"]
        return json_nostore({"ok": True})
    except Exception as e:
        return json_nostore({"ok": False, "error": str(e)}), 500

# ---- BEST OPT: one request for everything
@app.route("/api/all")
def api_all():
    with _LOCK:
        payload = {
            "state": dict(STATE),
            "audio": dict(AUDIO),
            "rds_scope": dict(RDS_SCOPE),
            "const": dict(CONST),
        }
    return json_nostore(payload)

# -----------------------------
# UI (FM style, optimized front)
# Layout: station LEFT, audio RIGHT, then RDS + constellation below
# + ADD: FM DIAL (graduations + cursor)
# -----------------------------
PAGE = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FM • RDS Demo</title>
<style>
:root{
  --bg:#070b18;
  --card:rgba(255,255,255,.06);
  --stroke:rgba(255,255,255,.13);
  --txt:#eaf0ff;
  --mut:rgba(234,240,255,.65);
  --acc:#41d6ff;
  --good:#2ee59d;
  --bad:#ff4d6d;
  --r:22px;
  --shadow:0 18px 60px rgba(0,0,0,.45);
}
*{box-sizing:border-box}
body{
  margin:0; color:var(--txt);
  background:
    radial-gradient(1200px 700px at 10% 10%, rgba(65,214,255,.16), transparent 60%),
    radial-gradient(900px 600px at 85% 20%, rgba(45,91,255,.16), transparent 60%),
    radial-gradient(900px 700px at 50% 100%, rgba(46,229,157,.08), transparent 60%),
    var(--bg);
  font-family:ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
  min-height:100vh;
}
.wrap{max-width:1260px;margin:22px auto;padding:0 16px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px}
.logo{
  width:38px;height:38px;border-radius:12px;
  background:linear-gradient(135deg, rgba(65,214,255,.9), rgba(45,91,255,.9));
  box-shadow:0 10px 30px rgba(0,0,0,.35);
}
.title{font-weight:950;letter-spacing:.10em;text-transform:uppercase;font-size:13px;opacity:.9}
.chips{display:flex;gap:10px;flex-wrap:wrap}
.chip{
  background:rgba(255,255,255,.06);
  border:1px solid var(--stroke);
  padding:8px 12px;border-radius:999px;
  font-size:13px;color:var(--mut);
  display:flex;align-items:center;gap:8px;
  backdrop-filter: blur(10px);
}
.dot{width:10px;height:10px;border-radius:50%;background:var(--bad);box-shadow:0 0 0 3px rgba(255,77,109,.15)}
.dot.ok{background:var(--good);box-shadow:0 0 0 3px rgba(46,229,157,.15)}

.gridTop{display:grid;grid-template-columns:1.05fr .95fr;gap:16px;margin-top:14px}
.gridBottom{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}
@media(max-width:980px){
  .gridTop,.gridBottom{grid-template-columns:1fr}
}
.card{
  background:var(--card);
  border:1px solid var(--stroke);
  border-radius:var(--r);
  box-shadow:var(--shadow);
  padding:16px;
  backdrop-filter: blur(14px);
  overflow:hidden;
  position:relative;
}
.card:before{
  content:"";
  position:absolute;inset:-1px;
  background:
    radial-gradient(600px 350px at 20% 20%, rgba(65,214,255,.14), transparent 60%),
    radial-gradient(600px 350px at 80% 80%, rgba(45,91,255,.12), transparent 60%);
  opacity:.8;
  pointer-events:none;
}
.card > *{position:relative}
.h{font-weight:850;letter-spacing:.12em;text-transform:uppercase;font-size:12px;color:var(--mut)}
.ps{font-size:46px;font-weight:950;letter-spacing:3px;line-height:1;margin:10px 0 6px;text-shadow:0 8px 26px rgba(0,0,0,.45)}
.rt{font-size:18px;opacity:.92;margin-top:6px;white-space:pre-wrap}
.kv{margin-top:8px;font-size:13px;color:var(--mut);display:flex;gap:12px;flex-wrap:wrap}
.btns{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
button{
  background:rgba(255,255,255,.07);
  border:1px solid var(--stroke);
  color:var(--txt);
  padding:10px 12px;
  border-radius:14px;
  cursor:pointer;
  font-weight:850;
  letter-spacing:.02em;
}
button:hover{border-color:rgba(65,214,255,.55)}
button.sel{border-color:rgba(46,229,157,.75); box-shadow:0 0 0 3px rgba(46,229,157,.15) inset}
button:disabled{opacity:.45;cursor:not-allowed}

canvas{width:100%;height:240px;display:block;border-radius:14px}
.small{font-size:12px;color:var(--mut);margin-top:8px}
.meter{margin-top:12px;height:10px;border-radius:999px;overflow:hidden;border:1px solid var(--stroke);background:rgba(0,0,0,.22)}
.meter > div{height:100%;width:20%;background:linear-gradient(90deg, rgba(45,91,255,.95), rgba(65,214,255,.95));transition:width .15s ease}

/* =========================
   FM DIAL (graduations + cursor)
   ========================= */
.dialWrap{margin-top:12px}
.dial{
  position:relative;
  height:62px;
  border-radius:16px;
  border:1px solid var(--stroke);
  background:rgba(0,0,0,.18);
  overflow:hidden;
}
.dial:before{
  content:"";
  position:absolute;inset:0;
  background:
    linear-gradient(180deg, rgba(255,255,255,.06), transparent 40%),
    radial-gradient(600px 220px at 50% 0%, rgba(65,214,255,.10), transparent 60%);
  pointer-events:none;
}
.tick{
  position:absolute;
  bottom:14px;
  width:1px;
  background:rgba(234,240,255,.55);
  opacity:.75;
}
.tick.small{height:10px; bottom:16px; opacity:.45}
.tick.big{height:18px; bottom:14px; opacity:.75}
.label{
  position:absolute;
  bottom:2px;
  transform:translateX(-50%);
  font-size:11px;
  color:rgba(234,240,255,.62);
  letter-spacing:.04em;
  user-select:none;
}
.cursor{
  position:absolute;
  top:6px; bottom:6px;
  width:10px;
  border-radius:12px;
  background:linear-gradient(180deg, rgba(65,214,255,.95), rgba(45,91,255,.95));
  box-shadow:
    0 0 0 2px rgba(255,255,255,.10) inset,
    0 0 22px rgba(65,214,255,.55),
    0 10px 26px rgba(0,0,0,.35);
  transform:translateX(-50%);
}
.cursor:after{
  content:"";
  position:absolute;
  left:50%; top:50%;
  width:26px; height:26px;
  transform:translate(-50%,-50%);
  border-radius:999px;
  background:radial-gradient(circle, rgba(65,214,255,.35), transparent 70%);
  filter:blur(0.2px);
  opacity:.8;
  pointer-events:none;
}
.dialHeader{
  display:flex; align-items:baseline; justify-content:space-between;
  margin-top:6px;
  color:rgba(234,240,255,.65);
  font-size:12px;
}
</style>
</head>
<body>
<div class="wrap">

  <div class="topbar">
    <div class="brand">
      <div class="logo"></div>
      <div>
        <div class="title">FM Monitor • Demo fichiers • RDS</div>
      </div>
    </div>
    <div class="chips">
      <div class="chip"><span class="dot" id="dot"></span><span id="status">pas de données</span></div>
      <div class="chip">Sélection: <b id="sel">—</b></div>
      <div class="chip">Age: <b id="age">—</b> s</div>
    </div>
  </div>

  <div class="gridTop">
    <!-- LEFT: Station + RDS text -->
    <div class="card">
      <div class="h">Station</div>

      <div class="btns" id="btns"></div>

      <!-- DIAL + CURSOR (ADDED) -->
      <div class="dialWrap">
        <div class="dial" id="dial">
          <div class="cursor" id="cursor" style="left:0%"></div>
        </div>
        <div class="dialHeader">
          <span>FM band</span>
          <span>87–108 MHz</span>
        </div>
      </div>

      <div class="ps" id="ps">--------</div>
      <div class="rt" id="rt">…</div>

      <div class="kv">
        <div>Fréquence: <b id="freq">—</b> MHz</div>
        <div>RDS t: <b id="rds_t">—</b></div>
      </div>

      <div class="meter"><div id="meterfill"></div></div>
    </div>

    <!-- RIGHT: Audio scope -->
    <div class="card">
      <div class="h">Audio • Scope</div>
      <canvas id="c_audio"></canvas>
      <div class="kv">
        <div>RMS: <b id="a_rms">0</b></div>
        <div>Peak: <b id="a_peak">0</b></div>
        <div>SR: <b id="a_sr">0</b> Hz</div>
      </div>
    </div>
  </div>

  <div class="gridBottom">
    <div class="card">
      <div class="h">RDS • Scope (signal)</div>
      <canvas id="c_rds"></canvas>
      <div class="kv">
        <div>RMS: <b id="r_rms">0</b></div>
        <div>Peak: <b id="r_peak">0</b></div>
        <div>SR: <b id="r_sr">0</b> Hz</div>
      </div>
    </div>

    <div class="card">
      <div class="h">RDS • Constellation (sortie Symbol Sync)</div>
      <canvas id="c_const"></canvas>
      <div class="kv">
        <div>Points: <b id="cn">0</b></div>
      </div>
    </div>
  </div>

</div>

<script>
let stations = [];
let selected = null;
let selecting = false;

// draw throttling: only redraw when "t" changes
let lastStateT = 0, lastAudioT = 0, lastRdsT = 0, lastConstT = 0;

// canvases
const cAudio = document.getElementById("c_audio");
const xAudio = cAudio.getContext("2d");
const cRds   = document.getElementById("c_rds");
const xRds   = cRds.getContext("2d");
const cConst = document.getElementById("c_const");
const xConst = cConst.getContext("2d");

// ===== DIAL refs (ADDED)
const dial = document.getElementById("dial");
const cursor = document.getElementById("cursor");
const FM_MIN = 87.0;
const FM_MAX = 108.0;
let dialBuilt = false;

function resize(c){
  const dpr = window.devicePixelRatio || 1;
  const r = c.getBoundingClientRect();
  const w = Math.max(10, Math.floor(r.width*dpr));
  const h = Math.max(10, Math.floor(r.height*dpr));
  if(c.width !== w || c.height !== h){ c.width = w; c.height = h; }
}

// ===== Build dial graduations + labels (ADDED)
function buildDial(){
  if(!dial) return;
  // remove existing ticks/labels except cursor
  [...dial.querySelectorAll(".tick, .label")].forEach(n=>n.remove());

  const W = dial.clientWidth;
  if(W <= 20) return;

  // ticks every 0.5 MHz, big each 1 MHz, label each 2 MHz
  for(let f = FM_MIN; f <= FM_MAX + 1e-6; f += 0.5){
    const x = (f - FM_MIN) / (FM_MAX - FM_MIN) * W;

    const t = document.createElement("div");
    const isInt = Math.abs(f - Math.round(f)) < 1e-6;
    t.className = "tick " + (isInt ? "big" : "small");
    t.style.left = `${Math.round(x)}px`;
    dial.appendChild(t);

    if(isInt && (Math.round(f) % 2 === 0)){
      const lab = document.createElement("div");
      lab.className = "label";
      lab.style.left = `${Math.round(x)}px`;
      lab.textContent = `${Math.round(f)}`;
      dial.appendChild(lab);
    }
  }
  dialBuilt = true;
}

// ===== Set cursor position from frequency (ADDED)
function setCursorFreq(freq){
  if(!dialBuilt) buildDial();
  const W = dial.clientWidth;
  if(W <= 20) return;

  // clamp
  let f = Number(freq);
  if(!Number.isFinite(f)) return;
  if(f < FM_MIN) f = FM_MIN;
  if(f > FM_MAX) f = FM_MAX;

  const x = (f - FM_MIN) / (FM_MAX - FM_MIN) * W;
  cursor.style.left = `${x}px`;
}

function drawScope(canvas, ctx, y){
  resize(canvas);
  const W=canvas.width,H=canvas.height;
  ctx.clearRect(0,0,W,H);
  if(!y||y.length<2)return;

  let max=0;
  for(const v of y) max=Math.max(max,Math.abs(v));
  if(max<1e-6)max=1;

  // light grid
  ctx.globalAlpha=0.14;
  ctx.strokeStyle="white";
  ctx.beginPath();
  for(let k=1;k<10;k++){ const x=(W*k)/10; ctx.moveTo(x,0); ctx.lineTo(x,H); }
  for(let k=1;k<10;k++){ const yy=(H*k)/10; ctx.moveTo(0,yy); ctx.lineTo(W,yy); }
  ctx.stroke();
  ctx.globalAlpha=1.0;

  ctx.strokeStyle="white";
  ctx.beginPath();
  const scale = (H*0.45)/max;
  for(let i=0;i<y.length;i++){
    const x=i*(W/(y.length-1));
    const yy=H/2 - y[i]*scale;
    if(i===0) ctx.moveTo(x,yy); else ctx.lineTo(x,yy);
  }
  ctx.stroke();
}

function drawConst(canvas, ctx, I, Q){
  resize(canvas);
  const W=canvas.width,H=canvas.height;
  ctx.clearRect(0,0,W,H);
  if(!I||!Q||I.length<2)return;

  // grid + axes
  ctx.globalAlpha=0.14;
  ctx.strokeStyle="white";
  ctx.beginPath();
  for(let k=1;k<10;k++){ const x=(W*k)/10; ctx.moveTo(x,0); ctx.lineTo(x,H); }
  for(let k=1;k<10;k++){ const y=(H*k)/10; ctx.moveTo(0,y); ctx.lineTo(W,y); }
  ctx.stroke();

  ctx.globalAlpha=0.35;
  ctx.beginPath();
  ctx.moveTo(W/2,0); ctx.lineTo(W/2,H);
  ctx.moveTo(0,H/2); ctx.lineTo(W,H/2);
  ctx.stroke();
  ctx.globalAlpha=1.0;

  let max=0;
  for(let k=0;k<I.length;k++){
    const a = Math.abs(I[k]), b = Math.abs(Q[k]);
    if(a>max) max=a;
    if(b>max) max=b;
  }
  if(max<1e-6)max=1;
  const sx=(W/2)/(max*1.2), sy=(H/2)/(max*1.2);

  ctx.fillStyle="white";
  // draw fewer points if huge
  const step = Math.max(1, Math.floor(I.length/1200));
  for(let k=0;k<I.length;k+=step){
    const x=W/2 + I[k]*sx;
    const y=H/2 - Q[k]*sy;
    ctx.fillRect(x, y, 2, 2);
  }
}

function renderButtons(){
  const el = document.getElementById("btns");
  const btns = el.querySelectorAll("button");
  btns.forEach((b)=>{
    b.classList.toggle("sel", b.dataset.name === selected);
    b.disabled = selecting;
  });
}

async function loadStations(){
  const r = await fetch("/api/stations",{cache:"no-store"});
  stations = await r.json();

  const el = document.getElementById("btns");
  el.innerHTML = "";
  for(const s of stations){
    const b = document.createElement("button");
    b.textContent = `${s.freq.toFixed(1)} • ${s.name}`;
    b.dataset.name = s.name;
    b.dataset.freq = s.freq;

    b.onclick = async ()=>{
      if(selecting) return;
      selecting = true;
      renderButtons();
      try{
        const resp = await fetch("/api/select",{
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body: JSON.stringify({name:s.name})
        });
        await resp.json().catch(()=>null);
        selected = s.name;

        // update cursor immediately on click (ADDED)
        setCursorFreq(s.freq);

      }finally{
        selecting = false;
        renderButtons();
      }
    };
    el.appendChild(b);
  }
  renderButtons();

  // build dial once stations exist (ADDED)
  buildDial();
}

function setStatus(ok, age){
  document.getElementById("status").textContent = ok ? "RDS en direct" : "pas de données";
  document.getElementById("dot").className = ok ? "dot ok" : "dot";
  document.getElementById("age").textContent = (age<999)?age.toFixed(2):"—";
  document.getElementById("meterfill").style.width = ok ? "85%" : "20%";
}

function findFreqByName(name){
  const s = stations.find(x=>x.name===name);
  return s ? s.freq : null;
}

async function tick(){
  // 1 request only
  const all = await (await fetch("/api/all",{cache:"no-store"})).json();

  const st = all.state || {};
  const a  = all.audio || {};
  const r  = all.rds_scope || {};
  const co = all.const || {};

  // selection + frequency
  selected = st.selected || selected;
  document.getElementById("sel").textContent = selected || "—";
  const f = selected ? findFreqByName(selected) : null;
  document.getElementById("freq").textContent = (f!=null) ? f.toFixed(1) : "—";

  // update dial cursor when selection known (ADDED)
  if(f != null) setCursorFreq(f);

  renderButtons();

  // RDS text
  if ((st.t||0) !== lastStateT){
    document.getElementById("ps").textContent = (st.ps||"").trim() || "--------";
    document.getElementById("rt").textContent = (st.rt||"").trim() || "…";
    lastStateT = st.t||0;
  }
  document.getElementById("rds_t").textContent = st.t ? new Date((st.t||0)*1000).toLocaleTimeString() : "—";

  // age + led
  const now = Date.now()/1000;
  const age = st.last_rx ? (now - st.last_rx) : 1e9;
  setStatus(age < 2.0, age);

  // audio redraw only if new
  if ((a.t||0) !== lastAudioT){
    drawScope(cAudio, xAudio, a.y);
    lastAudioT = a.t||0;
  }
  document.getElementById("a_rms").textContent = (a.rms||0).toFixed(3);
  document.getElementById("a_peak").textContent = (a.peak||0).toFixed(3);
  document.getElementById("a_sr").textContent = Math.round(a.sr||0);

  // rds redraw only if new
  if ((r.t||0) !== lastRdsT){
    drawScope(cRds, xRds, r.y);
    lastRdsT = r.t||0;
  }
  document.getElementById("r_rms").textContent = (r.rms||0).toFixed(3);
  document.getElementById("r_peak").textContent = (r.peak||0).toFixed(3);
  document.getElementById("r_sr").textContent = Math.round(r.sr||0);

  // const redraw only if new
  if ((co.t||0) !== lastConstT){
    drawConst(cConst, xConst, co.i, co.q);
    lastConstT = co.t||0;
  }
  document.getElementById("cn").textContent = co.n || 0;
}

loadStations();

// 250ms is plenty; UI stays smooth; CPU stays cool
setInterval(tick, 250);
tick();

// re-render on resize (cheap)
window.addEventListener("resize", ()=>{
  // force redraw plots
  lastAudioT = 0; lastRdsT = 0; lastConstT = 0;

  // rebuild dial graduations (ADDED)
  dialBuilt = false;
  buildDial();

  // re-place cursor
  const f = selected ? findFreqByName(selected) : null;
  if(f != null) setCursorFreq(f);
});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    resp = make_response(render_template_string(PAGE))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Start ZMQ subscribers (low HWM to avoid backlog)
    threading.Thread(target=zmq_json_sub_loop, args=(ZMQ_RDS_ADDR, on_rds, 10), daemon=True).start()
    threading.Thread(target=zmq_json_sub_loop, args=(ZMQ_AUDIO_ADDR, on_audio, 3), daemon=True).start()
    threading.Thread(target=zmq_json_sub_loop, args=(ZMQ_RDS_SCOPE_ADDR, on_rds_scope, 3), daemon=True).start()
    threading.Thread(target=zmq_json_sub_loop, args=(ZMQ_CONST_ADDR, on_const, 3), daemon=True).start()

    # Flask
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
