from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, url_for

from vectrion.config_store import (
    get_active_stages,
    get_stage_name,
    get_stage_order,
    is_setup_complete,
    load_config,
    save_config,
)
from vectrion.constants import DEFAULT_STAGES, LEGAL_DISCLAIMER
from vectrion.runbook import next_layer, run_layer
from vectrion.storage import Storage

# ─────────────────────────────────────────────
# SHARED STYLES & LAYOUT
# ─────────────────────────────────────────────

_CSS = """
<style>
:root {
  --navy:        #0A1628;
  --navy-2:      #132240;
  --navy-3:      #1E3A5F;
  --blue:        #1D4ED8;
  --blue-light:  #3B82F6;
  --blue-glow:   rgba(59,130,246,0.18);
  --silver:      #94A3B8;
  --silver-light:#CBD5E1;
  --silver-pale: #E2E8F0;
  --bg:          #F0F4F9;
  --white:       #FFFFFF;
  --text:        #0F172A;
  --muted:       #64748B;
  --border:      #D1D9E6;
  --success:     #059669;
  --danger:      #DC2626;
  --gold:        #C8A84B;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
}

/* ── TOP BAR ── */
.topbar {
  display: flex;
  align-items: center;
  background: var(--navy);
  border-bottom: 1px solid var(--navy-3);
  height: 58px;
  padding: 0 28px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 12px rgba(0,0,0,0.35);
}
.topbar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
}
.topbar-icon {
  width: 34px; height: 34px;
  background: linear-gradient(135deg, var(--blue-light), var(--navy-3));
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  box-shadow: 0 0 12px var(--blue-glow);
}
.topbar-name {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--white);
}
.topbar-sub {
  font-size: 9px;
  letter-spacing: 2.5px;
  color: var(--silver);
  text-transform: uppercase;
  margin-top: 1px;
}
.topbar-divider {
  width: 1px; height: 32px;
  background: var(--navy-3);
  margin: 0 20px;
}
nav { margin-left: auto; display: flex; align-items: center; gap: 4px; }
nav a {
  color: var(--silver-light);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  padding: 7px 16px;
  border-radius: 6px;
  letter-spacing: 0.5px;
  transition: all 0.15s;
  border: 1px solid transparent;
}
nav a:hover {
  background: rgba(255,255,255,0.07);
  color: var(--white);
  border-color: var(--navy-3);
}
nav a.active {
  background: var(--navy-3);
  color: var(--white);
  border-color: var(--blue);
}
.topbar-badge {
  font-size: 10px;
  padding: 2px 8px;
  background: var(--blue);
  color: #fff;
  border-radius: 999px;
  letter-spacing: 1px;
  margin-left: 8px;
}

/* ── PAGE WRAPPER ── */
.page { max-width: 1140px; margin: 32px auto; padding: 0 28px 60px; }
.page-header { margin-bottom: 24px; }
.page-title {
  font-size: 22px; font-weight: 700;
  color: var(--navy); letter-spacing: 0.5px;
}
.page-sub { color: var(--muted); font-size: 13px; margin-top: 3px; }

/* ── CARDS ── */
.card {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 22px 26px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(10,22,40,0.06);
}
.card-title {
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--navy-3);
  padding-bottom: 14px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--silver-pale);
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── BUTTONS ── */
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 9px 20px;
  font-size: 13px; font-weight: 600;
  border-radius: 7px; border: none; cursor: pointer;
  text-decoration: none;
  transition: all 0.15s;
  letter-spacing: 0.3px;
}
.btn-primary {
  background: var(--blue);
  color: #fff;
  box-shadow: 0 2px 8px rgba(29,78,216,0.3);
}
.btn-primary:hover { background: #1a44c4; box-shadow: 0 4px 14px rgba(29,78,216,0.4); }
.btn-secondary {
  background: var(--white);
  color: var(--text);
  border: 1px solid var(--border);
}
.btn-secondary:hover { background: var(--bg); border-color: var(--silver); }
.btn-danger { background: var(--danger); color: #fff; }
.btn-danger:hover { background: #b91c1c; }
.btn-sm { padding: 5px 12px; font-size: 12px; }
.btn-ghost {
  background: transparent;
  color: var(--silver);
  border: none;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 5px;
  font-size: 18px;
}
.btn-ghost:hover { color: var(--text); background: var(--silver-pale); }

/* ── FORM ELEMENTS ── */
label { font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; display: block; margin-bottom: 5px; }
input[type=text], input[type=number], select, textarea {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 7px;
  font-size: 13px;
  background: var(--white);
  color: var(--text);
  transition: border 0.15s, box-shadow 0.15s;
}
input[type=text]:focus, input[type=number]:focus, select:focus, textarea:focus {
  outline: none;
  border-color: var(--blue-light);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
}

/* ── TABLES ── */
table { border-collapse: collapse; width: 100%; }
thead th {
  background: var(--navy);
  color: var(--silver-light);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  padding: 10px 14px;
  text-align: left;
}
thead th:first-child { border-radius: 8px 0 0 0; }
thead th:last-child  { border-radius: 0 8px 0 0; }
tbody td { padding: 11px 14px; border-bottom: 1px solid var(--silver-pale); vertical-align: middle; }
tbody tr:hover td { background: #F5F8FF; }
tbody tr:last-child td { border-bottom: none; }

/* ── BADGES / PILLS ── */
.badge {
  display: inline-flex; align-items: center;
  padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
}
.badge-blue   { background: #DBEAFE; color: #1D4ED8; }
.badge-green  { background: #D1FAE5; color: #065F46; }
.badge-silver { background: var(--silver-pale); color: var(--muted); }
.badge-gold   { background: #FEF3C7; color: #92400E; }

.stage-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 12px; border-radius: 999px;
  font-size: 11px; font-weight: 600;
  background: var(--silver-pale); color: var(--muted);
  margin: 3px;
  border: 1px solid var(--border);
}
.stage-pill.done    { background: #D1FAE5; color: #065F46; border-color: #A7F3D0; }
.stage-pill.current { background: #DBEAFE; color: #1E40AF; border-color: #93C5FD; font-weight: 700; }

/* ── PRE / CODE ── */
pre {
  background: var(--navy);
  color: #A8C0E0;
  padding: 16px 18px;
  border-radius: 9px;
  white-space: pre-wrap;
  max-height: 400px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.7;
  border: 1px solid var(--navy-3);
}

/* ── SETUP WIZARD STEPS ── */
.wizard-steps { display: flex; margin-bottom: 28px; gap: 0; }
.wizard-step {
  flex: 1; text-align: center;
  padding: 12px 16px; font-size: 13px; font-weight: 600;
  background: var(--white); border: 1px solid var(--border);
  color: var(--muted);
}
.wizard-step:first-child { border-radius: 8px 0 0 8px; }
.wizard-step:last-child  { border-radius: 0 8px 8px 0; }
.wizard-step.active { background: var(--blue); color: #fff; border-color: var(--blue); }
.wizard-step.done   { background: #D1FAE5; color: #065F46; border-color: #A7F3D0; }

/* ── DISCLAIMER ── */
.disclaimer {
  font-size: 11px; color: var(--muted);
  border-top: 1px solid var(--border);
  padding-top: 14px; margin-top: 8px;
  letter-spacing: 0.2px;
}

/* ── MUTED TEXT ── */
.muted { color: var(--muted); font-size: 13px; }

/* ─────────────────────────────────────────────
   WELCOME PAGE
───────────────────────────────────────────── */
.welcome-wrap {
  min-height: calc(100vh - 58px);
  background: linear-gradient(160deg, var(--navy) 0%, var(--navy-2) 55%, #0E2040 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}
.welcome-inner {
  width: 100%;
  max-width: 780px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}
.welcome-hero { text-align: center; }
.welcome-logo {
  width: 70px; height: 70px;
  background: linear-gradient(135deg, var(--blue-light), var(--blue));
  border-radius: 18px;
  display: flex; align-items: center; justify-content: center;
  font-size: 36px;
  margin: 0 auto 20px;
  box-shadow: 0 0 40px rgba(59,130,246,0.35);
}
.welcome-title {
  font-size: 42px; font-weight: 800;
  letter-spacing: 5px;
  color: var(--white);
}
.welcome-tagline {
  font-size: 13px;
  letter-spacing: 4px;
  color: var(--silver);
  text-transform: uppercase;
  margin-top: 6px;
}
.welcome-chat {
  width: 100%;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  overflow: hidden;
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 40px rgba(0,0,0,0.4);
}
.welcome-chat-header {
  background: rgba(255,255,255,0.05);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding: 14px 20px;
  display: flex; align-items: center; gap: 10px;
  color: var(--silver-light);
  font-size: 13px; font-weight: 600; letter-spacing: 0.5px;
}
.welcome-chat-header .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #22C55E;
  box-shadow: 0 0 6px #22C55E;
}
.welcome-messages {
  padding: 20px;
  display: flex; flex-direction: column; gap: 14px;
  min-height: 220px;
  max-height: 340px;
  overflow-y: auto;
}
.w-msg {
  display: flex; gap: 12px; align-items: flex-start;
}
.w-msg.user { flex-direction: row-reverse; }
.w-avatar {
  width: 34px; height: 34px; flex-shrink: 0;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px;
  font-weight: 700;
}
.w-avatar.bot  { background: linear-gradient(135deg, var(--blue-light), var(--blue)); }
.w-avatar.user { background: var(--navy-3); color: var(--silver-light); font-size: 12px; }
.w-bubble {
  max-width: 82%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.w-bubble.bot  {
  background: rgba(255,255,255,0.07);
  color: var(--silver-light);
  border: 1px solid rgba(255,255,255,0.08);
  border-top-left-radius: 3px;
}
.w-bubble.user {
  background: var(--blue);
  color: #fff;
  border-top-right-radius: 3px;
}
.welcome-input-row {
  border-top: 1px solid rgba(255,255,255,0.08);
  padding: 14px 16px;
  display: flex; gap: 10px;
  background: rgba(255,255,255,0.03);
}
.welcome-input {
  flex: 1;
  background: rgba(255,255,255,0.07) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  color: var(--white) !important;
  border-radius: 8px !important;
}
.welcome-input::placeholder { color: var(--silver) !important; }
.welcome-input:focus {
  border-color: var(--blue-light) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.2) !important;
}
.welcome-actions {
  display: flex; gap: 14px; justify-content: center;
  margin-top: 4px;
}
.btn-enter {
  background: var(--blue);
  color: #fff;
  padding: 13px 36px;
  font-size: 14px; font-weight: 700;
  letter-spacing: 1px;
  border-radius: 9px;
  text-decoration: none;
  border: none; cursor: pointer;
  box-shadow: 0 4px 20px rgba(29,78,216,0.45);
  transition: all 0.15s;
}
.btn-enter:hover { background: #1a44c4; box-shadow: 0 6px 28px rgba(29,78,216,0.55); transform: translateY(-1px); }

/* ─── CHAT BUBBLE (non-welcome pages) ─── */
#chat-bubble { position: fixed; bottom: 28px; right: 28px; z-index: 9999; }
#chat-toggle {
  width: 54px; height: 54px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--blue-light), var(--blue));
  color: #fff;
  font-size: 24px;
  border: none; cursor: pointer;
  box-shadow: 0 4px 18px rgba(29,78,216,0.45);
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
#chat-toggle:hover { transform: scale(1.08); box-shadow: 0 6px 24px rgba(29,78,216,0.55); }
#chat-panel {
  display: none;
  position: absolute; bottom: 66px; right: 0;
  width: 380px;
  background: var(--navy);
  border: 1px solid var(--navy-3);
  border-radius: 16px;
  box-shadow: 0 12px 50px rgba(0,0,0,0.4);
  flex-direction: column;
  overflow: hidden;
}
#chat-panel.open { display: flex; }
#chat-header {
  background: var(--navy-2);
  border-bottom: 1px solid var(--navy-3);
  padding: 14px 18px;
  display: flex; align-items: center; gap: 10px;
}
#chat-header-info { flex: 1; }
#chat-header-name { font-size: 14px; font-weight: 700; color: var(--white); letter-spacing: 0.5px; }
#chat-header-status { font-size: 11px; color: #22C55E; margin-top: 1px; }
#chat-close {
  background: none; border: none; color: var(--silver);
  font-size: 18px; cursor: pointer; padding: 2px 6px;
  border-radius: 5px;
}
#chat-close:hover { color: var(--white); background: rgba(255,255,255,0.08); }
#chat-messages {
  flex: 1; overflow-y: auto;
  padding: 16px;
  max-height: 320px;
  display: flex; flex-direction: column; gap: 12px;
}
.chat-msg {
  display: flex; gap: 10px; align-items: flex-start;
}
.chat-msg.user { flex-direction: row-reverse; }
.chat-avatar {
  width: 28px; height: 28px; flex-shrink: 0;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--blue-light), var(--blue));
  display: flex; align-items: center; justify-content: center;
  font-size: 14px;
}
.chat-avatar.user { background: var(--navy-3); color: var(--silver-light); font-size: 11px; font-weight: 700; }
.chat-bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px; line-height: 1.55;
}
.chat-bubble.bot {
  background: rgba(255,255,255,0.07);
  color: var(--silver-light);
  border: 1px solid rgba(255,255,255,0.08);
  border-top-left-radius: 3px;
}
.chat-bubble.user {
  background: var(--blue);
  color: #fff;
  border-top-right-radius: 3px;
}
#chat-input-row {
  border-top: 1px solid var(--navy-3);
  padding: 12px 14px;
  display: flex; gap: 8px;
  background: var(--navy-2);
}
#chat-input {
  flex: 1;
  background: rgba(255,255,255,0.07) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  color: var(--white) !important;
  padding: 8px 12px !important;
  border-radius: 7px !important;
  font-size: 13px;
}
#chat-input::placeholder { color: var(--silver) !important; }
#chat-input:focus {
  border-color: var(--blue-light) !important;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}
#chat-send {
  background: var(--blue); color: #fff;
  border: none; border-radius: 7px;
  padding: 8px 16px; font-size: 13px; font-weight: 600;
  cursor: pointer;
}
#chat-send:hover { background: #1a44c4; }
</style>
"""

