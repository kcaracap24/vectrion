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

# ---------------------------------------------------------------------------
# Shared layout pieces (top-bar + chat bubble injected into every page)
# ---------------------------------------------------------------------------

_LAYOUT_HEAD = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vectorian — {{ page_title }}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body { font-family: Arial, sans-serif; margin: 0; color: #111; background: #f5f6fa; }

    /* Top bar */
    .topbar {
      display: flex; align-items: center; gap: 16px;
      background: #1a1a2e; color: #fff; padding: 0 24px; height: 52px;
    }
    .topbar .brand { font-size: 20px; font-weight: bold; letter-spacing: 1px; color: #e0c97f; }
    .topbar nav a {
      color: #ccc; text-decoration: none; font-size: 14px; padding: 6px 12px;
      border-radius: 6px; transition: background 0.15s;
    }
    .topbar nav a:hover, .topbar nav a.active { background: rgba(255,255,255,0.12); color: #fff; }
    .topbar nav { margin-left: auto; display: flex; gap: 4px; }

    /* Page wrapper */
    .page { max-width: 1100px; margin: 32px auto; padding: 0 24px; }

    /* Cards */
    .card {
      background: #fff; border: 1px solid #e0e0e0; border-radius: 12px;
      padding: 20px 24px; margin-bottom: 18px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .card h3 { margin: 0 0 14px; font-size: 16px; }

    /* Form elements */
    input[type=text], input[type=number], select, textarea {
      font-size: 14px; padding: 7px 10px; border: 1px solid #ccc;
      border-radius: 6px; width: 100%;
    }
    input[type=text]:focus, input[type=number]:focus, select:focus, textarea:focus {
      outline: none; border-color: #5b6ee1;
    }
    button, .btn {
      font-size: 14px; padding: 8px 16px; cursor: pointer;
      border: none; border-radius: 6px; background: #5b6ee1; color: #fff;
      text-decoration: none; display: inline-block;
    }
    button:hover, .btn:hover { background: #4a5dcc; }
    button.secondary { background: #f0f0f0; color: #333; }
    button.secondary:hover { background: #e0e0e0; }
    button.danger { background: #e53935; }
    button.danger:hover { background: #c62828; }
    button.sm { font-size: 12px; padding: 4px 10px; }

    .muted { color: #666; font-size: 13px; }
    .badge {
      display: inline-block; padding: 2px 10px; border-radius: 999px;
      background: #eef; font-size: 12px; margin-right: 4px;
    }
    .badge.done { background: #dff6e5; color: #1a7a3a; }
    .stage-pill {
      display: inline-block; padding: 3px 10px; border-radius: 999px;
      background: #f4f4f4; margin: 2px; font-size: 12px;
    }
    .stage-pill.done { background: #dff6e5; color: #1a7a3a; }
    .stage-pill.current { background: #fff3cd; color: #856404; font-weight: bold; }

    pre {
      background: #f6f8fa; padding: 12px; border-radius: 8px;
      white-space: pre-wrap; max-height: 380px; overflow: auto;
      font-size: 13px;
    }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #e0e0e0; padding: 8px 10px; text-align: left; font-size: 13px; }
    th { background: #f7f7f7; font-weight: 600; }
    tr:hover td { background: #fafafa; }

    /* Setup wizard steps */
    .steps { display: flex; gap: 0; margin-bottom: 28px; }
    .step {
      flex: 1; text-align: center; padding: 10px; font-size: 13px;
      background: #f0f0f0; border: 1px solid #ddd;
    }
    .step:first-child { border-radius: 8px 0 0 8px; }
    .step:last-child { border-radius: 0 8px 8px 0; }
    .step.active { background: #5b6ee1; color: #fff; font-weight: bold; border-color: #5b6ee1; }
    .step.done-step { background: #dff6e5; color: #1a7a3a; border-color: #b8e6c8; }

    /* --- Chat bubble --- */
    #chat-bubble {
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    }
    #chat-toggle {
      width: 56px; height: 56px; border-radius: 50%; background: #1a1a2e;
      color: #e0c97f; font-size: 26px; border: none; cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,0.25); display: flex;
      align-items: center; justify-content: center;
    }
    #chat-panel {
      display: none; position: absolute; bottom: 68px; right: 0;
      width: 360px; background: #fff; border: 1px solid #ddd;
      border-radius: 14px; box-shadow: 0 8px 32px rgba(0,0,0,0.18);
      flex-direction: column; overflow: hidden;
    }
    #chat-panel.open { display: flex; }
    #chat-header {
      background: #1a1a2e; color: #e0c97f; padding: 12px 16px;
      font-weight: bold; font-size: 14px; display: flex;
      justify-content: space-between; align-items: center;
    }
    #chat-close { cursor: pointer; background: none; border: none; color: #e0c97f; font-size: 18px; }
    #chat-messages {
      flex: 1; overflow-y: auto; padding: 14px; max-height: 320px;
      display: flex; flex-direction: column; gap: 10px;
    }
    .chat-msg { max-width: 85%; padding: 8px 12px; border-radius: 10px; font-size: 13px; line-height: 1.5; }
    .chat-msg.bot { background: #f0f0f7; align-self: flex-start; }
    .chat-msg.user { background: #5b6ee1; color: #fff; align-self: flex-end; }
    #chat-input-row { display: flex; gap: 8px; padding: 10px 12px; border-top: 1px solid #eee; }
    #chat-input { flex: 1; font-size: 13px; padding: 7px 10px; border: 1px solid #ccc; border-radius: 6px; }
    #chat-send { padding: 7px 14px; font-size: 13px; }
  </style>
</head>
<body>
<div class="topbar">
  <span class="brand">&#9670; Vectorian</span>
  <nav>
    <a href="/" class="{{ 'active' if active_nav == 'dashboard' else '' }}">Dashboard</a>
    <a href="/config" class="{{ 'active' if active_nav == 'config' else '' }}">Configuration</a>
  </nav>
</div>
"""

_LAYOUT_CHAT = """
<!-- Floating chat bubble -->
<div id="chat-bubble">
  <div id="chat-panel">
    <div id="chat-header">
      <span>&#129302; Vectorian AI</span>
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
  const STORAGE_KEY = 'vectorian_chat_history';
  let opened = false;

  function getHistory() {
    try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; }
  }
  function saveHistory(h) { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(h)); }

  function renderMessages() {
    const box = document.getElementById('chat-messages');
    const history = getHistory();
    box.innerHTML = '';
    history.forEach(m => {
      const div = document.createElement('div');
      div.className = 'chat-msg ' + m.role;
      div.textContent = m.text;
      box.appendChild(div);
    });
    box.scrollTop = box.scrollHeight;
  }

  function addMessage(role, text) {
    const h = getHistory();
    h.push({role, text});
    saveHistory(h);
    renderMessages();
  }

  window.toggleChat = function() {
    const panel = document.getElementById('chat-panel');
    opened = !opened;
    panel.classList.toggle('open', opened);
    if (opened && getHistory().length === 0) {
      addMessage('bot', 'Hi, I am your Breach Agent Vectorian! How can I help you today?');
    }
    if (opened) {
      renderMessages();
      document.getElementById('chat-input').focus();
    }
  };

  window.sendChat = function() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';
    addMessage('user', msg);

    const incidentId = document.body.dataset.incidentId || '';
    const payload = {message: msg};
    if (incidentId) payload.incident_id = incidentId;

    fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(d => addMessage('bot', d.reply || 'No response.'))
    .catch(() => addMessage('bot', 'Error reaching Vectorian. Please try again.'));
  };

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && document.activeElement === document.getElementById('chat-input')) {
      sendChat();
    }
  });
})();
</script>
"""

_LAYOUT_FOOT = """
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Index / Dashboard
# ---------------------------------------------------------------------------

INDEX_TMPL = _LAYOUT_HEAD + """
<div class="page">
  <div class="card">
    <h3>Create Incident</h3>
    <form method="post" action="/incidents/create" style="display:flex;gap:10px;align-items:center">
      <input type="text" name="incident_id" id="inc-id-input"
             placeholder="INC-2026-0001" style="max-width:260px"
             oninput="updatePreview()" required />
      <button type="submit">Create</button>
    </form>
    <p class="muted" style="margin-top:8px">Preview: <span id="inc-preview" style="font-family:monospace"></span></p>
  </div>

  <div class="card">
    <h3>Incidents</h3>
    {% if incidents %}
      <table>
        <tr><th>Incident ID</th><th>Current Stage</th><th>Completed</th></tr>
        {% for i in incidents %}
        <tr>
          <td><a href="/incidents/{{ i.id }}">{{ i.id }}</a></td>
          <td>{{ i.stage_name }}</td>
          <td class="muted">{{ i.completed }}</td>
        </tr>
        {% endfor %}
      </table>
    {% else %}
      <p class="muted">No incidents yet. Create one above.</p>
    {% endif %}
  </div>

  <p class="muted">{{ disclaimer }}</p>
</div>
""" + _LAYOUT_CHAT + """
<script>
(function() {
  var fmt = {{ format_json | safe }};
  function buildId(val) {
    if (!val) return '';
    return val;
  }
  document.getElementById('inc-id-input').setAttribute('placeholder', fmt.prefix + fmt.separator + (fmt.year ? '2026' + fmt.separator : '') + '0001');
  window.updatePreview = function() {
    var v = document.getElementById('inc-id-input').value;
    document.getElementById('inc-preview').textContent = v || '—';
  };
})();
</script>
""" + _LAYOUT_FOOT

# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------

SETUP_TMPL = _LAYOUT_HEAD + """
<div class="page">
  <h2 style="margin-bottom:20px">First-Run Setup</h2>
  <div class="steps">
    <div class="step {{ 'active' if step == 1 else 'done-step' if step > 1 else '' }}">1. Incident Code Format</div>
    <div class="step {{ 'active' if step == 2 else '' }}">2. Stage Names</div>
  </div>

  {% if step == 1 %}
  <div class="card">
    <h3>Incident Code Format</h3>
    <form method="post" action="/setup/step1" id="fmt-form">
      <table style="width:auto;margin-bottom:16px">
        <tr>
          <td style="padding:8px"><label>Prefix</label></td>
          <td style="padding:8px"><input type="text" name="prefix" value="{{ cfg.incident_code_format.prefix }}" style="width:100px" oninput="updatePreview()" /></td>
        </tr>
        <tr>
          <td style="padding:8px"><label>Separator</label></td>
          <td style="padding:8px">
            <select name="separator" onchange="updatePreview()">
              <option value="-" {{ 'selected' if cfg.incident_code_format.separator == '-' }}>- (hyphen)</option>
              <option value="_" {{ 'selected' if cfg.incident_code_format.separator == '_' }}>_ (underscore)</option>
              <option value="/" {{ 'selected' if cfg.incident_code_format.separator == '/' }}>/ (slash)</option>
            </select>
          </td>
        </tr>
        <tr>
          <td style="padding:8px"><label>Include Year</label></td>
          <td style="padding:8px">
            <input type="checkbox" name="year" id="year-chk" onchange="updatePreview()"
                   {{ 'checked' if cfg.incident_code_format.year }} /> Yes
          </td>
        </tr>
        <tr>
          <td style="padding:8px"><label>Digit Count</label></td>
          <td style="padding:8px">
            <input type="number" name="digits" min="2" max="8"
                   value="{{ cfg.incident_code_format.digits }}" style="width:80px"
                   oninput="updatePreview()" />
          </td>
        </tr>
      </table>
      <p><strong>Preview:</strong> <span id="fmt-preview" style="font-family:monospace;font-size:15px"></span></p>
      <button type="submit">Next &rarr;</button>
    </form>
  </div>
  <script>
  function updatePreview() {
    var prefix = document.querySelector('[name=prefix]').value || 'INC';
    var sep = document.querySelector('[name=separator]').value || '-';
    var year = document.getElementById('year-chk').checked;
    var digits = parseInt(document.querySelector('[name=digits]').value) || 4;
    var seq = '1'.padStart(digits, '0');
    var parts = [prefix];
    if (year) parts.push('2026');
    parts.push(seq);
    document.getElementById('fmt-preview').textContent = parts.join(sep);
  }
  updatePreview();
  </script>

  {% elif step == 2 %}
  <div class="card">
    <h3>Stage Names</h3>
    <form method="post" action="/setup/save">
      <table id="stages-table">
        <tr><th>#</th><th>Default Name</th><th>Custom Name (optional)</th></tr>
        {% for s in cfg.stages %}
        <tr>
          <td>{{ s.id }}</td>
          <td>{{ s.name }}</td>
          <td>
            <input type="hidden" name="id[]" value="{{ s.id }}" />
            <input type="hidden" name="name[]" value="{{ s.name }}" />
            <input type="text" name="custom_name[]" value="{{ s.custom_name }}" placeholder="Leave blank to use default" />
          </td>
        </tr>
        {% endfor %}
      </table>
      <div style="margin-top:14px;display:flex;gap:10px">
        <button type="button" class="secondary" onclick="addStage()">+ Add Custom Stage</button>
        <button type="submit">Finish Setup &rarr;</button>
      </div>
    </form>
  </div>
  <script>
  var customCount = 0;
  function addStage() {
    customCount++;
    var table = document.getElementById('stages-table').querySelector('tbody') ||
                document.getElementById('stages-table');
    var tr = document.createElement('tr');
    var cid = 'custom_' + customCount;
    tr.innerHTML = '<td>' + cid + '</td><td><em>Custom Stage</em></td>' +
      '<td>' +
        '<input type="hidden" name="id[]" value="' + cid + '" />' +
        '<input type="hidden" name="name[]" value="Custom Stage" />' +
        '<input type="text" name="custom_name[]" placeholder="Enter stage name" />' +
      '</td>';
    table.appendChild(tr);
  }
  </script>
  {% endif %}
</div>
""" + _LAYOUT_CHAT + _LAYOUT_FOOT

# ---------------------------------------------------------------------------
# Configuration panel
# ---------------------------------------------------------------------------

CONFIG_TMPL = _LAYOUT_HEAD + """
<div class="page">
  <h2 style="margin-bottom:4px">Configuration</h2>
  <p class="muted" style="margin-bottom:20px">Manage incident format and stages.</p>

  <form method="post" action="/config/save">
    <div class="card">
      <h3>Incident Code Format</h3>
      <table style="width:auto">
        <tr>
          <td style="padding:8px"><label>Prefix</label></td>
          <td style="padding:8px"><input type="text" name="prefix" value="{{ cfg.incident_code_format.prefix }}" style="width:100px" oninput="updatePreview()" /></td>
        </tr>
        <tr>
          <td style="padding:8px"><label>Separator</label></td>
          <td style="padding:8px">
            <select name="separator" onchange="updatePreview()">
              <option value="-" {{ 'selected' if cfg.incident_code_format.separator == '-' }}>- (hyphen)</option>
              <option value="_" {{ 'selected' if cfg.incident_code_format.separator == '_' }}>_ (underscore)</option>
              <option value="/" {{ 'selected' if cfg.incident_code_format.separator == '/' }}>/ (slash)</option>
            </select>
          </td>
        </tr>
        <tr>
          <td style="padding:8px"><label>Include Year</label></td>
          <td style="padding:8px">
            <input type="checkbox" name="year" id="year-chk" onchange="updatePreview()"
                   {{ 'checked' if cfg.incident_code_format.year }} /> Yes
          </td>
        </tr>
        <tr>
          <td style="padding:8px"><label>Digit Count</label></td>
          <td style="padding:8px">
            <input type="number" name="digits" min="2" max="8"
                   value="{{ cfg.incident_code_format.digits }}" style="width:80px"
                   oninput="updatePreview()" />
          </td>
        </tr>
      </table>
      <p style="margin-top:10px"><strong>Preview:</strong>
        <span id="fmt-preview" style="font-family:monospace;font-size:15px"></span></p>
    </div>

    <div class="card">
      <h3>Stages</h3>
      <table id="stages-table">
        <thead>
          <tr>
            <th style="width:60px">Order</th>
            <th>Stage Name</th>
            <th>Custom Name</th>
            <th>Owner</th>
            <th>Notes</th>
            <th style="width:70px">Enabled</th>
            <th style="width:60px">Delete</th>
          </tr>
        </thead>
        <tbody id="stages-body">
          {% for i, s in stages_enum %}
          <tr id="row-{{ s.id }}">
            <td style="text-align:center">
              <button type="button" class="sm secondary" onclick="moveRow('{{ s.id }}', -1)">&#8593;</button>
              <button type="button" class="sm secondary" onclick="moveRow('{{ s.id }}', 1)">&#8595;</button>
            </td>
            <td>
              <input type="hidden" name="id[]" value="{{ s.id }}" />
              {{ s.name }}
            </td>
            <td><input type="text" name="custom_name[]" value="{{ s.custom_name }}" placeholder="Override name" /></td>
            <td><input type="text" name="owner[]" value="{{ s.owner }}" placeholder="Assignee" /></td>
            <td><textarea name="notes[]" rows="1" style="resize:vertical">{{ s.notes }}</textarea></td>
            <td style="text-align:center">
              <input type="checkbox" name="enabled_{{ s.id }}" {{ 'checked' if s.enabled }} />
            </td>
            <td style="text-align:center">
              <button type="button" class="sm danger" onclick="deleteRow('{{ s.id }}')">&#x2715;</button>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      <div style="margin-top:12px">
        <button type="button" class="secondary" onclick="addStage()">+ Add Stage</button>
      </div>
    </div>

    <div style="display:flex;gap:10px;margin-bottom:32px">
      <button type="submit">Save Configuration</button>
      <a href="/" class="btn secondary">Cancel</a>
    </div>
  </form>
</div>
""" + _LAYOUT_CHAT + """
<script>
var customCount = {{ custom_count }};

function updatePreview() {
  var prefix = document.querySelector('[name=prefix]').value || 'INC';
  var sep = document.querySelector('[name=separator]').value || '-';
  var year = document.getElementById('year-chk').checked;
  var digits = parseInt(document.querySelector('[name=digits]').value) || 4;
  var seq = '1'.padStart(digits, '0');
  var parts = [prefix];
  if (year) parts.push('2026');
  parts.push(seq);
  document.getElementById('fmt-preview').textContent = parts.join(sep);
}
updatePreview();

function moveRow(id, dir) {
  var tbody = document.getElementById('stages-body');
  var row = document.getElementById('row-' + id);
  if (!row) return;
  if (dir === -1 && row.previousElementSibling) {
    tbody.insertBefore(row, row.previousElementSibling);
  } else if (dir === 1 && row.nextElementSibling) {
    tbody.insertBefore(row.nextElementSibling, row);
  }
}

function deleteRow(id) {
  var row = document.getElementById('row-' + id);
  if (row) row.remove();
}

function addStage() {
  customCount++;
  var cid = 'custom_' + customCount;
  var tbody = document.getElementById('stages-body');
  var tr = document.createElement('tr');
  tr.id = 'row-' + cid;
  tr.innerHTML =
    '<td style="text-align:center">' +
      '<button type="button" class="sm secondary" onclick="moveRow(\\'' + cid + '\\', -1)">&#8593;</button>' +
      '<button type="button" class="sm secondary" onclick="moveRow(\\'' + cid + '\\', 1)">&#8595;</button>' +
    '</td>' +
    '<td>' +
      '<input type="hidden" name="id[]" value="' + cid + '" />' +
      'Custom Stage' +
    '</td>' +
    '<td><input type="text" name="custom_name[]" placeholder="Stage name" /></td>' +
    '<td><input type="text" name="owner[]" placeholder="Assignee" /></td>' +
    '<td><textarea name="notes[]" rows="1" style="resize:vertical"></textarea></td>' +
    '<td style="text-align:center"><input type="checkbox" name="enabled_' + cid + '" checked /></td>' +
    '<td style="text-align:center"><button type="button" class="sm danger" onclick="deleteRow(\\'' + cid + '\\')">&#x2715;</button></td>';
  tbody.appendChild(tr);
}
</script>
""" + _LAYOUT_FOOT

# ---------------------------------------------------------------------------
# Incident detail
# ---------------------------------------------------------------------------

DETAIL_TMPL = _LAYOUT_HEAD + """
<div class="page" data-incident-id="{{ incident_id }}">
  <p><a href="/">&#8592; Back to Dashboard</a></p>
  <h2>Incident {{ incident_id }}</h2>

  <div class="card">
    <b>Current Stage:</b> {{ current_stage_name or 'Complete' }}
    <div style="margin-top:12px">
      {% for s in all_stages %}
        <span class="stage-pill
          {% if s.id in completed %}done
          {% elif s.id == current_layer %}current
          {% endif %}">
          {{ s.id }}: {{ s.custom_name or s.name }}
        </span>
      {% endfor %}
    </div>
    <p class="muted" style="margin-top:8px">
      Completed: {{ completed|join(', ') if completed else '(none)' }}
    </p>
    {% if current_layer %}
    <form method="post" action="/incidents/{{ incident_id }}/proceed" style="margin-top:10px">
      <button type="submit">Run Stage {{ current_layer }}: {{ current_stage_name }}</button>
    </form>
    {% else %}
    <p style="color:#1a7a3a;font-weight:bold;margin-top:10px">&#10003; Runbook complete.</p>
    {% endif %}
  </div>

  <div class="card">
    <h3>Runbook Output</h3>
    <pre>{{ runbook_json }}</pre>
  </div>

  <p class="muted">{{ disclaimer }}</p>
</div>
""" + _LAYOUT_CHAT + """
<script>
  // Expose incident id to chat bubble
  document.querySelector('.page[data-incident-id]')
    && (document.body.dataset.incidentId = document.querySelector('.page[data-incident-id]').dataset.incidentId);
</script>
""" + _LAYOUT_FOOT


# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------

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
                    "completed": ", ".join(s.get("completed_layers", [])),
                })
            except Exception:
                continue
        return rows

    @app.get("/")
    def home():
        if not is_setup_complete(workdir):
            return redirect(url_for("setup"))
        cfg = load_config(workdir)
        return render_template_string(
            INDEX_TMPL,
            page_title="Dashboard",
            active_nav="dashboard",
            incidents=_list_incidents(),
            disclaimer=LEGAL_DISCLAIMER,
            format_json=json.dumps(cfg.get("incident_code_format", {})),
        )

    @app.get("/setup")
    def setup():
        cfg = load_config(workdir)
        step = int(request.args.get("step", 1))
        return render_template_string(
            SETUP_TMPL,
            page_title="Setup",
            active_nav="",
            cfg=cfg,
            step=step,
        )

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
        new_stages = []
        for i, sid in enumerate(ids):
            new_stages.append({
                "id": sid,
                "name": names[i] if i < len(names) else sid,
                "custom_name": custom_names[i] if i < len(custom_names) else "",
                "enabled": True,
                "owner": "",
                "notes": "",
            })
        cfg["stages"] = new_stages
        cfg["setup_complete"] = True
        save_config(workdir, cfg)
        return redirect(url_for("home"))

    @app.get("/config")
    def config_panel():
        cfg = load_config(workdir)
        stages = cfg.get("stages", [])
        # Count existing custom stages for JS counter
        custom_count = sum(1 for s in stages if s["id"].startswith("custom_"))
        return render_template_string(
            CONFIG_TMPL,
            page_title="Configuration",
            active_nav="config",
            cfg=cfg,
            stages_enum=list(enumerate(stages)),
            custom_count=custom_count,
        )

    @app.post("/config/save")
    def config_save():
        cfg = load_config(workdir)
        ids = request.form.getlist("id[]")
        custom_names = request.form.getlist("custom_name[]")
        owners = request.form.getlist("owner[]")
        notes_list = request.form.getlist("notes[]")

        new_stages = []
        for i, sid in enumerate(ids):
            # Find original stage for its base name
            orig = next((s for s in cfg.get("stages", []) if s["id"] == sid), None)
            base_name = orig["name"] if orig else "Custom Stage"
            new_stages.append({
                "id": sid,
                "name": base_name,
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

    @app.post("/incidents/create")
    def create_incident():
        incident_id = (request.form.get("incident_id") or "").strip()
        if not incident_id:
            return redirect(url_for("home"))
        if not storage.load_state_obj(incident_id):
            first_stage = get_stage_order(workdir)
            start = first_stage[0] if first_stage else "1"
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
            page_title=incident_id,
            active_nav="dashboard",
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
            storage.audit(
                incident_id, "proceed_ui",
                {"completed": current, "next": s.get("current_layer")},
            )
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
