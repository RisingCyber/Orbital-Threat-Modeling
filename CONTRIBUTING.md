# Contributing

## Before you open a PR

Run the test suite. It's fast and it's the actual bar for correctness here:

```bash
pip install -r requirements.txt pytest
pytest -q
```

CI runs the same thing on Python 3.11 and 3.12 for every PR.

## What tends to matter most in review

- **No raw SQL.** Every query goes through the SQLAlchemy ORM. If a change
  needs a query, use `Model.query` / `db.session`, not a string-built
  statement.
- **No `|safe` in templates.** Jinja2's autoescaping is what keeps this app
  XSS-safe. If you're tempted to add `|safe` or `Markup()`, that's a sign
  the data should be restructured instead.
- **CSRF on every POST.** New forms should use `FlaskForm` (see
  `app/forms.py`) so a token is issued and checked automatically.
- **Cite your data.** Anything added to `app/data/*.json` needs a real
  source. Don't hand-write a plausible-looking SPARTA technique or EU
  Space Act clause - link to where it actually came from, the way the
  existing entries do.
- **The AI-assist layer stays constrained.** If you touch
  `app/ai_assist.py`, keep the property that it can only reference
  technique IDs the deterministic engine already selected, and keep the
  post-hoc validation that rejects output referencing anything else.

## Reporting a bug

Two things found while building this were both severity/ranking logic
bugs that only showed up when the app was actually exercised end to end
(not from reading the code) - see the commit history. If you find
something similar, a failing test that reproduces it is the fastest path
to a fix; a plain description works too.