_TOPBAR = """
<div class="topbar">
  <a href="/" class="topbar-brand">
    <div class="topbar-icon">&#9670;</div>
    <div>
      <div class="topbar-name">VECTORIAN</div>
      <div class="topbar-sub">Breach Response Platform</div>
    </div>
  </a>
  <div class="topbar-divider"></div>
  <nav>
    <a href="/" class="{{ 'active' if active_nav == 'dashboard' else '' }}">Dashboard</a>
    <a href="/config" class="{{ 'active' if active_nav == 'config' else '' }}">Configuration</a>
  </nav>
</div>
"""

_CHAT_BUBBLE = """
<div id="chat-bubble">
  <div id="chat-panel">
    <div id="chat-header">
      <div class="chat-avatar">&#129302;</div>
      <div id="chat-header-info">
        <div id="chat-header-name">Vectorian AI</div>
        <div id="chat-header-status">&#9679; Online</div>
      </div>
      <button id="chat-close" onclick="toggleChat()">&#x2715;</button>
    </div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
      <input id="chat-input" type="text" placeholder="Ask Vectorian..." />
      <button id="chat-send" onclick="sendChat()">Send</button>
    </div>
  </div>
  <button id="chat-toggle" onclick="toggleChat()" title="Chat with Vectorian">&#129302;</button>
</div>
<script>
(function() {
  const KEY = 'vect_chat_v2';
  function getHist() { try { return JSON.parse(sessionStorage.getItem(KEY)||'[]'); } catch { return []; } }
  function saveHist(h) { sessionStorage.setItem(KEY, JSON.stringify(h)); }
  function renderMsgs() {
    const box = document.getElementById('chat-messages');
    const h = getHist();
    box.innerHTML = '';
    h.forEach(m => {
      const wrap = document.createElement('div');
      wrap.className = 'chat-msg ' + m.role;
      const av = document.createElement('div');
      av.className = 'chat-avatar ' + m.role;
      av.textContent = m.role === 'bot' ? '⚙' : 'OP';
      const bub = document.createElement('div');
      bub.className = 'chat-bubble ' + m.role;
      bub.textContent = m.text;
      wrap.appendChild(av); wrap.appendChild(bub);
      box.appendChild(wrap);
    });
    box.scrollTop = box.scrollHeight;
  }
  function addMsg(role, text) {
    const h = getHist(); h.push({role, text}); saveHist(h); renderMsgs();
  }
  window.toggleChat = function() {
    const panel = document.getElementById('chat-panel');
    const open = panel.classList.toggle('open');
    if (open) {
      if (!getHist().length) {
        addMsg('bot', 'Hello, Operator. I am Vectorian — your AI breach response agent. I can guide you through all 9 stages of the breach response workflow, answer questions about regulatory requirements, or help you assess incident scope. How can I assist you today?');
      }
      renderMsgs();
      document.getElementById('chat-input').focus();
    }
  };
  window.sendChat = function() {
    const inp = document.getElementById('chat-input');
    const msg = inp.value.trim();
    if (!msg) return;
    inp.value = '';
    addMsg('user', msg);
    const iid = document.body.dataset.incidentId || '';
    const payload = {message: msg};
    if (iid) payload.incident_id = iid;
    fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    }).then(r=>r.json()).then(d=>addMsg('bot', d.reply||'No response.')).catch(()=>addMsg('bot','Unable to reach Vectorian. Please try again.'));
  };
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' && document.activeElement === document.getElementById('chat-input')) sendChat();
  });
})();
</script>
"""

