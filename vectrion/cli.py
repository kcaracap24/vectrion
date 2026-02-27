from __future__ import annotations

import argparse
import json
from pathlib import Path

from vectrion.constants import LAYER_ORDER, LEGAL_DISCLAIMER
from vectrion.runbook import next_layer, run_layer
from vectrion.storage import Storage


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def cmd_migrate(args: argparse.Namespace) -> None:
    st = Storage(Path(args.workdir))
    if st.pg:
        st.pg.apply_migrations()
        print("Migrations applied")
    else:
        print("No VECTRION_DATABASE_URL configured; using file storage only")


def cmd_start(args: argparse.Namespace) -> None:
    st = Storage(Path(args.workdir))
    state = st.load_state(args.incident_id)
    if state:
        print(f"Incident {args.incident_id} already exists")
        return
    base = {
        "incident_id": args.incident_id,
        "current_layer": "A",
        "completed_layers": [],
        "runbook": {"config": {"detectors": [], "transforms": [], "cohorts": []}},
    }
    st.save_state_obj(args.incident_id, base)
    st.audit(args.incident_id, "start", {"layer": "A"})
    print(f"Started incident {args.incident_id} at layer A")


def cmd_status(args: argparse.Namespace) -> None:
    st = Storage(Path(args.workdir))
    s = st.load_state_obj(args.incident_id)
    if not s:
        print("not found")
        return
    print(json.dumps(s, indent=2))


def _run_and_persist(st: Storage, s: dict, current: str, data_dir: Path, workdir: Path) -> None:
    updated = run_layer(s.get("runbook", {}), current, data_dir, workdir / "exports")
    s["runbook"] = updated
    if current not in s["completed_layers"]:
        s["completed_layers"].append(current)
    nxt = next_layer(current)
    s["current_layer"] = nxt or current
    st.save_state_obj(s["incident_id"], s)
    st.persist_core_entities(s["incident_id"], s["runbook"])
    st.audit(s["incident_id"], "proceed", {"completed": current, "next": nxt})
    if st.pg:
        st.pg.insert_run(s["incident_id"], current, "completed", {"next": nxt})


def cmd_proceed(args: argparse.Namespace) -> None:
    st = Storage(Path(args.workdir))
    s = st.load_state_obj(args.incident_id)
    if not s:
        raise SystemExit("incident not found")
    current = s["current_layer"]
    if args.layer and args.layer != current:
        raise SystemExit(f"Layer gate violation. Expected {current}, got {args.layer}")
    data_dir = Path(args.data_dir) if args.data_dir else _default_data_dir()
    _run_and_persist(st, s, current, data_dir, Path(args.workdir))
    print(f"Completed layer {current}. Next: {s['current_layer'] or 'none'}")
    print(LEGAL_DISCLAIMER)


def _interactive_help() -> None:
    print("Commands:")
    print("  proceed                - run current gated layer")
    print("  rerun                  - rerun current layer")
    print("  add-detector <name>    - add deterministic detector")
    print("  add-transform <name>   - add transform hint")
    print("  split-cohort <field>   - split cohort by field")
    print("  status                 - print incident state")
    print("  help                   - show this menu")
    print("  quit                   - exit")


def cmd_interactive(args: argparse.Namespace) -> None:
    st = Storage(Path(args.workdir))
    s = st.load_state_obj(args.incident_id)
    if not s:
        s = {
            "incident_id": args.incident_id,
            "current_layer": "A",
            "completed_layers": [],
            "runbook": {"config": {"detectors": [], "transforms": [], "cohorts": []}},
        }
        st.save_state_obj(args.incident_id, s)
        st.audit(args.incident_id, "interactive_start", {})

    data_dir = Path(args.data_dir) if args.data_dir else _default_data_dir()
    print(f"Interactive runbook for {args.incident_id}")
    _interactive_help()

    while True:
        cur = s["current_layer"]
        desc = f"{cur}: {s.get('runbook', {}).get('layer_description', '')}" if s.get("runbook") else cur
        cmd = input(f"vectrion[{desc}]> ").strip()
        if not cmd:
            continue
        if cmd == "quit":
            break
        if cmd == "help":
            _interactive_help()
            continue
        if cmd == "status":
            print(json.dumps(st.load_state_obj(args.incident_id), indent=2))
            continue
        if cmd == "proceed":
            cur = s["current_layer"]
            _run_and_persist(st, s, cur, data_dir, Path(args.workdir))
            print(f"Completed {cur}; next {s['current_layer']}")
            print(LEGAL_DISCLAIMER)
            continue
        if cmd == "rerun":
            cur = s["current_layer"]
            s["runbook"] = run_layer(s.get("runbook", {}), cur, data_dir, Path(args.workdir) / "exports")
            st.save_state_obj(args.incident_id, s)
            st.persist_core_entities(args.incident_id, s["runbook"])
            st.audit(args.incident_id, "interactive_rerun", {"layer": cur})
            print(f"Reran {cur} with current config")
            continue
        if cmd.startswith("add-detector "):
            name = cmd.split(" ", 1)[1].strip()
            cfg = s.setdefault("runbook", {}).setdefault("config", {}).setdefault("detectors", [])
            if name and name not in cfg:
                cfg.append(name)
            st.save_state_obj(args.incident_id, s)
            print(f"Added detector: {name}")
            continue
        if cmd.startswith("add-transform "):
            name = cmd.split(" ", 1)[1].strip()
            cfg = s.setdefault("runbook", {}).setdefault("config", {}).setdefault("transforms", [])
            if name and name not in cfg:
                cfg.append(name)
            st.save_state_obj(args.incident_id, s)
            print(f"Added transform: {name}")
            continue
        if cmd.startswith("split-cohort "):
            field = cmd.split(" ", 1)[1].strip()
            cfg = s.setdefault("runbook", {}).setdefault("config", {}).setdefault("cohorts", [])
            if field and field not in cfg:
                cfg.append(field)
            st.save_state_obj(args.incident_id, s)
            print(f"Cohort split will include: {field}")
            continue
        print("Unknown command. Type 'help'.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vectrion")
    p.add_argument("--workdir", default=".vectrion")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("migrate")
    s.set_defaults(func=cmd_migrate)

    s = sub.add_parser("start")
    s.add_argument("incident_id")
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("status")
    s.add_argument("incident_id")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("proceed")
    s.add_argument("incident_id")
    s.add_argument("--layer", choices=LAYER_ORDER)
    s.add_argument("--data-dir", default=None)
    s.set_defaults(func=cmd_proceed)

    s = sub.add_parser("interactive")
    s.add_argument("incident_id")
    s.add_argument("--data-dir", default=None)
    s.set_defaults(func=cmd_interactive)
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
