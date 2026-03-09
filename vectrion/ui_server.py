from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote as _url_quote, unquote as _url_unquote

from flask import Flask, redirect, render_template_string, request, url_for

from vectrion.config_store import (
    get_stage_name,
    get_stage_order,
    is_setup_complete,
    load_config,
    save_config,
)
from vectrion.constants import DEFAULT_STAGES, LEGAL_DISCLAIMER
from vectrion.runbook import next_layer, run_layer
from vectrion.storage import Storage

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """<style>
:root {
  --navy:        #07111D;
  --navy-2:      #0D1E32;
  --navy-3:      #172E4A;
  --navy-4:      #1F3D62;
  --blue:        #1D4ED8;
  --blue-2:      #2563EB;
  --blue-light:  #3B82F6;
  --blue-pale:   #EFF6FF;
  --blue-glow:   rgba(59,130,246,0.22);
  --silver:      #7A8FA8;
  --silver-2:    #A0B4CC;
  --silver-3:    #C8D8E8;
  --silver-pale: #E4EDF8;
  --bg:          #EBF1F8;
  --bg-2:        #F4F7FB;
  --white:       #FFFFFF;
  --text:        #0B1726;
  --muted:       #5B7290;
  --border:      #C8D8E8;
  --success:     #059669;
  --success-bg:  #D1FAE5;
  --danger:      #DC2626;
  --danger-bg:   #FEE2E2;
  --warn:        #D97706;
  --warn-bg:     #FEF3C7;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Segoe UI',system-ui,Arial,sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.55;}

/* ── TOPBAR ── */
.topbar{
  display:flex;align-items:center;background:var(--navy);
  border-bottom:2px solid var(--navy-3);height:58px;padding:0 28px;
  position:sticky;top:0;z-index:200;box-shadow:0 2px 24px rgba(0,0,0,0.5),0 1px 0 rgba(59,130,246,0.25);
}
.topbar-brand{display:flex;align-items:center;gap:12px;text-decoration:none;}
.tb-icon{
  width:36px;height:36px;border-radius:9px;
  background:linear-gradient(135deg,var(--blue-light),var(--blue));
  display:flex;align-items:center;justify-content:center;font-size:18px;
  box-shadow:0 0 16px var(--blue-glow);
}
.tb-name{font-size:17px;font-weight:800;letter-spacing:2.5px;color:#fff;}
.tb-sub{font-size:9px;letter-spacing:2.5px;color:var(--silver);text-transform:uppercase;margin-top:1px;}
.tb-div{width:1px;height:30px;background:var(--navy-3);margin:0 22px;}
nav{margin-left:auto;display:flex;align-items:center;gap:4px;}
nav a{
  color:var(--silver-2);text-decoration:none;font-size:11px;font-weight:700;
  padding:6px 16px;border-radius:6px;letter-spacing:1px;text-transform:uppercase;
  transition:all 0.15s;border:1px solid transparent;
}
nav a:hover{background:rgba(255,255,255,0.07);color:#fff;border-color:var(--navy-3);}
nav a.active{background:rgba(59,130,246,0.14);color:var(--blue-light);border-color:rgba(59,130,246,0.28);}

/* ── LAYOUT ── */
.split-wrap{display:flex;min-height:calc(100vh - 58px);}
.split-main{flex:1;min-width:0;padding:28px 32px 60px;}
.split-panel{
  width:310px;flex-shrink:0;background:var(--navy);
  border-left:1px solid var(--navy-3);display:flex;flex-direction:column;
  height:calc(100vh - 58px);position:sticky;top:58px;overflow:hidden;
}
.page{max-width:1120px;margin:0 auto;padding:28px 28px 60px;}

/* ── STATS ROW ── */
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:26px;}
.stat-card{
  background:var(--white);border:1px solid var(--border);border-radius:12px;
  padding:18px 20px;box-shadow:0 2px 8px rgba(10,22,40,0.06);
  display:flex;flex-direction:column;gap:4px;
  transition:box-shadow 0.18s,transform 0.18s;
}
.stat-card:hover{transform:translateY(-2px);box-shadow:0 4px 16px rgba(7,17,29,0.12);}
.stat-num{font-size:28px;font-weight:800;color:var(--navy);line-height:1;}
.stat-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);}
.stat-icon{font-size:22px;margin-bottom:4px;}

/* ── CARDS ── */
.card{
  background:var(--white);border:1px solid var(--border);border-radius:12px;
  padding:24px 28px;margin-bottom:22px;
  box-shadow:0 1px 4px rgba(0,0,0,0.08),0 4px 20px rgba(7,17,29,0.08);
  transition:box-shadow 0.2s,transform 0.2s;
}
.card:hover{box-shadow:0 2px 8px rgba(0,0,0,0.10),0 8px 28px rgba(7,17,29,0.12);}
.card-header{
  display:flex;align-items:center;gap:10px;
  padding-bottom:16px;margin-bottom:20px;border-bottom:1px solid var(--silver-pale);
}
.card-title{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;color:var(--navy-4);}
.section-title{
  font-size:13px;font-weight:700;color:var(--navy);
  padding:16px 0 12px;border-bottom:1px solid var(--silver-pale);margin-bottom:16px;
  display:flex;align-items:center;gap:8px;
}

/* ── BUTTONS ── */
.btn{
  display:inline-flex;align-items:center;gap:6px;padding:9px 20px;
  font-size:13px;font-weight:600;border-radius:7px;border:none;cursor:pointer;
  text-decoration:none;transition:all 0.12s;letter-spacing:0.3px;
}
.btn-primary{background:var(--blue);color:#fff;box-shadow:0 2px 10px rgba(29,78,216,0.3);}
.btn-primary:hover{background:#1a44c4;box-shadow:0 4px 20px rgba(29,78,216,0.55);transform:translateY(-1px);}
.btn-secondary{background:var(--white);color:var(--text);border:1px solid var(--border);}
.btn-secondary:hover{background:var(--bg);border-color:var(--silver);}
.btn-danger{background:var(--danger);color:#fff;}
.btn-danger:hover{background:#b91c1c;}
.btn-success{background:var(--success);color:#fff;}
.btn-success:hover{background:#047857;}
.btn-ghost{background:transparent;color:var(--silver);border:none;cursor:pointer;padding:4px 8px;border-radius:5px;font-size:16px;}
.btn-ghost:hover{color:#fff;background:rgba(255,255,255,0.08);}
.btn-sm{padding:5px 12px;font-size:12px;}
.btn-action{
  display:inline-flex;align-items:center;gap:5px;padding:7px 14px;
  font-size:12px;font-weight:600;background:var(--navy-3);color:var(--silver-3);
  border:1px solid var(--navy-4);border-radius:6px;cursor:pointer;
  text-decoration:none;transition:all 0.15s;margin-top:6px;margin-right:4px;
}
.btn-action:hover{background:var(--blue);color:#fff;border-color:var(--blue);}

/* ── FORMS ── */
label{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.8px;display:block;margin-bottom:5px;}
.form-group{margin-bottom:18px;}
.form-row{display:grid;gap:18px;margin-bottom:18px;}
.form-row-2{grid-template-columns:1fr 1fr;}
.form-row-3{grid-template-columns:1fr 1fr 1fr;}
input[type=text],input[type=email],input[type=tel],input[type=number],input[type=date],select,textarea{
  width:100%;padding:9px 13px;border:1px solid var(--border);border-radius:7px;
  font-size:13px;background:var(--white);color:var(--text);transition:all 0.15s;
  font-family:inherit;
}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--blue-light);box-shadow:0 0 0 3px rgba(59,130,246,0.14);}
.check-group{display:flex;flex-wrap:wrap;gap:10px;}
.check-item{
  display:flex;align-items:center;gap:7px;padding:7px 13px;
  border:1px solid var(--border);border-radius:7px;cursor:pointer;
  font-size:13px;font-weight:500;background:var(--white);transition:all 0.15s;
  user-select:none;
}
.check-item:hover{border-color:var(--blue-light);background:var(--blue-pale);}
.check-item input{width:auto;margin:0;}
.check-item.selected{border-color:var(--blue);background:var(--blue-pale);color:var(--blue);font-weight:600;}
.radio-group{display:flex;gap:10px;flex-wrap:wrap;}
.radio-item{
  display:flex;align-items:center;gap:7px;padding:7px 16px;
  border:1px solid var(--border);border-radius:7px;cursor:pointer;
  font-size:13px;font-weight:500;background:var(--white);transition:all 0.15s;
  user-select:none;
}
.radio-item:hover{border-color:var(--blue-light);background:var(--blue-pale);}
.radio-item.selected{border-color:var(--blue);background:var(--blue-pale);color:var(--blue);font-weight:600;}
.radio-item input{width:auto;margin:0;}
.input-hint{font-size:11px;color:var(--muted);margin-top:4px;}

/* ── TABLES ── */
table{border-collapse:collapse;width:100%;}
thead th{
  background:var(--navy);color:var(--silver-2);font-size:10px;
  font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
  padding:11px 16px;text-align:left;
}
thead th:first-child{border-radius:8px 0 0 0;}
thead th:last-child{border-radius:0 8px 0 0;}
tbody td{padding:13px 16px;border-bottom:1px solid var(--silver-pale);vertical-align:middle;}
tbody tr:last-child td{border-bottom:none;}
tbody tr:hover td{background:#EBF4FF;transition:background 0.1s;}

/* ── BADGES ── */
.badge{display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;letter-spacing:0.4px;white-space:nowrap;}
.badge-blue  {background:#DBEAFE;color:#1D4ED8;}
.badge-green {background:#D1FAE5;color:#065F46;}
.badge-silver{background:var(--silver-pale);color:var(--muted);}
.badge-warn  {background:#FEF3C7;color:#92400E;}
.badge-navy  {background:var(--navy-3);color:var(--silver-2);}
.stage-pill{
  display:inline-flex;align-items:center;gap:5px;padding:4px 12px;border-radius:999px;
  font-size:11px;font-weight:600;background:var(--silver-pale);color:var(--muted);
  margin:3px;border:1px solid var(--border);
}
.stage-pill.done   {background:#D1FAE5;color:#065F46;border-color:#A7F3D0;}
.stage-pill.current{background:#DBEAFE;color:#1E40AF;border-color:#93C5FD;font-weight:700;}

/* ── PROGRESS BAR ── */
.progress-track{height:6px;background:var(--silver-pale);border-radius:999px;overflow:hidden;min-width:100px;}
.progress-fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--blue-light));border-radius:999px;transition:width 0.3s;box-shadow:0 0 8px rgba(59,130,246,0.35);}

/* ── PRE ── */
pre{
  background:var(--navy);color:#A8C8E8;padding:18px 20px;border-radius:10px;
  white-space:pre-wrap;max-height:440px;overflow:auto;font-size:12px;line-height:1.8;
  border:1px solid var(--navy-3);
}

/* ── WIZARD STEPS ── */
.wizard-steps{display:flex;margin-bottom:28px;}
.wizard-step{
  flex:1;display:flex;align-items:center;gap:10px;padding:14px 18px;
  background:var(--white);border:1px solid var(--border);color:var(--muted);
  font-size:13px;font-weight:600;transition:all 0.2s;
}
.wizard-step:first-child{border-radius:10px 0 0 10px;}
.wizard-step:last-child{border-radius:0 10px 10px 0;}
.wizard-step .step-num{
  width:26px;height:26px;border-radius:50%;background:var(--silver-pale);
  color:var(--muted);font-size:12px;font-weight:800;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
}
.wizard-step.active{background:var(--navy);border-color:var(--navy);color:#fff;}
.wizard-step.active .step-num{background:var(--blue);color:#fff;box-shadow:0 0 10px var(--blue-glow);}
.wizard-step.done{background:#F0FDF4;border-color:#A7F3D0;color:var(--success);}
.wizard-step.done .step-num{background:var(--success);color:#fff;}

/* ── CLIENT INFO BLOCK ── */
.client-block{
  background:linear-gradient(135deg,var(--navy-2),var(--navy-3));
  border:1px solid var(--navy-4);border-radius:12px;padding:20px 24px;
  margin-bottom:22px;color:var(--silver-2);
}
.client-block-name{font-size:20px;font-weight:800;color:#fff;letter-spacing:0.5px;}
.client-block-meta{display:flex;gap:20px;flex-wrap:wrap;margin-top:10px;font-size:13px;}
.client-block-field{display:flex;flex-direction:column;gap:2px;}
.client-block-label{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--silver);font-weight:700;}
.client-block-value{color:var(--silver-3);font-weight:600;}

/* ── MISC ── */
.muted{color:var(--muted);font-size:13px;}
.plain{color:var(--blue);text-decoration:none;font-weight:500;}
.plain:hover{text-decoration:underline;}
.disclaimer{font-size:11px;color:var(--muted);border-top:1px solid var(--border);padding-top:14px;margin-top:8px;line-height:1.6;}
.divider{height:1px;background:var(--silver-pale);margin:22px 0;}
.step-section{display:none;}
.step-section.active{display:block;}

/* ─────────────────────────────────────
   ROBOT PANEL
───────────────────────────────────── */
.robot-header{
  padding:18px 14px 14px;background:var(--navy-2);
  border-bottom:1px solid var(--navy-3);
  display:flex;flex-direction:column;align-items:center;gap:8px;
}
.robot-wrap{position:relative;display:flex;flex-direction:column;align-items:center;width:80px;height:90px;}
.robot-antenna-tip{
  position:absolute;top:0;left:50%;transform:translateX(-50%);
  width:10px;height:10px;border-radius:50%;background:var(--blue-light);
  box-shadow:0 0 12px var(--blue-light),0 0 24px var(--blue-glow);
  animation:antPulse 2.4s ease-in-out infinite;
}
.robot-ant-stem{width:3px;height:14px;background:var(--silver);border-radius:2px;margin-top:11px;}
.robot-neck{width:20px;height:5px;background:var(--navy-3);border-radius:2px;}
.robot-face{
  width:74px;height:60px;background:var(--navy-2);
  border:2px solid var(--navy-4);border-radius:13px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;
  box-shadow:0 0 24px rgba(59,130,246,0.12),inset 0 1px 0 rgba(255,255,255,0.04);
  position:relative;overflow:hidden;
}
.robot-face::before{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--blue-light),transparent);opacity:0.5;
}
.robot-ear{
  position:absolute;top:50%;transform:translateY(-50%);
  width:5px;height:22px;border-radius:3px;background:var(--navy-4);border:1px solid var(--navy-3);
}
.robot-ear.l{left:-6px;} .robot-ear.r{right:-6px;}
.robot-eyes{display:flex;gap:18px;}
.robot-eye{
  width:13px;height:13px;border-radius:50%;background:var(--blue-light);
  box-shadow:0 0 10px var(--blue-light),0 0 20px var(--blue-glow);
  animation:eyeBlink 5s ease-in-out infinite;
}
.robot-eye:nth-child(2){animation-delay:0.1s;}
.robot-mouth{
  width:40px;height:7px;border-radius:3px;opacity:0.65;
  background:repeating-linear-gradient(90deg,var(--silver) 0,var(--silver) 4px,transparent 4px,transparent 8px);
}
@keyframes antPulse{0%,100%{opacity:1;box-shadow:0 0 12px var(--blue-light),0 0 24px var(--blue-glow);}50%{opacity:0.35;box-shadow:0 0 4px var(--blue-light);}}
@keyframes eyeBlink{0%,90%,100%{transform:scaleY(1);}94%,97%{transform:scaleY(0.08);}}

.robot-name{font-size:12px;font-weight:800;letter-spacing:2.5px;color:#fff;text-transform:uppercase;}
.robot-status{display:flex;align-items:center;gap:6px;font-size:10px;color:#22C55E;letter-spacing:1px;text-transform:uppercase;}
.robot-status-dot{width:7px;height:7px;border-radius:50%;background:#22C55E;box-shadow:0 0 7px #22C55E;animation:sPulse 2s infinite;}
@keyframes sPulse{0%,100%{opacity:1;}50%{opacity:0.4;}}

.panel-messages{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth;}
.panel-messages::-webkit-scrollbar{width:4px;}
.panel-messages::-webkit-scrollbar-thumb{background:var(--navy-3);border-radius:4px;}
.pmsg{display:flex;gap:8px;align-items:flex-start;}
.pmsg.user{flex-direction:row-reverse;}
.pmsg-av{width:26px;height:26px;flex-shrink:0;border-radius:7px;background:linear-gradient(135deg,var(--blue-light),var(--blue));display:flex;align-items:center;justify-content:center;font-size:12px;color:#fff;font-weight:700;}
.pmsg-av.user{background:var(--navy-3);color:var(--silver-2);font-size:10px;}
.pmsg-content{max-width:84%;display:flex;flex-direction:column;gap:4px;}
.pmsg-bubble{padding:9px 13px;border-radius:10px;font-size:12px;line-height:1.6;}
.pmsg-bubble.bot{background:rgba(255,255,255,0.06);color:var(--silver-2);border:1px solid rgba(255,255,255,0.08);border-top-left-radius:3px;}
.pmsg-bubble.user{background:var(--blue);color:#fff;border-top-right-radius:3px;}
.pmsg-actions{display:flex;flex-wrap:wrap;gap:4px;padding-left:2px;}
.typing-dots{display:flex;gap:4px;padding:9px 13px;}
.typing-dots span{width:6px;height:6px;border-radius:50%;background:var(--silver);animation:tDot 1.2s infinite;}
.typing-dots span:nth-child(2){animation-delay:0.2s;}
.typing-dots span:nth-child(3){animation-delay:0.4s;}
@keyframes tDot{0%,60%,100%{opacity:0.2;transform:translateY(0);}30%{opacity:1;transform:translateY(-4px);}}
.panel-input-row{border-top:1px solid var(--navy-3);padding:12px;display:flex;gap:8px;background:var(--navy-2);flex-shrink:0;}
.panel-input{flex:1;background:rgba(255,255,255,0.07)!important;border:1px solid rgba(255,255,255,0.12)!important;color:#fff!important;padding:8px 11px!important;border-radius:7px!important;font-size:12px!important;}
.panel-input::placeholder{color:var(--silver)!important;}
.panel-input:focus{border-color:var(--blue-light)!important;box-shadow:0 0 0 2px rgba(59,130,246,0.2)!important;}
.panel-send{background:var(--blue);color:#fff;border:none;border-radius:7px;padding:8px 14px;font-size:12px;font-weight:700;cursor:pointer;}
.panel-send:hover{background:#1a44c4;}

/* ── WELCOME ── */
.welcome-wrap{min-height:calc(100vh - 58px);background:linear-gradient(155deg,var(--navy) 0%,#0C1E35 55%,#091525 100%);display:flex;align-items:center;justify-content:center;padding:40px 20px;}
.welcome-inner{width:100%;max-width:820px;display:flex;flex-direction:column;align-items:center;gap:36px;}
.welcome-logo{width:80px;height:80px;border-radius:20px;margin:0 auto 16px;background:linear-gradient(135deg,var(--blue-light),var(--blue));display:flex;align-items:center;justify-content:center;font-size:42px;box-shadow:0 0 50px rgba(59,130,246,0.4);}
.welcome-title{font-size:46px;font-weight:900;letter-spacing:6px;color:#fff;}
.welcome-bar{width:60px;height:2px;background:linear-gradient(90deg,transparent,var(--blue-light),transparent);margin:6px auto;}
.welcome-tag{font-size:11px;letter-spacing:4px;color:var(--silver);text-transform:uppercase;}
.welcome-chat-card{width:100%;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:18px;overflow:hidden;backdrop-filter:blur(10px);box-shadow:0 12px 60px rgba(0,0,0,0.5);}
.wch-header{background:rgba(255,255,255,0.04);border-bottom:1px solid rgba(255,255,255,0.08);padding:14px 20px;display:flex;align-items:center;gap:12px;color:var(--silver-2);font-size:13px;font-weight:700;letter-spacing:0.5px;}
.wch-dot{width:8px;height:8px;border-radius:50%;background:#22C55E;box-shadow:0 0 8px #22C55E;}
.welcome-messages{padding:20px;display:flex;flex-direction:column;gap:14px;min-height:240px;max-height:360px;overflow-y:auto;}
.wmsg{display:flex;gap:12px;align-items:flex-start;}
.wmsg.user{flex-direction:row-reverse;}
.wmsg-av{width:36px;height:36px;flex-shrink:0;border-radius:10px;background:linear-gradient(135deg,var(--blue-light),var(--blue));display:flex;align-items:center;justify-content:center;font-size:18px;}
.wmsg-av.user{background:var(--navy-3);color:var(--silver-2);font-size:12px;font-weight:700;}
.wmsg-bubble{max-width:84%;padding:13px 16px;border-radius:12px;font-size:14px;line-height:1.65;}
.wmsg-bubble.bot{background:rgba(255,255,255,0.07);color:var(--silver-2);border:1px solid rgba(255,255,255,0.08);border-top-left-radius:3px;}
.wmsg-bubble.user{background:var(--blue);color:#fff;border-top-right-radius:3px;}
.welcome-input-row{border-top:1px solid rgba(255,255,255,0.08);padding:14px 16px;display:flex;gap:10px;background:rgba(255,255,255,0.03);}
.welcome-input{flex:1;background:rgba(255,255,255,0.07)!important;border:1px solid rgba(255,255,255,0.12)!important;color:#fff!important;border-radius:9px!important;}
.welcome-input::placeholder{color:var(--silver)!important;}
.welcome-input:focus{border-color:var(--blue-light)!important;box-shadow:0 0 0 3px rgba(59,130,246,0.2)!important;}
.btn-enter{background:var(--blue);color:#fff;padding:14px 42px;font-size:14px;font-weight:700;letter-spacing:1.5px;border-radius:10px;text-decoration:none;border:none;cursor:pointer;box-shadow:0 4px 24px rgba(29,78,216,0.5);transition:all 0.15s;display:inline-block;}
.btn-enter:hover{background:#1a44c4;box-shadow:0 6px 32px rgba(29,78,216,0.65);transform:translateY(-2px);}

/* ── TABS ── */
.tab-bar{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:22px;position:sticky;top:58px;z-index:100;background:var(--bg);}
.tab-btn{
  padding:11px 24px;font-size:13px;font-weight:600;color:var(--muted);
  border:none;background:none;cursor:pointer;border-bottom:2px solid transparent;
  margin-bottom:-2px;transition:all 0.15s;letter-spacing:0.3px;
}
.tab-btn:hover{color:var(--navy);}
.tab-btn.active{color:var(--blue-light);border-bottom-color:var(--blue-light);font-weight:700;}
.tab-pane{display:none;}
.tab-pane.active{display:block;}

/* ── DATA VAULT ── */
.upload-zone{
  border:2px dashed var(--border);border-radius:14px;padding:48px 28px;
  text-align:center;cursor:pointer;transition:all 0.2s;background:var(--bg-2);
  user-select:none;
}
.upload-zone:hover,.upload-zone.drag-over{border-color:var(--blue);background:var(--blue-pale);}
.upload-zone-icon{font-size:48px;margin-bottom:14px;}
.upload-zone-title{font-size:16px;font-weight:700;color:var(--navy);margin-bottom:6px;}
.upload-zone-sub{font-size:13px;color:var(--muted);}
.upload-zone input[type=file]{display:none;}
.security-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;}
.sec-badge{
  display:flex;align-items:center;gap:7px;padding:8px 14px;
  background:var(--white);border:1px solid var(--border);border-radius:8px;
  font-size:12px;font-weight:600;color:var(--navy);
}
.sec-badge-icon{font-size:15px;}
.fmt-grid{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px;}
.fmt-chip{
  padding:4px 10px;background:var(--navy);color:var(--silver-2);
  border-radius:5px;font-family:monospace;font-size:11px;letter-spacing:0.4px;
}
.proc-ok  {color:var(--success);font-weight:600;font-size:12px;}
.proc-err {color:var(--danger);font-weight:600;font-size:12px;}
.proc-pend{color:var(--warn);font-weight:600;font-size:12px;}

/* ── CUSTOM SCROLLBARS ── */
::-webkit-scrollbar{width:6px;height:6px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--silver-3);border-radius:6px;}
::-webkit-scrollbar-thumb:hover{background:var(--silver);}

/* ── FLOATING CHAT FAB ── */
#vect-fab{
  position:fixed;bottom:28px;right:28px;z-index:999;
  width:56px;height:56px;border-radius:50%;
  background:linear-gradient(135deg,var(--blue-light),var(--blue));
  box-shadow:0 4px 20px rgba(29,78,216,0.45),0 0 0 1px rgba(59,130,246,0.2);
  border:none;cursor:pointer;color:#fff;font-size:22px;
  display:flex;align-items:center;justify-content:center;transition:all 0.2s;
}
#vect-fab:hover{transform:scale(1.08);box-shadow:0 6px 28px rgba(29,78,216,0.65),0 0 0 2px rgba(59,130,246,0.3);}
#vect-fab.chat-open{background:var(--navy-3);box-shadow:0 2px 8px rgba(0,0,0,0.4);}
#vect-chat{
  position:fixed;bottom:96px;right:28px;z-index:998;width:360px;max-height:520px;
  background:var(--navy);border:1px solid var(--navy-3);border-radius:16px;
  overflow:hidden;display:flex;flex-direction:column;
  box-shadow:0 16px 60px rgba(0,0,0,0.55),0 0 0 1px rgba(59,130,246,0.06);
  transition:opacity 0.2s,transform 0.22s;
  opacity:0;pointer-events:none;transform:translateY(14px) scale(0.97);
}
#vect-chat.open{opacity:1;pointer-events:all;transform:translateY(0) scale(1);}
.vc-header{
  display:flex;align-items:center;gap:12px;padding:14px 16px;
  background:var(--navy-2);border-bottom:1px solid var(--navy-3);flex-shrink:0;
}
.vc-avatar{
  width:32px;height:32px;border-radius:8px;
  background:linear-gradient(135deg,var(--blue-light),var(--blue));
  display:flex;align-items:center;justify-content:center;font-size:16px;color:#fff;flex-shrink:0;
}
.vc-name{font-size:12px;font-weight:800;letter-spacing:2px;color:#fff;text-transform:uppercase;}
.vc-status{display:flex;align-items:center;gap:5px;font-size:10px;color:#22C55E;letter-spacing:0.5px;margin-top:2px;}
.vc-dot{width:6px;height:6px;border-radius:50%;background:#22C55E;box-shadow:0 0 6px #22C55E;animation:sPulse 2s infinite;}
.vc-close{margin-left:auto;background:transparent;border:none;color:var(--silver);cursor:pointer;font-size:16px;padding:4px 6px;border-radius:4px;line-height:1;}
.vc-close:hover{color:#fff;background:rgba(255,255,255,0.08);}
.vc-msgs{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:9px;scroll-behavior:smooth;}
.vc-msgs::-webkit-scrollbar{width:4px;}
.vc-msgs::-webkit-scrollbar-thumb{background:var(--navy-3);border-radius:4px;}
.vc-bub{
  max-width:88%;padding:9px 13px;border-radius:10px;font-size:12px;line-height:1.6;word-break:break-word;
}
.vc-bub.bot{background:rgba(255,255,255,0.06);color:var(--silver-2);border:1px solid rgba(255,255,255,0.08);border-top-left-radius:3px;align-self:flex-start;}
.vc-bub.user{background:var(--blue);color:#fff;border-top-right-radius:3px;align-self:flex-end;}
.vc-typing{display:flex;gap:4px;padding:9px 13px;align-self:flex-start;}
.vc-typing span{width:6px;height:6px;border-radius:50%;background:var(--silver);animation:tDot 1.2s infinite;}
.vc-typing span:nth-child(2){animation-delay:0.2s;}
.vc-typing span:nth-child(3){animation-delay:0.4s;}
.vc-input-row{border-top:1px solid var(--navy-3);padding:10px 12px;display:flex;gap:8px;background:var(--navy-2);flex-shrink:0;}
.vc-input{flex:1;background:rgba(255,255,255,0.07)!important;border:1px solid rgba(255,255,255,0.12)!important;color:#fff!important;padding:7px 11px!important;border-radius:7px!important;font-size:12px!important;}
.vc-input::placeholder{color:var(--silver)!important;}
.vc-input:focus{border-color:var(--blue-light)!important;box-shadow:0 0 0 2px rgba(59,130,246,0.2)!important;}
.vc-send{background:var(--blue);color:#fff;border:none;border-radius:7px;padding:7px 13px;font-size:13px;cursor:pointer;flex-shrink:0;}
.vc-send:hover{background:#1a44c4;}

/* ── PLUGIN LANGUAGE BADGES ── */
.lang-badge{font-size:10px;padding:1px 6px;border-radius:10px;font-weight:700;text-transform:uppercase;display:inline-block;}
.lang-python {background:#1e40af;color:#93c5fd;}
.lang-node   {background:#14532d;color:#86efac;}
.lang-java   {background:#7c2d12;color:#fca5a5;}
.lang-bash   {background:#1e3a5f;color:#7dd3fc;}
.lang-go     {background:#0f4c5c;color:#67e8f9;}
.lang-ruby   {background:#4c1130;color:#f9a8d4;}
.lang-rust   {background:#431407;color:#fdba74;}
.lang-unknown{background:var(--navy-3);color:var(--silver);}
</style>"""

