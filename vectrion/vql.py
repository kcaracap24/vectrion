from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Query:
    kind: str
    fields: list[str] = None
    source: str = None
    where_field: str = None
    where_op: str = None
    where_value: str = None
    limit: int = None
    group_by: str = None
    exclude_field: str = None
    exclude_value: str = None
    find_value: str = None


SELECT_RE = re.compile(
    r"^SELECT\s+(?P<fields>[\w,*\s]+)\s+FROM\s+(?P<source>\w+)"
    r"(?:\s+WHERE\s+(?P<wf>\w+)\s*(?P<op>=|!=|~)\s*'(?P<wv>[^']+)')?"
    r"(?:\s+EXCLUDE\s+(?P<ef>\w+)\s*=\s*'(?P<ev>[^']+)')?"
    r"(?:\s+GROUP\s+BY\s+(?P<group>\w+))?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?$",
    re.IGNORECASE,
)
STATS_RE = re.compile(
    r"^STATS\s+COUNT\s+BY\s+(?P<group>\w+)\s+FROM\s+(?P<source>\w+)$",
    re.IGNORECASE,
)
FIND_RE = re.compile(
    r"^FIND\s+'(?P<needle>[^']+)'\s+IN\s+(?P<source>\w+)"
    r"(?:\s+EXCLUDE\s+(?P<ef>\w+)\s*=\s*'(?P<ev>[^']+)')?"
    r"(?:\s+GROUP\s+BY\s+(?P<group>\w+))?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?$",
    re.IGNORECASE,
)


def parse_vql(text: str) -> Query:
    s = text.strip()
    m = SELECT_RE.match(s)
    if m:
        fields = [x.strip() for x in m.group("fields").split(",")]
        return Query(
            kind="select",
            fields=fields,
            source=m.group("source"),
            where_field=m.group("wf"),
            where_op=m.group("op"),
            where_value=m.group("wv"),
            limit=int(m.group("limit")) if m.group("limit") else None,
            group_by=m.group("group"),
            exclude_field=m.group("ef"),
            exclude_value=m.group("ev"),
        )
    m = STATS_RE.match(s)
    if m:
        return Query(kind="stats", source=m.group("source"), group_by=m.group("group"))
    m = FIND_RE.match(s)
    if m:
        return Query(
            kind="find",
            source=m.group("source"),
            find_value=m.group("needle"),
            group_by=m.group("group"),
            exclude_field=m.group("ef"),
            exclude_value=m.group("ev"),
            limit=int(m.group("limit")) if m.group("limit") else None,
        )
    raise ValueError("Unsupported VQL")


def _where(row: dict, field: str, op: str, value: str) -> bool:
    if not field:
        return True
    v = str(row.get(field, ""))
    if op == "=":
        return v == value
    if op == "!=":
        return v != value
    if op == "~":
        return value.lower() in v.lower()
    return True


def _exclude(row: dict, field: str, value: str) -> bool:
    if not field:
        return True
    return str(row.get(field, "")) != value


def _group_counts(rows: list[dict], group_by: str) -> list[dict]:
    counts: dict[str, int] = {}
    g = group_by or ""
    for r in rows:
        key = str(r.get(g, ""))
        counts[key] = counts.get(key, 0) + 1
    return [{g: k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: kv[0])]


def execute_vql(query: Query, rows: list[dict]) -> list[dict]:
    if query.kind == "select":
        filtered = [
            r for r in rows if _where(r, query.where_field, query.where_op, query.where_value) and _exclude(r, query.exclude_field, query.exclude_value)
        ]
        if query.group_by:
            return _group_counts(filtered, query.group_by)
        if query.limit is not None:
            filtered = filtered[: query.limit]
        if query.fields == ["*"]:
            return filtered
        return [{k: r.get(k, "") for k in (query.fields or [])} for r in filtered]
    if query.kind == "stats":
        return _group_counts(rows, query.group_by or "")
    if query.kind == "find":
        needle = (query.find_value or "").lower()
        filtered = []
        for r in rows:
            hay = " ".join(str(v) for v in r.values()).lower()
            if needle in hay and _exclude(r, query.exclude_field, query.exclude_value):
                filtered.append(r)
        if query.group_by:
            return _group_counts(filtered, query.group_by)
        if query.limit is not None:
            filtered = filtered[: query.limit]
        return filtered
    raise ValueError("Unsupported query kind")
