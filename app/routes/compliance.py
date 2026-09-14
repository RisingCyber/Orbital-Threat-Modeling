from flask import Blueprint, render_template, abort

from app import db
from app.data_loader import load_eu_governance
from app.models import SpaceSystem

compliance_bp = Blueprint("compliance", __name__, url_prefix="/compliance")

# Maps a governance requirement theme to a SpaceSystem boolean field this
# tool actually captures. Only themes listed here get an automated
# "addressed / gap" verdict; everything else is shown as
# "not assessed by this tool" rather than guessed at, because we have no
# corresponding input to base a verdict on.
THEME_TO_SYSTEM_FIELD = {
    "Encryption": "has_encrypted_tt_and_c",
    "Supply chain risk management": "has_supply_chain_program",
}


@compliance_bp.route("/")
def overview():
    data = load_eu_governance()
    return render_template("compliance.html", data=data, system=None, verdicts={})


@compliance_bp.route("/system/<system_id>")
def system_compliance(system_id):
    system = db.session.get(SpaceSystem, system_id)
    if system is None:
        abort(404)
    data = load_eu_governance()

    verdicts = {}
    for framework in data["frameworks"]:
        for req in framework.get("resilience_requirements", []):
            field = THEME_TO_SYSTEM_FIELD.get(req["theme"])
            if field is None:
                verdicts[req["theme"]] = "not_assessed"
            else:
                verdicts[req["theme"]] = "addressed" if getattr(system, field) else "gap"

    return render_template("compliance.html", data=data, system=system, verdicts=verdicts)