# ─────────────────────────────────────────────────────────────────────────────
# TOPBAR
# ─────────────────────────────────────────────────────────────────────────────
_TOPBAR = """<div class="topbar">
  <a href="/" class="topbar-brand">
    <div class="tb-icon">&#9670;</div>
    <div><div class="tb-name">VECTORIAN</div><div class="tb-sub">Breach Response Platform</div></div>
  </a>
  <div class="tb-div"></div>
  <nav>
    <a href="/" class="{{ 'active' if active_nav=='dashboard' else '' }}">Dashboard</a>
    <a href="/plugins" class="{{ 'active' if active_nav=='plugins' else '' }}">Plugins</a>
    <a href="/config" class="{{ 'active' if active_nav=='config' else '' }}">Configuration</a>
  </nav>
</div>
<!-- Vectorian Chat FAB -->
<button id="vect-fab" onclick="toggleVectChat()" title="Ask Vectorian">&#9670;</button>
<div id="vect-chat">
  <div class="vc-header">
    <div class="vc-avatar">&#9670;</div>
    <div>
      <div class="vc-name">VECTORIAN</div>
      <div class="vc-status"><div class="vc-dot"></div>AI Agent Online</div>
    </div>
    <button class="vc-close" onclick="toggleVectChat()">&#x2715;</button>
  </div>
  <div class="vc-msgs" id="vc-msgs-box"></div>
  <div class="vc-input-row">
    <input class="vc-input" id="vc-input" type="text" placeholder="Ask Vectorian anything..."/>
    <button class="vc-send" onclick="vcSend()">&#9658;</button>
  </div>
</div>
<script>
(function(){
  const PK='vect_fab_'+(document.body.dataset.page||'x');
  function gH(){try{return JSON.parse(sessionStorage.getItem(PK)||'[]');}catch{return[];}}
  function sH(h){sessionStorage.setItem(PK,JSON.stringify(h));}
  function render(){
    const box=document.getElementById('vc-msgs-box');
    if(!box)return;
    box.innerHTML='';
    gH().forEach(function(m){
      const bub=document.createElement('div');
      bub.className='vc-bub '+(m.role==='user'?'user':'bot');
      bub.textContent=m.text;
      box.appendChild(bub);
    });
    box.scrollTop=box.scrollHeight;
  }
  function addMsg(role,text){const h=gH();h.push({role:role,text:text});sH(h);render();}
  function showTyping(){
    const box=document.getElementById('vc-msgs-box');if(!box)return;
    const t=document.createElement('div');t.id='vc-typing';t.className='vc-typing';
    t.innerHTML='<span></span><span></span><span></span>';
    box.appendChild(t);box.scrollTop=box.scrollHeight;
  }
  function hideTyping(){const t=document.getElementById('vc-typing');if(t)t.remove();}
  window.toggleVectChat=function(){
    const chat=document.getElementById('vect-chat');
    const fab=document.getElementById('vect-fab');
    const isOpen=chat.classList.toggle('open');
    fab.classList.toggle('chat-open',isOpen);
    if(isOpen){
      if(!gH().length)addMsg('bot',"Hello, Operator. I'm Vectorian. Ask me about breach response stages, regulatory compliance, or platform configuration.");
      else render();
      setTimeout(function(){const inp=document.getElementById('vc-input');if(inp)inp.focus();},200);
    }
  };
  window.vcSend=function(){
    const inp=document.getElementById('vc-input');
    const msg=inp.value.trim();if(!msg)return;inp.value='';
    addMsg('user',msg);showTyping();
    const iid=document.body.dataset.incidentId||'';
    // send last 12 messages as history (excludes the just-added user msg)
    const history=gH().slice(-13,-1).map(function(m){return{role:m.role,text:m.text};});
    const payload={message:msg,history:history};if(iid)payload.incident_id=iid;
    fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(function(r){return r.json();})
      .then(function(d){hideTyping();addMsg('bot',d.reply||'No response.');})
      .catch(function(){hideTyping();addMsg('bot','Unable to reach Vectorian AI.');});
  };
  document.addEventListener('keydown',function(e){
    if(e.key==='Enter'&&document.activeElement===document.getElementById('vc-input'))vcSend();
  });
})();
</script>"""

# ─────────────────────────────────────────────────────────────────────────────
# ROBOT PANEL
# ─────────────────────────────────────────────────────────────────────────────
_ROBOT_PANEL = """<div class="split-panel" id="vectorian-panel">
  <div class="robot-header">
    <div class="robot-wrap">
      <div class="robot-antenna-tip"></div>
      <div class="robot-ant-stem"></div>
      <div class="robot-neck"></div>
      <div class="robot-face">
        <div class="robot-ear l"></div><div class="robot-ear r"></div>
        <div class="robot-eyes"><div class="robot-eye"></div><div class="robot-eye"></div></div>
        <div class="robot-mouth"></div>
      </div>
    </div>
    <div class="robot-name">Vectorian</div>
    <div class="robot-status"><div class="robot-status-dot"></div>AI Agent Online</div>
  </div>
  <div class="panel-messages" id="panel-msgs"></div>
  <div class="panel-input-row">
    <input class="panel-input" id="panel-input" type="text" placeholder="Ask Vectorian anything..."/>
    <button class="panel-send" onclick="panelSend()">&#9658;</button>
  </div>
</div>
<script>
(function(){
  const PK='vect_panel_'+(document.body.dataset.page||'x');
  function gH(){try{return JSON.parse(sessionStorage.getItem(PK)||'[]');}catch{return[];}}
  function sH(h){sessionStorage.setItem(PK,JSON.stringify(h));}
  function render(){
    const box=document.getElementById('panel-msgs');
    box.innerHTML='';
    gH().forEach(m=>{
      const wrap=document.createElement('div');
      wrap.className='pmsg '+(m.role==='user'?'user':'');
      const av=document.createElement('div');
      av.className='pmsg-av '+(m.role==='user'?'user':'');
      av.textContent=m.role==='user'?'OP':'V';
      const cont=document.createElement('div');
      cont.className='pmsg-content';
      const bub=document.createElement('div');
      bub.className='pmsg-bubble '+(m.role==='user'?'user':'bot');
      bub.textContent=m.text;
      cont.appendChild(bub);
      if(m.actions&&m.actions.length){
        const ar=document.createElement('div');ar.className='pmsg-actions';
        m.actions.forEach(a=>{
          const btn=document.createElement('a');
          btn.className='btn-action';btn.href=a.href;
          btn.textContent='▶ '+a.label;ar.appendChild(btn);
        });
        cont.appendChild(ar);
      }
      wrap.appendChild(av);wrap.appendChild(cont);box.appendChild(wrap);
    });
    box.scrollTop=box.scrollHeight;
  }
  function addMsg(role,text,actions){const h=gH();h.push({role,text,actions:actions||[]});sH(h);render();}
  function showTyping(){
    const box=document.getElementById('panel-msgs');
    const t=document.createElement('div');t.id='typing-ind';t.className='pmsg';
    t.innerHTML='<div class="pmsg-av">V</div><div class="typing-dots"><span></span><span></span><span></span></div>';
    box.appendChild(t);box.scrollTop=box.scrollHeight;
  }
  function hideTyping(){const t=document.getElementById('typing-ind');if(t)t.remove();}
  window.panelSend=function(){
    const inp=document.getElementById('panel-input');
    const msg=inp.value.trim();if(!msg)return;inp.value='';
    addMsg('user',msg,[]);showTyping();
    const iid=document.body.dataset.incidentId||'';
    const payload={message:msg};if(iid)payload.incident_id=iid;
    fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      .then(r=>r.json()).then(d=>{hideTyping();addMsg('bot',d.reply||'No response.',d.actions||[]);})
      .catch(()=>{hideTyping();addMsg('bot','Unable to reach Vectorian AI.');});
  };
  document.addEventListener('keydown',e=>{if(e.key==='Enter'&&document.activeElement===document.getElementById('panel-input'))panelSend();});
  if(!gH().length)addMsg('bot',"Hello, Operator. I'm Vectorian. I can guide you through the 9-stage breach workflow, answer compliance questions, help configure this platform, or take action for you. What do you need?",[]);
  else render();
})();
</script>"""

# ─────────────────────────────────────────────────────────────────────────────
# WELCOME PAGE
# ─────────────────────────────────────────────────────────────────────────────
WELCOME_TMPL = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Breach Response Platform</title>""" + _CSS + """</head>
<body>""" + _TOPBAR + """
<div class="welcome-wrap">
  <div class="welcome-inner">
    <div style="text-align:center">
      <div class="welcome-logo">&#9670;</div>
      <div class="welcome-title">VECTORIAN</div>
      <div class="welcome-bar"></div>
      <div class="welcome-tag">AI-Powered Breach Response Platform</div>
    </div>
    <div class="welcome-chat-card">
      <div class="wch-header">
        <div class="wch-dot"></div>Vectorian AI — Breach Response Agent
        <span style="margin-left:auto;font-size:10px;color:var(--silver);letter-spacing:2px">SECURE CHANNEL</span>
      </div>
      <div class="welcome-messages" id="w-msgs">
        <div class="wmsg"><div class="wmsg-av">&#9670;</div><div class="wmsg-bubble bot" id="w-greeting"></div></div>
      </div>
      <div class="welcome-input-row">
        <input class="welcome-input" id="w-input" type="text" placeholder="Ask Vectorian about breach response, stages, regulatory compliance..."/>
        <button class="btn-enter" style="padding:10px 22px;font-size:13px;letter-spacing:0.5px" onclick="wSend()">Send</button>
      </div>
    </div>
    <a href="{{ enter_url }}" class="btn-enter">&#9654;&nbsp;&nbsp;Enter Platform</a>
    <div style="text-align:center;color:var(--silver);font-size:11px;max-width:640px;line-height:1.7">{{ disclaimer }}</div>
  </div>
</div>
<script>
const G=`Welcome, Operator.\n\nI am Vectorian — your AI-powered breach response agent.\n\nMy purpose is to guide your organization through the complete 9-stage data breach response workflow: from confirmed scope handoff and data normalization, through regulatory trigger analysis, individual notification preparation, regulatory filings, and public disclosure support.\n\nI combine deep breach response expertise with agentic platform capabilities. I don't just answer questions — I can take action within the platform on your behalf.\n\nAll outputs are draft-only and require human legal review. How can I assist you today?`;
const WK='vect_welcome_v3';
function gWH(){try{return JSON.parse(sessionStorage.getItem(WK)||'[]');}catch{return[];}}
function sWH(h){sessionStorage.setItem(WK,JSON.stringify(h));}
function renderW(){
  const box=document.getElementById('w-msgs');
  while(box.children.length>1)box.removeChild(box.lastChild);
  gWH().forEach(m=>{
    const w=document.createElement('div');w.className='wmsg '+(m.role==='user'?'user':'');
    const av=document.createElement('div');av.className='wmsg-av '+(m.role==='user'?'user':'');
    av.textContent=m.role==='user'?'OP':'◆';
    const b=document.createElement('div');b.className='wmsg-bubble '+(m.role==='user'?'user':'bot');
    b.textContent=m.text;w.appendChild(av);w.appendChild(b);box.appendChild(w);
  });
  box.scrollTop=box.scrollHeight;
}
function wSend(){
  const inp=document.getElementById('w-input');const msg=inp.value.trim();if(!msg)return;inp.value='';
  const h=gWH();h.push({role:'user',text:msg});sWH(h);renderW();
  fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})})
    .then(r=>r.json()).then(d=>{const h2=gWH();h2.push({role:'bot',text:d.reply||'No response.'});sWH(h2);renderW();})
    .catch(()=>{const h2=gWH();h2.push({role:'bot',text:'Unable to reach Vectorian AI.'});sWH(h2);renderW();});
}
document.getElementById('w-input').addEventListener('keydown',e=>{if(e.key==='Enter')wSend();});
(function typewrite(){
  const el=document.getElementById('w-greeting');let i=0;
  function tick(){if(i<G.length){el.textContent+=G[i++];document.getElementById('w-msgs').scrollTop=99999;setTimeout(tick,i<100?16:4);}}
  tick();
})();
</script></body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
INDEX_TMPL = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Dashboard</title>""" + _CSS + """</head>
<body data-page="dashboard">""" + _TOPBAR + """
<div class="split-wrap">
<div class="split-main">
<div class="page" style="padding-top:0">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
    <div>
      <div style="font-size:22px;font-weight:800;color:var(--navy)">Breach Response Dashboard</div>
      <div class="muted" style="margin-top:3px">Active engagements and response status</div>
    </div>
    <a href="/engagements/new" class="btn btn-primary">&#43;&nbsp; Open New Engagement</a>
  </div>

  <!-- Stats -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-icon">&#128203;</div>
      <div class="stat-num">{{ stats.total }}</div>
      <div class="stat-label">Total Engagements</div>
    </div>
    <div class="stat-card" style="border-top:3px solid var(--blue)">
      <div class="stat-icon">&#9654;</div>
      <div class="stat-num" style="color:var(--blue)">{{ stats.active }}</div>
      <div class="stat-label">Active</div>
    </div>
    <div class="stat-card" style="border-top:3px solid var(--success)">
      <div class="stat-icon">&#10003;</div>
      <div class="stat-num" style="color:var(--success)">{{ stats.complete }}</div>
      <div class="stat-label">Complete</div>
    </div>
    <div class="stat-card" style="border-top:3px solid var(--warn)">
      <div class="stat-icon">&#9650;</div>
      <div class="stat-num" style="color:var(--warn)">{{ stats.stages_run }}</div>
      <div class="stat-label">Stages Run</div>
    </div>
  </div>

  <!-- Engagements table -->
  <div class="card" style="padding:0;overflow:hidden">
    <div style="padding:20px 24px 0;display:flex;align-items:center;justify-content:space-between">
      <div class="card-title" style="border:none;padding:0;margin:0">&#128203; Engagements</div>
      <a href="/engagements/new" class="btn btn-primary btn-sm">&#43; New</a>
    </div>
    <div style="padding:0 0 0 0;margin-top:16px">
    {% if engagements %}
    <table>
      <thead>
        <tr>
          <th>Client</th>
          <th>Engagement ID</th>
          <th>Breach Type</th>
          <th>Stage</th>
          <th>Progress</th>
          <th>Opened</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {% for e in engagements %}
        <tr>
          <td>
            <div style="font-weight:700;color:var(--navy)">{{ e.company or e.id }}</div>
            <div class="muted" style="font-size:11px">{{ e.industry or '' }}</div>
          </td>
          <td><span style="font-family:monospace;font-size:13px;color:var(--navy-4);font-weight:600">{{ e.id }}</span></td>
          <td><span class="muted" style="font-size:12px">{{ e.breach_type or '—' }}</span></td>
          <td>
            {% if e.current_layer %}
              <span class="badge badge-blue">Stage {{ e.current_layer }}</span>
              <div class="muted" style="font-size:11px;margin-top:2px">{{ e.stage_name }}</div>
            {% else %}
              <span class="badge badge-green">&#10003; Complete</span>
            {% endif %}
          </td>
          <td style="min-width:120px">
            <div class="progress-track"><div class="progress-fill" style="width:{{ e.pct }}%"></div></div>
            <div class="muted" style="font-size:11px;margin-top:3px">{{ e.completed_count }}/{{ e.total_stages }} stages</div>
          </td>
          <td class="muted" style="font-size:12px">{{ e.created_at }}</td>
          <td style="display:flex;gap:6px;align-items:center">
            <a href="/engagements/{{ e.id }}" class="btn btn-secondary btn-sm">Open &rarr;</a>
            <form method="post" action="/engagements/{{ e.id }}/delete"
                  onsubmit="return confirm('Delete engagement {{ e.id }}? This cannot be undone.')">
              <button type="submit" class="btn btn-danger btn-sm">&#128465;</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div style="text-align:center;padding:52px 0;color:var(--muted)">
      <div style="font-size:44px;margin-bottom:14px">&#128203;</div>
      <div style="font-weight:700;font-size:16px;color:var(--navy)">No engagements yet</div>
      <div class="muted" style="margin-top:6px;margin-bottom:20px">Open your first breach response engagement to get started</div>
      <a href="/engagements/new" class="btn btn-primary">&#43; Open New Engagement</a>
    </div>
    {% endif %}
    </div>
  </div>
  <div class="disclaimer">{{ disclaimer }}</div>
