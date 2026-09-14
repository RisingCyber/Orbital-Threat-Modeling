from flask import Blueprint, render_template, abort

from app import db
from app.models import Tactic, Technique, SpaceSystem, Finding

matrix_bp = Blueprint("matrix", __name__, url_prefix="/matrix")


def _tactics_with_techniques():
    tactics = Tactic.query.order_by(Tactic.display_order).all()
    for tactic in tactics:
        tactic.non_sub_techniques = (
            Technique.query.filter_by(tactic_id=tactic.id, is_subtechnique=False)
            .order_by(Technique.id)
            .all()
        )
    return tactics


@matrix_bp.route("/")
def reference_matrix():
    tactics = _tactics_with_techniques()
    return render_template("matrix.html", tactics=tactics, system=None, findings_by_technique={})


@matrix_bp.route("/system/<system_id>")
def system_matrix(system_id):
    system = db.session.get(SpaceSystem, system_id)
    if system is None:
        abort(404)
    tactics = _tactics_with_techniques()
    findings = Finding.query.filter_by(system_id=system.id).all()
    findings_by_technique = {f.technique_id: f for f in findings}
    return render_template(
        "matrix.html", tactics=tactics, system=system, findings_by_technique=findings_by_technique
    )


@matrix_bp.route("/technique/<technique_id>")
def technique_detail(technique_id):
    technique = db.session.get(Technique, technique_id)
    if technique is None:
        abort(404)
    sub_techniques = (
        Technique.query.filter_by(parent_id=technique.id, is_subtechnique=True).order_by(Technique.id).all()
    )
    return render_template("technique_detail.html", technique=technique, sub_techniques=sub_techniques)