# ─────────────────────────────────────────────
# WELCOME PAGE
# ─────────────────────────────────────────────

WELCOME_TMPL = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vectorian — Breach Response Platform</title>
  """ + _CSS + """
</head>
<body>
""" + _TOPBAR + """
<div class="welcome-wrap">
  <div class="welcome-inner">
    <div class="welcome-hero">
      <div class="welcome-logo">&#9670;</div>
      <div class="welcome-title">VECTORIAN</div>
      <div class="welcome-tagline">AI-Powered Breach Response Platform</div>
    </div>

    <div class="welcome-chat" style="width:100%">
      <div class="welcome-chat-header">
        <div class="dot"></div>
        Vectorian AI &mdash; Breach Response Agent
        <span style="margin-left:auto;font-size:11px;color:var(--silver);letter-spacing:1px">SECURE CHANNEL</span>
      </div>
      <div class="welcome-messages" id="w-messages">
        <div class="w-msg">
          <div class="w-avatar bot">&#9670;</div>
          <div class="w-bubble bot" id="greeting-bubble"></div>
        </div>
      </div>
      <div class="welcome-input-row">
        <input class="welcome-input" id="w-input" type="text" placeholder="Ask Vectorian anything about breach response..." />
        <button class="btn-enter" style="padding:9px 22px;font-size:13px" onclick="wSend()">Send</button>
      </div>
    </div>

    <div class="welcome-actions">
      <a href="{{ enter_url }}" class="btn-enter">&#9654;&nbsp; Enter Platform</a>
    </div>

    <div style="text-align:center;color:var(--silver);font-size:11px;letter-spacing:0.5px">
      {{ disclaimer }}
    </div>
  </div>