</div>
</div>
</div>
</body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# NEW ENGAGEMENT WIZARD
# ─────────────────────────────────────────────────────────────────────────────
NEW_ENG_TMPL = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — New Engagement</title>""" + _CSS + """</head>
<body data-page="new-engagement">""" + _TOPBAR + """
<div class="split-wrap">
<div class="split-main">
  <div style="margin-bottom:6px"><a href="/" class="plain">&larr; Back to Dashboard</a></div>
  <div style="margin-bottom:24px">
    <div style="font-size:22px;font-weight:800;color:var(--navy)">Open New Engagement</div>
    <div class="muted" style="margin-top:3px">Complete client intake before beginning the breach response workflow</div>
  </div>

  <!-- Wizard steps -->
  <div class="wizard-steps" style="margin-bottom:28px">
    <div class="wizard-step active" id="ws-1">
      <div class="step-num" id="sn-1">1</div>Client Profile
    </div>
    <div class="wizard-step" id="ws-2">
      <div class="step-num" id="sn-2">2</div>Breach Details
    </div>
    <div class="wizard-step" id="ws-3">
      <div class="step-num" id="sn-3">3</div>Legal &amp; Regulatory
    </div>
  </div>

  <form method="post" action="/engagements/create" id="intake-form">

    <!-- STEP 1: Client Profile -->
    <div class="step-section active" id="step-1">
      <div class="card">
        <div class="card-header">
          <div class="card-title">&#127970; Client Profile</div>
          <div style="margin-left:auto;font-size:11px;color:var(--muted)">* Required fields</div>
        </div>

        <!-- Engagement ID — first thing to fill in -->
        <div style="background:var(--blue-pale);border:1px solid rgba(29,78,216,0.22);border-radius:9px;padding:16px 18px;margin-bottom:22px">
          <div class="form-row form-row-2" style="margin-bottom:0">
            <div class="form-group" style="margin-bottom:0">
              <label style="color:var(--blue)">Engagement ID *</label>
              <input type="text" name="engagement_id" id="eng-id-input" value="{{ suggested_id }}" required
                style="font-family:monospace;font-size:15px;font-weight:700;letter-spacing:1px"/>
              <div class="input-hint">Auto-generated — edit as needed</div>
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label style="color:var(--blue)">Preview</label>
              <div style="padding:9px 14px;background:var(--navy);border-radius:7px;font-family:monospace;font-size:15px;color:#fff;letter-spacing:2px;font-weight:700;margin-top:5px">
                <span id="id-preview">{{ suggested_id }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="form-row form-row-2">
          <div class="form-group">
            <label>Company / Organization Name *</label>
            <input type="text" name="company_name" placeholder="Acme Corporation" required/>
          </div>
          <div class="form-group">
            <label>Industry Sector *</label>
            <select name="industry" required>
              <option value="">Select industry...</option>
              <option>Financial Services</option>
              <option>Healthcare &amp; Life Sciences</option>
              <option>Retail &amp; E-Commerce</option>
              <option>Technology &amp; SaaS</option>
              <option>Legal Services</option>
              <option>Insurance</option>
              <option>Government &amp; Public Sector</option>
              <option>Education</option>
              <option>Manufacturing</option>
              <option>Energy &amp; Utilities</option>
              <option>Media &amp; Entertainment</option>
              <option>Other</option>
            </select>
          </div>
        </div>
        <div class="form-row form-row-2">
          <div class="form-group">
            <label>Organization Size</label>
            <select name="org_size">
              <option value="">Select size...</option>
              <option>1–50 employees</option>
              <option>51–250 employees</option>
              <option>251–1,000 employees</option>
              <option>1,001–5,000 employees</option>
              <option>5,000+ employees</option>
            </select>
          </div>
          <div class="form-group">
            <label>Annual Revenue (approx.)</label>
            <select name="revenue">
              <option value="">Select range...</option>
              <option>Under $1M</option>
              <option>$1M–$10M</option>
              <option>$10M–$100M</option>
              <option>$100M–$1B</option>
              <option>Over $1B</option>
            </select>
          </div>
        </div>
        <div class="divider"></div>
        <div class="section-title">&#128100; Primary Contact</div>
        <div class="form-row form-row-3">
          <div class="form-group">
            <label>Contact Name *</label>
            <input type="text" name="contact_name" placeholder="Jane Smith" required/>
          </div>
          <div class="form-group">
            <label>Email Address *</label>
            <input type="email" name="contact_email" placeholder="jsmith@company.com" required/>
          </div>
          <div class="form-group">
            <label>Phone Number</label>
            <input type="tel" name="contact_phone" placeholder="+1 (555) 000-0000"/>
          </div>
        </div>
        <div class="form-group">
          <label>Contact Role / Title</label>
          <input type="text" name="contact_title" placeholder="General Counsel, CISO, VP of Compliance..."/>
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end">
        <button type="button" class="btn btn-primary" onclick="goStep(2)">Next: Breach Details &rarr;</button>
      </div>
    </div>

    <!-- STEP 2: Breach Details -->
    <div class="step-section" id="step-2">
      <div class="card">
        <div class="card-header"><div class="card-title">&#9888; Breach Details</div></div>
        <div class="form-row form-row-2">
          <div class="form-group">
            <label>Date Breach Discovered *</label>
            <input type="date" name="date_discovered" required/>
          </div>
          <div class="form-group">
            <label>Estimated Date of Breach <span style="text-transform:none;font-weight:400">(if known)</span></label>
            <input type="date" name="date_of_breach"/>
          </div>
        </div>
        <div class="form-group">
          <label>Breach Type <span style="text-transform:none;font-weight:400">(select all that apply)</span></label>
          <div class="check-group" id="breach-type-group">
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Ransomware"/> Ransomware</label>
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Unauthorized Access"/> Unauthorized Access</label>
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Data Exfiltration"/> Data Exfiltration</label>
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Phishing"/> Phishing</label>
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Insider Threat"/> Insider Threat</label>
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Lost / Stolen Device"/> Lost / Stolen Device</label>
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Third-Party Vendor"/> Third-Party Vendor</label>
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Other"/> Other</label>
            <label class="check-item"><input type="checkbox" name="breach_type[]" value="Not Sure"/> Not Sure</label>
          </div>
        </div>
        <div class="form-group" style="margin-top:18px">
          <label>Data Types Involved <span style="text-transform:none;font-weight:400">(select all that apply)</span></label>
          <div class="check-group">
            <label class="check-item"><input type="checkbox" name="data_types[]" value="PII (Names, Addresses, SSNs)"/> PII — Names, Addresses, SSNs</label>
            <label class="check-item"><input type="checkbox" name="data_types[]" value="PHI (Health Records)"/> PHI — Health Records</label>
            <label class="check-item"><input type="checkbox" name="data_types[]" value="PCI (Payment Card)"/> PCI — Payment Card Data</label>
            <label class="check-item"><input type="checkbox" name="data_types[]" value="Credentials / Passwords"/> Credentials / Passwords</label>
            <label class="check-item"><input type="checkbox" name="data_types[]" value="Financial Records"/> Financial Records</label>
            <label class="check-item"><input type="checkbox" name="data_types[]" value="IP / Trade Secrets"/> IP / Trade Secrets</label>
            <label class="check-item"><input type="checkbox" name="data_types[]" value="Employee Records"/> Employee Records</label>
            <label class="check-item"><input type="checkbox" name="data_types[]" value="Other"/> Other</label>
            <label class="check-item"><input type="checkbox" name="data_types[]" value="Not Sure"/> Not Sure</label>
          </div>
        </div>
        <div class="form-row form-row-2" style="margin-top:18px">
          <div class="form-group">
            <label>Estimated Affected Individuals</label>
            <input type="number" name="affected_count" placeholder="e.g. 50000" min="0"/>
            <div class="input-hint">Rough estimate is fine — will be refined in Stage 5</div>
          </div>
          <div class="form-group">
            <label>Is the breach currently contained?</label>
            <div class="radio-group" style="margin-top:8px">
              <label class="radio-item"><input type="radio" name="contained" value="Yes"/> Yes</label>
              <label class="radio-item"><input type="radio" name="contained" value="No"/> No</label>
              <label class="radio-item"><input type="radio" name="contained" value="Unknown" checked/> Unknown</label>
              <label class="radio-item"><input type="radio" name="contained" value="Not Sure"/> Not Sure</label>
            </div>
          </div>
        </div>
        <div class="form-group">
          <label>Brief Incident Summary</label>
          <textarea name="summary" rows="3" placeholder="Describe what is known about the breach in plain language..."></textarea>
        </div>
      </div>
      <div style="display:flex;justify-content:space-between">
        <button type="button" class="btn btn-secondary" onclick="goStep(1)">&larr; Back</button>
        <button type="button" class="btn btn-primary" onclick="goStep(3)">Next: Legal &amp; Regulatory &rarr;</button>
      </div>
    </div>

    <!-- STEP 3: Legal & Regulatory -->
    <div class="step-section" id="step-3">
      <div class="card">
        <div class="card-header"><div class="card-title">&#9878; Legal &amp; Regulatory Context</div></div>
        <div class="form-group">
          <label>Applicable Regulatory Frameworks <span style="text-transform:none;font-weight:400">(select all that apply)</span></label>
          <div class="check-group">
            <label class="check-item"><input type="checkbox" name="regulations[]" value="HIPAA"/> HIPAA</label>
            <label class="check-item"><input type="checkbox" name="regulations[]" value="GDPR"/> GDPR</label>
            <label class="check-item"><input type="checkbox" name="regulations[]" value="CCPA / CPRA"/> CCPA / CPRA</label>
            <label class="check-item"><input type="checkbox" name="regulations[]" value="GLBA"/> GLBA</label>
            <label class="check-item"><input type="checkbox" name="regulations[]" value="PCI-DSS"/> PCI-DSS</label>
            <label class="check-item"><input type="checkbox" name="regulations[]" value="State Breach Laws (US)"/> State Breach Laws (US)</label>
            <label class="check-item"><input type="checkbox" name="regulations[]" value="PIPEDA (Canada)"/> PIPEDA (Canada)</label>
            <label class="check-item"><input type="checkbox" name="regulations[]" value="Other"/> Other</label>
          </div>
        </div>
        <div class="form-group" style="margin-top:18px">
          <label>Geographic Scope <span style="text-transform:none;font-weight:400">(jurisdictions with potentially affected individuals)</span></label>
          <input type="text" name="jurisdictions" placeholder="e.g. California, New York, Texas, EU, Canada"/>
        </div>
        <div class="divider"></div>
        <div class="form-row form-row-2">
          <div class="form-group">
            <label>Legal Counsel Engaged?</label>
            <div class="radio-group" style="margin-top:8px">
              <label class="radio-item"><input type="radio" name="counsel_engaged" value="Yes"/> Yes</label>
              <label class="radio-item"><input type="radio" name="counsel_engaged" value="No" checked/> No</label>
            </div>
          </div>
          <div class="form-group">
            <label>Law Enforcement Notified?</label>
            <div class="radio-group" style="margin-top:8px">
              <label class="radio-item"><input type="radio" name="law_enforcement" value="Yes"/> Yes</label>
              <label class="radio-item"><input type="radio" name="law_enforcement" value="No" checked/> No</label>
              <label class="radio-item"><input type="radio" name="law_enforcement" value="Pending"/> Pending</label>
            </div>
          </div>
        </div>
        <div class="form-row form-row-2">
          <div class="form-group">
            <label>Law Firm Name <span style="text-transform:none;font-weight:400">(if applicable)</span></label>
            <input type="text" name="law_firm" placeholder="Smith &amp; Associates LLP"/>
          </div>
          <div class="form-group">
            <label>Matter Under Attorney-Client Privilege?</label>
            <div class="radio-group" style="margin-top:8px">
              <label class="radio-item"><input type="radio" name="privilege" value="Yes"/> Yes</label>
              <label class="radio-item"><input type="radio" name="privilege" value="No" checked/> No</label>
            </div>
          </div>
        </div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <button type="button" class="btn btn-secondary" onclick="goStep(2)">&larr; Back</button>
        <button type="submit" class="btn btn-success" style="font-size:14px;padding:11px 28px">
          &#9670;&nbsp; Open Engagement
        </button>
      </div>
    </div>

  </form>
</div>
</div>
<script>
let currentStep=1;
function goStep(n){
  document.getElementById('step-'+currentStep).classList.remove('active');
  document.getElementById('ws-'+currentStep).classList.remove('active');
  if(n>currentStep)document.getElementById('ws-'+currentStep).classList.add('done');
  currentStep=n;
  document.getElementById('step-'+n).classList.add('active');
  document.getElementById('ws-'+n).classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
}
// Styled checkboxes/radios
document.querySelectorAll('.check-group input[type=checkbox]').forEach(inp=>{
  inp.addEventListener('change',()=>{inp.closest('.check-item').classList.toggle('selected',inp.checked);});
});
document.querySelectorAll('.radio-group input[type=radio]').forEach(inp=>{
  inp.addEventListener('change',()=>{
    document.querySelectorAll('[name="'+inp.name+'"]').forEach(r=>r.closest('.radio-item').classList.remove('selected'));
    inp.closest('.radio-item').classList.add('selected');
  });
});
// Pre-select defaults
document.querySelectorAll('.radio-item input[type=radio]:checked').forEach(inp=>{inp.closest('.radio-item').classList.add('selected');});
// ID preview
document.getElementById('eng-id-input').addEventListener('input',function(){
  document.getElementById('id-preview').textContent=this.value||'—';
});
</script>
</body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_TMPL = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Configuration</title>""" + _CSS + """</head>
<body data-page="config">""" + _TOPBAR + """
<div class="split-wrap">
<div class="split-main">
  <div style="margin-bottom:24px">
    <div style="font-size:22px;font-weight:800;color:var(--navy)">Platform Configuration</div>
    <div class="muted" style="margin-top:3px">Customize your organization's workflow, stages, and engagement ID format</div>
  </div>

  <form method="post" action="/config/save">

    <!-- Engagement ID Format -->
    <div class="card">
      <div class="card-header">
        <div style="width:34px;height:34px;background:var(--navy);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;">&#9881;</div>
        <div>
          <div class="card-title" style="border:none;padding:0;margin:0">Engagement ID Format</div>
          <div class="muted" style="font-size:12px;margin-top:1px">Controls how new engagement identifiers are generated</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:18px;max-width:680px">
        <div><label>Prefix</label><input type="text" name="prefix" value="{{ cfg.incident_code_format.prefix }}" oninput="updatePreview()"/></div>
        <div><label>Separator</label>
          <select name="separator" onchange="updatePreview()">
            <option value="-" {{ 'selected' if cfg.incident_code_format.separator=='-' }}>Hyphen ( - )</option>
            <option value="_" {{ 'selected' if cfg.incident_code_format.separator=='_' }}>Underscore ( _ )</option>
            <option value="/" {{ 'selected' if cfg.incident_code_format.separator=='/' }}>Slash ( / )</option>
          </select>
        </div>
        <div><label>Include Year</label>
          <div style="padding:9px 12px;border:1px solid var(--border);border-radius:7px;background:var(--white);cursor:pointer" onclick="document.getElementById('year-chk').click()">
            <input type="checkbox" name="year" id="year-chk" onchange="updatePreview()" {{ 'checked' if cfg.incident_code_format.year }} style="width:auto;margin-right:8px"/>Append year
          </div>
        </div>
        <div><label>Digits</label><input type="number" name="digits" min="2" max="8" value="{{ cfg.incident_code_format.digits }}" oninput="updatePreview()"/></div>
      </div>
      <div style="margin-top:20px;background:var(--navy);border-radius:10px;padding:16px 24px;max-width:500px;display:flex;align-items:center;gap:20px">
        <div>
          <div style="font-size:10px;letter-spacing:2px;color:var(--silver);text-transform:uppercase;margin-bottom:4px">Generated ID Preview</div>
          <div id="fmt-preview" style="font-size:24px;font-family:monospace;color:#fff;font-weight:800;letter-spacing:4px"></div>
        </div>
      </div>
    </div>

    <!-- Stage Configuration -->
    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:20px 24px;display:flex;align-items:center;gap:12px;border-bottom:1px solid var(--silver-pale)">
        <div style="width:34px;height:34px;background:var(--navy);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;">&#9776;</div>
        <div style="flex:1">
          <div class="card-title" style="border:none;padding:0;margin:0">Breach Response Stages</div>
          <div class="muted" style="font-size:12px;margin-top:1px">Reorder, rename, assign owners, and enable/disable stages</div>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addStage()">&#43; Add Custom Stage</button>
      </div>
      <table id="stages-table">
        <thead>
          <tr>
            <th style="width:80px">Order</th>
            <th>Stage</th>
            <th>Custom Name</th>
            <th>Owner / Assignee</th>
            <th>Notes</th>
            <th style="width:82px;text-align:center">Enabled</th>
            <th style="width:54px"></th>
          </tr>
        </thead>
        <tbody id="stages-body">
        {% for i, s in stages_enum %}
        <tr id="row-{{ s.id }}">
          <td style="text-align:center">
            <button type="button" class="btn btn-secondary btn-sm" onclick="moveRow('{{ s.id }}',-1)" style="padding:3px 9px;margin-bottom:3px">&#8593;</button><br/>
            <button type="button" class="btn btn-secondary btn-sm" onclick="moveRow('{{ s.id }}',1)"  style="padding:3px 9px">&#8595;</button>
          </td>
          <td>
            <input type="hidden" name="id[]" value="{{ s.id }}"/>
            <div style="display:flex;align-items:center;gap:8px">
              <span class="badge badge-navy" style="font-family:monospace">{{ s.id }}</span>
              <span class="muted" style="font-size:12px;line-height:1.3">{{ s.name }}</span>
            </div>
          </td>
          <td><input type="text" name="custom_name[]" value="{{ s.custom_name }}" placeholder="Override display name..."/></td>
          <td><input type="text" name="owner[]" value="{{ s.owner }}" placeholder="e.g. Privacy Counsel..."/></td>
          <td><textarea name="notes[]" rows="1" style="resize:vertical;font-size:12px;min-height:36px">{{ s.notes }}</textarea></td>
          <td style="text-align:center">
            <input type="checkbox" name="enabled_{{ s.id }}" {{ 'checked' if s.enabled }} style="width:18px;height:18px;cursor:pointer"/>
          </td>
          <td style="text-align:center">
            <button type="button" class="btn btn-danger btn-sm" onclick="deleteRow('{{ s.id }}')" title="Remove stage">&#x2715;</button>
          </td>
        </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:40px">
      <button type="submit" class="btn btn-primary">&#10003;&nbsp; Save Configuration</button>
      <a href="/" class="btn btn-secondary">Discard Changes</a>
    </div>
  </form>
</div>
</div>
<script>
var cc={{ custom_count }};
function updatePreview(){
  var p=document.querySelector('[name=prefix]').value||'INC';
  var s=document.querySelector('[name=separator]').value||'-';
  var y=document.getElementById('year-chk').checked;
  var d=parseInt(document.querySelector('[name=digits]').value)||4;
  var parts=[p];if(y)parts.push('2026');parts.push('1'.padStart(d,'0'));
  document.getElementById('fmt-preview').textContent=parts.join(s);
}
updatePreview();
function moveRow(id,dir){
  var el=document.getElementById('row-'+id);if(!el)return;
  if(dir===-1&&el.previousElementSibling)el.parentNode.insertBefore(el,el.previousElementSibling);
  else if(dir===1&&el.nextElementSibling)el.parentNode.insertBefore(el.nextElementSibling,el);
}
function deleteRow(id){var el=document.getElementById('row-'+id);if(el)el.remove();}
function addStage(){
  cc++;var cid='custom_'+cc;
  var tbody=document.getElementById('stages-body');
  var tr=document.createElement('tr');tr.id='row-'+cid;
  tr.innerHTML='<td style="text-align:center">'+
    '<button type="button" class="btn btn-secondary btn-sm" onclick="moveRow(\\\''+cid+'\\\',-1)" style="padding:3px 9px;margin-bottom:3px">&#8593;</button><br/>'+
    '<button type="button" class="btn btn-secondary btn-sm" onclick="moveRow(\\\''+cid+'\\\',1)" style="padding:3px 9px">&#8595;</button></td>'+
    '<td><input type="hidden" name="id[]" value="'+cid+'"/>'+
      '<div style="display:flex;align-items:center;gap:8px">'+
        '<span class="badge badge-silver" style="font-family:monospace">'+cid+'</span>'+
        '<span class="muted" style="font-size:12px">Custom Stage</span></div></td>'+
    '<td><input type="text" name="custom_name[]" placeholder="Stage name..."/></td>'+
    '<td><input type="text" name="owner[]" placeholder="Assignee..."/></td>'+
    '<td><textarea name="notes[]" rows="1" style="resize:vertical;font-size:12px;min-height:36px"></textarea></td>'+
    '<td style="text-align:center"><input type="checkbox" name="enabled_'+cid+'" checked style="width:18px;height:18px;cursor:pointer"/></td>'+
    '<td style="text-align:center"><button type="button" class="btn btn-danger btn-sm" onclick="deleteRow(\\\''+cid+'\\\')">&#x2715;</button></td>';
  tbody.appendChild(tr);tr.querySelector('[name="custom_name[]"]').focus();
}
</script>
</body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# PLUGINS PAGE
# ─────────────────────────────────────────────────────────────────────────────
PLUGINS_TMPL = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Plugins</title>""" + _CSS + """
<style>
.plugin-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-bottom:24px;}
@media(max-width:820px){.plugin-grid{grid-template-columns:1fr;}}
.plugin-card{
  background:var(--white);border:1px solid var(--border);border-radius:12px;
  padding:18px 20px;box-shadow:0 2px 8px rgba(10,22,40,0.06);
  display:flex;flex-direction:column;gap:10px;
}
.plugin-card.disabled-card{opacity:0.55;filter:grayscale(0.4);}
.plugin-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;}
.plugin-icon{font-size:22px;flex-shrink:0;}
.plugin-name{font-size:14px;font-weight:700;color:var(--navy);}
.plugin-cat{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
  color:var(--muted);margin-top:2px;}
.plugin-desc{font-size:12px;color:var(--muted);line-height:1.6;}
.plugin-tags{display:flex;flex-wrap:wrap;gap:5px;}
.plugin-tag{padding:2px 8px;background:var(--navy);color:var(--silver-2);
  border-radius:4px;font-family:monospace;font-size:10px;}
.toggle-wrap{display:flex;align-items:center;gap:8px;flex-shrink:0;}
.toggle-label{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:0.8px;white-space:nowrap;}
/* Toggle switch */
.tgl-sw{position:relative;display:inline-block;width:40px;height:22px;}
.tgl-sw input{opacity:0;width:0;height:0;}
.tgl-slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;
  background:#ccd6e0;border-radius:22px;transition:.2s;}
.tgl-slider:before{position:absolute;content:"";height:16px;width:16px;left:3px;bottom:3px;
  background:white;border-radius:50%;transition:.2s;box-shadow:0 1px 4px rgba(0,0,0,0.2);}
