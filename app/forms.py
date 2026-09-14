from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectMultipleField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Optional as OptionalValidator
from wtforms.widgets import ListWidget, CheckboxInput

from app.models import SEGMENT_CHOICES

MISSION_TYPES = [
    ("", "Select a mission type"),
    ("earth_observation", "Earth observation"),
    ("communications", "Communications / broadband constellation"),
    ("navigation", "Navigation / PNT"),
    ("scientific", "Scientific / research"),
    ("technology_demo", "Technology demonstration"),
    ("human_spaceflight", "Human spaceflight"),
    ("other", "Other"),
]


class SpaceSystemForm(FlaskForm):
    name = StringField(
        "System / mission name",
        validators=[DataRequired(), Length(max=200)],
    )
    mission_type = SelectField("Mission type", choices=MISSION_TYPES, validators=[OptionalValidator()])
    description = TextAreaField(
        "Architecture summary (free text - not sent anywhere unless you enable AI narrative)",
        validators=[OptionalValidator(), Length(max=4000)],
    )
    segments = SelectMultipleField(
        "Segments in scope",
        choices=SEGMENT_CHOICES,
        validators=[DataRequired(message="Select at least one segment.")],
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    uses_third_party_auth = BooleanField("Uses third-party authentication / identity provider")
    uses_commercial_ground_station = BooleanField("Uses a commercial/shared ground station network")
    has_encrypted_tt_and_c = BooleanField("TT&C link is encrypted end-to-end")
    has_supply_chain_program = BooleanField("Has a formal supply-chain security program")
    is_constellation = BooleanField("This is a multi-satellite constellation")
    is_nis2_in_scope = BooleanField("Organization is in scope of the EU NIS2 Directive")

    def validate_segments(self, field):
        allowed = {c[0] for c in SEGMENT_CHOICES}
        for v in field.data:
            if v not in allowed:
                raise ValueError("Invalid segment selection.")


class FindingUpdateForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[
            ("open", "Open"),
            ("mitigated", "Mitigated"),
            ("accepted", "Risk accepted"),
            ("false_positive", "False positive"),
        ],
        validators=[DataRequired()],
    )
    analyst_note = TextAreaField("Analyst note", validators=[OptionalValidator(), Length(max=2000)])
