from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request

from vectrion.chat import chat
from vectrion.constants import LEGAL_DISCLAIMER
from vectrion.runbook import next_layer, run_layer
from vectrion.storage import Storage


def create_app(workdir: str = ".vectrion", data_dir: str = None) -> Flask:
    app = Flask(__name__)
    storage = Storage(Path(workdir))
    dd = Path(data_dir) if data_dir else Path(__file__).resolve().parent / "data"

    @app.post("/api/chat")
    def api_chat():
        body = request.get_json(force=True)
        incident_id = body.get("incident_id")
        incident_context = storage.load_state_obj(incident_id) if incident_id else None
        reply = chat(body.get("message", ""), incident_context)
        return jsonify({"reply": reply})

    @app.post("/trigger")
    def trigger():
        body = request.get_json(force=True)
        incident_id = body.get("incident_id")
        if not incident_id:
            return jsonify({"error": "incident_id required"}), 400
        if storage.load_state_obj(incident_id):
            return jsonify({"error": "already exists"}), 409
        state = {"incident_id": incident_id, "current_layer": "1", "completed_layers": [], "runbook": {}}
        storage.save_state_obj(incident_id, state)
        storage.audit(incident_id, "trigger", {"source": "http"})
        return jsonify({"ok": True, "incident_id": incident_id, "current_layer": "1"})

    @app.get("/status/<incident_id>")
    def status(incident_id: str):
        s = storage.load_state_obj(incident_id)
        if not s:
            return jsonify({"error": "not found"}), 404
        s["disclaimer"] = LEGAL_DISCLAIMER
        return jsonify(s)

    @app.post("/proceed/<incident_id>")
    def proceed(incident_id: str):
        s = storage.load_state_obj(incident_id)
        if not s:
            return jsonify({"error": "not found"}), 404
        requested = (request.get_json(silent=True) or {}).get("layer")
        current = s["current_layer"]
        if requested and requested != current:
            return jsonify({"error": "layer gate violation", "expected": current, "got": requested}), 400
        updated = run_layer(s.get("runbook", {}), current, dd, Path(workdir) / "exports")
        s["runbook"] = updated
        s["completed_layers"].append(current)
        nxt = next_layer(current)
        s["current_layer"] = nxt or current
        storage.save_state_obj(incident_id, s)
        storage.audit(incident_id, "proceed_http", {"completed": current, "next": nxt})
        return jsonify({"ok": True, "completed": current, "next": nxt, "disclaimer": LEGAL_DISCLAIMER})

    return app


def main() -> None:
    app = create_app()
    app.run(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