input:checked+.tgl-slider{background:var(--blue);}
input:checked+.tgl-slider:before{transform:translateX(18px);}
/* Section header */
.plugin-section-hdr{
  display:flex;align-items:center;gap:10px;margin:8px 0 14px;
  font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;color:var(--navy-4);
}
.plugin-section-hdr::after{content:'';flex:1;height:1px;background:var(--border);}
/* Coming soon card */
.cs-card{
  background:var(--bg-2);border:1px dashed var(--border);border-radius:12px;
  padding:18px 20px;display:flex;flex-direction:column;gap:8px;opacity:0.7;
}
/* API key details */
details.api-details summary{
  cursor:pointer;font-size:11px;font-weight:600;color:var(--blue);
  list-style:none;padding:4px 0;
}
details.api-details summary::before{content:'▶ ';}
details.api-details[open] summary::before{content:'▼ ';}
details.api-details .api-body{padding:10px 0 4px;}
</style>
</head>
<body data-page="plugins">""" + _TOPBAR + """
<div class="page">
  <div style="margin-bottom:6px"><a href="/" class="plain">&larr; Back to Dashboard</a></div>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
    <div>
      <div style="font-size:22px;font-weight:800;color:var(--navy)">Plugins &amp; Scanners</div>
      <div class="muted" style="margin-top:3px">Plugins run automatically during Stage 2 analysis. Toggle to enable or disable per installation.</div>
    </div>
  </div>

  {# ── CORE SCANNERS ── #}
  <div class="plugin-section-hdr">Core Scanners</div>
  <div class="plugin-grid">
  {% for p in plugin_meta if p.category == "Core Scanners" %}
  {% set cfg_p = plugin_cfg.get(p.id, {}) %}
  {% set is_on = cfg_p.get("enabled", True) %}
  <div class="plugin-card{% if not is_on %} disabled-card{% endif %}">
    <div class="plugin-top">
      <div style="display:flex;gap:12px;align-items:flex-start;min-width:0">
        <div class="plugin-icon">{{ p.icon|safe }}</div>
        <div>
          <div class="plugin-name">{{ p.name }}</div>
          <div class="plugin-cat">{{ p.category }}</div>
        </div>
      </div>
      <form method="post" action="/plugins/save" class="toggle-wrap">
        <input type="hidden" name="plugin_id" value="{{ p.id }}"/>
        <label class="toggle-label">{{ "ON" if is_on else "OFF" }}</label>
        <label class="tgl-sw">
          <input type="checkbox" name="enabled" {% if is_on %}checked{% endif %}
            onchange="this.form.submit()"/>
          <span class="tgl-slider"></span>
        </label>
      </form>
    </div>
    <div class="plugin-desc">{{ p.description }}</div>
    <div class="plugin-tags">
      {% for tag in p.tags %}<span class="plugin-tag">{{ tag }}</span>{% endfor %}
    </div>
  </div>
  {% endfor %}
  </div>

  {# ── EXTERNAL INTEGRATIONS ── #}
  <div class="plugin-section-hdr">External Integrations</div>
  <div class="plugin-grid">
  {% for p in plugin_meta if p.category == "External Integrations" %}
  {% set cfg_p = plugin_cfg.get(p.id, {}) %}
  {% set is_on = cfg_p.get("enabled", False) %}
  {% set has_key = cfg_p.get("api_key", "") %}
  <div class="plugin-card{% if not is_on %} disabled-card{% endif %}">
    <div class="plugin-top">
      <div style="display:flex;gap:12px;align-items:flex-start;min-width:0">
        <div class="plugin-icon">{{ p.icon|safe }}</div>
        <div>
          <div class="plugin-name">{{ p.name }}</div>
          <div class="plugin-cat">{{ p.category }}</div>
        </div>
      </div>
      <form method="post" action="/plugins/save" class="toggle-wrap">
        <input type="hidden" name="plugin_id" value="{{ p.id }}"/>
        <label class="toggle-label">{{ "ON" if is_on else "OFF" }}</label>
        <label class="tgl-sw">
          <input type="checkbox" name="enabled" {% if is_on %}checked{% endif %}
            onchange="this.form.submit()"/>
          <span class="tgl-slider"></span>
        </label>
      </form>
    </div>
    <div class="plugin-desc">{{ p.description }}</div>
    <div class="plugin-tags">
      {% for tag in p.tags %}<span class="plugin-tag">{{ tag }}</span>{% endfor %}
    </div>
    {# API key config #}
    <details class="api-details">
      <summary>{{ p.api_key_label }} configuration</summary>
      <div class="api-body">
        <form method="post" action="/plugins/save" style="display:flex;gap:8px;align-items:center">
          <input type="hidden" name="plugin_id" value="{{ p.id }}"/>
          {% if is_on %}<input type="hidden" name="enabled" value="on"/>{% endif %}
          <input type="text" name="api_key" value="{{ has_key }}"
            placeholder="Paste API key here…"
            style="flex:1;font-family:monospace;font-size:12px;padding:6px 10px"/>
          <button type="submit" class="btn btn-primary btn-sm">Save</button>
        </form>
        <div class="input-hint" style="margin-top:6px">
          Get your key at <a href="{{ p.api_key_url }}" target="_blank" rel="noopener" class="plain">{{ p.api_key_url }}</a>
        </div>
        {% if has_key %}
        <div style="margin-top:6px;font-size:11px;color:var(--success)">&#10003; API key configured ({{ has_key[:4] }}…)</div>
        {% endif %}
      </div>
    </details>
  </div>
  {% endfor %}
  </div>

  {# ── COMING SOON ── #}
  <div class="plugin-section-hdr">Coming Soon</div>
  <div class="plugin-grid">
    <div class="cs-card">
      <div style="display:flex;gap:12px;align-items:flex-start">
        <div class="plugin-icon">&#128196;</div>
        <div>
          <div class="plugin-name">YARA Rules Engine</div>
          <div class="plugin-cat">Core Scanners</div>
        </div>
      </div>
      <div class="plugin-desc">Custom YARA rule sets for malware signatures, threat actor TTPs, and proprietary data patterns. Import any .yar rule file.</div>
      <div class="plugin-tags">
        <span class="plugin-tag">YARA</span>
        <span class="plugin-tag">Malware</span>
        <span class="plugin-tag">Custom Rules</span>
      </div>
      <span class="badge badge-silver" style="width:fit-content">Coming Soon</span>
    </div>
    <div class="cs-card">
      <div style="display:flex;gap:12px;align-items:flex-start">
        <div class="plugin-icon">&#128295;</div>
        <div>
          <div class="plugin-name">Custom Plugin SDK</div>
          <div class="plugin-cat">Developer Tools</div>
        </div>
      </div>
      <div class="plugin-desc">Build and deploy your own Vectrion plugins using the Plugin SDK. Implement scan_file() / scan_vault() and drop in the plugins/ directory.</div>
      <div class="plugin-tags">
        <span class="plugin-tag">Python SDK</span>
        <span class="plugin-tag">Custom</span>
        <span class="plugin-tag">Extensible</span>
      </div>
      <span class="badge badge-silver" style="width:fit-content">Coming Soon</span>
    </div>
  </div>

  {# ── CUSTOM PLUGINS ── #}
  <div class="plugin-section-hdr">Custom Plugins</div>

  {# Upload card #}
  <div class="card" style="margin-bottom:20px">
    <div class="card-header">
      <div class="card-title">&#128196; Upload Custom Scanner</div>
    </div>
    <form method="post" action="/plugins/upload" enctype="multipart/form-data"
          style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
      <label class="btn btn-secondary" style="cursor:pointer;margin:0">
        &#128193;&nbsp; Choose File
        <input type="file" name="file" accept=".py,.zip" style="display:none" onchange="this.form.submit()"/>
      </label>
      <span style="color:var(--muted);font-size:12px">SDK starters:</span>
      <a href="/plugins/sdk-template" class="plain" style="font-size:13px">&#11015; Python</a>
      <a href="/plugins/sdk/node"     class="plain" style="font-size:13px">&#11015; Node.js</a>
      <a href="/plugins/sdk/java"     class="plain" style="font-size:13px">&#11015; Java</a>
      <a href="/plugins/sdk/bash"     class="plain" style="font-size:13px">&#11015; Bash</a>
      <a href="/plugins/sdk/go"       class="plain" style="font-size:13px">&#11015; Go</a>
    </form>
    <div class="input-hint" style="margin-top:10px">
      Upload a <code style="background:var(--bg-2);padding:1px 5px;border-radius:3px;font-family:monospace">.py</code> file (legacy Python)
      or a <code style="background:var(--bg-2);padding:1px 5px;border-radius:3px;font-family:monospace">.zip</code> bundle containing a
      <code style="background:var(--bg-2);padding:1px 5px;border-radius:3px;font-family:monospace">plugin.json</code> manifest
      and your scanner entry point. Supports Python, Node.js, Java, Bash, Go, Ruby, and Rust.
    </div>
  </div>

  {# Installed custom plugins #}
  {% if custom_plugins %}
  <div class="plugin-grid">
  {% for cp in custom_plugins %}
  {% set cp_ref = cp.get('filename') or cp.get('dirname', '') %}
  {% set cp_lang = cp.get('language', 'unknown') %}
  <div class="plugin-card{% if cp.error %} disabled-card{% endif %}">
    <div class="plugin-top">
      <div style="display:flex;gap:12px;align-items:flex-start;min-width:0">
        <div class="plugin-icon">&#9881;</div>
        <div>
          <div class="plugin-name">{{ cp.name }}</div>
          <div class="plugin-cat" style="display:flex;align-items:center;gap:6px;margin-top:2px">
            <span>Custom Plugin &mdash; {{ cp_ref }}</span>
            <span class="lang-badge lang-{{ cp_lang }}">{{ cp_lang }}</span>
          </div>
        </div>
      </div>
      {% if cp.error %}
      <span class="badge" style="background:var(--danger-bg);color:var(--danger);flex-shrink:0">Error</span>
      {% else %}
      <span class="badge badge-green" style="flex-shrink:0">&#10003; Loaded</span>
      {% endif %}
    </div>
    {% if cp.error %}
    <div style="font-size:12px;color:var(--danger);background:var(--danger-bg);padding:8px 12px;border-radius:6px;font-family:monospace;word-break:break-all">
      {{ cp.error }}
    </div>
    {% endif %}
    <form method="post" action="/plugins/custom/{{ cp_ref | urlencode }}/remove"
          style="display:flex;justify-content:flex-end;margin-top:4px">
      <button type="submit" class="btn btn-danger btn-sm"
              onclick="return confirm('Remove {{ cp_ref }}?')">&#x2715;&nbsp; Remove</button>
    </form>
  </div>
  {% endfor %}
  </div>
  {% else %}
  <div style="color:var(--muted);font-size:13px;padding:10px 0 20px">
    No custom plugins installed. Upload a <code style="background:var(--bg-2);padding:1px 5px;border-radius:3px;font-family:monospace">.py</code> file
    or a <code style="background:var(--bg-2);padding:1px 5px;border-radius:3px;font-family:monospace">.zip</code> bundle above to get started.
  </div>
  {% endif %}

</div>
</body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# SETUP WIZARD
# ─────────────────────────────────────────────────────────────────────────────
SETUP_TMPL = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Setup</title>""" + _CSS + """</head>
<body data-page="setup">""" + _TOPBAR + """
<div class="split-wrap">
<div class="split-main">
  <div style="margin-bottom:24px">
    <div style="font-size:22px;font-weight:800;color:var(--navy)">Platform Setup</div>
    <div class="muted" style="margin-top:3px">Configure Vectorian for your organization — takes under 2 minutes</div>
  </div>
  <div class="wizard-steps">
    <div class="wizard-step {{ 'active' if step==1 else 'done' if step>1 else '' }}" id="ws-1">
      <div class="step-num">{{ '✓' if step>1 else '1' }}</div>Engagement Code Format
    </div>
    <div class="wizard-step {{ 'active' if step==2 else '' }}" id="ws-2">
      <div class="step-num">2</div>Stage Names
    </div>
  </div>

  {% if step == 1 %}
  <div class="card">
    <div class="card-header">
      <div style="width:34px;height:34px;background:var(--navy);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px">&#9881;</div>
      <div><div class="card-title" style="border:none;padding:0;margin:0">Engagement ID Format</div>
      <div class="muted" style="font-size:12px;margin-top:1px">How should engagement identifiers look? (e.g. ENG-2026-0001)</div></div>
    </div>
    <form method="post" action="/setup/step1">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;max-width:540px;margin-bottom:24px">
        <div><label>Prefix</label><input type="text" name="prefix" value="{{ cfg.incident_code_format.prefix }}" oninput="updatePreview()"/></div>
        <div><label>Separator</label>
          <select name="separator" onchange="updatePreview()">
            <option value="-" {{ 'selected' if cfg.incident_code_format.separator=='-' }}>Hyphen  —  -</option>
            <option value="_" {{ 'selected' if cfg.incident_code_format.separator=='_' }}>Underscore  —  _</option>
            <option value="/" {{ 'selected' if cfg.incident_code_format.separator=='/' }}>Slash  —  /</option>
          </select>
        </div>
        <div><label>Include Year</label>
          <div style="padding:9px 12px;border:1px solid var(--border);border-radius:7px;background:var(--white)">
            <input type="checkbox" name="year" id="year-chk" onchange="updatePreview()" {{ 'checked' if cfg.incident_code_format.year }} style="width:auto;margin-right:8px"/>Append current year
          </div>
        </div>
        <div><label>Sequence Digits</label><input type="number" name="digits" min="2" max="8" value="{{ cfg.incident_code_format.digits }}" oninput="updatePreview()"/></div>
      </div>
      <div style="background:var(--navy);border-radius:12px;padding:20px 28px;max-width:540px;margin-bottom:24px">
        <div style="font-size:10px;letter-spacing:2px;color:var(--silver);text-transform:uppercase;margin-bottom:8px">Live Preview</div>
        <div id="fmt-preview" style="font-size:30px;font-family:monospace;color:#fff;font-weight:900;letter-spacing:5px"></div>
      </div>
      <button class="btn btn-primary" type="submit">Next &rarr;</button>
    </form>
  </div>
  <script>
  function updatePreview(){
    var p=document.querySelector('[name=prefix]').value||'INC';
    var s=document.querySelector('[name=separator]').value||'-';
    var y=document.getElementById('year-chk').checked;
    var d=parseInt(document.querySelector('[name=digits]').value)||4;
    var parts=[p];if(y)parts.push('2026');parts.push('1'.padStart(d,'0'));
    document.getElementById('fmt-preview').textContent=parts.join(s);
  }
  updatePreview();
  </script>

  {% elif step == 2 %}
  <div class="card" style="padding:0;overflow:hidden">
    <div style="padding:20px 24px;border-bottom:1px solid var(--silver-pale);display:flex;align-items:center;gap:12px">
      <div style="width:34px;height:34px;background:var(--navy);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px">&#9776;</div>
      <div><div class="card-title" style="border:none;padding:0;margin:0">Stage Names</div>
      <div class="muted" style="font-size:12px;margin-top:1px">Customize stage display names for your organization (optional)</div></div>
    </div>
    <form method="post" action="/setup/save">
      <table id="stages-table">
        <thead><tr><th>#</th><th>Default Stage Name</th><th>Custom Name <span style="font-weight:400;text-transform:none;letter-spacing:0">(optional — leave blank to keep default)</span></th></tr></thead>
        <tbody>
        {% for s in cfg.stages %}
        <tr>
          <td><span class="badge badge-navy" style="font-family:monospace">{{ s.id }}</span></td>
          <td class="muted" style="font-size:13px">{{ s.name }}</td>
          <td>
            <input type="hidden" name="id[]" value="{{ s.id }}"/>
            <input type="hidden" name="name[]" value="{{ s.name }}"/>
            <input type="text" name="custom_name[]" value="{{ s.custom_name }}" placeholder="Leave blank to use default"/>
          </td>
        </tr>
        {% endfor %}
        </tbody>
      </table>
      <div style="padding:20px 24px;display:flex;gap:12px;border-top:1px solid var(--silver-pale)">
        <button type="button" class="btn btn-secondary" onclick="addStage()">&#43; Add Custom Stage</button>
        <button type="submit" class="btn btn-success">&#9670;&nbsp; Complete Setup &amp; Enter Platform</button>
      </div>
    </form>
  </div>
  <script>
  var cc=0;
  function addStage(){
    cc++;var cid='custom_'+cc;
    var tbody=document.querySelector('#stages-table tbody');var tr=document.createElement('tr');
    tr.innerHTML='<td><span class="badge badge-silver" style="font-family:monospace">'+cid+'</span></td>'+
      '<td class="muted"><em>Custom Stage</em></td><td>'+
        '<input type="hidden" name="id[]" value="'+cid+'"/>'+
        '<input type="hidden" name="name[]" value="Custom Stage"/>'+
        '<input type="text" name="custom_name[]" placeholder="Enter stage name"/></td>';
    tbody.appendChild(tr);
  }
  </script>
  {% endif %}
</div>
</div></body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# ENGAGEMENT DETAIL
# ─────────────────────────────────────────────────────────────────────────────
DETAIL_TMPL = """<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — {{ engagement_id }}</title>""" + _CSS + """</head>
<body data-page="eng-{{ engagement_id }}" data-incident-id="{{ engagement_id }}">""" + _TOPBAR + """
<div class="split-wrap">
<div class="split-main">
  <div style="margin-bottom:16px"><a href="/" class="plain">&larr; Back to Dashboard</a></div>

  <!-- Client identity block -->
  <div class="client-block">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:14px">
      <div>
        <div class="client-block-name">{{ client.company_name or engagement_id }}</div>
        <div style="margin-top:6px;display:flex;gap:10px;flex-wrap:wrap">
          {% if client.industry %}<span class="badge badge-navy">{{ client.industry }}</span>{% endif %}
          {% if client.org_size %}<span class="badge badge-silver">{{ client.org_size }}</span>{% endif %}
          {% if current_layer %}
            <span class="badge badge-blue">Stage {{ current_layer }} Active</span>
          {% else %}
            <span class="badge badge-green">&#10003; Engagement Complete</span>
          {% endif %}
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:10px">
        <div style="font-family:monospace;font-size:13px;color:var(--silver-3);background:rgba(0,0,0,0.2);padding:6px 14px;border-radius:7px;font-weight:700;letter-spacing:2px">
          {{ engagement_id }}
        </div>
        <form method="post" action="/engagements/{{ engagement_id }}/delete"
              onsubmit="return confirm('Permanently delete engagement {{ engagement_id }} and all vault files? This cannot be undone.')">
          <button type="submit" class="btn btn-danger btn-sm">&#128465; Delete</button>
        </form>
      </div>
    </div>
    <div class="client-block-meta" style="margin-top:16px">
      {% if client.contact_name %}
      <div class="client-block-field">
        <span class="client-block-label">Primary Contact</span>
        <span class="client-block-value">{{ client.contact_name }}</span>
      </div>
      {% endif %}
      {% if client.contact_email %}
      <div class="client-block-field">
        <span class="client-block-label">Email</span>
        <span class="client-block-value">{{ client.contact_email }}</span>
      </div>
      {% endif %}
      {% if client.date_discovered %}
      <div class="client-block-field">
        <span class="client-block-label">Date Discovered</span>
        <span class="client-block-value">{{ client.date_discovered }}</span>
      </div>
      {% endif %}
      {% if client.breach_type %}
      <div class="client-block-field">
        <span class="client-block-label">Breach Type</span>
        <span class="client-block-value">{{ client.breach_type if client.breach_type is string else client.breach_type|join(', ') }}</span>
      </div>
      {% endif %}
      {% if client.affected_count %}
      <div class="client-block-field">
        <span class="client-block-label">Est. Affected</span>
        <span class="client-block-value">{{ client.affected_count | format_number }}</span>
      </div>
      {% endif %}
      {% if client.jurisdictions %}
      <div class="client-block-field">
        <span class="client-block-label">Jurisdictions</span>
        <span class="client-block-value">{{ client.jurisdictions }}</span>
      </div>
      {% endif %}
    </div>
  </div>

  <!-- Tab bar -->
  <div class="tab-bar" id="main-tab-bar">
    <button type="button" class="tab-btn{% if not vault_files and not completed %}" data-tab="overview"{% else %} active" data-tab="overview"{% endif %}>&#9776;&nbsp; Overview</button>
    <button type="button" class="tab-btn{% if not vault_files and not completed %} active{% endif %}" data-tab="vault">&#128274;&nbsp; Data Vault
      {% if vault_files %}<span style="margin-left:6px;background:var(--blue);color:#fff;border-radius:999px;font-size:10px;padding:1px 7px;font-weight:700">{{ vault_files|length }}</span>{% endif %}
    </button>
    <button type="button" class="tab-btn" data-tab="runbook">&#128200;&nbsp; Analysis
      {% if completed %}<span style="margin-left:6px;background:var(--success);color:#fff;border-radius:999px;font-size:10px;padding:1px 7px;font-weight:700">{{ completed|length }}</span>{% endif %}
    </button>
    <button type="button" class="tab-btn" data-tab="tables">&#128202;&nbsp; Data Tables</button>
  </div>

  <!-- TAB: OVERVIEW -->
  <div class="tab-pane{% if vault_files or completed %} active{% endif %}" id="tab-overview">
    <div class="card">
      <div class="card-header">
        <div class="card-title">&#9776; Stage Progress</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:14px">
          <div style="font-size:12px;color:var(--muted)">{{ completed|length }}/{{ all_stages|length }} complete</div>
        </div>
      </div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:12px;display:flex;align-items:center;gap:6px">
        &#9998;&nbsp; Click any completed stage to go back and update it
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:20px">
        {% for s in all_stages %}

        {% if s.id in completed %}
        <form method="post" action="/engagements/{{ engagement_id }}/rerun/{{ s.id }}">
          <button type="submit" style="width:100%;display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:10px;cursor:pointer;text-align:left;background:#F0FDF4;border:2px solid #A7F3D0;transition:all 0.15s;" onmouseover="this.style.background='#DCFCE7';this.style.borderColor='#059669';this.style.transform='translateY(-1px)';this.style.boxShadow='0 4px 12px rgba(5,150,105,0.15)'" onmouseout="this.style.background='#F0FDF4';this.style.borderColor='#A7F3D0';this.style.transform='';this.style.boxShadow=''">
            <span style="width:30px;height:30px;border-radius:50%;background:var(--success);color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;flex-shrink:0">&#10003;</span>
            <span style="flex:1;font-size:13px;font-weight:600;color:var(--navy)">Stage {{ s.id }}: {{ s.custom_name or s.name }}</span>
            <span style="font-size:12px;color:var(--success);font-weight:700;white-space:nowrap;display:flex;align-items:center;gap:5px">
              &#8592; Go Back &amp; Update
            </span>
          </button>
        </form>

        {% elif s.id == current_layer %}
        <div style="display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:10px;background:#EFF6FF;border:2px solid var(--blue);">
          <span style="width:30px;height:30px;border-radius:50%;background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;flex-shrink:0">{{ s.id }}</span>
          <span style="flex:1;font-size:13px;font-weight:700;color:var(--blue)">Stage {{ s.id }}: {{ s.custom_name or s.name }}</span>
          <span style="font-size:10px;background:var(--blue);color:#fff;padding:3px 11px;border-radius:999px;font-weight:700;letter-spacing:1px">UP NEXT</span>
        </div>

        {% else %}
        <div style="display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:10px;background:var(--bg-2);border:1px solid var(--border);opacity:0.55;">
          <span style="width:30px;height:30px;border-radius:50%;background:var(--silver-pale);color:var(--muted);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0">{{ s.id }}</span>
          <span style="font-size:13px;color:var(--muted)">Stage {{ s.id }}: {{ s.custom_name or s.name }}</span>
        </div>
        {% endif %}

        {% endfor %}
      </div>
      {% if current_layer %}
      <div style="background:var(--blue-pale);border:1px solid #BFDBFE;border-radius:9px;padding:16px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
        <div>
          <div style="font-weight:700;color:var(--navy)">Next: Stage {{ current_layer }}</div>
          <div class="muted" style="font-size:12px;margin-top:2px">{{ current_stage_name }}</div>
        </div>
        {% if vault_files|length == 0 and all_stages and current_layer == all_stages[0].id %}
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:7px">
          <button class="btn btn-primary" type="button" disabled style="opacity:0.4;cursor:not-allowed">&#9658;&nbsp; Run Stage {{ current_layer }}</button>
          <div style="font-size:12px;color:var(--muted)">&#9888;&nbsp; <button type="button" onclick="switchTab('vault')" style="background:none;border:none;padding:0;color:var(--blue);cursor:pointer;font-size:12px;text-decoration:underline">Upload files to the Data Vault</button> first</div>
        </div>
        {% else %}
        <form method="post" action="/engagements/{{ engagement_id }}/proceed">
          <button class="btn btn-primary" type="submit">&#9658;&nbsp; Run Stage {{ current_layer }}</button>
        </form>
        {% endif %}
      </div>
      {% else %}
      <div style="background:#F0FDF4;border:1px solid #A7F3D0;border-radius:9px;padding:16px 20px;color:var(--success);font-weight:700;font-size:15px">
        &#10003; All stages complete. Engagement ready for final human review and closure.
      </div>
      {% endif %}
    </div>

    <!-- Breach & regulatory summary -->
    {% if client.summary or client.regulations or client.counsel_engaged %}
    <div class="card">
      <div class="card-header"><div class="card-title">&#128203; Engagement Summary</div></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:22px">
        {% if client.summary %}
        <div>
          <div class="section-title" style="border:none;padding:0;margin-bottom:8px">Incident Summary</div>
          <div style="font-size:13px;color:var(--text);line-height:1.7">{{ client.summary }}</div>
        </div>
        {% endif %}
        <div>
          {% if client.regulations %}
          <div class="section-title" style="border:none;padding:0;margin-bottom:8px">Regulations</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px">
            {% for r in client.regulations %}
            <span class="badge badge-blue">{{ r }}</span>
            {% endfor %}
          </div>
          {% endif %}
          {% if client.data_types %}
          <div class="section-title" style="border:none;padding:0;margin-bottom:8px">Data Types</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px">
            {% for d in client.data_types %}
            <span class="badge badge-warn">{{ d }}</span>
            {% endfor %}
          </div>
          {% endif %}
        </div>
      </div>
      {% if client.counsel_engaged == 'Yes' %}
      <div style="margin-top:16px;padding:10px 16px;background:var(--blue-pale);border-radius:8px;border:1px solid #BFDBFE;font-size:13px;color:var(--navy)">
        &#9878;&nbsp; <strong>Legal counsel engaged</strong>{% if client.law_firm %}: {{ client.law_firm }}{% endif %}
        {% if client.privilege == 'Yes' %} — <span style="color:var(--blue);font-weight:700">Attorney-Client Privilege</span>{% endif %}
      </div>
      {% endif %}
    </div>
    {% endif %}
  </div>

  <!-- TAB: DATA VAULT -->
  <div class="tab-pane{% if not vault_files and not completed %} active{% endif %}" id="tab-vault">
    <!-- Security row -->
    <div class="security-row">
      <div class="sec-badge"><div class="sec-badge-icon">&#128274;</div>SHA-256 Chain of Custody</div>
      <div class="sec-badge"><div class="sec-badge-icon">&#128203;</div>Full Audit Log</div>
      <div class="sec-badge"><div class="sec-badge-icon">&#128196;</div>Stored Locally Only</div>
      <div class="sec-badge"><div class="sec-badge-icon">&#9881;</div>Processed On-Premises</div>
      <div class="sec-badge"><div class="sec-badge-icon">&#128683;</div>Never Transmitted</div>
    </div>

    <!-- Upload zone -->
    <div class="upload-zone" id="upload-zone">
      <input type="file" id="file-input" multiple style="display:none"/>
      <input type="file" id="folder-input" webkitdirectory multiple style="display:none"/>
      <div class="upload-zone-icon">&#128228;</div>
      <div class="upload-zone-title">Drop files or folders here</div>
      <div class="upload-zone-sub">All formats processed automatically — drop a whole folder to ingest everything at once</div>
      <div style="display:flex;gap:10px;justify-content:center;margin-top:14px">
        <button type="button" onclick="document.getElementById('file-input').click()" class="btn btn-secondary" style="font-size:12px;padding:7px 18px">&#128196; Browse Files</button>
        <button type="button" onclick="document.getElementById('folder-input').click()" class="btn btn-secondary" style="font-size:12px;padding:7px 18px">&#128193; Browse Folder</button>
      </div>
      <div class="fmt-grid" style="justify-content:center;margin-top:18px">
        <span class="fmt-chip">PDF</span><span class="fmt-chip">DOCX</span>
        <span class="fmt-chip">XLSX</span><span class="fmt-chip">CSV</span>
        <span class="fmt-chip">JSON</span><span class="fmt-chip">XML</span>
        <span class="fmt-chip">HTML</span><span class="fmt-chip">TXT</span>
        <span class="fmt-chip">JPG</span><span class="fmt-chip">PNG</span>
        <span class="fmt-chip">TIFF</span><span class="fmt-chip">MP4</span>
        <span class="fmt-chip">MOV</span><span class="fmt-chip">AVI</span>
        <span class="fmt-chip" style="background:var(--navy-4)">+more</span>
      </div>
    </div>

    <!-- Field Configuration panel -->
    <div class="card" id="field-config-card" style="margin-top:22px">
      <div class="card-header">
        <div class="card-title">&#128269; What Are You Looking For?</div>
        <div style="margin-left:auto;font-size:12px;color:var(--muted)">Configure before running Stage 1</div>
      </div>

      <!-- Preset categories -->
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:8px">Standard Categories</div>
      <div id="preset-grid" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px">
        <label id="preset-identity" style="display:flex;align-items:center;gap:5px;padding:5px 12px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;user-select:none;transition:all 0.12s">
          <input type="checkbox" value="identity" onchange="togglePreset(this)" style="margin:0"> &#128100; Identity
        </label>
        <label id="preset-financial" style="display:flex;align-items:center;gap:5px;padding:5px 12px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;user-select:none;transition:all 0.12s">
          <input type="checkbox" value="financial" onchange="togglePreset(this)" style="margin:0"> &#128181; Financial
        </label>
        <label id="preset-medical" style="display:flex;align-items:center;gap:5px;padding:5px 12px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;user-select:none;transition:all 0.12s">
          <input type="checkbox" value="medical" onchange="togglePreset(this)" style="margin:0"> &#9877;&#65039; Medical
        </label>
        <label id="preset-credentials" style="display:flex;align-items:center;gap:5px;padding:5px 12px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;user-select:none;transition:all 0.12s">
          <input type="checkbox" value="credentials" onchange="togglePreset(this)" style="margin:0"> &#128274; Credentials
        </label>
        <label id="preset-network" style="display:flex;align-items:center;gap:5px;padding:5px 12px;border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;user-select:none;transition:all 0.12s">
          <input type="checkbox" value="network" onchange="togglePreset(this)" style="margin:0"> &#127760; Network
        </label>
      </div>

      <!-- Custom fields table -->
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:8px">Custom Fields (company-specific)</div>
      <div style="overflow-x:auto">
      <table id="custom-fields-table" style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px">
        <thead>
          <tr style="background:var(--bg-2)">
            <th style="text-align:left;padding:7px 10px;border:1px solid var(--border);font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:0.8px;color:var(--muted)">Field Name</th>
            <th style="text-align:left;padding:7px 10px;border:1px solid var(--border);font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:0.8px;color:var(--muted)">Also look for these column names (comma-separated)</th>
            <th style="text-align:left;padding:7px 10px;border:1px solid var(--border);font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:0.8px;color:var(--muted)">Sensitivity</th>
            <th style="width:36px;border:1px solid var(--border)"></th>
          </tr>
        </thead>
        <tbody id="custom-fields-body"></tbody>
      </table>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="addCustomField()" style="margin-bottom:14px">+ Add Custom Field</button>

      <!-- Auto-discover toggle -->
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <input type="checkbox" id="auto-discover-toggle" checked style="width:15px;height:15px">
        <label for="auto-discover-toggle" style="font-size:13px;cursor:pointer;font-weight:500">
          Also auto-discover all additional fields found in the data
        </label>
      </div>

      <div style="display:flex;gap:10px;align-items:center">
        <button class="btn btn-primary btn-sm" onclick="saveFieldConfig()">&#10003; Save Configuration</button>
        <span id="field-config-status" style="font-size:12px;color:var(--muted)"></span>
      </div>
    </div>

    <!-- Files table -->
    <div class="card" style="padding:0;overflow:hidden;margin-top:22px">
      <div style="padding:18px 24px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--silver-pale)">
        <div class="card-title" style="border:none;padding:0;margin:0">&#128190; Ingested Evidence Files</div>
        <div class="muted" style="font-size:12px" id="file-count">{{ vault_files|length }} file{{ 's' if vault_files|length != 1 else '' }}</div>
      </div>
      {% if vault_files or True %}
      <table>
        <thead>
          <tr>
            <th style="width:36px"></th>
            <th>File</th>
            <th style="width:90px">Size</th>
            <th style="width:130px">Type</th>
            <th style="width:160px">Extraction</th>
            <th style="width:100px">Text</th>
          </tr>
        </thead>
        <tbody id="files-tbody">
          {% for f in vault_files %}
          <tr>
            <td style="text-align:center;font-size:18px">{{ f.icon }}</td>
            <td>
              <div style="font-weight:600;color:var(--navy)">{{ f.original_name }}</div>
              <div style="font-size:10px;font-family:monospace;color:var(--silver);margin-top:2px">{{ f.sha256[:20] }}...</div>
            </td>
            <td class="muted" style="font-size:12px">{{ f.size_label }}</td>
            <td><span class="muted" style="font-size:12px">{{ f.type_label }}</span></td>
            <td>
              {% if f.error %}
              <span class="proc-err">&#9888; {{ f.error[:40] }}</span>
              {% else %}
              <span class="proc-ok">&#10003; {{ f.method }}</span>
              {% endif %}
            </td>
            <td>
              {% if not f.error %}
              <a href="/engagements/{{ engagement_id }}/files/{{ f.filename }}/text" class="plain" target="_blank" style="font-size:12px">View &rarr;</a>
              {% else %}
              <span class="muted" style="font-size:12px">—</span>
              {% endif %}
            </td>
          </tr>
          {% else %}
          <tr id="empty-row">
            <td colspan="6" style="text-align:center;padding:44px 0;color:var(--muted)">
              <div style="font-size:36px;margin-bottom:10px">&#128228;</div>
              <div style="font-weight:700;color:var(--navy)">No files uploaded yet</div>
              <div class="muted" style="margin-top:4px">Drop evidence files above to begin ingestion</div>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% endif %}
    </div>
  </div>

  <!-- TAB: RUNBOOK ANALYSIS -->
  <div class="tab-pane" id="tab-runbook">

    {% if not completed %}
    <div class="card" style="text-align:center;padding:48px 24px;color:var(--muted)">
      <div style="font-size:40px;margin-bottom:12px">&#9989;</div>
      <div style="font-weight:700;color:var(--navy);font-size:16px">No stages completed yet</div>
      <div style="margin-top:6px;font-size:13px">Run the first stage from the Overview tab to see analysis results here.</div>
    </div>
    {% endif %}

    <!-- STAGE 1: DATA INTAKE -->
    {% if "1" in completed and rb_ingest %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#128229; Stage 1 — Data Intake</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span class="badge badge-blue">Complete</span>
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/1" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:4px">
        <div class="stat-card">
          <div class="stat-icon">&#128193;</div>
          <div class="stat-num">{{ rb_ingest.get("file_count", rb_ingest.get("source","—")) }}</div>
          <div class="stat-label">{{ "Files Ingested" if rb_ingest.get("file_count") else "Source" }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">&#128203;</div>
          <div class="stat-num">{{ rb_ingest.get("record_count", "—") }}</div>
          <div class="stat-label">Records Extracted</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">{{ "&#128274;" if rb_ingest.get("source")=="vault" else "&#128196;" }}</div>
          <div class="stat-num" style="font-size:18px;text-transform:capitalize">{{ rb_ingest.get("source","—") }}</div>
          <div class="stat-label">Data Source</div>
        </div>
      </div>
      {% if rb_ingest.get("files") %}
      <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:6px">
        {% for fname in rb_ingest.files %}
        <span class="badge" style="background:var(--silver-pale);color:var(--navy);font-weight:600;font-size:11px">{{ fname }}</span>
        {% endfor %}
      </div>
      {% endif %}
    </div>
    {% endif %}

    <!-- STAGE 2: PII DETECTION -->
    {% if "2" in completed and rb_norm_stats %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#128269; Stage 2 — PII Detection &amp; Normalization</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span class="badge badge-blue">Complete</span>
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/2" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:10px">
        <div class="stat-card">
          <div class="stat-icon">&#128203;</div>
          <div class="stat-num">{{ rb_norm_stats.get("records_processed","—") }}</div>
          <div class="stat-label">Records Processed</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">&#9888;</div>
          <div class="stat-num" style="color:var(--danger)">{{ rb_norm_stats.get("total_pii_hits","—") }}</div>
          <div class="stat-label">PII Hits Detected</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">&#128272;</div>
          <div class="stat-num">{{ rb_pii_kinds|length }}</div>
          <div class="stat-label">PII Types Found</div>
        </div>
      </div>
      {% if rb_pii_kinds %}
      <div style="display:flex;flex-wrap:wrap;gap:6px">
        {% for kind in rb_pii_kinds %}
        <span class="badge badge-warn">{{ kind }}</span>
        {% endfor %}
      </div>
      {% endif %}

      {# ── Secrets Scan Results ── #}
      {% set ss = rb_secrets_scan %}
      {% if ss %}
      <div style="margin-top:18px;border-top:1px solid var(--border);padding-top:14px">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
          <span style="font-weight:700;font-size:13px;color:var(--text)">&#128272; Secrets Scan</span>
          {% if ss.get("method") == "trufflehog" %}
          <span class="badge badge-blue" style="font-size:10px">TruffleHog</span>
          {% else %}
          <span class="badge" style="font-size:10px;background:#f5f5f5;color:#666;border:1px solid #ddd">Regex Engine</span>
          {% endif %}
          {% if ss.get("total_findings", 0) == 0 %}
          <span class="badge" style="background:#d1fae5;color:#065f46;font-size:11px">&#10003; No secrets found</span>
          {% else %}
          <span class="badge badge-danger" style="font-size:11px">{{ ss.get("total_findings") }} finding{{ "s" if ss.get("total_findings") != 1 else "" }}</span>
          {% endif %}
        </div>

        {% if ss.get("total_findings", 0) > 0 %}
        {# Severity summary pills #}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
          {% if ss.get("critical_count", 0) %}
          <span style="background:#fee2e2;color:#991b1b;border-radius:4px;padding:3px 10px;font-size:12px;font-weight:600">
            &#9888; {{ ss.critical_count }} Critical
          </span>
          {% endif %}
          {% if ss.get("high_count", 0) %}
          <span style="background:#fff7ed;color:#9a3412;border-radius:4px;padding:3px 10px;font-size:12px;font-weight:600">
            &#9650; {{ ss.high_count }} High
          </span>
          {% endif %}
          {% if ss.get("medium_count", 0) %}
          <span style="background:#fef9c3;color:#854d0e;border-radius:4px;padding:3px 10px;font-size:12px;font-weight:600">
            &#9679; {{ ss.get("medium_count", 0) }} Medium
          </span>
          {% endif %}
        </div>

        {# Findings table — no raw values shown, only hashes #}
        <div style="overflow-x:auto">
        <table style="font-size:12px;margin-bottom:0">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Secret Type</th>
              <th>File</th>
              <th>Line</th>
              <th>Hash (SHA-256 prefix)</th>
            </tr>
          </thead>
          <tbody>
          {% for f in ss.get("findings", [])[:50] %}
          <tr>
            <td>
              {% if f.severity == "critical" %}
              <span style="color:#dc2626;font-weight:700">&#9888; CRITICAL</span>
              {% elif f.severity == "high" %}
              <span style="color:#ea580c;font-weight:600">&#9650; HIGH</span>
              {% elif f.severity == "medium" %}
              <span style="color:#d97706;font-weight:600">&#9679; MEDIUM</span>
              {% else %}
              <span style="color:#6b7280">{{ f.severity|upper }}</span>
              {% endif %}
            </td>
            <td style="font-weight:500">{{ f.detector }}</td>
            <td style="color:var(--text-muted);font-family:monospace;font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ f.get('original_name', f.source_file) }}">{{ f.get("original_name", f.source_file) }}</td>
            <td style="font-family:monospace;text-align:right">{{ f.line }}</td>
            <td style="font-family:monospace;color:var(--text-muted);font-size:11px">{{ f.secret_hash }}…</td>
          </tr>
          {% endfor %}
          {% if ss.get("findings", [])|length > 50 %}
          <tr><td colspan="5" style="text-align:center;color:var(--text-muted);font-size:11px">… and {{ ss.get("findings",[])|length - 50 }} more findings</td></tr>
          {% endif %}
          </tbody>
        </table>
        </div>
        <p style="font-size:11px;color:var(--text-muted);margin-top:8px">
          &#128274; Raw secret values are never stored. Hashes shown for deduplication only.
          Remediate all findings before closing this engagement.
        </p>
        {% else %}
        <p style="font-size:13px;color:#065f46;margin:0">
          &#10003; No exposed secrets detected in {{ ss.get("files_scanned", [])|length }} file{{ "s" if ss.get("files_scanned", [])|length != 1 else "" }} scanned.
        </p>
        {% endif %}
      </div>
      {% endif %}

      {# ── Additional Scanner Results ── #}
      {% if rb_plugin_results %}
      <div style="margin-top:16px;border-top:1px solid var(--border);padding-top:14px">
        <div style="font-weight:700;font-size:13px;margin-bottom:10px">Additional Scanner Results</div>
        {% for pid, result in rb_plugin_results.items() %}
        <details style="margin-bottom:8px;border:1px solid var(--border);border-radius:8px;overflow:hidden">
          <summary style="cursor:pointer;padding:10px 14px;background:var(--bg-2);display:flex;align-items:center;gap:10px;list-style:none">
            <span style="font-weight:600;flex:1;font-size:13px">{{ result.get("scanner_name", pid) }}</span>
            {% set tot = result.get("total_findings", 0) %}
            {% if result.get("critical_count", 0) %}
            <span style="background:#fee2e2;color:#991b1b;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600">&#9888; {{ result.critical_count }} Critical</span>
            {% endif %}
            {% if result.get("high_count", 0) %}
            <span style="background:#fff7ed;color:#9a3412;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600">&#9650; {{ result.high_count }} High</span>
            {% endif %}
            {% if result.get("medium_count", 0) %}
            <span style="background:#fef9c3;color:#854d0e;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600">&#9679; {{ result.get("medium_count",0) }} Medium</span>
            {% endif %}
            {% if tot == 0 %}
            <span style="background:#d1fae5;color:#065f46;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600">&#10003; Clean</span>
            {% else %}
            <span style="background:#fee2e2;color:#991b1b;border-radius:999px;padding:2px 10px;font-size:11px;font-weight:700">{{ tot }} finding{{ "s" if tot != 1 else "" }}</span>
            {% endif %}
          </summary>
          <div style="padding:12px 14px">
            {% if tot > 0 %}
            <div style="overflow-x:auto">
            <table style="font-size:12px;margin-bottom:0">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Type</th>
                  <th>File</th>
                  <th>Line</th>
                  <th>Hash (SHA-256 prefix)</th>
                </tr>
              </thead>
              <tbody>
              {% for f in result.get("findings", [])[:50] %}
              <tr>
                <td>
                  {% if f.severity == "critical" %}
                  <span style="color:#dc2626;font-weight:700">&#9888; CRITICAL</span>
                  {% elif f.severity == "high" %}
                  <span style="color:#ea580c;font-weight:600">&#9650; HIGH</span>
                  {% elif f.severity == "medium" %}
                  <span style="color:#d97706;font-weight:600">&#9679; MEDIUM</span>
                  {% else %}
                  <span style="color:#6b7280">{{ f.severity|upper }}</span>
                  {% endif %}
                </td>
                <td style="font-weight:500">{{ f.detector }}</td>
                <td style="color:var(--muted);font-family:monospace;font-size:11px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ f.get('original_name', f.source_file) }}">{{ f.get("original_name", f.source_file) }}</td>
                <td style="font-family:monospace;text-align:right">{{ f.line }}</td>
                <td style="font-family:monospace;color:var(--muted);font-size:11px">{{ f.secret_hash }}…</td>
              </tr>
              {% endfor %}
              {% if result.get("findings", [])|length > 50 %}
              <tr><td colspan="5" style="text-align:center;color:var(--muted);font-size:11px">… and {{ result.get("findings",[])|length - 50 }} more findings</td></tr>
              {% endif %}
              </tbody>
            </table>
            </div>
            <p style="font-size:11px;color:var(--muted);margin-top:8px">
              &#128274; Raw values are never stored. Hashes shown for deduplication only.
            </p>
            {% else %}
            <p style="font-size:13px;color:#065f46;margin:0">
              &#10003; No findings in {{ result.get("files_scanned", [])|length }} file{{ "s" if result.get("files_scanned",[])|length != 1 else "" }} scanned.
            </p>
            {% endif %}
          </div>
        </details>
        {% endfor %}
      </div>
      {% endif %}

    </div>
    {% endif %}

    <!-- STAGE 3: SENSITIVITY CLASSIFICATION -->
    {% if "3" in completed and rb_sensitivity %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#127777; Stage 3 — Sensitivity Classification</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span class="badge badge-blue">Complete</span>
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/3" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      <table style="margin-bottom:10px">
        <thead><tr><th>Tier</th><th>Records</th></tr></thead>
        <tbody>
        {% for tier, cnt in rb_sensitivity.items() %}
        <tr>
          <td>
            {% if "PHI" in tier %}<span class="badge" style="background:#FEE2E2;color:#991B1B">{{ tier }}</span>
            {% elif "PCI" in tier %}<span class="badge" style="background:#FEF3C7;color:#92400E">{{ tier }}</span>
            {% elif "Credentials" in tier %}<span class="badge" style="background:#F3E8FF;color:#6B21A8">{{ tier }}</span>
            {% else %}<span class="badge badge-blue">{{ tier }}</span>{% endif %}
          </td>
          <td style="font-weight:700;color:var(--navy)">{{ cnt }}</td>
        </tr>
        {% endfor %}
        </tbody>
      </table>
      {% if rb_applicable_laws %}
      <div style="margin-top:6px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px">Applicable Laws Detected</div>
        <div style="display:flex;flex-wrap:wrap;gap:6px">
          {% for law in rb_applicable_laws %}
          <span class="badge" style="background:var(--danger-bg);color:var(--danger);font-weight:700">{{ law }}</span>
          {% endfor %}
        </div>
      </div>
      {% endif %}
    </div>
    {% endif %}

    <!-- STAGE 4: AFFECTED PEOPLE -->
    {% if "4" in completed %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#128101; Stage 4 — Entity Resolution</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span class="badge badge-blue">Complete</span>
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/4" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      {% if rb_entity_resolution %}
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px">
        <div class="stat-card">
          <div class="stat-num">{{ rb_entity_resolution.get("total_records","—") }}</div>
          <div class="stat-label">Total Records</div>
        </div>
        <div class="stat-card">
          <div class="stat-num" style="color:var(--danger)">{{ rb_entity_resolution.get("unique_affected_people","—") }}</div>
          <div class="stat-label">Unique Individuals</div>
        </div>
        <div class="stat-card">
          <div class="stat-num" style="color:var(--warning)">{{ rb_entity_resolution.get("duplicate_records_merged","—") }}</div>
          <div class="stat-label">Duplicate Records Merged</div>
        </div>
        <div class="stat-card">
          <div class="stat-num" style="color:var(--blue)">{{ rb_entity_resolution.get("cross_file_matches","—") }}</div>
          <div class="stat-label">Cross-File Matches</div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:14px">
        Dedup method: <strong>person_key</strong> &nbsp;·&nbsp;
        {{ rb_entity_resolution.get("records_without_identity",0) }} records had no identity anchor
      </div>
      {% endif %}
      {% if rb_affected %}
      <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Name</th><th>Email</th><th>SSN</th><th>DOB</th><th>CC</th><th>MRN</th><th>Files</th><th>Records</th><th>Confidence</th></tr></thead>
        <tbody>
        {% for p in rb_affected %}
        <tr>
          <td style="font-weight:600">{{ p.name or "—" }}</td>
          <td style="font-family:monospace;font-size:12px">{{ p.email or "—" }}</td>
          <td style="text-align:center">{{ "&#9888;" if p.ssn else "—" }}</td>
          <td style="text-align:center">{{ "&#10003;" if p.dob else "—" }}</td>
          <td style="text-align:center">{{ "&#9888;" if p.cc else "—" }}</td>
          <td style="text-align:center">{{ "&#10003;" if p.mrn else "—" }}</td>
          <td style="font-size:11px;color:var(--muted)">
            {{ p.source_files | join(", ") if p.source_files else (p.get("source","") or "—") }}
            {% if p.cross_file %}<span class="badge badge-blue" style="font-size:10px;margin-left:4px">cross-file</span>{% endif %}
          </td>
          <td style="text-align:center;font-size:12px">{{ p.record_count or 1 }}</td>
          <td style="font-size:11px">
            <span class="badge {% if p.confidence == 'high' %}badge-red{% elif p.confidence == 'medium' %}badge-yellow{% else %}badge-muted{% endif %}">{{ p.confidence or "—" }}</span>
          </td>
        </tr>
        {% endfor %}
        </tbody>
      </table>
      </div>
      {% endif %}
    </div>
    {% endif %}

    <!-- STAGE 5: IMPACT ASSESSMENT -->
    {% if "5" in completed and rb_impact %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#128200; Stage 5 — Impact Assessment</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span class="badge badge-blue">Complete</span>
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/5" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px">
        <div class="stat-card">
          <div class="stat-icon">&#128101;</div>
          <div class="stat-num" style="color:var(--danger)">{{ rb_impact.get("affected_count","—") }}</div>
          <div class="stat-label">Affected Individuals</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">&#128196;</div>
          <div class="stat-num">{{ rb_impact.get("affected_with_ssn","—") }}</div>
          <div class="stat-label">With SSN</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">&#127973;</div>
          <div class="stat-num">{{ rb_impact.get("affected_with_health","—") }}</div>
          <div class="stat-label">With Health Data</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">&#128181;</div>
          <div class="stat-num">{{ rb_impact.get("affected_with_financial","—") }}</div>
          <div class="stat-label">With Financial Data</div>
        </div>
      </div>
      {% if rb_impact.get("estimated_regulatory_exposure") %}
      <div style="background:var(--warn-bg);border:1px solid #FCD34D;border-radius:8px;padding:12px 18px;display:flex;align-items:center;gap:12px">
        <div style="font-size:22px">&#128181;</div>
        <div>
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--warn);margin-bottom:2px">Estimated Regulatory Exposure</div>
          <div style="font-weight:700;color:var(--navy)">{{ rb_impact.estimated_regulatory_exposure }}</div>
        </div>
      </div>
      {% endif %}
      {% if rb_impact.get("jurisdictions") and rb_impact.jurisdictions != "Unknown" %}
      <div style="margin-top:10px;font-size:13px;color:var(--muted)"><strong>Jurisdictions:</strong> {{ rb_impact.jurisdictions }}</div>
      {% endif %}
    </div>
    {% endif %}

    <!-- STAGE 6: REGULATORY TRIGGERS -->
    {% if "6" in completed and rb_triggers %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#9878; Stage 6 — Regulatory Triggers</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          {% if rb_legal.get("notification_required") %}
          <span class="badge" style="background:var(--danger-bg);color:var(--danger);font-weight:700">&#9888; Notification Required</span>
          {% else %}
          <span class="badge badge-blue">Complete</span>
          {% endif %}
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/6" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      <table style="margin-bottom:10px">
        <thead><tr><th>Law</th><th>Triggered</th><th>Deadline</th><th>Notes</th></tr></thead>
        <tbody>
        {% for t in rb_triggers %}
        <tr>
          <td><span class="badge" style="{{ 'background:var(--danger-bg);color:var(--danger)' if t.triggered else 'background:var(--silver-pale);color:var(--muted)' }}">{{ t.law }}</span></td>
          <td style="font-weight:700;color:{{ 'var(--danger)' if t.triggered else 'var(--success)' }}">{{ "YES" if t.triggered else "No" }}</td>
          <td style="font-size:12px;color:var(--navy)">{{ t.deadline or "—" }}</td>
          <td style="font-size:11px;color:var(--muted)">{{ t.notes or "—" }}</td>
        </tr>
        {% endfor %}
        </tbody>
      </table>
      {% if rb_legal.get("earliest_deadline") %}
      <div style="background:var(--danger-bg);border:1px solid #FECACA;border-radius:8px;padding:10px 16px;font-size:13px">
        <strong style="color:var(--danger)">Earliest Deadline:</strong>
        <span style="color:var(--navy);font-weight:700;margin-left:6px">{{ rb_legal.earliest_deadline }}</span>
        <span style="color:var(--muted);font-size:11px;margin-left:8px">— Verify with qualified legal counsel</span>
      </div>
      {% endif %}
    </div>
    {% endif %}

    <!-- STAGE 7: NOTIFICATION DRAFT -->
    {% if "7" in completed %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#128140; Stage 7 — Notification Preparation</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span class="badge badge-blue">Complete</span>
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/7" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <div class="stat-card" style="flex:1;max-width:200px">
          <div class="stat-icon">&#128101;</div>
          <div class="stat-num">{{ rb_notif_queue_count }}</div>
          <div class="stat-label">Notifications Queued</div>
        </div>
        <div style="flex:1;padding:12px 16px;background:var(--warn-bg);border:1px solid #FCD34D;border-radius:8px;font-size:12px;color:var(--warn);font-weight:600">
          &#9888; Draft only — no notifications sent. Requires legal review before distribution.
        </div>
      </div>
      {% if rb_notif_draft %}
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px">Draft Notification Preview</div>
      <pre style="max-height:220px;overflow-y:auto;font-size:11px;background:var(--bg-2);border:1px solid var(--border);border-radius:8px;padding:14px">{{ rb_notif_draft[:1200] }}{% if rb_notif_draft|length > 1200 %}&#8230;{% endif %}</pre>
      {% endif %}
    </div>
    {% endif %}

    <!-- STAGE 8: REVIEW PACK -->
    {% if "8" in completed %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#128230; Stage 8 — Review Pack Generated</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span class="badge" style="background:var(--success-bg);color:var(--success);font-weight:700">&#10003; Ready for Review</span>
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/8" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px">
        {% if rb_review_pack_html %}
        <a href="/exports/{{ engagement_id }}/html" class="btn btn-primary" target="_blank">&#128196; Open HTML Report</a>
        {% endif %}
        {% if rb_review_pack_json %}
        <a href="/exports/{{ engagement_id }}/json" class="btn" style="border:1px solid var(--border)" target="_blank">&#128190; Download JSON Pack</a>
        {% endif %}
      </div>
      <div style="font-size:12px;color:var(--muted)">&#9888; HTML report is print-to-PDF friendly. Open in browser, then File &rarr; Print &rarr; Save as PDF.</div>
    </div>
    {% endif %}

    <!-- STAGE 9: DISCLOSURE CHECKLIST -->
    {% if "9" in completed and rb_disclosure_checklist %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#9989; Stage 9 — Disclosure Checklist</div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
          <span class="badge" style="background:var(--warn-bg);color:var(--warn);font-weight:700">&#128336; Awaiting Approval</span>
          <form method="post" action="/engagements/{{ engagement_id }}/rerun/9" style="display:inline">
            <button class="btn" style="font-size:11px;padding:4px 12px;border:1px solid var(--border)">&#8635; Re-run</button>
          </form>
        </div>
      </div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:12px">All items require human confirmation before engagement closure.</div>
      <div style="display:flex;flex-direction:column;gap:8px">
        {% for item in rb_disclosure_checklist %}
        <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:{{ 'var(--success-bg)' if item.complete else 'var(--bg-2)' }};border:1px solid {{ '#A7F3D0' if item.complete else 'var(--border)' }};border-radius:8px">
          <div style="width:20px;height:20px;border-radius:4px;border:2px solid {{ 'var(--success)' if item.complete else 'var(--silver)' }};display:flex;align-items:center;justify-content:center;flex-shrink:0">
            {% if item.complete %}<span style="color:var(--success);font-size:13px;font-weight:700">&#10003;</span>{% endif %}
          </div>
          <span style="font-size:13px;color:var(--navy)">{{ item.item }}</span>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endif %}

    <!-- RAW JSON TOGGLE -->
    {% if completed %}
    <div style="margin-top:10px">
      <button class="btn" style="font-size:11px;padding:5px 14px;border:1px solid var(--border);background:transparent;color:var(--muted)" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none';this.textContent=this.textContent.includes('Show')?'Hide Raw JSON':'Show Raw JSON'">Show Raw JSON</button>
      <div style="display:none;margin-top:10px">
        <div class="card">
          <div class="card-header"><div class="card-title">&#128196; Raw Runbook JSON</div></div>
          <pre style="font-size:11px;max-height:500px;overflow-y:auto">{{ runbook_json }}</pre>
        </div>
      </div>
    </div>
    {% endif %}

  </div>

  <!-- TAB: DATA TABLES -->
  <div class="tab-pane" id="tab-tables">

    <div style="display:grid;grid-template-columns:260px 1fr;gap:18px;align-items:flex-start">

      <!-- ── Left sidebar: Medallion Schema Browser ── -->
      <div>

        <!-- Layer tabs -->
        <div class="card" style="padding:0;overflow:hidden;margin-bottom:12px">
          <div style="padding:0;background:var(--navy);display:flex">
            <button id="layer-tab-bronze" onclick="switchLayer('bronze')" style="flex:1;padding:10px 4px;border:none;border-bottom:2px solid #cd7f32;background:rgba(205,127,50,0.18);color:#cd7f32;font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;cursor:pointer">&#129483; Bronze</button>
            <button id="layer-tab-silver" onclick="switchLayer('silver')" style="flex:1;padding:10px 4px;border:none;border-bottom:2px solid transparent;background:transparent;color:var(--silver);font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;cursor:pointer">&#129688; Silver</button>
            <button id="layer-tab-gold" onclick="switchLayer('gold')" style="flex:1;padding:10px 4px;border:none;border-bottom:2px solid transparent;background:transparent;color:var(--silver);font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;cursor:pointer">&#129351; Gold</button>
          </div>
          <div id="schema-panel-bronze" style="padding:10px 12px;font-family:monospace;font-size:11px">
            <div id="schema-bronze-content" style="color:var(--muted);font-style:italic;font-size:10px">Loading&hellip;</div>
          </div>
          <div id="schema-panel-silver" style="display:none;padding:10px 12px;font-family:monospace;font-size:11px">
            <div id="schema-silver-content" style="color:var(--muted);font-style:italic;font-size:10px">Loading&hellip;</div>
          </div>
          <div id="schema-panel-gold" style="display:none;padding:10px 12px;font-family:monospace;font-size:11px">
            <div id="schema-gold-content" style="color:var(--muted);font-style:italic;font-size:10px">Loading&hellip;</div>
          </div>
          <div style="padding:6px 12px 10px;background:var(--bg-2);border-top:1px solid var(--border);font-size:9px;color:var(--muted)">&#9654; Click a table name to query it</div>
        </div>

        <!-- Legacy rename panel (hidden by default) -->
        <div id="alias-panel" style="display:none">
          <div class="card" style="padding:0;overflow:hidden">
            <div style="padding:11px 16px;background:var(--navy)">
              <span style="font-size:10px;font-weight:800;letter-spacing:1.5px;color:var(--silver-2);text-transform:uppercase">Rename Tables</span>
            </div>
            <div style="padding:14px 16px">
              <div class="form-group"><label>Records table</label><input type="text" id="alias-records" placeholder="records" style="font-family:monospace"/></div>
              <div class="form-group"><label>Affected people table</label><input type="text" id="alias-affected" placeholder="affected_people" style="font-family:monospace"/></div>
              <div class="form-group"><label>PII detections table</label><input type="text" id="alias-pii" placeholder="pii_detections" style="font-family:monospace"/></div>
              <div class="form-group" style="margin-bottom:14px"><label>Regulatory triggers table</label><input type="text" id="alias-reg" placeholder="regulatory_triggers" style="font-family:monospace"/></div>
              <button class="btn btn-primary btn-sm" style="width:100%" onclick="saveAliases()">&#10003; Save Names</button>
            </div>
          </div>
        </div>

      </div>

      <!-- ── Right: query area ── -->
      <div>

        <!-- Quick search -->
        <div class="card" style="padding:16px 20px;margin-bottom:14px">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:10px">&#128269; Quick Search</div>
          <div style="display:flex;gap:8px">
            <input type="text" id="qs-text" placeholder="Type any value to search for..." style="flex:3" onkeydown="if(event.key==='Enter')runQuickSearch()"/>
            <select id="qs-table" style="flex:1;min-width:130px">
              <option value="records" id="qs-opt-records">records</option>
              <option value="affected_people" id="qs-opt-affected">affected_people</option>
              <option value="pii_detections" id="qs-opt-pii">pii_detections</option>
              <option value="regulatory_triggers" id="qs-opt-reg">regulatory_triggers</option>
            </select>
            <button class="btn btn-secondary" onclick="runQuickSearch()">Search</button>
          </div>
        </div>

        <!-- Preset queries -->
        <div style="margin-bottom:14px">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:8px">Preset Queries</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px">
            <span style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;align-self:center;letter-spacing:0.8px">&#129483; Bronze</span>
            <button class="btn btn-secondary btn-sm" onclick="setMedallionPreset('bronze_preview')">Preview Source</button>
            <span style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;align-self:center;letter-spacing:0.8px">&#129688; Silver</span>
            <button class="btn btn-secondary btn-sm" onclick="setMedallionPreset('silver_all')">All Silver</button>
            <button class="btn btn-secondary btn-sm" onclick="setMedallionPreset('silver_high_risk')">High Risk</button>
            <button class="btn btn-secondary btn-sm" onclick="setMedallionPreset('silver_people')">People</button>
            <span style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;align-self:center;letter-spacing:0.8px">&#129351; Gold</span>
            <button class="btn btn-secondary btn-sm" onclick="setMedallionPreset('gold_affected')">Affected People</button>
            <button class="btn btn-secondary btn-sm" onclick="setMedallionPreset('gold_summary')">Exposure Summary</button>
            <button class="btn btn-secondary btn-sm" onclick="setMedallionPreset('gold_by_field')">PII by Field</button>
            <button class="btn btn-secondary btn-sm" onclick="setMedallionPreset('gold_file_risk')">File Risk</button>
            <span style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;align-self:center;letter-spacing:0.8px">&#x25B8; Legacy</span>
            <button class="btn btn-secondary btn-sm" onclick="setPreset('all')">Records</button>
            <button class="btn btn-secondary btn-sm" onclick="setPreset('all_people')">Affected</button>
            <button class="btn btn-secondary btn-sm" onclick="setPreset('regulatory')">Regulatory</button>
          </div>
        </div>

        <!-- SQL editor -->
        <div class="card" style="padding:0;overflow:hidden;margin-bottom:14px">
          <div style="padding:10px 16px;background:var(--navy);display:flex;align-items:center;gap:8px">
            <span style="font-size:10px;font-weight:800;letter-spacing:1.5px;color:var(--silver-2);text-transform:uppercase">SQL Editor</span>
            <button onclick="copySQL()" style="margin-left:auto;background:rgba(255,255,255,0.07);border:1px solid var(--navy-3);color:var(--silver-2);font-size:11px;padding:3px 10px;border-radius:5px;cursor:pointer">&#128203; Copy</button>
          </div>
          <div style="padding:0">
            <textarea id="sql-input" rows="5" spellcheck="false" style="width:100%;font-family:'Courier New',monospace;font-size:12px;line-height:1.75;resize:vertical;background:var(--navy);color:#93C5FD;border:none;border-bottom:1px solid var(--navy-3);padding:14px 16px;outline:none">SELECT * FROM silver LIMIT 100;</textarea>
            <div style="padding:12px 16px;background:var(--bg-2);border-bottom:1px solid var(--border)">
              <label style="margin-bottom:5px">Query Note <span style="font-weight:400;text-transform:none;font-size:11px">(describe what this search is looking for)</span></label>
              <input type="text" id="query-note" placeholder="e.g. Identifying records with SSNs to assess notification scope..."/>
            </div>
            <div style="padding:12px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
              <button class="btn btn-primary" id="run-query-btn" onclick="runSqlQuery()">&#9654;&nbsp; Run Query</button>
              <button class="btn btn-secondary" id="csv-btn" onclick="downloadCSV()" style="display:none">&#11015; Export CSV</button>
              <span id="query-status" style="font-size:12px;color:var(--muted)"></span>
            </div>
          </div>
        </div>

        <!-- Results -->
        <div id="query-result"></div>

      </div>
    </div>
  </div>

  <div class="disclaimer">{{ disclaimer }}</div>
</div>
</div>
<script>
// ── Tabs ──
function switchTab(name) {
  document.querySelectorAll('#main-tab-bar .tab-btn').forEach(function(b) {
    if (b.dataset.tab === name) b.classList.add('active');
    else b.classList.remove('active');
  });
  document.querySelectorAll('.tab-pane').forEach(function(p) {
    if (p.id === 'tab-' + name) p.classList.add('active');
    else p.classList.remove('active');
  });
  window.scrollTo(0, 0);
}
// Attach tab clicks via event delegation (avoids inline onclick issues)
document.getElementById('main-tab-bar').addEventListener('click', function(e) {
  var btn = e.target.closest('[data-tab]');
  if (btn) switchTab(btn.dataset.tab);
});

// ── SQL Table Viewer ──
const _EID = document.body.dataset.incidentId || '';
let _lastCols = [], _lastRows = [], _sortCol = -1, _sortDir = 1;
let _aliases = { records: 'records', affected_people: 'affected_people', pii_detections: 'pii_detections', regulatory_triggers: 'regulatory_triggers' };

// Load saved aliases from server on page load
(function loadAliases(){
  if (!_EID) return;
  fetch('/engagements/' + _EID + '/table-aliases')
    .then(r => r.ok ? r.json() : null)
    .then(d => { if (d && d.aliases) applyAliases(d.aliases); })
    .catch(() => {});
})();

function applyAliases(a) {
  _aliases = Object.assign(_aliases, a);
  ['records','affected_people','pii_detections','regulatory_triggers'].forEach(k => {
    const alias = _aliases[k] || k;
    const lbl = document.getElementById('lbl-' + (k === 'affected_people' ? 'affected' : k === 'pii_detections' ? 'pii' : k === 'regulatory_triggers' ? 'reg' : 'records'));
    if (lbl) lbl.textContent = alias;
    const inp = document.getElementById('alias-' + (k === 'affected_people' ? 'affected' : k === 'pii_detections' ? 'pii' : k === 'regulatory_triggers' ? 'reg' : 'records'));
    if (inp) inp.value = alias !== k ? alias : '';
    const opt = document.getElementById('qs-opt-' + (k === 'affected_people' ? 'affected' : k === 'pii_detections' ? 'pii' : k === 'regulatory_triggers' ? 'reg' : 'records'));
    if (opt) { opt.value = alias; opt.textContent = alias; }
  });
}

function toggleAliases() {
  const p = document.getElementById('alias-panel');
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
}

function saveAliases() {
  const body = {
    records: document.getElementById('alias-records').value.trim() || 'records',
    affected_people: document.getElementById('alias-affected').value.trim() || 'affected_people',
    pii_detections: document.getElementById('alias-pii').value.trim() || 'pii_detections',
    regulatory_triggers: document.getElementById('alias-reg').value.trim() || 'regulatory_triggers',
  };
  fetch('/engagements/' + _EID + '/table-aliases', {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
  }).then(r => r.json()).then(d => {
    if (d.ok) { applyAliases(d.aliases); toggleAliases(); }
  });
}

function useTable(aliasKey) {
  const tbl = aliasKey === 'records_alias' ? (_aliases.records||'records')
    : aliasKey === 'affected_alias' ? (_aliases.affected_people||'affected_people')
    : aliasKey === 'pii_alias' ? (_aliases.pii_detections||'pii_detections')
    : (_aliases.regulatory_triggers||'regulatory_triggers');
  document.getElementById('sql-input').value = 'SELECT * FROM "' + tbl + '" LIMIT 100;';
}

function getAlias(key) { return _aliases[key] || key; }

const _PRESETS = {
  all: () => `SELECT record_id, source_file, name, email, has_ssn, has_dob, has_mrn, sensitivity_tier\nFROM "${getAlias('records')}"\nORDER BY source_file;`,
  ssn: () => `SELECT record_id, source_file, name, email, has_ssn, has_dob, sensitivity_tier\nFROM "${getAlias('records')}"\nWHERE has_ssn = 1\nORDER BY name;`,
  health: () => `SELECT record_id, source_file, name, email, has_mrn, has_dob, diagnosis\nFROM "${getAlias('records')}"\nWHERE has_mrn = 1 OR has_dob = 1\nORDER BY name;`,
  financial: () => `SELECT record_id, source_file, name, email, has_cc, has_account, has_routing\nFROM "${getAlias('records')}"\nWHERE has_cc = 1 OR has_account = 1\nORDER BY name;`,
  pii_type: () => `SELECT kind, COUNT(*) AS count, ROUND(AVG(confidence), 2) AS avg_conf\nFROM "${getAlias('pii_detections')}"\nGROUP BY kind\nORDER BY count DESC;`,
  regulatory: () => `SELECT law, triggered, deadline, filing_required, notes\nFROM "${getAlias('regulatory_triggers')}";`,
  all_people: () => `SELECT person_key, name, email, phone, has_ssn, has_dob, has_cc, source_files, record_count, cross_file, confidence\nFROM "${getAlias('affected_people')}"\nORDER BY name;`,
  cross_file: () => `SELECT person_key, name, email, source_files, record_count\nFROM "${getAlias('affected_people')}"\nWHERE cross_file = 1\nORDER BY record_count DESC;`,
  crossref: () => `SELECT r.name, r.email, r.has_ssn, r.has_mrn, r.sensitivity_tier,\n       p.kind, p.confidence\nFROM "${getAlias('records')}" r\nJOIN "${getAlias('pii_detections')}" p ON r.record_id = p.record_id\nORDER BY r.name;`,
};

function setPreset(k) {
  if (_PRESETS[k]) document.getElementById('sql-input').value = _PRESETS[k]();
}

// ── Medallion Schema Browser ──
let _currentLayer = 'bronze';
let _schemaCache = null;

function switchLayer(layer) {
  _currentLayer = layer;
  ['bronze','silver','gold'].forEach(l => {
    const tab = document.getElementById('layer-tab-' + l);
    const panel = document.getElementById('schema-panel-' + l);
    if (!tab || !panel) return;
    const active = l === layer;
    const colors = {bronze:'#cd7f32', silver:'#a8a9ad', gold:'#ffd700'};
    tab.style.borderBottom = active ? '2px solid ' + colors[l] : '2px solid transparent';
    tab.style.background = active ? 'rgba(255,255,255,0.06)' : 'transparent';
    tab.style.color = active ? colors[l] : 'var(--silver)';
    panel.style.display = active ? 'block' : 'none';
  });
  if (_schemaCache) {
    renderLayerPanel(layer, _schemaCache[layer] || {});
  } else {
    loadMedallionSchema();
  }
}

function loadMedallionSchema() {
  if (!_EID) return;
  fetch('/engagements/' + _EID + '/schema')
    .then(r => r.ok ? r.json() : {bronze:{}, silver:{}, gold:{}})
    .then(schema => {
      _schemaCache = schema;
      renderLayerPanel(_currentLayer, schema[_currentLayer] || {});
    })
    .catch(() => {});
}

function renderLayerPanel(layer, tables) {
  const el = document.getElementById('schema-' + layer + '-content');
  if (!el) return;
  const names = Object.keys(tables);
  if (!names.length) {
    const msgs = {
      bronze: 'Run Stage 1 to populate Bronze tables.',
      silver: 'Run Stage 2 to build the Silver table.',
      gold:   'Run Stage 3+ to build Gold aggregations.',
    };
    el.innerHTML = '<span style="color:var(--muted);font-style:italic;font-size:10px">' + (msgs[layer]||'No tables yet.') + '</span>';
    return;
  }
  const layerColors = {bronze:'#cd7f32', silver:'#a8a9ad', gold:'#ffd700'};
  const col = layerColors[layer] || 'var(--blue)';
  let html = '';
  names.forEach(tbl => {
    const info = tables[tbl];
    const cols = info.columns || [];
    const rowCount = info.rows || 0;
    html += '<div style="margin-bottom:10px">';
    html += '<div style="color:' + col + ';font-weight:700;cursor:pointer;display:flex;align-items:center;gap:6px" data-tbl="' + escHtml(tbl) + '" onclick="selectTable(this.dataset.tbl)">';
    html += '&#9654; ' + escHtml(tbl);
    html += '<span style="font-size:9px;background:rgba(255,255,255,0.1);padding:1px 5px;border-radius:4px;color:var(--silver)">' + rowCount + ' rows</span>';
    html += '</div>';
    const showCols = cols.filter(c => !c.startsWith('_')).slice(0, 8);
    if (showCols.length) {
      html += '<div style="color:var(--muted);padding-left:12px;font-size:9.5px;line-height:1.7;word-break:break-all">';
      html += showCols.join(', ');
      if (cols.filter(c=>!c.startsWith('_')).length > 8) html += ', &hellip;';
      html += '</div>';
    }
    html += '</div>';
  });
  el.innerHTML = html;
}

function selectTable(tbl) {
  document.getElementById('sql-input').value = 'SELECT * FROM "' + tbl + '" LIMIT 100;';
}

// Medallion preset queries
let _lastBronzeTable = '';
const _MEDALLION_PRESETS = {
  bronze_preview: () => {
    const firstBronze = _schemaCache && Object.keys(_schemaCache.bronze||{})[0];
    const tbl = firstBronze || 'bronze_your_file_csv';
    _lastBronzeTable = tbl;
    return 'SELECT * FROM "' + tbl + '" LIMIT 50;';
  },
  silver_all:       () => 'SELECT * FROM silver LIMIT 100;',
  silver_high_risk: () => "SELECT * FROM silver WHERE _sensitivity_tier IN ('critical','high') ORDER BY _sensitivity_tier, _source_file LIMIT 200;",
  silver_people:    () => "SELECT * FROM silver WHERE _entity_type = 'person' ORDER BY name LIMIT 200;",
  gold_affected:    () => 'SELECT * FROM gold_affected_people ORDER BY name;',
  gold_summary:     () => 'SELECT * FROM gold_exposure_summary;',
  gold_by_field:    () => 'SELECT * FROM gold_pii_by_field ORDER BY record_count DESC;',
  gold_file_risk:   () => 'SELECT * FROM gold_file_risk ORDER BY sensitive_rows DESC;',
};

function setMedallionPreset(k) {
  if (!_schemaCache) {
    loadMedallionSchema();
    setTimeout(() => { if (_MEDALLION_PRESETS[k]) document.getElementById('sql-input').value = _MEDALLION_PRESETS[k](); }, 600);
  } else {
    if (_MEDALLION_PRESETS[k]) document.getElementById('sql-input').value = _MEDALLION_PRESETS[k]();
  }
}

// ── Field Configuration ──
let _fieldConfig = { user_fields: [], presets: ['identity','financial','medical','credentials'], auto_discover: true };

function loadFieldConfig() {
  if (!_EID) return;
  fetch('/engagements/' + _EID + '/field-config')
    .then(r => r.ok ? r.json() : null)
    .then(cfg => {
      if (!cfg) return;
      _fieldConfig = cfg;
      // Apply presets
      ['identity','financial','medical','credentials','network'].forEach(p => {
        const el = document.querySelector('#preset-' + p + ' input');
        if (el) el.checked = (_fieldConfig.presets || []).includes(p);
        stylePresetLabel(document.getElementById('preset-' + p), el ? el.checked : false);
      });
      // Auto-discover
      const ad = document.getElementById('auto-discover-toggle');
      if (ad) ad.checked = _fieldConfig.auto_discover !== false;
      // Custom fields
      (_fieldConfig.user_fields || []).forEach(f => addCustomField(f));
    })
    .catch(() => {});
}

function stylePresetLabel(label, checked) {
  if (!label) return;
  if (checked) {
    label.style.background = 'rgba(29,78,216,0.12)';
    label.style.borderColor = 'var(--blue)';
    label.style.color = 'var(--blue)';
  } else {
    label.style.background = '';
    label.style.borderColor = 'var(--border)';
    label.style.color = '';
  }
}

function togglePreset(cb) {
  stylePresetLabel(cb.closest('label'), cb.checked);
}

function addCustomField(data) {
  data = data || {};
  const tbody = document.getElementById('custom-fields-body');
  if (!tbody) return;
  const tr = document.createElement('tr');
  const terms = Array.isArray(data.search_terms) ? data.search_terms.join(', ') : (data.search_terms || '');
  tr.innerHTML = `
    <td style="padding:5px 8px;border:1px solid var(--border)">
      <input type="text" class="cf-name" value="${escHtml(data.name||'')}" placeholder="e.g. employee_id" style="width:100%;font-size:12px"/>
    </td>
    <td style="padding:5px 8px;border:1px solid var(--border)">
      <input type="text" class="cf-terms" value="${escHtml(terms)}" placeholder="e.g. emp_id, staff_id" style="width:100%;font-size:12px"/>
    </td>
    <td style="padding:5px 8px;border:1px solid var(--border)">
      <select class="cf-sens" style="font-size:12px">
        <option value="medium" ${data.sensitivity==='medium'?'selected':''}>Medium</option>
        <option value="high" ${data.sensitivity==='high'?'selected':''}>High</option>
        <option value="critical" ${data.sensitivity==='critical'?'selected':''}>Critical</option>
      </select>
    </td>
    <td style="padding:5px 8px;border:1px solid var(--border);text-align:center">
      <button onclick="this.closest('tr').remove()" style="background:none;border:none;color:var(--danger);cursor:pointer;font-size:15px">&#10005;</button>
    </td>
  `;
  tbody.appendChild(tr);
}

function saveFieldConfig() {
  const presets = [];
  ['identity','financial','medical','credentials','network'].forEach(p => {
    const el = document.querySelector('#preset-' + p + ' input');
    if (el && el.checked) presets.push(p);
  });
  const user_fields = [];
  document.querySelectorAll('#custom-fields-body tr').forEach(tr => {
    const name = tr.querySelector('.cf-name')?.value.trim();
    const terms = tr.querySelector('.cf-terms')?.value.trim();
    const sens = tr.querySelector('.cf-sens')?.value || 'medium';
    if (name) {
      user_fields.push({
        name,
        search_terms: terms ? terms.split(',').map(t => t.trim()).filter(Boolean) : [],
        sensitivity: sens,
      });
    }
  });
  const auto_discover = document.getElementById('auto-discover-toggle')?.checked !== false;
  const cfg = { user_fields, presets, auto_discover };
  const status = document.getElementById('field-config-status');
  fetch('/engagements/' + _EID + '/field-config', {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(cfg)
  }).then(r => r.json()).then(d => {
    if (d.ok) {
      _fieldConfig = cfg;
      if (status) { status.textContent = '✓ Saved'; setTimeout(() => { status.textContent = ''; }, 2000); }
    }
  }).catch(() => {
    if (status) status.textContent = 'Save failed';
  });
}

// Init on page load
(function init() {
  loadFieldConfig();
  loadMedallionSchema();
})();

function runQuickSearch() {
  const q = document.getElementById('qs-text').value.trim();
  const tbl = document.getElementById('qs-table').value;
  if (!q) return;
  const cols = {
    [_aliases.records||'records']: ['name','email','phone','source_file','record_id'],
    [_aliases.affected_people||'affected_people']: ['name','email','phone','record_id','source'],
    [_aliases.pii_detections||'pii_detections']: ['kind','evidence_ref','source_file','record_id'],
    [_aliases.regulatory_triggers||'regulatory_triggers']: ['law','deadline','notes'],
  };
  const searchCols = cols[tbl] || ['name','email'];
  const where = searchCols.map(c => `"${c}" LIKE '%${q.replace(/'/g,"''")}%'`).join(' OR ');
  document.getElementById('sql-input').value = `SELECT *\nFROM "${tbl}"\nWHERE ${where}\nLIMIT 200;`;
  document.getElementById('query-note').value = `Quick search for "${q}" in ${tbl}`;
  runSqlQuery();
}

function copySQL() {
  const t = document.getElementById('sql-input').value;
  navigator.clipboard.writeText(t).catch(() => {});
}

function downloadCSV() {
  if (!_lastCols.length) return;
  let csv = _lastCols.map(c => '"' + String(c).replace(/"/g,'""') + '"').join(',') + '\\n';
  _lastRows.forEach(row => {
    csv += row.map(c => '"' + String(c === null ? '' : c).replace(/"/g,'""') + '"').join(',') + '\\n';
  });
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
  a.download = 'query-results.csv';
  a.click();
}

function sortResults(colIdx) {
  if (_sortCol === colIdx) _sortDir *= -1;
  else { _sortCol = colIdx; _sortDir = 1; }
  _lastRows.sort((a, b) => {
    const av = a[colIdx], bv = b[colIdx];
    if (av === bv) return 0;
    if (av === null) return 1; if (bv === null) return -1;
    return (av < bv ? -1 : 1) * _sortDir;
  });
  renderResults(_lastCols, _lastRows, document.getElementById('query-result').dataset.rowTotal);
}

function renderResults(cols, rows, total) {
  const rid = document.getElementById('record-id-col-idx');
  const ridIdx = cols.indexOf('record_id');
  let html = `<div class="card" style="padding:0;overflow:hidden">`;
  html += `<div style="padding:10px 16px;background:var(--bg-2);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px">`;
  html += `<span style="font-size:12px;font-weight:700;color:var(--navy)">${rows.length} row${rows.length !== 1 ? 's' : ''}</span>`;
  const note = document.getElementById('query-note').value.trim();
  if (note) html += `<span style="font-size:11px;color:var(--muted);font-style:italic">&mdash; ${escHtml(note)}</span>`;
  html += `</div>`;
  html += `<div style="overflow-x:auto"><table><thead><tr>`;
  cols.forEach((c, i) => {
    const arrow = _sortCol === i ? (_sortDir === 1 ? ' &#9650;' : ' &#9660;') : '';
    html += `<th style="cursor:pointer;user-select:none" onclick="sortResults(${i})">${escHtml(c)}${arrow}</th>`;
  });
  if (ridIdx >= 0) html += `<th></th>`;
  html += `</tr></thead><tbody>`;
  rows.forEach(row => {
    html += `<tr>`;
    row.forEach((cell, i) => {
      let display;
      if (cell === null) display = `<span style="color:var(--silver);font-style:italic">null</span>`;
      else if ((cols[i]==='has_ssn'||cols[i]==='has_dob'||cols[i]==='has_mrn'||cols[i]==='has_cc'||cols[i]==='has_account'||cols[i]==='has_routing'||cols[i]==='has_insurance_id'||cols[i]==='triggered'||cols[i]==='filing_required') && (cell===0||cell===1||cell==='0'||cell==='1'))
        display = cell==1||cell==='1' ? `<span style="color:var(--success);font-weight:700">&#10003; YES</span>` : `<span style="color:var(--muted)">&#8212; no</span>`;
      else display = escHtml(String(cell));
      html += `<td style="font-size:12px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(String(cell??''))}">${display}</td>`;
    });
    if (ridIdx >= 0) {
      const rid2 = row[ridIdx];
      html += rid2 ? `<td><a href="/engagements/${encodeURIComponent(_EID)}/discovery/${encodeURIComponent(rid2)}" target="_blank" style="font-size:11px;white-space:nowrap">&#128269;</a></td>` : `<td></td>`;
    }
    html += `</tr>`;
  });
  html += `</tbody></table></div></div>`;
  const el = document.getElementById('query-result');
  el.innerHTML = html;
  el.dataset.rowTotal = total || rows.length;
}

function runSqlQuery() {
  const sql = document.getElementById('sql-input').value.trim();
  if (!sql) return;
  const status = document.getElementById('query-status');
  const result = document.getElementById('query-result');
  const csvBtn = document.getElementById('csv-btn');
  status.textContent = 'Running\u2026';
  result.innerHTML = '';
  csvBtn.style.display = 'none';
  const t0 = Date.now();
  fetch('/engagements/' + _EID + '/query', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({sql})
  })
  .then(r => r.json())
  .then(d => {
    const ms = Date.now() - t0;
    if (d.error) {
      status.textContent = '';
      result.innerHTML = `<div style="padding:14px 18px;background:var(--danger-bg);border:1px solid #FECACA;border-radius:9px;color:var(--danger);font-size:13px;font-family:monospace">&#9888; ${escHtml(d.error)}</div>`;
      return;
    }
    _lastCols = d.columns || [];
    _lastRows = d.rows || [];
    _sortCol = -1; _sortDir = 1;
    status.textContent = `${_lastRows.length} row${_lastRows.length !== 1 ? 's' : ''} \u00B7 ${ms}ms`;
    csvBtn.style.display = _lastRows.length ? 'inline-flex' : 'none';
    renderResults(_lastCols, _lastRows, _lastRows.length);
  })
  .catch(e => {
    status.textContent = '';
    result.innerHTML = `<div style="padding:14px 18px;background:var(--danger-bg);border-radius:9px;color:var(--danger);font-size:13px">Query failed: ${escHtml(e.message)}</div>`;
  });
}

// ── Upload ──
const zone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const folderInput = document.getElementById('folder-input');
if (zone) {
  ['dragenter','dragover'].forEach(ev => zone.addEventListener(ev, e => {e.preventDefault(); zone.classList.add('drag-over');}));
  ['dragleave','drop'].forEach(ev => zone.addEventListener(ev, e => {e.preventDefault(); zone.classList.remove('drag-over');}));
  zone.addEventListener('drop', e => {
    if (e.dataTransfer.items && e.dataTransfer.items.length) {
      const entries = Array.from(e.dataTransfer.items).map(i => i.webkitGetAsEntry()).filter(Boolean);
      entries.forEach(processEntry);
    } else {
      handleFiles(e.dataTransfer.files);
    }
  });
  fileInput.addEventListener('change', e => handleFiles(e.target.files));
  folderInput.addEventListener('change', e => handleFiles(e.target.files));
}

function processEntry(entry) {
  if (entry.isFile) {
    entry.file(f => uploadFile(f));
  } else if (entry.isDirectory) {
    const reader = entry.createReader();
    function readBatch() {
      reader.readEntries(entries => {
        if (!entries.length) return;
        entries.forEach(processEntry);
        readBatch(); // readEntries returns max 100 at a time
      });
    }
    readBatch();
  }
}

function handleFiles(fl) { Array.from(fl).forEach(f => uploadFile(f)); }

function formatSize(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(1) + ' MB';
}
function escHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function escJs(s) { return encodeURIComponent(String(s)); }
function dtChatSend() {
  var inp = document.getElementById('dt-chat-input');
  var msg = inp.value.trim(); if (!msg) return; inp.value = '';
  var box = document.getElementById('dt-chat-msgs');
  var eid = document.body.dataset.incidentId || '';
  var ud = document.createElement('div');
  ud.style.cssText = 'text-align:right;margin-bottom:8px';
  ud.innerHTML = '<span style="display:inline-block;background:var(--blue);color:#fff;border-radius:10px 10px 2px 10px;padding:6px 12px;font-size:13px;max-width:85%">' + escHtml(msg) + '</span>';
  box.appendChild(ud);
  var tid = document.createElement('div');
  tid.id = 'dt-typing'; tid.style.cssText = 'margin-bottom:8px;color:var(--muted);font-size:12px;font-style:italic';
  tid.textContent = 'Vectorian is thinking...';
  box.appendChild(tid); box.scrollTop = box.scrollHeight;
  var payload = {message: msg}; if (eid) payload.incident_id = eid;
  fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})
    .then(function(r){return r.json();})
    .then(function(d) {
      var t = document.getElementById('dt-typing'); if (t) t.remove();
      var reply = d.reply || 'No response.';
      var bd = document.createElement('div');
      bd.style.cssText = 'margin-bottom:10px';
      // split on ```sql ... ``` blocks; capturing group gives code at odd indices
      var parts = reply.split(/```(?:sql)?\\n?([\\s\\S]*?)```/gi);
      var innerHtml = '';
      var lastSql = '';
      for (var i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          innerHtml += '<span style="white-space:pre-wrap">' + escHtml(parts[i]) + '</span>';
        } else {
          var cleanCode = parts[i].trim();
          lastSql = cleanCode;
          innerHtml += '<pre style="background:rgba(0,0,0,0.3);border-radius:6px;padding:8px 10px;font-size:11px;overflow-x:auto;white-space:pre-wrap;margin:6px 0">' + escHtml(cleanCode) + '</pre>';
        }
      }
      if (lastSql) {
        innerHtml += '<button type="button" class="dt-use-query" style="font-size:11px;padding:3px 9px;background:var(--blue);color:#fff;border:none;border-radius:5px;cursor:pointer;margin-top:4px">&#9654; Use this query</button>';
        bd.dataset.sql = lastSql;
      }
      bd.innerHTML = '<div style="display:flex;align-items:flex-start;gap:8px">' +
        '<div style="width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,var(--blue-light),var(--blue));display:flex;align-items:center;justify-content:center;font-size:11px;flex-shrink:0;margin-top:1px">&#9670;</div>' +
        '<div style="background:rgba(255,255,255,0.07);border-radius:2px 10px 10px 10px;padding:8px 12px;font-size:13px;color:rgba(255,255,255,0.9);max-width:90%;line-height:1.5">' + innerHtml + '</div></div>';
      if (lastSql) bd.dataset.sql = lastSql;
      box.appendChild(bd); box.scrollTop = box.scrollHeight;
    })
    .catch(function() {
      var t = document.getElementById('dt-typing'); if (t) t.remove();
      var bd = document.createElement('div'); bd.style.cssText = 'margin-bottom:8px;color:var(--red);font-size:12px';
      bd.textContent = 'Unable to reach Vectorian AI.';
      box.appendChild(bd); box.scrollTop = box.scrollHeight;
    });
}
function dtAutoSql(el) {
  while (el && !el.dataset.sql) el = el.parentElement;
  var sql = el ? el.dataset.sql : '';
  if (!sql) return;
  var editor = document.getElementById('sql-editor');
  if (editor) editor.value = sql;
  switchTab('tables');
  setTimeout(function() {
    var runBtn = document.getElementById('run-query-btn');
    if (runBtn) runBtn.click();
  }, 150);
}
document.addEventListener('click', function(e) {
  var btn = e.target.closest('.dt-use-query');
  if (btn) dtAutoSql(btn);
});
function fileIcon(name) {
  const e = (name.split('.').pop()||'').toLowerCase();
  const m = {pdf:'📄',docx:'📄',doc:'📄',txt:'📝',md:'📝',csv:'📊',xlsx:'📊',xls:'📊',
    json:'📊',jsonl:'📊',xml:'📊',html:'🌐',htm:'🌐',eml:'🌐',
    jpg:'🖼',jpeg:'🖼',png:'🖼',gif:'🖼',bmp:'🖼',tiff:'🖼',tif:'🖼',webp:'🖼',
    mp4:'🎥',mov:'🎥',avi:'🎥',mkv:'🎥',wmv:'🎥'};
  return m[e] || '📁';
}

function uploadFile(file) {
  const eid = document.body.dataset.incidentId;
  const fd = new FormData(); fd.append('file', file);
  const rowId = 'fr-' + Date.now() + Math.random().toString(36).slice(2);
  const tbody = document.getElementById('files-tbody');
  const empty = document.getElementById('empty-row');
  if (empty) empty.remove();
  const tr = document.createElement('tr'); tr.id = rowId;
  tr.innerHTML =
    '<td style="text-align:center;font-size:18px">' + fileIcon(file.name) + '</td>' +
    '<td><div style="font-weight:600;color:var(--navy)">' + escHtml(file.name) + '</div></td>' +
    '<td class="muted" style="font-size:12px">' + formatSize(file.size) + '</td>' +
    '<td>—</td><td><span class="proc-pend">&#8987; Uploading...</span></td><td>—</td>';
  tbody.prepend(tr);
  updateCount(1);

  fetch('/engagements/' + eid + '/upload', {method:'POST', body:fd})
    .then(r => r.json())
    .then(d => {
      if (d.error) {
        tr.cells[4].innerHTML = '<span class="proc-err">&#9888; ' + escHtml(d.error) + '</span>';
      } else {
        tr.cells[0].textContent = fileIcon(d.original_name);
        tr.cells[1].innerHTML = '<div style="font-weight:600;color:var(--navy)">' + escHtml(d.original_name) + '</div>' +
          '<div style="font-size:10px;font-family:monospace;color:var(--silver);margin-top:2px">' + d.sha256.substring(0,20) + '...</div>';
        tr.cells[2].textContent = formatSize(d.size_bytes);
        tr.cells[3].innerHTML = '<span class="muted" style="font-size:12px">' + escHtml(d.type_label) + '</span>';
        tr.cells[4].innerHTML = d.proc_error
          ? '<span class="proc-err">&#9888; ' + escHtml(d.proc_error) + '</span>'
          : '<span class="proc-ok">&#10003; ' + escHtml(d.method) + '</span>';
        tr.cells[5].innerHTML = d.proc_error ? '<span class="muted" style="font-size:12px">—</span>'
          : '<a href="/engagements/' + eid + '/files/' + encodeURIComponent(d.filename) + '/text" class="plain" target="_blank" style="font-size:12px">View &rarr;</a>';
      }
    })
    .catch(() => { tr.cells[4].innerHTML = '<span class="proc-err">Upload failed</span>'; });
}

function updateCount(delta) {
  const el = document.getElementById('file-count');
  if (!el) return;
  const n = (parseInt(el.dataset.count || el.textContent) || 0) + delta;
  el.dataset.count = n;
  el.textContent = n + ' file' + (n !== 1 ? 's' : '');
}
</script>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _next_engagement_id(storage: Storage, cfg: dict) -> str:
    fmt = cfg.get("incident_code_format", {})
    prefix = fmt.get("prefix", "INC")
    sep = fmt.get("separator", "-")
    year = fmt.get("year", True)
    digits = fmt.get("digits", 4)
    existing = list(storage.state_dir.glob("*.json"))
    n = len(existing) + 1
    parts = [prefix]
    if year:
        from datetime import datetime
        parts.append(str(datetime.now().year))
    parts.append(str(n).zfill(digits))
    return sep.join(parts)


def _format_number(n):
    if n is None or n == "":
        return "—"
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _build_engagement_row(p: Path, storage, workdir: str, total_stages: int):
    s = storage.load_state_obj(p.stem)
    cur = s.get("current_layer")
    client = s.get("client", {})
    completed = s.get("completed_layers", [])
    pct = int(len(completed) / total_stages * 100) if total_stages else 0
    breach_types = client.get("breach_type", "")
    if isinstance(breach_types, list):
        breach_types = ", ".join(breach_types[:2]) + ("..." if len(breach_types) > 2 else "")
    return {
        "id": p.stem,
        "company": client.get("company_name", ""),
        "industry": client.get("industry", ""),
        "breach_type": breach_types,
        "current_layer": cur,
        "stage_name": get_stage_name(cur, workdir) if cur else "Complete",
        "completed": " → ".join(completed) or "—",
        "completed_count": len(completed),
        "total_stages": total_stages,
        "pct": pct,
        "created_at": s.get("created_at", "")[:10],
    }


def _upload_dir(workdir: str, engagement_id: str) -> Path:
    d = Path(workdir) / "uploads" / engagement_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_upload_index(workdir: str, engagement_id: str) -> list:
    idx = _upload_dir(workdir, engagement_id) / "_index.json"
    if idx.exists():
        try:
            return json.loads(idx.read_text())
        except Exception:
            pass
    return []


def _save_upload_index(workdir: str, engagement_id: str, records: list) -> None:
    idx = _upload_dir(workdir, engagement_id) / "_index.json"
    idx.write_text(json.dumps(records, indent=2))


def _size_label(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1_048_576:
        return f"{b/1024:.1f} KB"
    return f"{b/1_048_576:.1f} MB"


# Keys cleared per stage re-run (each stage clears its own + all downstream)
_RERUN_KEYS: dict[str, list[str]] = {
    "1": ["incident", "evidence", "evidence_files", "ingest"],
    "2": ["extracted", "pii_summary", "normalization_stats", "secrets_scan", "plugin_results"],
    "3": ["sensitivity_classification", "applicable_laws"],
    "4": ["affected_people", "identity_scores", "entity_resolution"],
    "5": ["impact_summary", "timeline", "chain_of_custody"],
    "6": ["regulatory_triggers", "legal_determination", "notification_required"],
    "7": ["notification_draft", "notification_queue", "notification_sent"],
    "8": ["review_pack_path", "review_pack_html_path", "review_pack_manifest"],
    "9": ["disclosure_checklist", "status", "final_note"],
}


def _sensitive_bool(v) -> int:
    """Return 1 if value is present/non-empty, 0 otherwise. Never exposes raw value."""
    if not v:  # handles None, 0, False, "", [], {}
        return 0
    if isinstance(v, str):
        stripped = v.strip()
        if not stripped:
            return 0
        return 1  # non-empty string → present (regardless of "[PRESENT]" or actual value)
    return 1


def _build_sqlite_db(runbook: dict, aliases: dict | None = None) -> sqlite3.Connection:
    """Build an in-memory SQLite DB from the runbook. Sensitive fields are boolean."""
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()

    # ── records ──────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE records (
        record_id TEXT, source_file TEXT, source_type TEXT, row_num TEXT,
        name TEXT, email TEXT, phone TEXT, address TEXT, city TEXT,
        state_col TEXT, zip TEXT, diagnosis TEXT, provider TEXT, insurance_plan TEXT,
        has_ssn INTEGER, has_dob INTEGER, has_mrn INTEGER,
        has_cc INTEGER, has_account INTEGER, has_routing INTEGER, has_insurance_id INTEGER,
        sensitivity_tier TEXT, pii_hit_count INTEGER
    )""")
    records_src = runbook.get("extracted", runbook.get("evidence", []))
    if isinstance(records_src, list):
        for rec in records_src:
            rid = rec.get("record_id", "")
            parts = rid.split(":row:", 1)
            src_file = parts[0] if parts else rid
            row_num = parts[1] if len(parts) > 1 else ""
            c.execute(
                "INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid, src_file, rec.get("source_type", ""), row_num,
                    rec.get("name", ""), rec.get("email", ""), rec.get("phone", ""),
                    rec.get("address", ""), rec.get("city", ""),
                    rec.get("state", ""), rec.get("zip", ""),
                    rec.get("diagnosis", ""), rec.get("provider", ""), rec.get("insurance_plan", ""),
                    _sensitive_bool(rec.get("ssn")),
                    _sensitive_bool(rec.get("dob")),
                    _sensitive_bool(rec.get("mrn")),
                    _sensitive_bool(rec.get("cc")),
                    _sensitive_bool(rec.get("account")),
                    _sensitive_bool(rec.get("routing")),
                    _sensitive_bool(rec.get("insurance_id")),
                    rec.get("sensitivity_tier", ""),
                    rec.get("pii_hit_count", 0),
                ),
            )

    # ── affected_people ───────────────────────────────────────────────────────
    c.execute("""CREATE TABLE affected_people (
        person_key TEXT, record_id TEXT, name TEXT, email TEXT, phone TEXT,
        has_ssn INTEGER, has_dob INTEGER, has_mrn INTEGER, has_cc INTEGER,
        source_files TEXT, record_count INTEGER, cross_file INTEGER,
        sensitivity_tier TEXT, confidence TEXT
    )""")
    for p in runbook.get("affected_people", []):
        src_files = p.get("source_files") or [p.get("source", "")]
        c.execute(
            "INSERT INTO affected_people VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                p.get("person_key") or "",
                p.get("record_id", ""), p.get("name", ""), p.get("email", ""), p.get("phone", ""),
                _sensitive_bool(p.get("ssn")),
                _sensitive_bool(p.get("dob")),
                _sensitive_bool(p.get("mrn")),
                _sensitive_bool(p.get("cc")),
                ", ".join(src_files),
                p.get("record_count", 1),
                1 if p.get("cross_file") else 0,
                p.get("sensitivity_tier", ""),
                str(p.get("confidence", "")),
            ),
        )

    # ── pii_detections ────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE pii_detections (
        kind TEXT, confidence REAL, evidence_ref TEXT, source_file TEXT, record_id TEXT
    )""")
    for hit in runbook.get("pii_summary", []):
        c.execute(
            "INSERT INTO pii_detections VALUES (?,?,?,?,?)",
            (
                hit.get("kind", ""),
                float(hit.get("confidence", 0) or 0),
                hit.get("evidence_ref", ""),
                hit.get("source_file", ""),
                hit.get("record_id", ""),
            ),
        )

    # ── regulatory_triggers ───────────────────────────────────────────────────
    c.execute("""CREATE TABLE regulatory_triggers (
        law TEXT, triggered INTEGER, threshold TEXT, deadline TEXT,
        filing_required INTEGER, notes TEXT
    )""")
    for t in runbook.get("regulatory_triggers", []):
        c.execute(
            "INSERT INTO regulatory_triggers VALUES (?,?,?,?,?,?)",
            (
                t.get("law", ""),
                1 if t.get("triggered") else 0,
                str(t.get("threshold", "")),
                t.get("deadline", ""),
                1 if t.get("filing_required") else 0,
                t.get("notes", ""),
            ),
        )

    # Create alias views so queries can use configured table names
    if aliases:
        for base, alias in aliases.items():
            alias = (alias or "").strip()
            if alias and alias != base:
                try:
                    conn.execute(f'CREATE VIEW IF NOT EXISTS "{alias}" AS SELECT * FROM "{base}"')
                except Exception:
                    pass

    conn.commit()
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────────────────────────────────────

def create_app(workdir: str = ".vectrion", data_dir: str = None) -> Flask:
    app = Flask(__name__)
    app.jinja_env.filters["format_number"] = _format_number
    app.jinja_env.filters["urlencode"] = lambda v: _url_quote(str(v), safe="")
    storage = Storage(Path(workdir))
    dd = Path(data_dir) if data_dir else Path(__file__).resolve().parent / "data"

    @app.get("/")
    def home():
        if not is_setup_complete(workdir):
            return redirect(url_for("welcome"))
        cfg = load_config(workdir)
        all_stages = cfg.get("stages", [])
        total = len(all_stages)
        rows = []
        for p in sorted(storage.state_dir.glob("*.json")):
            try:
                rows.append(_build_engagement_row(p, storage, workdir, total))
            except Exception:
                continue
        active = sum(1 for r in rows if r["current_layer"])
        complete = sum(1 for r in rows if not r["current_layer"])
        stages_run = sum(r["completed_count"] for r in rows)
        return render_template_string(
            INDEX_TMPL,
            page_title="Dashboard", active_nav="dashboard",
            engagements=rows,
            stats={"total": len(rows), "active": active, "complete": complete, "stages_run": stages_run},
            disclaimer=LEGAL_DISCLAIMER,
        )

    @app.get("/welcome")
    def welcome():
        enter_url = url_for("setup") if not is_setup_complete(workdir) else url_for("home")
        return render_template_string(WELCOME_TMPL, page_title="Welcome", active_nav="", disclaimer=LEGAL_DISCLAIMER, enter_url=enter_url)

    @app.get("/setup")
    def setup():
        cfg = load_config(workdir)
        return render_template_string(SETUP_TMPL, page_title="Setup", active_nav="", cfg=cfg, step=int(request.args.get("step", 1)))

    @app.post("/setup/step1")
    def setup_step1():
        cfg = load_config(workdir)
        cfg["incident_code_format"] = {
            "prefix": request.form.get("prefix", "INC").strip(),
            "year": bool(request.form.get("year")),
            "separator": request.form.get("separator", "-"),
            "digits": int(request.form.get("digits", 4)),
        }
        save_config(workdir, cfg)
        return redirect(url_for("setup") + "?step=2")

    @app.post("/setup/save")
    def setup_save():
        cfg = load_config(workdir)
        ids = request.form.getlist("id[]")
        names = request.form.getlist("name[]")
        custom_names = request.form.getlist("custom_name[]")
        cfg["stages"] = [
            {"id": sid, "name": names[i] if i < len(names) else sid,
             "custom_name": custom_names[i] if i < len(custom_names) else "",
             "enabled": True, "owner": "", "notes": ""}
            for i, sid in enumerate(ids)
        ]
        cfg["setup_complete"] = True
        save_config(workdir, cfg)
        return redirect(url_for("home"))

    @app.get("/config")
    def config_panel():
        cfg = load_config(workdir)
        stages = cfg.get("stages", [])
        custom_count = sum(1 for s in stages if s["id"].startswith("custom_"))
        return render_template_string(CONFIG_TMPL, page_title="Configuration", active_nav="config",
                                      cfg=cfg, stages_enum=list(enumerate(stages)), custom_count=custom_count)

    @app.post("/config/save")
    def config_save():
        cfg = load_config(workdir)
        ids = request.form.getlist("id[]")
        custom_names = request.form.getlist("custom_name[]")
        owners = request.form.getlist("owner[]")
        notes_list = request.form.getlist("notes[]")
        new_stages = []
        for i, sid in enumerate(ids):
            orig = next((s for s in cfg.get("stages", []) if s["id"] == sid), None)
            new_stages.append({
                "id": sid, "name": orig["name"] if orig else "Custom Stage",
                "custom_name": custom_names[i] if i < len(custom_names) else "",
                "enabled": bool(request.form.get(f"enabled_{sid}")),
                "owner": owners[i] if i < len(owners) else "",
                "notes": notes_list[i] if i < len(notes_list) else "",
            })
        cfg["stages"] = new_stages
        cfg["incident_code_format"] = {
            "prefix": request.form.get("prefix", "INC").strip(),
            "year": bool(request.form.get("year")),
            "separator": request.form.get("separator", "-"),
            "digits": int(request.form.get("digits", 4)),
        }
        save_config(workdir, cfg)
        return redirect(url_for("config_panel"))

    @app.get("/plugins")
    def plugins_page():
        from vectrion.plugins.registry import (
            load_plugin_config, _PLUGIN_META, load_custom_plugins, load_manifest_plugins
        )
        cfg = load_plugin_config(workdir)
        legacy_plugins   = load_custom_plugins(workdir)
        manifest_plugins = load_manifest_plugins(workdir)
        all_custom = legacy_plugins + manifest_plugins
        return render_template_string(
            PLUGINS_TMPL,
            active_nav="plugins",
            page_title="Plugins",
            plugin_meta=_PLUGIN_META,
            plugin_cfg=cfg,
            custom_plugins=all_custom,
        )

    @app.post("/plugins/save")
    def plugins_save():
        from vectrion.plugins.registry import load_plugin_config, save_plugin_config
        cfg = load_plugin_config(workdir)
        plugin_id = request.form.get("plugin_id", "")
        if plugin_id and plugin_id in cfg:
            cfg[plugin_id]["enabled"] = bool(request.form.get("enabled"))
            if "api_key" in request.form:
                cfg[plugin_id]["api_key"] = request.form.get("api_key", "").strip()
            save_plugin_config(workdir, cfg)
        return redirect(url_for("plugins_page"))

    @app.post("/plugins/upload")
    def plugins_upload():
        import zipfile as _zipfile
        import shutil as _shutil
        from werkzeug.utils import secure_filename
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return redirect(url_for("plugins_page"))
        filename = secure_filename(uploaded.filename)
        dest_dir = Path(workdir) / "custom_plugins"
        dest_dir.mkdir(parents=True, exist_ok=True)

        if filename.endswith(".py"):
            # Legacy: save single Python file
            uploaded.save(str(dest_dir / filename))
        elif filename.endswith(".zip"):
            # New: extract into a subdirectory named after the zip stem
            stem = filename[:-4]
            extract_dir = dest_dir / stem
            extract_dir.mkdir(exist_ok=True)
            tmp = dest_dir / filename
            uploaded.save(str(tmp))
            try:
                with _zipfile.ZipFile(str(tmp), "r") as zf:
                    zf.extractall(str(extract_dir))
            finally:
                tmp.unlink(missing_ok=True)
        # Silently ignore other extensions

        return redirect(url_for("plugins_page"))

    @app.post("/plugins/custom/<name>/remove")
    def plugins_custom_remove(name: str):
        import shutil as _shutil
        from werkzeug.utils import secure_filename
        safe = secure_filename(name)
        base = Path(workdir) / "custom_plugins"
        # Try as a .py file first (legacy), then as a directory (manifest plugin)
        file_target = base / (safe if safe.endswith(".py") else safe + ".py")
        dir_target  = base / safe
        if file_target.exists() and file_target.is_file():
            file_target.unlink()
        elif dir_target.exists() and dir_target.is_dir():
            _shutil.rmtree(str(dir_target))
        return redirect(url_for("plugins_page"))

    @app.get("/plugins/sdk-template")
    def plugins_sdk_template():
        from flask import send_file
        template_path = Path(__file__).resolve().parent / "plugins" / "sdk_template.py"
        if not template_path.exists():
            return "SDK template not found.", 404
        return send_file(
            str(template_path), mimetype="text/x-python",
            as_attachment=True, download_name="custom_scanner_template.py",
        )

    @app.get("/plugins/sdk/<language>")
    def plugins_sdk_language(language: str):
        from flask import send_file
        from vectrion.plugins.sdk_templates import get_sdk_zip
        try:
            buf = get_sdk_zip(language)
        except ValueError:
            return f"No SDK template for language: {language!r}", 404
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"vectrion_sdk_{language}.zip",
        )

    @app.get("/engagements/new")
    def new_engagement():
        cfg = load_config(workdir)
        suggested = _next_engagement_id(storage, cfg)
        return render_template_string(NEW_ENG_TMPL, page_title="New Engagement", active_nav="dashboard", suggested_id=suggested)

    @app.post("/engagements/create")
    def create_engagement():
        form = request.form
        engagement_id = (form.get("engagement_id") or "").strip()
        if not engagement_id:
            return redirect(url_for("new_engagement"))

        client = {
            "company_name":    form.get("company_name", ""),
            "industry":        form.get("industry", ""),
            "org_size":        form.get("org_size", ""),
            "revenue":         form.get("revenue", ""),
            "contact_name":    form.get("contact_name", ""),
            "contact_email":   form.get("contact_email", ""),
            "contact_phone":   form.get("contact_phone", ""),
            "contact_title":   form.get("contact_title", ""),
            "date_discovered": form.get("date_discovered", ""),
            "date_of_breach":  form.get("date_of_breach", ""),
            "breach_type":     form.getlist("breach_type[]"),
            "data_types":      form.getlist("data_types[]"),
            "affected_count":  form.get("affected_count", ""),
            "contained":       form.get("contained", "Unknown"),
            "summary":         form.get("summary", ""),
            "regulations":     form.getlist("regulations[]"),
            "jurisdictions":   form.get("jurisdictions", ""),
            "counsel_engaged": form.get("counsel_engaged", "No"),
            "law_firm":        form.get("law_firm", ""),
            "law_enforcement": form.get("law_enforcement", "No"),
            "privilege":       form.get("privilege", "No"),
        }

        if not storage.load_state_obj(engagement_id):
            order = get_stage_order(workdir)
            start = order[0] if order else "1"
            state = {
                "incident_id": engagement_id,
                "current_layer": start,
                "completed_layers": [],
                "runbook": {},
                "client": client,
            }
            storage.save_state_obj(engagement_id, state)
            storage.audit(engagement_id, "engagement_opened", {"source": "ui", "company": client["company_name"]})

        return redirect(url_for("engagement_detail", engagement_id=engagement_id))

    @app.get("/engagements/<engagement_id>")
    def engagement_detail(engagement_id: str):
        s = storage.load_state_obj(engagement_id)
        if not s:
            return redirect(url_for("home"))
        cur = s.get("current_layer")
        cfg = load_config(workdir)
        client = s.get("client", {})
        # Load vault files
        from vectrion.ingestion import TYPE_ICONS
        raw_files = _load_upload_index(workdir, engagement_id)
        vault_files = []
        for f in raw_files:
            cat = f.get("type", "unknown")
            vault_files.append({
                **f,
                "icon": TYPE_ICONS.get(cat, "📁"),
                "size_label": _size_label(f.get("size_bytes", 0)),
            })
        rb = s.get("runbook", {})
        table_aliases = s.get("table_aliases", {})
        # Sensitivity: strip internal _keys
        rb_sensitivity = {k: v for k, v in rb.get("sensitivity_classification", {}).items() if not k.startswith("_")}
        # PII kinds as badges
        rb_pii_kinds = rb.get("normalization_stats", {}).get("pii_kinds", [])
        # Review pack paths relative to exports dir
        rb_review_pack_html = rb.get("review_pack_html_path", "")
        rb_review_pack_json = rb.get("review_pack_path", "")
        return render_template_string(
            DETAIL_TMPL,
            page_title=engagement_id, active_nav="dashboard",
            engagement_id=engagement_id,
            current_layer=cur,
            current_stage_name=get_stage_name(cur, workdir) if cur else None,
            completed=s.get("completed_layers", []),
            all_stages=cfg.get("stages", []),
            client=client,
            vault_files=vault_files,
            runbook_json=json.dumps(rb, indent=2),
            disclaimer=LEGAL_DISCLAIMER,
            # Structured stage data for analysis tab
            rb_ingest=rb.get("ingest", {}),
            rb_norm_stats=rb.get("normalization_stats", {}),
            rb_pii_kinds=rb_pii_kinds,
            rb_secrets_scan=rb.get("secrets_scan", {}),
            rb_plugin_results=rb.get("plugin_results", {}),
            rb_sensitivity=rb_sensitivity,
            rb_applicable_laws=list(rb.get("applicable_laws", {}).keys()),
            rb_affected=rb.get("affected_people", []),
            rb_entity_resolution=rb.get("entity_resolution", {}),
            rb_impact=rb.get("impact_summary", {}),
            rb_triggers=rb.get("regulatory_triggers", []),
            rb_legal=rb.get("legal_determination", {}),
            rb_notif_queue_count=len(rb.get("notification_queue", [])),
            rb_notif_draft=rb.get("notification_draft", ""),
            rb_review_pack_html=rb_review_pack_html,
            rb_review_pack_json=rb_review_pack_json,
            rb_disclosure_checklist=rb.get("disclosure_checklist", []),
            table_aliases=table_aliases,
        )

    @app.post("/engagements/<engagement_id>/proceed")
    def engagement_proceed(engagement_id: str):
        s = storage.load_state_obj(engagement_id)
        if not s:
            return redirect(url_for("home"))
        current = s.get("current_layer")
        if current:
            vault_dir = _upload_dir(workdir, engagement_id)
            ctx = {**s, "workdir": str(workdir), "field_config": s.get("field_config", {})}
            updated = run_layer(
                s.get("runbook", {}), current, dd, Path(workdir) / "exports",
                vault_dir=vault_dir,
                engagement_id=engagement_id,
                context=ctx,
            )
            s["runbook"] = updated
            done = s.get("completed_layers", [])
            if current not in done:
                done.append(current)
            s["completed_layers"] = done
            s["current_layer"] = next_layer(current, workdir)
            storage.save_state_obj(engagement_id, s)
            storage.audit(engagement_id, "stage_complete", {"completed": current, "next": s.get("current_layer")})
        return redirect(url_for("engagement_detail", engagement_id=engagement_id))

    @app.post("/engagements/<engagement_id>/upload")
    def engagement_upload(engagement_id: str):
        from datetime import datetime
        from werkzeug.utils import secure_filename
        from vectrion.ingestion import process_file, ALLOWED_EXTENSIONS, TYPE_ICONS

        s = storage.load_state_obj(engagement_id)
        if not s:
            return app.response_class(
                response=json.dumps({"error": "Engagement not found"}),
                mimetype="application/json", status=404,
            )

        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return app.response_class(
                response=json.dumps({"error": "No file provided"}),
                mimetype="application/json", status=400,
            )

        ext = Path(uploaded.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return app.response_class(
                response=json.dumps({"error": f"File type '{ext}' not supported"}),
                mimetype="application/json", status=415,
            )

        # Build a timestamped safe filename to avoid collisions
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        safe_base = secure_filename(Path(uploaded.filename).stem)[:40] or "file"
        safe_name = f"{safe_base}_{ts}{ext}"

        dest_dir = _upload_dir(workdir, engagement_id)
        dest = dest_dir / safe_name
        uploaded.save(str(dest))

        # Process the file
        result = process_file(dest)

        # Save extracted text alongside original
        text_path = dest_dir / (safe_name + ".txt")
        try:
            text_path.write_text(result["text"] or "", encoding="utf-8")
        except Exception:
            pass

        record = {
            "filename":      safe_name,
            "original_name": uploaded.filename,
            "sha256":        result["sha256"],
            "size_bytes":    result["size_bytes"],
            "type":          result["type"],
            "type_label":    result["type_label"],
            "method":        result["method"],
            "uploaded_at":   datetime.now().isoformat()[:19],
            "proc_error":    result["error"],
        }

        # Append to index
        records = _load_upload_index(workdir, engagement_id)
        records.append(record)
        _save_upload_index(workdir, engagement_id, records)

        storage.audit(engagement_id, "file_ingested", {
            "filename": safe_name,
            "original": uploaded.filename,
            "sha256":   result["sha256"],
            "method":   result["method"],
        })

        return app.response_class(
            response=json.dumps({**record, "engagement_id": engagement_id}),
            mimetype="application/json",
        )

    @app.get("/engagements/<engagement_id>/files/<filename>/text")
    def engagement_file_text(engagement_id: str, filename: str):
        from werkzeug.utils import secure_filename
        safe = secure_filename(filename)
        text_path = _upload_dir(workdir, engagement_id) / (safe + ".txt")
        if not text_path.exists():
            return "File not found or not yet processed.", 404
        text = text_path.read_text(encoding="utf-8", errors="replace")
        # Return as plain HTML for easy in-browser viewing
        lines = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = (
            f"<!doctype html><html><head><meta charset='utf-8'/>"
            f"<title>{safe}</title>"
            f"<style>body{{font-family:monospace;white-space:pre-wrap;padding:20px;background:#07111D;color:#A8C8E8;font-size:13px;line-height:1.7;}}</style></head>"
            f"<body>{lines}</body></html>"
        )
        return html

    # Keep legacy /incidents routes working
    @app.post("/incidents/create")
    def create_incident():
        return redirect(url_for("new_engagement"))

    @app.get("/incidents/<eid>")
    def incident_detail(eid: str):
        return redirect(url_for("engagement_detail", engagement_id=eid))

    @app.post("/incidents/<eid>/proceed")
    def incident_proceed(eid: str):
        return redirect(url_for("engagement_proceed", engagement_id=eid), code=307)

    @app.post("/api/chat")
    def api_chat():
        from vectrion.chat import chat
        body = request.get_json(force=True)
        incident_id = body.get("incident_id")
        incident_context = None
        if incident_id:
            s = storage.load_state_obj(incident_id)
            if s:
                rb = s.get("runbook", {})
                # Aggregate pii_summary to counts only — avoid sending full record list
                evidence_files = rb.get("evidence_files", [])
                pii_raw = rb.get("pii_summary", [])
                pii_counts: dict[str, int] = {}
                if isinstance(pii_raw, list):
                    for item in pii_raw:
                        k = item.get("kind", "unknown") if isinstance(item, dict) else "unknown"
                        pii_counts[k] = pii_counts.get(k, 0) + 1
                elif isinstance(pii_raw, dict):
                    pii_counts = {k: len(v) if isinstance(v, list) else v for k, v in pii_raw.items()}
                # Per-file PII summary from extracted records
                per_file: dict[str, dict] = {}
                for rec in rb.get("extracted", []):
                    fname = rec.get("source_file", "unknown")
                    if fname not in per_file:
                        per_file[fname] = {"records": 0, "pii_types": set()}
                    per_file[fname]["records"] += 1
                    for pt in (rec.get("pii_types") or []):
                        per_file[fname]["pii_types"].add(pt)
                per_file_summary = {
                    fn: {"records": v["records"], "pii_types": sorted(v["pii_types"])}
                    for fn, v in per_file.items()
                }
                incident_context = {
                    "incident_id": incident_id,
                    "stage": s.get("stage"),
                    "current_layer": s.get("current_layer"),
                    "completed_layers": s.get("completed_layers", []),
                    "incident": rb.get("incident", {}),
                    "pii_counts_by_type": pii_counts,
                    "affected_people_count": len(rb.get("affected_people", [])),
                    "files_ingested": len(evidence_files),
                    "files": [
                        {"name": ef.get("original_name", ""), "type": ef.get("type_label", ""), "method": ef.get("method", "")}
                        for ef in evidence_files
                    ],
                    "per_file_pii": per_file_summary,
                    "current_stage_name": rb.get("current_stage_name"),
                }
        history = body.get("history", [])
        return app.response_class(
            response=json.dumps(chat(body.get("message", ""), incident_context, history)),
            mimetype="application/json",
        )

    @app.get("/exports/<engagement_id>/html")
    def export_html(engagement_id: str):
        from flask import send_file
        s = storage.load_state_obj(engagement_id)
        if not s:
            return "Engagement not found", 404
        rel = s.get("runbook", {}).get("review_pack_html_path", "")
        if not rel:
            return "Review pack not yet generated. Run Stage 8 first.", 404
        # Resolve relative paths from workdir, absolute paths as-is
        p = Path(rel) if Path(rel).is_absolute() else Path(workdir).parent / rel
        if not p.exists():
            return "Review pack file missing. Re-run Stage 8.", 404
        return send_file(str(p.resolve()), mimetype="text/html", as_attachment=False)

    @app.get("/exports/<engagement_id>/json")
    def export_json(engagement_id: str):
        from flask import send_file
        s = storage.load_state_obj(engagement_id)
        if not s:
            return "Engagement not found", 404
        rel = s.get("runbook", {}).get("review_pack_path", "")
        if not rel:
            return "Review pack not yet generated. Run Stage 8 first.", 404
        p = Path(rel) if Path(rel).is_absolute() else Path(workdir).parent / rel
        if not p.exists():
            return "Review pack file missing. Re-run Stage 8.", 404
        iid = s.get("runbook", {}).get("incident", {}).get("incident_id", engagement_id)
        return send_file(str(p.resolve()), mimetype="application/json", as_attachment=True,
                         download_name=f"review-pack-{iid}.json")

    # ── TABLE ALIASES ─────────────────────────────────────────────────────────
    @app.get("/engagements/<engagement_id>/table-aliases")
    def engagement_table_aliases_get(engagement_id: str):
        s = storage.load_state_obj(engagement_id)
        aliases = s.get("table_aliases", {}) if s else {}
        return app.response_class(response=json.dumps({"aliases": aliases}), mimetype="application/json")

    @app.post("/engagements/<engagement_id>/table-aliases")
    def engagement_table_aliases(engagement_id: str):
        s = storage.load_state_obj(engagement_id)
        if not s:
            return redirect(url_for("home"))
        body = request.get_json(force=True, silent=True) or {}
        allowed = {"records", "affected_people", "pii_detections", "regulatory_triggers"}
        aliases = {k: v.strip() for k, v in body.items() if k in allowed and isinstance(v, str)}
        s["table_aliases"] = aliases
        storage.save_state_obj(engagement_id, s)
        return app.response_class(response=json.dumps({"ok": True, "aliases": aliases}), mimetype="application/json")

    # ── FIELD CONFIG ──────────────────────────────────────────────────────────
    @app.get("/engagements/<engagement_id>/field-config")
    def field_config_get(engagement_id: str):
        s = storage.load_state_obj(engagement_id)
        default = {
            "user_fields": [],
            "presets": ["identity", "financial", "medical", "credentials"],
            "auto_discover": True,
        }
        cfg = (s or {}).get("field_config", default)
        return app.response_class(
            response=json.dumps(cfg), mimetype="application/json"
        )

    @app.post("/engagements/<engagement_id>/field-config")
    def field_config_save(engagement_id: str):
        s = storage.load_state_obj(engagement_id)
        if not s:
            return app.response_class(
                response=json.dumps({"error": "Engagement not found"}),
                mimetype="application/json", status=404,
            )
        s["field_config"] = request.get_json(force=True, silent=True) or {}
        storage.save_state_obj(engagement_id, s)
        return app.response_class(
            response=json.dumps({"ok": True}), mimetype="application/json"
        )

    # ── MEDALLION SCHEMA ───────────────────────────────────────────────────────
    @app.get("/engagements/<engagement_id>/schema")
    def engagement_schema(engagement_id: str):
        from vectrion.analysis_db import get_db_path, get_full_schema
        db_path = get_db_path(str(workdir), engagement_id)
        return app.response_class(
            response=json.dumps(get_full_schema(db_path)), mimetype="application/json"
        )

    # ── STAGE RE-RUN ──────────────────────────────────────────────────────────
    @app.post("/engagements/<engagement_id>/rerun/<stage>")
    def engagement_rerun(engagement_id: str, stage: str):
        s = storage.load_state_obj(engagement_id)
        if not s:
            return redirect(url_for("home"))
        stage_order = get_stage_order(workdir)
        if stage not in stage_order:
            return redirect(url_for("engagement_detail", engagement_id=engagement_id))
        stage_idx = stage_order.index(stage)
        # Stages to clear: from stage_idx onwards
        stages_to_clear = stage_order[stage_idx:]
        # Build set of runbook keys to remove
        keys_to_clear: set[str] = set()
        for sid in stages_to_clear:
            keys_to_clear.update(_RERUN_KEYS.get(sid, []))
        # Remove stages from completed_layers
        completed = s.get("completed_layers", [])
        s["completed_layers"] = [c for c in completed if c not in stages_to_clear]
        # Reset current layer to the requested stage
        s["current_layer"] = stage
        # Clear downstream runbook keys
        rb = s.get("runbook", {})
        for k in keys_to_clear:
            rb.pop(k, None)
        s["runbook"] = rb
        storage.save_state_obj(engagement_id, s)
        storage.audit(engagement_id, "stage_rerun", {"stage": stage, "cleared_keys": sorted(keys_to_clear)})
        return redirect(url_for("engagement_detail", engagement_id=engagement_id))

    # ── DELETE ENGAGEMENT ─────────────────────────────────────────────────────
    @app.post("/engagements/<engagement_id>/delete")
    def engagement_delete(engagement_id: str):
        import shutil
        s = storage.load_state_obj(engagement_id)
        if not s:
            return redirect(url_for("home"))
        # Remove state file
        state_path = storage.state_dir / f"{engagement_id}.json"
        if state_path.exists():
            state_path.unlink()
        # Remove vault uploads directory
        vault_path = Path(workdir) / "uploads" / engagement_id
        if vault_path.exists():
            shutil.rmtree(vault_path)
        # Remove audit log
        audit_path = Path(workdir) / "audit" / f"{engagement_id}.jsonl"
        if audit_path.exists():
            audit_path.unlink()
        return redirect(url_for("home"))

    # ── SQL QUERY ─────────────────────────────────────────────────────────────
    @app.post("/engagements/<engagement_id>/query")
    def engagement_query(engagement_id: str):
        s = storage.load_state_obj(engagement_id)
        if not s:
            return app.response_class(
                response=json.dumps({"columns": [], "rows": [], "error": "Engagement not found"}),
                mimetype="application/json", status=404,
            )
        body = request.get_json(force=True, silent=True) or {}
        sql = (body.get("sql") or "").strip()
        if not sql:
            return app.response_class(
                response=json.dumps({"columns": [], "rows": [], "error": "No SQL provided"}),
                mimetype="application/json", status=400,
            )
        rb = s.get("runbook", {})
        try:
            from vectrion.analysis_db import get_db_path, open_db
            db_path = get_db_path(str(workdir), engagement_id)
            conn = open_db(db_path)
            if conn is None:
                # Legacy fallback: build in-memory DB from runbook state
                aliases = s.get("table_aliases", {})
                conn = _build_sqlite_db(rb, aliases)
            cur = conn.execute(sql)
            columns = [d[0] for d in (cur.description or [])]
            rows = [list(r) for r in cur.fetchall()]
            conn.close()
            return app.response_class(
                response=json.dumps({"columns": columns, "rows": rows, "error": None}),
                mimetype="application/json",
            )
        except Exception as exc:
            return app.response_class(
                response=json.dumps({"columns": [], "rows": [], "error": str(exc)}),
                mimetype="application/json",
            )

    # ── DISCOVERY / PROVENANCE ────────────────────────────────────────────────
    @app.get("/engagements/<engagement_id>/discovery/<path:record_id_enc>")
    def engagement_discovery(engagement_id: str, record_id_enc: str):
        record_id = _url_unquote(record_id_enc)
        s = storage.load_state_obj(engagement_id)
        if not s:
            return "Engagement not found.", 404

        # Parse record_id → (filename, index_type, index)
        if ":row:" in record_id:
            fname, _, idx_str = record_id.partition(":row:")
            index_type = "row"
        elif ":chunk:" in record_id:
            fname, _, idx_str = record_id.partition(":chunk:")
            index_type = "chunk"
        else:
            fname = record_id
            index_type = "raw"
            idx_str = "0"

        try:
            idx = int(idx_str)
        except ValueError:
            idx = 0

        # Find the vault file
        vault_records = _load_upload_index(workdir, engagement_id)
        vault_meta = next((f for f in vault_records if f.get("original_name") == fname or f.get("filename") == fname), None)

        # Load extracted text from vault
        vault_dir = _upload_dir(workdir, engagement_id)
        text_content = ""
        if vault_meta:
            txt_path = vault_dir / (vault_meta["filename"] + ".txt")
            if txt_path.exists():
                text_content = txt_path.read_text(encoding="utf-8", errors="replace")
        else:
            # Try to find any .txt file matching the base name
            for txt_path in vault_dir.glob("*.txt"):
                if fname in txt_path.name:
                    text_content = txt_path.read_text(encoding="utf-8", errors="replace")
                    break

        # Build excerpt with highlighted row/chunk
        excerpt_lines: list[tuple[int, str, bool]] = []  # (line_num, text, is_highlight)
        if index_type == "row":
            all_lines = text_content.splitlines()
            header = all_lines[0] if all_lines else ""
            lo = max(0, idx - 3)
            hi = min(len(all_lines), idx + 4)
            for i in range(lo, hi):
                line = all_lines[i] if i < len(all_lines) else ""
                excerpt_lines.append((i, line, i == idx))
            # Always include header if not already in range
            if lo > 1 and header:
                excerpt_lines.insert(0, (0, header, False))
        elif index_type == "chunk":
            paragraphs = text_content.split("\n\n")
            lo = max(0, idx - 1)
            hi = min(len(paragraphs), idx + 2)
            for i in range(lo, hi):
                para = paragraphs[i] if i < len(paragraphs) else ""
                excerpt_lines.append((i, para, i == idx))
        else:
            excerpt_lines.append((0, text_content[:2000], True))

        # PII hits matching this record_id
        rb = s.get("runbook", {})
        pii_hits = [h for h in rb.get("pii_summary", []) if h.get("record_id") == record_id]

        # Render standalone HTML
        def esc(v: str) -> str:
            return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        sha256 = vault_meta.get("sha256", "—") if vault_meta else "—"
        file_type = vault_meta.get("type_label", "—") if vault_meta else "—"

        rows_html = ""
        for line_num, text, highlight in excerpt_lines:
            bg = "background:#FFF9C4;border-left:3px solid #F59E0B;" if highlight else ""
            rows_html += (
                f'<tr style="{bg}">'
                f'<td style="padding:3px 10px;color:#888;font-size:11px;user-select:none;min-width:46px;text-align:right">{line_num}</td>'
                f'<td style="padding:3px 10px 3px 14px;white-space:pre-wrap">{esc(text)}</td>'
                f'</tr>'
            )

        pii_rows_html = ""
        for hit in pii_hits:
            pii_rows_html += (
                f'<tr>'
                f'<td>{esc(hit.get("kind",""))}</td>'
                f'<td>{esc(hit.get("evidence_ref",""))}</td>'
                f'<td>{esc(str(hit.get("confidence",""))[:6])}</td>'
                f'</tr>'
            )

        html = f"""<!doctype html><html><head><meta charset="utf-8"/>
<title>Discovery: {esc(record_id)}</title>
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#07111D;color:#C8D8E8;font-size:13px;margin:0;padding:0;}}
.wrap{{max-width:960px;margin:0 auto;padding:28px 24px 60px;}}
h1{{font-size:18px;font-weight:800;color:#fff;margin-bottom:4px;}}
.meta{{font-size:12px;color:#7A8FA8;margin-bottom:22px;}}
.card{{background:#0D1E32;border:1px solid #172E4A;border-radius:10px;padding:18px 22px;margin-bottom:20px;}}
.card-title{{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;color:#7A8FA8;margin-bottom:14px;}}
table{{border-collapse:collapse;width:100%;}}
.code-table td{{font-family:monospace;font-size:12px;line-height:1.7;border-bottom:1px solid #172E4A;vertical-align:top;color:#A8C8E8;}}
.code-table tr:last-child td{{border-bottom:none;}}
thead th{{background:#172E4A;color:#7A8FA8;font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:9px 12px;text-align:left;}}
tbody td{{padding:9px 12px;border-bottom:1px solid #172E4A;color:#A8C8E8;}}
.back{{color:#3B82F6;text-decoration:none;font-size:13px;font-weight:600;}}
.back:hover{{text-decoration:underline;}}
.badge{{display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600;background:#1F3D62;color:#7A8FA8;}}
</style>
</head>
<body>
<div class="wrap">
  <div style="margin-bottom:18px"><a href="/engagements/{esc(engagement_id)}" class="back">&larr; Back to Engagement</a></div>
  <h1>&#128269; Source Discovery</h1>
  <div class="meta">Record ID: <code style="color:#A8C8E8">{esc(record_id)}</code></div>

  <div class="card">
    <div class="card-title">File Information</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;font-size:13px">
      <div><div style="color:#7A8FA8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Filename</div><div style="color:#fff;font-weight:600">{esc(fname)}</div></div>
      <div><div style="color:#7A8FA8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Type</div><div>{esc(file_type)}</div></div>
      <div><div style="color:#7A8FA8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">SHA-256</div><div style="font-family:monospace;font-size:11px;color:#7A8FA8">{esc(sha256[:24])}...</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Source Excerpt &mdash; {esc(index_type.title())} {idx} <span class="badge" style="margin-left:8px;vertical-align:middle">highlighted</span></div>
    <div style="overflow-x:auto;border-radius:7px;border:1px solid #172E4A;background:#07111D">
      <table class="code-table"><tbody>{rows_html}</tbody></table>
    </div>
    {'<div style="margin-top:10px;font-size:11px;color:#7A8FA8">&#9888; Yellow row is the matched record. ±3 rows of context shown.</div>' if index_type == 'row' else ''}
  </div>

  {'<div class="card"><div class="card-title">PII Detections for this Record</div><div style="overflow-x:auto"><table><thead><tr><th>Kind</th><th>Position (evidence_ref)</th><th>Confidence</th></tr></thead><tbody>' + pii_rows_html + '</tbody></table></div></div>' if pii_hits else '<div class="card"><div class="card-title">PII Detections</div><div style="color:#7A8FA8;font-size:13px">No PII hits recorded for this record ID.</div></div>'}
</div>
</body></html>"""
        return html

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=8090)


if __name__ == "__main__":
    main()