</div>

<script>
const GREETING = "Hello, Operator. I am Vectorian — your AI-powered breach response agent.\\n\\nMy purpose is to guide your team through the complete 9-stage data breach response workflow: from initial scope confirmation and data normalization, through regulatory analysis and individual notification preparation, all the way to regulatory filings and public disclosure.\\n\\nAll output is draft-only and requires human review. How can I assist you today?";

const KEY = 'vect_welcome_chat';
function getHist() { try { return JSON.parse(sessionStorage.getItem(KEY)||'[]'); } catch { return []; } }
function saveHist(h) { sessionStorage.setItem(KEY, JSON.stringify(h)); }

function renderWelcome() {
  const box = document.getElementById('w-messages');
  const h = getHist();
  // clear all but greeting
  while (box.children.length > 1) box.removeChild(box.lastChild);
  h.forEach(m => {
    const wrap = document.createElement('div');
    wrap.className = 'w-msg ' + (m.role === 'user' ? 'user' : '');
    const av = document.createElement('div');
    av.className = 'w-avatar ' + (m.role === 'user' ? 'user' : 'bot');
    av.textContent = m.role === 'user' ? 'OP' : '◆';
    const bub = document.createElement('div');
    bub.className = 'w-bubble ' + (m.role === 'user' ? 'user' : 'bot');
    bub.textContent = m.text;
    wrap.appendChild(av); wrap.appendChild(bub);
    box.appendChild(wrap);
  });
  box.scrollTop = box.scrollHeight;
}

function wSend() {
  const inp = document.getElementById('w-input');
  const msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  const h = getHist(); h.push({role:'user', text:msg}); saveHist(h); renderWelcome();
  fetch('/api/chat', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({message: msg})
  }).then(r=>r.json()).then(d=>{
    const h2 = getHist(); h2.push({role:'bot', text: d.reply||'No response.'}); saveHist(h2); renderWelcome();
  }).catch(()=>{
    const h2 = getHist(); h2.push({role:'bot', text:'Unable to reach Vectorian AI. Check your API key configuration.'}); saveHist(h2); renderWelcome();
  });
}

// Typewriter greeting
(function typewrite() {
  const el = document.getElementById('greeting-bubble');
  let i = 0;
  el.textContent = '';
  function tick() {
    if (i < GREETING.length) {
      el.textContent += GREETING[i++];
      document.getElementById('w-messages').scrollTop = 99999;
      setTimeout(tick, i < 80 ? 18 : 6);
    }
  }
  tick();
})();

document.getElementById('w-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') wSend();
});
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

INDEX_TMPL = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vectorian — Dashboard</title>
  """ + _CSS + """
</head>
<body>
""" + _TOPBAR + """
<div class="page">
  <div class="page-header">
    <div class="page-title">Incident Dashboard</div>
    <div class="page-sub">Manage and monitor active breach response engagements</div>
  </div>

  <div class="card">
    <div class="card-title">&#43; New Incident</div>
    <form method="post" action="/incidents/create" style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">
      <div style="flex:1;min-width:220px">
        <label>Incident ID</label>
        <input type="text" name="incident_id" id="inc-input"
               placeholder="{{ id_placeholder }}" oninput="updatePreview()" required />
      </div>
      <div>
        <label>Preview</label>
        <div style="padding:9px 12px;background:var(--bg);border:1px solid var(--border);border-radius:7px;font-family:monospace;font-size:13px;color:var(--navy);min-width:160px">
          <span id="inc-preview">—</span>
        </div>
      </div>
      <button class="btn btn-primary" type="submit">Create Incident</button>
    </form>
  </div>

  <div class="card">
    <div class="card-title">&#128203; Active Incidents</div>
    {% if incidents %}
    <table>
      <thead>
        <tr>
          <th>Incident ID</th>
          <th>Current Stage</th>
          <th>Progress</th>
          <th>Created</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {% for i in incidents %}
        <tr>
          <td><a href="/incidents/{{ i.id }}" style="color:var(--blue);font-weight:600;text-decoration:none">{{ i.id }}</a></td>
          <td>
            {% if i.current_layer %}
              <span class="badge badge-blue">Stage {{ i.current_layer }}</span>
              <span style="color:var(--muted);font-size:12px;margin-left:6px">{{ i.stage_name }}</span>
            {% else %}
              <span class="badge badge-green">Complete</span>
            {% endif %}
          </td>
          <td style="color:var(--muted);font-size:12px">{{ i.completed }}</td>
          <td style="color:var(--muted);font-size:12px">{{ i.created_at }}</td>
          <td><a href="/incidents/{{ i.id }}" class="btn btn-secondary btn-sm">Open &rarr;</a></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div style="text-align:center;padding:40px 0;color:var(--muted)">
      <div style="font-size:36px;margin-bottom:12px">&#128203;</div>
      <div style="font-weight:600">No incidents yet</div>
      <div style="font-size:12px;margin-top:4px">Create your first incident using the form above</div>
    </div>
    {% endif %}
  </div>

  <div class="disclaimer">{{ disclaimer }}</div>
