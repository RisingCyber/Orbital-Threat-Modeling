"""
Smoke and flow tests. Run with:  pytest -q

These are intentionally black-box (HTTP through the Flask test client,
including real CSRF tokens) rather than importing internals directly,
so they catch template/route wiring bugs, not just unit-level logic bugs.
"""
import re
import tempfile
from pathlib import Path

import pytest

from app import create_app, db


@pytest.fixture()
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    test_app = create_app("config.DevConfig")
    test_app.config.update(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        WTF_CSRF_ENABLED=True,
        TESTING=True,
    )
    with test_app.app_context():
        db.drop_all()
        db.create_all()
        from app.data_loader import sync_reference_data
        sync_reference_data()
    yield test_app
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def _csrf_token(html: str) -> str:
    m = re.search(r'csrf_token"[^>]*?value="([^"]+)"', html)
    assert m, "CSRF token not found in rendered form"
    return m.group(1)


def test_reference_pages_load(client):
    for url in ["/", "/matrix/", "/compliance/", "/systems/new"]:
        resp = client.get(url)
        assert resp.status_code == 200, url


def test_reference_data_loaded(app):
    from app.models import Tactic, Technique, Mitigation
    with app.app_context():
        assert Tactic.query.count() == 9
        assert Technique.query.count() > 200  # parent techniques + sub-techniques
        assert Technique.query.filter_by(is_subtechnique=False).count() > 50
        assert Mitigation.query.count() > 100


def test_create_system_generates_findings(client, app):
    html = client.get("/systems/new").data.decode()
    token = _csrf_token(html)

    resp = client.post(
        "/systems/new",
        data={
            "csrf_token": token,
            "name": "Test Constellation",
            "mission_type": "communications",
            "segments": ["space", "ground", "link", "supply_chain"],
            "uses_third_party_auth": "y",
            "is_constellation": "y",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Findings" in resp.data

    from app.models import SpaceSystem, Finding
    with app.app_context():
        system = SpaceSystem.query.filter_by(name="Test Constellation").first()
        assert system is not None
        findings = Finding.query.filter_by(system_id=system.id).all()
        assert len(findings) > 0
        # every finding must reference a technique that overlaps a declared segment
        for f in findings:
            assert set(f.technique.segments) & set(system.segments)


def test_severity_is_not_all_critical(client):
    """Regression test: an earlier version of the severity heuristic
    stacked risk-modifier bumps unbounded and pushed ~85% of findings to
    'critical', which made prioritization meaningless. Bumps are now
    capped at one tier; this test keeps that constraint honest."""
    html = client.get("/systems/new").data.decode()
    token = _csrf_token(html)
    client.post(
        "/systems/new",
        data={
            "csrf_token": token,
            "name": "High Risk System",
            "segments": ["space", "ground", "link", "supply_chain"],
            "uses_third_party_auth": "y",
            "is_constellation": "y",
        },
        follow_redirects=True,
    )
    from app.models import SpaceSystem, Finding
    with client.application.app_context():
        system = SpaceSystem.query.filter_by(name="High Risk System").first()
        findings = Finding.query.filter_by(system_id=system.id).all()
        critical_share = sum(1 for f in findings if f.severity == "critical") / len(findings)
        assert critical_share < 0.5


def test_findings_are_ranked_by_actual_severity_not_alphabetically(client):
    """Regression test: Finding.severity is a plain string column, so an
    earlier version's SQL ORDER BY sorted it alphabetically - 'medium'
    rendered above 'critical' on the page because 'm' > 'c' as strings.
    Findings are now ranked in Python against SEVERITY_ORDER before being
    handed to the template; assert on the actual rendered HTML order,
    since that's what a previous version got wrong even though the data
    itself was fine."""
    html = client.get("/systems/new").data.decode()
    token = _csrf_token(html)
    client.post(
        "/systems/new",
        data={
            "csrf_token": token,
            "name": "Ranking Test",
            "segments": ["space", "ground", "link", "supply_chain"],
            "uses_third_party_auth": "y",
            "is_constellation": "y",
        },
        follow_redirects=True,
    )
    from app.models import SpaceSystem
    with client.application.app_context():
        sid = SpaceSystem.query.filter_by(name="Ranking Test").first().id

    detail_html = client.get(f"/systems/{sid}").data.decode()
    chip_order = re.findall(r'chip chip--(low|medium|high|critical)"', detail_html)
    assert len(chip_order) > 0
    rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    ranks_as_rendered = [rank[c] for c in chip_order]
    assert ranks_as_rendered == sorted(ranks_as_rendered, reverse=True), (
        "Findings are not rendered highest-severity-first: " + str(chip_order[:10])
    )


def test_no_segments_selected_is_rejected(client):
    html = client.get("/systems/new").data.decode()
    token = _csrf_token(html)
    resp = client.post(
        "/systems/new",
        data={"csrf_token": token, "name": "No Segments"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    from app.models import SpaceSystem
    with client.application.app_context():
        assert SpaceSystem.query.filter_by(name="No Segments").first() is None


def test_missing_csrf_token_is_rejected(client):
    resp = client.post(
        "/systems/new",
        data={"name": "No CSRF", "segments": ["space"]},
    )
    assert resp.status_code == 400


def test_unknown_system_id_returns_404(client):
    assert client.get("/systems/does-not-exist").status_code == 404
    assert client.get("/matrix/system/does-not-exist").status_code == 404
    assert client.get("/compliance/system/does-not-exist").status_code == 404
    assert client.get("/reports/system/does-not-exist").status_code == 404


def test_security_headers_present(client):
    resp = client.get("/")
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_finding_status_update_and_report(client, app):
    html = client.get("/systems/new").data.decode()
    token = _csrf_token(html)
    client.post(
        "/systems/new",
        data={"csrf_token": token, "name": "Report Test", "segments": ["space"]},
        follow_redirects=True,
    )
    from app.models import SpaceSystem, Finding
    with app.app_context():
        system = SpaceSystem.query.filter_by(name="Report Test").first()
        finding = Finding.query.filter_by(system_id=system.id).first()
        sid, fid = system.id, finding.id

    detail_html = client.get(f"/systems/{sid}").data.decode()
    token = _csrf_token(detail_html)
    resp = client.post(
        f"/systems/{sid}/findings/{fid}",
        data={"csrf_token": token, "status": "mitigated", "analyst_note": "Fixed."},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    report_resp = client.get(f"/reports/system/{sid}")
    assert report_resp.status_code == 200
    assert b"EU compliance" in report_resp.data or b"compliance summary" in report_resp.data
