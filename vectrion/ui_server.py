from __future__ import annotations

import json
import re
from pathlib import Path

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
  position:sticky;top:0;z-index:200;box-shadow:0 2px 20px rgba(0,0,0,0.45);
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
nav a.active{background:var(--navy-3);color:#fff;border-color:var(--blue);}

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
}
.stat-num{font-size:28px;font-weight:800;color:var(--navy);line-height:1;}
.stat-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);}
.stat-icon{font-size:22px;margin-bottom:4px;}

/* ── CARDS ── */
.card{
  background:var(--white);border:1px solid var(--border);border-radius:12px;
  padding:24px 28px;margin-bottom:22px;box-shadow:0 2px 10px rgba(10,22,40,0.07);
}
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
  text-decoration:none;transition:all 0.15s;letter-spacing:0.3px;
}
.btn-primary{background:var(--blue);color:#fff;box-shadow:0 2px 10px rgba(29,78,216,0.3);}
.btn-primary:hover{background:#1a44c4;box-shadow:0 4px 16px rgba(29,78,216,0.45);transform:translateY(-1px);}
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
tbody tr:hover td{background:#F0F6FF;}

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
.progress-fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--blue-light));border-radius:999px;transition:width 0.3s;}

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
.tab-bar{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:22px;}
.tab-btn{
  padding:11px 24px;font-size:13px;font-weight:600;color:var(--muted);
  border:none;background:none;cursor:pointer;border-bottom:2px solid transparent;
  margin-bottom:-2px;transition:all 0.15s;letter-spacing:0.3px;
}
.tab-btn:hover{color:var(--navy);}
.tab-btn.active{color:var(--blue);border-bottom-color:var(--blue);font-weight:700;}
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
    <a href="/config" class="{{ 'active' if active_nav=='config' else '' }}">Configuration</a>
  </nav>
