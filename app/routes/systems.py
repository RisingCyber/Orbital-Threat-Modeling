from flask import Blueprint, render_template, redirect, url_for, flash, current_app, abort

from app import db
from app.forms import SpaceSystemForm, FindingUpdateForm
from app.models import SpaceSystem, Finding, Technique, SEVERITY_ORDER
from app.engine import suggest_findings
from app.ai_assist import generate_narrative

systems_bp = Blueprint("systems", __name__, url_prefix="/systems")


def _get_system_or_404(system_id: str) -> SpaceSystem:
    system = db.session.get(SpaceSystem, system_id)
    if system is None:
        abort(404)
    return system


@systems_bp.route("/new", methods=["GET", "POST"])
def new_system():
    form = SpaceSystemForm()
    if form.validate_on_submit():
        system = SpaceSystem(
            name=form.name.data.strip(),
            mission_type=form.mission_type.data or None,
            description=form.description.data or None,
            uses_third_party_auth=form.uses_third_party_auth.data,
            uses_commercial_ground_station=form.uses_commercial_ground_station.data,
            has_encrypted_tt_and_c=form.has_encrypted_tt_and_c.data,
            has_supply_chain_program=form.has_supply_chain_program.data,
            is_constellation=form.is_constellation.data,
            is_nis2_in_scope=form.is_nis2_in_scope.data,
        )
        system.segments = form.segments.data
        db.session.add(system)
        db.session.commit()
        _regenerate_findings(system)
        flash("System created and threat matrix generated.", "success")
        return redirect(url_for("systems.system_detail", system_id=system.id))
    return render_template("system_form.html", form=form, system=None)


@systems_bp.route("/<system_id>/edit", methods=["GET", "POST"])
def edit_system(system_id):
    system = _get_system_or_404(system_id)
    form = SpaceSystemForm(obj=system)
    if not form.is_submitted():
        form.segments.data = system.segments

    if form.validate_on_submit():
        system.name = form.name.data.strip()
        system.mission_type = form.mission_type.data or None
        system.description = form.description.data or None
        system.uses_third_party_auth = form.uses_third_party_auth.data
        system.uses_commercial_ground_station = form.uses_commercial_ground_station.data
        system.has_encrypted_tt_and_c = form.has_encrypted_tt_and_c.data
        system.has_supply_chain_program = form.has_supply_chain_program.data
        system.is_constellation = form.is_constellation.data
        system.is_nis2_in_scope = form.is_nis2_in_scope.data
        system.segments = form.segments.data
        db.session.commit()
        _regenerate_findings(system)
        flash("System updated and threat matrix regenerated.", "success")
        return redirect(url_for("systems.system_detail", system_id=system.id))
    return render_template("system_form.html", form=form, system=system)


@systems_bp.route("/<system_id>")
def system_detail(system_id):
    system = _get_system_or_404(system_id)
    # SQL ORDER BY on Finding.severity sorts the raw string ("medium" comes
    # after "critical" alphabetically), not the actual severity rank - so
    # rank in Python against SEVERITY_ORDER instead of at the DB layer.
    findings = Finding.query.filter_by(system_id=system.id).join(Technique).all()
    findings.sort(key=lambda f: SEVERITY_ORDER[f.severity], reverse=True)
    narrative = None
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if api_key and findings:
        from app.engine import SuggestedFinding
        suggested = [
            SuggestedFinding(technique_id=f.technique_id, severity=f.severity, rationale=f.rationale or "")
            for f in findings
        ]
        narrative = generate_narrative(system, suggested, api_key)
    return render_template("system_detail.html", system=system, findings=findings, narrative=narrative)


@systems_bp.route("/<system_id>/findings/<finding_id>", methods=["POST"])
def update_finding(system_id, finding_id):
    system = _get_system_or_404(system_id)
    finding = db.session.get(Finding, finding_id)
    if finding is None or finding.system_id != system.id:
        abort(404)
    form = FindingUpdateForm()
    if form.validate_on_submit():
        finding.status = form.status.data
        finding.analyst_note = form.analyst_note.data or None
        db.session.commit()
        flash("Finding updated.", "success")
    return redirect(url_for("systems.system_detail", system_id=system.id))


def _regenerate_findings(system: SpaceSystem):
    """Recompute findings from the current engine rules. Existing analyst
    status/notes on findings for techniques still flagged are preserved;
    findings for techniques no longer flagged are removed."""
    suggested = suggest_findings(system)
    suggested_by_id = {s.technique_id: s for s in suggested}

    existing = {f.technique_id: f for f in Finding.query.filter_by(system_id=system.id).all()}

    for tech_id, existing_finding in existing.items():
        if tech_id not in suggested_by_id:
            db.session.delete(existing_finding)

    for tech_id, s in suggested_by_id.items():
        if tech_id in existing:
            existing[tech_id].severity = s.severity
            existing[tech_id].rationale = s.rationale
        else:
            db.session.add(
                Finding(
                    system_id=system.id,
                    technique_id=s.technique_id,
                    severity=s.severity,
                    rationale=s.rationale,
                )
            )
    db.session.commit()