</div>
""" + _CHAT_BUBBLE + """
<script>
(function() {
  var fmt = {{ format_json | safe }};
  var placeholder = fmt.prefix + (fmt.separator||'-') + (fmt.year ? '2026' + (fmt.separator||'-') : '') + '0001';
  document.getElementById('inc-input').setAttribute('placeholder', placeholder);
  window.updatePreview = function() {
    var v = document.getElementById('inc-input').value;
    document.getElementById('inc-preview').textContent = v || '—';
  };
})();
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
# SETUP WIZARD
# ─────────────────────────────────────────────

SETUP_TMPL = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vectorian — Setup</title>
  """ + _CSS + """
</head>
<body>
""" + _TOPBAR + """
<div class="page">
  <div class="page-header">
    <div class="page-title">Platform Setup</div>
    <div class="page-sub">Configure Vectorian for your organization before your first engagement</div>
  </div>

  <div class="wizard-steps">
    <div class="wizard-step {{ 'active' if step == 1 else 'done' if step > 1 else '' }}">
      &#9312; Incident Code Format
    </div>
    <div class="wizard-step {{ 'active' if step == 2 else '' }}">
      &#9313; Stage Configuration
    </div>
  </div>

  {% if step == 1 %}
  <div class="card">
    <div class="card-title">&#9881; Incident Code Format</div>
    <form method="post" action="/setup/step1">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;max-width:600px;margin-bottom:24px">
        <div>
          <label>Prefix</label>
          <input type="text" name="prefix" value="{{ cfg.incident_code_format.prefix }}" oninput="updatePreview()" />
        </div>
        <div>
          <label>Separator</label>
          <select name="separator" onchange="updatePreview()">
            <option value="-" {{ 'selected' if cfg.incident_code_format.separator == '-' }}>Hyphen  ( - )</option>
            <option value="_" {{ 'selected' if cfg.incident_code_format.separator == '_' }}>Underscore  ( _ )</option>
            <option value="/" {{ 'selected' if cfg.incident_code_format.separator == '/' }}>Slash  ( / )</option>
          </select>
        </div>
        <div>
          <label>Include Year</label>
          <div style="padding:9px 12px;border:1px solid var(--border);border-radius:7px;background:var(--white)">
            <input type="checkbox" name="year" id="year-chk" onchange="updatePreview()"
                   {{ 'checked' if cfg.incident_code_format.year }} style="width:auto;margin-right:8px" />
            Append current year
          </div>
        </div>
        <div>
          <label>Sequence Digits</label>
          <input type="number" name="digits" min="2" max="8"
                 value="{{ cfg.incident_code_format.digits }}" oninput="updatePreview()" />
        </div>
      </div>
      <div style="background:var(--navy);border-radius:10px;padding:18px 24px;margin-bottom:24px;max-width:600px">
        <div style="font-size:11px;letter-spacing:2px;color:var(--silver);text-transform:uppercase;margin-bottom:8px">Live Preview</div>
        <div id="fmt-preview" style="font-size:26px;font-family:monospace;color:var(--white);font-weight:700;letter-spacing:3px"></div>
      </div>
      <button class="btn btn-primary" type="submit">Next &rarr;</button>
    </form>
  </div>

  <script>
  function updatePreview() {
    var prefix = document.querySelector('[name=prefix]').value || 'INC';
    var sep    = document.querySelector('[name=separator]').value || '-';
    var year   = document.getElementById('year-chk').checked;
    var digits = parseInt(document.querySelector('[name=digits]').value) || 4;
    var seq    = '1'.padStart(digits, '0');
    var parts  = [prefix];
    if (year) parts.push('2026');
    parts.push(seq);
    document.getElementById('fmt-preview').textContent = parts.join(sep);
  }
  updatePreview();
  </script>

  {% elif step == 2 %}
  <div class="card">
    <div class="card-title">&#9776; Stage Configuration</div>
    <form method="post" action="/setup/save">
      <table id="stages-table" style="margin-bottom:18px">
        <thead>
          <tr>
            <th style="width:50px">#</th>
            <th>Default Stage Name</th>
            <th>Custom Name <span style="font-weight:400;text-transform:none;letter-spacing:0">(optional)</span></th>
          </tr>
        </thead>
        <tbody>
          {% for s in cfg.stages %}
          <tr>
            <td><span class="badge badge-blue">{{ s.id }}</span></td>
            <td style="color:var(--muted)">{{ s.name }}</td>
            <td>
              <input type="hidden" name="id[]" value="{{ s.id }}" />
              <input type="hidden" name="name[]" value="{{ s.name }}" />
              <input type="text" name="custom_name[]" value="{{ s.custom_name }}" placeholder="Leave blank to use default name" />
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      <div style="display:flex;gap:12px">
        <button type="button" class="btn btn-secondary" onclick="addStage()">&#43; Add Custom Stage</button>
        <button type="submit" class="btn btn-primary">Complete Setup &rarr;</button>
      </div>
    </form>
  </div>
  <script>
  var cc = 0;
  function addStage() {
    cc++;
    var cid = 'custom_' + cc;
    var tbody = document.querySelector('#stages-table tbody');
    var tr = document.createElement('tr');
    tr.innerHTML = '<td><span class="badge badge-silver">' + cid + '</span></td>' +
      '<td style="color:var(--muted)"><em>Custom Stage</em></td>' +
      '<td>' +
        '<input type="hidden" name="id[]" value="' + cid + '" />' +
        '<input type="hidden" name="name[]" value="Custom Stage" />' +
        '<input type="text" name="custom_name[]" placeholder="Enter stage name" />' +
      '</td>';
    tbody.appendChild(tr);
  }
  </script>
  {% endif %}