</div>"""

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
  if(!gH().length)addMsg('bot','Hello, Operator. I\'m Vectorian. I can guide you through the 9-stage breach workflow, answer compliance questions, help configure this platform, or take action for you. What do you need?',[]);
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
<body>""" + _TOPBAR + """
<div class="page">
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
          <td><a href="/engagements/{{ e.id }}" class="btn btn-secondary btn-sm">Open &rarr;</a></td>
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
        <div class="card-header"><div class="card-title">&#127970; Client Profile</div></div>
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
        <div class="divider"></div>
        <div class="section-title">&#9670; Engagement ID</div>
        <div class="form-row form-row-2">
          <div class="form-group">
            <label>Engagement ID *</label>
            <input type="text" name="engagement_id" id="eng-id-input" value="{{ suggested_id }}" required/>
            <div class="input-hint">Auto-generated from your format config — edit as needed</div>
          </div>
          <div class="form-group">
            <label>Preview</label>
            <div style="padding:9px 14px;background:var(--navy);border-radius:7px;font-family:monospace;font-size:15px;color:#fff;letter-spacing:2px;font-weight:700">
              <span id="id-preview">{{ suggested_id }}</span>
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
""" + _ROBOT_PANEL + """
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
""" + _ROBOT_PANEL + """
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
""" + _ROBOT_PANEL + """
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
      <div style="font-family:monospace;font-size:13px;color:var(--silver-3);background:rgba(0,0,0,0.2);padding:6px 14px;border-radius:7px;font-weight:700;letter-spacing:2px">
        {{ engagement_id }}
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
  <div class="tab-bar">
    <button class="tab-btn active" data-tab="overview" onclick="switchTab('overview')">&#9776;&nbsp; Overview</button>
    <button class="tab-btn" data-tab="vault" onclick="switchTab('vault')">&#128274;&nbsp; Data Vault
      {% if vault_files %}<span style="margin-left:6px;background:var(--blue);color:#fff;border-radius:999px;font-size:10px;padding:1px 7px;font-weight:700">{{ vault_files|length }}</span>{% endif %}
    </button>
    <button class="tab-btn" data-tab="runbook" onclick="switchTab('runbook')">&#128200;&nbsp; Analysis
      {% if completed %}<span style="margin-left:6px;background:var(--success);color:#fff;border-radius:999px;font-size:10px;padding:1px 7px;font-weight:700">{{ completed|length }}</span>{% endif %}
    </button>
  </div>

  <!-- TAB: OVERVIEW -->
  <div class="tab-pane active" id="tab-overview">
    <div class="card">
      <div class="card-header">
        <div class="card-title">&#9776; Stage Progress</div>
        <div style="margin-left:auto;font-size:12px;color:var(--muted)">{{ completed|length }}/{{ all_stages|length }} stages complete</div>
      </div>
      <div style="margin-bottom:16px">
        {% for s in all_stages %}
          <span class="stage-pill{% if s.id in completed %} done{% elif s.id==current_layer %} current{% endif %}">
            {{ s.id }}: {{ s.custom_name or s.name }}{% if s.id in completed %} &#10003;{% endif %}
          </span>
        {% endfor %}
      </div>
      {% if current_layer %}
      <div style="background:var(--blue-pale);border:1px solid #BFDBFE;border-radius:9px;padding:16px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
        <div>
          <div style="font-weight:700;color:var(--navy)">Next: Stage {{ current_layer }}</div>
          <div class="muted" style="font-size:12px;margin-top:2px">{{ current_stage_name }}</div>
        </div>
        <form method="post" action="/engagements/{{ engagement_id }}/proceed">
          <button class="btn btn-primary" type="submit">&#9658;&nbsp; Run Stage {{ current_layer }}</button>
        </form>
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
  <div class="tab-pane" id="tab-vault">
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
      <input type="file" id="file-input" multiple/>
      <div class="upload-zone-icon">&#128228;</div>
      <div class="upload-zone-title">Drop evidence files here or click to browse</div>
      <div class="upload-zone-sub">All formats processed automatically — no configuration needed</div>
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
        <span class="badge badge-blue" style="margin-left:auto">Complete</span>
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
        <span class="badge badge-blue" style="margin-left:auto">Complete</span>
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
    </div>
    {% endif %}

    <!-- STAGE 3: SENSITIVITY CLASSIFICATION -->
    {% if "3" in completed and rb_sensitivity %}
    <div class="card" style="margin-bottom:18px">
      <div class="card-header">
        <div class="card-title">&#127777; Stage 3 — Sensitivity Classification</div>
        <span class="badge badge-blue" style="margin-left:auto">Complete</span>
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
        <span class="badge badge-blue" style="margin-left:auto">Complete</span>
      </div>
      {% if rb_entity_resolution %}
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px">
        <div class="stat-card">
          <div class="stat-num">{{ rb_entity_resolution.get("total_records","—") }}</div>
          <div class="stat-label">Total Records</div>
        </div>
        <div class="stat-card">
          <div class="stat-num" style="color:var(--danger)">{{ rb_entity_resolution.get("unique_affected_people","—") }}</div>
          <div class="stat-label">Unique Individuals</div>
        </div>
        <div class="stat-card">
          <div class="stat-num">{{ rb_entity_resolution.get("dedup_emails","—") }}</div>
          <div class="stat-label">Deduplicated by Email</div>
        </div>
      </div>
      {% endif %}
      {% if rb_affected %}
      <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Name</th><th>Email</th><th>SSN</th><th>DOB</th><th>MRN</th><th>Source</th></tr></thead>
        <tbody>
        {% for p in rb_affected %}
        <tr>
          <td style="font-weight:600">{{ p.name or "—" }}</td>
          <td style="font-family:monospace;font-size:12px">{{ p.email or "—" }}</td>
          <td style="text-align:center">{{ "&#9888;" if p.ssn else "—" }}</td>
          <td style="text-align:center">{{ "&#10003;" if p.dob else "—" }}</td>
          <td style="text-align:center">{{ "&#10003;" if p.mrn else "—" }}</td>
          <td style="font-size:11px;color:var(--muted)">{{ p.source or "—" }}</td>
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
        <span class="badge badge-blue" style="margin-left:auto">Complete</span>
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
        {% if rb_legal.get("notification_required") %}
        <span class="badge" style="margin-left:auto;background:var(--danger-bg);color:var(--danger);font-weight:700">&#9888; Notification Required</span>
        {% else %}
        <span class="badge badge-blue" style="margin-left:auto">Complete</span>
        {% endif %}
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
        <span class="badge badge-blue" style="margin-left:auto">Complete</span>
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
        <span class="badge" style="margin-left:auto;background:var(--success-bg);color:var(--success);font-weight:700">&#10003; Ready for Review</span>
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
        <span class="badge" style="margin-left:auto;background:var(--warn-bg);color:var(--warn);font-weight:700">&#128336; Awaiting Approval</span>
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

  <div class="disclaimer">{{ disclaimer }}</div>
</div>
""" + _ROBOT_PANEL + """
</div>
<script>
// ── Tabs ──
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
}

// ── Upload ──
const zone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
if (zone) {
  ['dragenter','dragover'].forEach(ev => zone.addEventListener(ev, e => {e.preventDefault(); zone.classList.add('drag-over');}));
  ['dragleave','drop'].forEach(ev => zone.addEventListener(ev, e => {e.preventDefault(); zone.classList.remove('drag-over');}));
  zone.addEventListener('drop', e => handleFiles(e.dataTransfer.files));
  zone.addEventListener('click', e => {if(e.target !== fileInput) fileInput.click();});
  fileInput.addEventListener('change', e => handleFiles(e.target.files));
}

function handleFiles(fl) { Array.from(fl).forEach(f => uploadFile(f)); }

function formatSize(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(1) + ' MB';
}
function escHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
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


# ─────────────────────────────────────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────────────────────────────────────

def create_app(workdir: str = ".vectrion", data_dir: str = None) -> Flask:
    app = Flask(__name__)
    app.jinja_env.filters["format_number"] = _format_number
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
        )

    @app.post("/engagements/<engagement_id>/proceed")
    def engagement_proceed(engagement_id: str):
        s = storage.load_state_obj(engagement_id)
        if not s:
            return redirect(url_for("home"))
        current = s.get("current_layer")
        if current:
            vault_dir = _upload_dir(workdir, engagement_id)
            updated = run_layer(
                s.get("runbook", {}), current, dd, Path(workdir) / "exports",
                vault_dir=vault_dir,
                engagement_id=engagement_id,
                context=s,
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
        incident_context = storage.load_state_obj(incident_id) if incident_id else None
        return app.response_class(
            response=json.dumps(chat(body.get("message", ""), incident_context)),
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

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=8090)


if __name__ == "__main__":
    main()
