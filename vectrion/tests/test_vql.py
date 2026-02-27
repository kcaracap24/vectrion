from vectrion.vql import execute_vql, parse_vql


ROWS = [
    {"event_id": "1", "subject": "VPN", "source": "vpn", "detail": "alpha"},
    {"event_id": "2", "subject": "Email", "source": "mail", "detail": "beta"},
    {"event_id": "3", "subject": "VPN", "source": "vpn", "detail": "gamma"},
]


def test_parse_select_and_execute():
    q = parse_vql("SELECT event_id,subject FROM evidence WHERE source='vpn' LIMIT 1")
    out = execute_vql(q, ROWS)
    assert out == [{"event_id": "1", "subject": "VPN"}]


def test_parse_stats_and_execute():
    q = parse_vql("STATS COUNT BY source FROM evidence")
    out = execute_vql(q, ROWS)
    assert {r["source"]: r["count"] for r in out} == {"mail": 1, "vpn": 2}


def test_find_group_by_exclude():
    q = parse_vql("FIND 'vpn' IN evidence EXCLUDE source='mail' GROUP BY source")
    out = execute_vql(q, ROWS)
    assert out == [{"source": "vpn", "count": 2}]


def test_select_group_by_with_exclude():
    q = parse_vql("SELECT * FROM evidence EXCLUDE source='mail' GROUP BY source")
    out = execute_vql(q, ROWS)
    assert out == [{"source": "vpn", "count": 2}]
