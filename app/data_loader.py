"""
Synchronizes the bundled reference datasets (app/data/*.json) into the
database. This is the ONLY place reference data enters the system, and it
always reads from local, version-controlled JSON files - never from a
user-supplied upload or an unbounded network call at request time. That
keeps the SPARTA taxonomy identical for every user of the app and keeps
provenance traceable to the sources cited in README.md.

All writes below go through the SQLAlchemy ORM (session.merge / model
attributes), so there is no string-built SQL anywhere in this file.
"""
import json

from flask import current_app

from app import db
from app.models import Tactic, Technique, Mitigation


def _load_json(filename):
    path = current_app.config["DATA_DIR"] / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sync_reference_data():
    _sync_tactics()
    _sync_techniques()
    _sync_mitigations()
    db.session.commit()


def _sync_tactics():
    for row in _load_json("sparta_tactics.json"):
        tactic = db.session.get(Tactic, row["id"]) or Tactic(id=row["id"])
        tactic.shortname = row["shortname"]
        tactic.name = row["name"]
        tactic.description = row["description"]
        tactic.display_order = row["order"]
        tactic.source_url = row["source_url"]
        db.session.add(tactic)


def _sync_techniques():
    for row in _load_json("sparta_techniques.json"):
        tech = db.session.get(Technique, row["id"]) or Technique(id=row["id"])
        tech.name = row["name"]
        tech.description = row["description"]
        # A technique's kill_chain in the source data can list more than one
        # tactic; our schema stores one primary tactic per row, so we take
        # the first and note this simplification in README.md.
        tech.tactic_id = row["tactic_ids"][0]
        tech.is_subtechnique = row["is_subtechnique"]
        tech.parent_id = row.get("parent_id")
        tech.segments_csv = ",".join(row.get("segments", []))
        tech.source_url = row["source_url"]
        db.session.add(tech)


def _sync_mitigations():
    for row in _load_json("sparta_mitigations.json"):
        mit = db.session.get(Mitigation, row["id"]) or Mitigation(id=row["id"])
        mit.name = row["name"]
        mit.description = row["description"]
        mit.nist_refs_csv = ",".join(row.get("nist_800_53_refs", []))[:1024]
        mit.iso_refs_csv = ",".join(row.get("iso_27001_refs", []))[:1024]
        mit.source_url = row["source_url"]
        db.session.add(mit)


def load_eu_governance():
    """Read-only accessor for the EU governance dataset - it's small and
    reference-only, so it's served straight from JSON rather than mirrored
    into tables."""
    return _load_json("eu_governance.json")