</div>
""" + _CHAT_BUBBLE + """
</body>
</html>
"""

# ─────────────────────────────────────────────
# CONFIGURATION PANEL
# ─────────────────────────────────────────────

CONFIG_TMPL = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vectorian — Configuration</title>
  """ + _CSS + """
</head>
<body>
""" + _TOPBAR + """
<div class="page">
  <div class="page-header">
    <div class="page-title">Configuration</div>
    <div class="page-sub">Manage incident codes, stages, owners, and workflow settings</div>
  </div>

  <form method="post" action="/config/save">
    <div class="card">
      <div class="card-title">&#9881; Incident Code Format</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:18px;max-width:720px;margin-bottom:18px">
        <div>
          <label>Prefix</label>
          <input type="text" name="prefix" value="{{ cfg.incident_code_format.prefix }}" oninput="updatePreview()" />
        </div>
        <div>
          <label>Separator</label>
          <select name="separator" onchange="updatePreview()">
            <option value="-" {{ 'selected' if cfg.incident_code_format.separator == '-' }}>-</option>
            <option value="_" {{ 'selected' if cfg.incident_code_format.separator == '_' }}>_</option>
            <option value="/" {{ 'selected' if cfg.incident_code_format.separator == '/' }}>/</option>
          </select>
        </div>
        <div>
          <label>Include Year</label>
          <div style="padding:9px 12px;border:1px solid var(--border);border-radius:7px;background:var(--white)">
            <input type="checkbox" name="year" id="year-chk" onchange="updatePreview()"
                   {{ 'checked' if cfg.incident_code_format.year }} style="width:auto;margin-right:8px" />Yes
          </div>
        </div>
        <div>
          <label>Digits</label>
          <input type="number" name="digits" min="2" max="8"
                 value="{{ cfg.incident_code_format.digits }}" oninput="updatePreview()" />
        </div>
      </div>
      <div style="background:var(--navy);border-radius:9px;padding:14px 20px;max-width:400px;display:inline-block">
        <span style="font-size:11px;letter-spacing:2px;color:var(--silver);text-transform:uppercase;margin-right:14px">Preview</span>
        <span id="fmt-preview" style="font-size:20px;font-family:monospace;color:var(--white);font-weight:700;letter-spacing:2px"></span>
      </div>
    </div>

    <div class="card">
      <div class="card-title">&#9776; Stages
        <button type="button" class="btn btn-secondary btn-sm" style="margin-left:auto" onclick="addStage()">&#43; Add Stage</button>
      </div>
      <table id="stages-table">
        <thead>
          <tr>
            <th style="width:80px">Order</th>
            <th>Stage</th>
            <th>Custom Name</th>
            <th>Owner</th>
            <th>Notes</th>
            <th style="width:80px">Enabled</th>
            <th style="width:60px"></th>
          </tr>
        </thead>
        <tbody id="stages-body">
          {% for i, s in stages_enum %}
          <tr id="row-{{ s.id }}">
            <td style="text-align:center">
              <button type="button" class="btn btn-secondary btn-sm" onclick="moveRow('{{ s.id }}',-1)" style="padding:3px 8px">&#8593;</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="moveRow('{{ s.id }}',1)"  style="padding:3px 8px">&#8595;</button>
            </td>
            <td>
              <input type="hidden" name="id[]" value="{{ s.id }}" />
              <div>
                <span class="badge badge-blue" style="margin-right:6px">{{ s.id }}</span>
                <span style="font-size:12px;color:var(--muted)">{{ s.name }}</span>
              </div>
            </td>
            <td><input type="text" name="custom_name[]" value="{{ s.custom_name }}" placeholder="Override..." /></td>
            <td><input type="text" name="owner[]" value="{{ s.owner }}" placeholder="Assignee..." /></td>
            <td><textarea name="notes[]" rows="1" style="resize:vertical;font-size:12px">{{ s.notes }}</textarea></td>
            <td style="text-align:center">
              <input type="checkbox" name="enabled_{{ s.id }}" {{ 'checked' if s.enabled }} style="width:auto;transform:scale(1.3)" />
            </td>
            <td style="text-align:center">
              <button type="button" class="btn btn-danger btn-sm" onclick="deleteRow('{{ s.id }}')">&#x2715;</button>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:40px">
      <button type="submit" class="btn btn-primary">Save Configuration</button>
      <a href="/" class="btn btn-secondary">Cancel</a>
    </div>
  </form>
</div>
""" + _CHAT_BUBBLE + """
<script>
var cc = {{ custom_count }};
function updatePreview() {
  var prefix = document.querySelector('[name=prefix]').value||'INC';
  var sep    = document.querySelector('[name=separator]').value||'-';
  var year   = document.getElementById('year-chk').checked;
  var digits = parseInt(document.querySelector('[name=digits]').value)||4;
  var seq    = '1'.padStart(digits,'0');
  var parts  = [prefix];
  if (year) parts.push('2026');
  parts.push(seq);
  document.getElementById('fmt-preview').textContent = parts.join(sep);
}
updatePreview();
function moveRow(id, dir) {
  var el = document.getElementById('row-'+id);
  if (!el) return;
  if (dir===-1 && el.previousElementSibling) el.parentNode.insertBefore(el, el.previousElementSibling);
  else if (dir===1 && el.nextElementSibling)  el.parentNode.insertBefore(el.nextElementSibling, el);
}
function deleteRow(id) { var el = document.getElementById('row-'+id); if (el) el.remove(); }
function addStage() {
  cc++;
  var cid = 'custom_'+cc;
  var tbody = document.getElementById('stages-body');
  var tr = document.createElement('tr');
  tr.id = 'row-'+cid;
  tr.innerHTML =
    '<td style="text-align:center">' +
      '<button type="button" class="btn btn-secondary btn-sm" onclick="moveRow(\\'' + cid + '\\',-1)" style="padding:3px 8px">&#8593;</button>' +
      '<button type="button" class="btn btn-secondary btn-sm" onclick="moveRow(\\'' + cid + '\\',1)"  style="padding:3px 8px">&#8595;</button>' +
    '</td>' +
    '<td><input type="hidden" name="id[]" value="'+cid+'" />' +
      '<span class="badge badge-silver">'+cid+'</span>' +
      '<span style="font-size:12px;color:var(--muted);margin-left:6px">Custom Stage</span></td>' +
    '<td><input type="text" name="custom_name[]" placeholder="Stage name..." /></td>' +
    '<td><input type="text" name="owner[]" placeholder="Assignee..." /></td>' +
    '<td><textarea name="notes[]" rows="1" style="resize:vertical;font-size:12px"></textarea></td>' +
    '<td style="text-align:center"><input type="checkbox" name="enabled_'+cid+'" checked style="width:auto;transform:scale(1.3)" /></td>' +
    '<td style="text-align:center"><button type="button" class="btn btn-danger btn-sm" onclick="deleteRow(\\'' + cid + '\\')">&#x2715;</button></td>';
  tbody.appendChild(tr);
}
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
# INCIDENT DETAIL
# ─────────────────────────────────────────────

DETAIL_TMPL = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vectorian — {{ incident_id }}</title>
  """ + _CSS + """
</head>
<body data-incident-id="{{ incident_id }}">
""" + _TOPBAR + """
<div class="page">
  <div style="margin-bottom:20px">
    <a href="/" style="color:var(--blue);text-decoration:none;font-size:13px;font-weight:500">&larr; Back to Dashboard</a>
  </div>

  <div class="page-header">
    <div style="display:flex;align-items:center;gap:14px">
      <div class="page-title">{{ incident_id }}</div>
      {% if current_layer %}
        <span class="badge badge-blue" style="font-size:12px">Stage {{ current_layer }} Active</span>
      {% else %}
        <span class="badge badge-green" style="font-size:12px">&#10003; Complete</span>
      {% endif %}
    </div>
    <div class="page-sub">{{ current_stage_name or 'All stages complete' }}</div>
  </div>

  <div class="card">
    <div class="card-title">&#9776; Stage Progress</div>
    <div style="margin-bottom:18px">
      {% for s in all_stages %}
        <span class="stage-pill
          {%- if s.id in completed %} done
          {%- elif s.id == current_layer %} current
          {%- endif %}">
          {{ s.id }}: {{ s.custom_name or s.name }}
          {%- if s.id in completed %} &#10003;{%- endif %}
        </span>
      {% endfor %}
    </div>
    <div style="color:var(--muted);font-size:12px;margin-bottom:18px">
      Completed stages: {{ completed|join(', ') if completed else 'None yet' }}
    </div>
    {% if current_layer %}
    <form method="post" action="/incidents/{{ incident_id }}/proceed">
      <button class="btn btn-primary" type="submit">
        &#9658;&nbsp; Run Stage {{ current_layer }}: {{ current_stage_name }}
      </button>
    </form>
    {% else %}
    <div style="color:var(--success);font-weight:700;font-size:15px">&#10003; Runbook complete. All stages executed.</div>
    {% endif %}
  </div>

  <div class="card">
    <div class="card-title">&#128196; Runbook Output</div>
    <pre>{{ runbook_json }}</pre>
  </div>

  <div class="disclaimer">{{ disclaimer }}</div>
</div>
""" + _CHAT_BUBBLE + """
<script>
  // Expose incident id to chat bubble
  document.body.dataset.incidentId = '{{ incident_id }}';
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────

def create_app(workdir: str = ".vectrion", data_dir: str = None) -> Flask:
    app = Flask(__name__)
    storage = Storage(Path(workdir))
    dd = Path(data_dir) if data_dir else Path(__file__).resolve().parent / "data"

    def _list_incidents():
        rows = []
        for p in sorted(storage.state_dir.glob("*.json")):
            try:
                s = storage.load_state_obj(p.stem)
                cur = s.get("current_layer")
                rows.append({
                    "id": p.stem,
                    "current_layer": cur,
                    "stage_name": get_stage_name(cur, workdir) if cur else "Complete",
                    "completed": " → ".join(s.get("completed_layers", [])) or "—",
                    "created_at": s.get("created_at", "")[:10],
                })
            except Exception:
                continue
        return rows

    @app.get("/")
    def home():
        if not is_setup_complete(workdir):
            return redirect(url_for("welcome"))
        cfg = load_config(workdir)
        fmt = cfg.get("incident_code_format", {})
        sep = fmt.get("separator", "-")
        prefix = fmt.get("prefix", "INC")
        year = fmt.get("year", True)
        digits = fmt.get("digits", 4)
        placeholder = prefix + sep + ("2026" + sep if year else "") + "1".zfill(digits)
        return render_template_string(
            INDEX_TMPL,
            page_title="Dashboard", active_nav="dashboard",
            incidents=_list_incidents(),
            disclaimer=LEGAL_DISCLAIMER,
            format_json=json.dumps(fmt),
            id_placeholder=placeholder,
        )

    @app.get("/welcome")
    def welcome():
        enter_url = url_for("setup") if not is_setup_complete(workdir) else url_for("home")
        return render_template_string(
            WELCOME_TMPL,
            page_title="Welcome", active_nav="",
            disclaimer=LEGAL_DISCLAIMER,
            enter_url=enter_url,
        )

    @app.get("/setup")
    def setup():
        cfg = load_config(workdir)
        step = int(request.args.get("step", 1))
        return render_template_string(
            SETUP_TMPL,
            page_title="Setup", active_nav="",
            cfg=cfg, step=step,
        )

    @app.post("/setup/step1")
    def setup_step1():
        cfg = load_config(workdir)
        cfg["incident_code_format"] = {
            "prefix":    request.form.get("prefix", "INC").strip(),
            "year":      bool(request.form.get("year")),
            "separator": request.form.get("separator", "-"),
            "digits":    int(request.form.get("digits", 4)),
        }
        save_config(workdir, cfg)
        return redirect(url_for("setup") + "?step=2")

    @app.post("/setup/save")
    def setup_save():
        cfg = load_config(workdir)
        ids          = request.form.getlist("id[]")
        names        = request.form.getlist("name[]")
        custom_names = request.form.getlist("custom_name[]")
        new_stages = []
        for i, sid in enumerate(ids):
            new_stages.append({
                "id":          sid,
                "name":        names[i] if i < len(names) else sid,
                "custom_name": custom_names[i] if i < len(custom_names) else "",
                "enabled":     True,
                "owner":       "",
                "notes":       "",
            })
        cfg["stages"] = new_stages
        cfg["setup_complete"] = True
        save_config(workdir, cfg)
        return redirect(url_for("home"))

    @app.get("/config")
    def config_panel():
        cfg = load_config(workdir)
        stages = cfg.get("stages", [])
        custom_count = sum(1 for s in stages if s["id"].startswith("custom_"))
        return render_template_string(
            CONFIG_TMPL,
            page_title="Configuration", active_nav="config",
            cfg=cfg,
            stages_enum=list(enumerate(stages)),
            custom_count=custom_count,
        )

    @app.post("/config/save")
    def config_save():
        cfg = load_config(workdir)
        ids          = request.form.getlist("id[]")
        custom_names = request.form.getlist("custom_name[]")
        owners       = request.form.getlist("owner[]")
        notes_list   = request.form.getlist("notes[]")
        new_stages = []
        for i, sid in enumerate(ids):
            orig = next((s for s in cfg.get("stages", []) if s["id"] == sid), None)
            new_stages.append({
                "id":          sid,
                "name":        orig["name"] if orig else "Custom Stage",
                "custom_name": custom_names[i] if i < len(custom_names) else "",
                "enabled":     bool(request.form.get(f"enabled_{sid}")),
                "owner":       owners[i] if i < len(owners) else "",
                "notes":       notes_list[i] if i < len(notes_list) else "",
            })
        cfg["stages"] = new_stages
        cfg["incident_code_format"] = {
            "prefix":    request.form.get("prefix", "INC").strip(),
            "year":      bool(request.form.get("year")),
            "separator": request.form.get("separator", "-"),
            "digits":    int(request.form.get("digits", 4)),
        }
        save_config(workdir, cfg)
        return redirect(url_for("config_panel"))

    @app.post("/incidents/create")
    def create_incident():
        incident_id = (request.form.get("incident_id") or "").strip()
        if not incident_id:
            return redirect(url_for("home"))
        if not storage.load_state_obj(incident_id):
            order = get_stage_order(workdir)
            start = order[0] if order else "1"
            state = {
                "incident_id": incident_id,
                "current_layer": start,
                "completed_layers": [],
                "runbook": {},
            }
            storage.save_state_obj(incident_id, state)
            storage.audit(incident_id, "trigger", {"source": "ui"})
        return redirect(url_for("incident_detail", incident_id=incident_id))

    @app.get("/incidents/<incident_id>")
    def incident_detail(incident_id: str):
        s = storage.load_state_obj(incident_id)
        if not s:
            return redirect(url_for("home"))
        cur = s.get("current_layer")
        cfg = load_config(workdir)
        return render_template_string(
            DETAIL_TMPL,
            page_title=incident_id, active_nav="dashboard",
            incident_id=incident_id,
            current_layer=cur,
            current_stage_name=get_stage_name(cur, workdir) if cur else None,
            completed=s.get("completed_layers", []),
            all_stages=cfg.get("stages", []),
            runbook_json=json.dumps(s.get("runbook", {}), indent=2),
            disclaimer=LEGAL_DISCLAIMER,
        )

    @app.post("/incidents/<incident_id>/proceed")
    def incident_proceed(incident_id: str):
        s = storage.load_state_obj(incident_id)
        if not s:
            return redirect(url_for("home"))
        current = s.get("current_layer")
        if current:
            updated = run_layer(s.get("runbook", {}), current, dd, Path(workdir) / "exports")
            s["runbook"] = updated
            done = s.get("completed_layers", [])
            if current not in done:
                done.append(current)
            s["completed_layers"] = done
            s["current_layer"] = next_layer(current, workdir)
            storage.save_state_obj(incident_id, s)
            storage.audit(incident_id, "proceed_ui", {"completed": current, "next": s.get("current_layer")})
        return redirect(url_for("incident_detail", incident_id=incident_id))

    @app.post("/api/chat")
    def api_chat():
        from vectrion.chat import chat
        body = request.get_json(force=True)
        incident_id = body.get("incident_id")
        incident_context = storage.load_state_obj(incident_id) if incident_id else None
        reply = chat(body.get("message", ""), incident_context)
        return {"reply": reply}

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=8090)


if __name__ == "__main__":
    main()
