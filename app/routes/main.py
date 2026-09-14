from flask import Blueprint, render_template

from app.models import SpaceSystem, Tactic, Technique, Finding

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    systems = SpaceSystem.query.order_by(SpaceSystem.updated_at.desc()).all()
    stats = {
        "system_count": len(systems),
        "tactic_count": Tactic.query.count(),
        "technique_count": Technique.query.count(),
        "open_findings": Finding.query.filter_by(status="open").count(),
    }
    return render_template("dashboard.html", systems=systems, stats=stats)
