from datetime import datetime, timezone

from flask import Blueprint, render_template, abort

from app import db
from app.data_loader import load_eu_governance
from app.models import SpaceSystem, Finding, Technique, SEVERITY_ORDER
from app.routes.compliance import THEME_TO_SYSTEM_FIELD

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/system/<system_id>")
def system_report(system_id):
    system = db.session.get(SpaceSystem, system_id)
    if system is None:
        abort(404)

    # See app/routes/systems.py for why this sorts in Python rather than
    # via SQL ORDER BY - Finding.severity is a plain string column, so a DB
    # sort would rank "medium" above "critical" alphabetically.
    findings = Finding.query.filter_by(system_id=system.id).join(Technique).all()
    findings.sort(key=lambda f: SEVERITY_ORDER[f.severity], reverse=True)

    gov_data = load_eu_governance()
    verdicts = {}
    for framework in gov_data["frameworks"]:
        for req in framework.get("resilience_requirements", []):
            field = THEME_TO_SYSTEM_FIELD.get(req["theme"])
            if field is None:
                verdicts[req["theme"]] = "not_assessed"
            else:
                verdicts[req["theme"]] = "addressed" if getattr(system, field) else "gap"

    return render_template(
        "report.html",
        system=system,
        findings=findings,
        gov_data=gov_data,
        verdicts=verdicts,
        generated_at=datetime.now(timezone.utc),
    )
