---
name: odoo-module-builder
description: Create, scaffold, refactor, or review scalable Odoo addons/modules from scratch. Use when Codex is asked to build an Odoo module, define an addon structure, create models/controllers/views/security/assets, split a monolithic Odoo module into maintainable files, or explain the recommended Odoo module architecture.
---

# Odoo Module Builder

Use this skill to create Odoo addons with a maintainable structure instead of a single-file prototype. Prefer existing project conventions when working inside an existing repo.

## Workflow

1. Inspect the Odoo version, existing addon style, and target addon name.
2. Normalize the addon folder name to lowercase snake_case, for example `risk_module`.
3. Choose a technical model name that describes the business record, not the addon itself:
   - Prefer `risk.submission`, `fleet.onboarding.request`, `third.party.profile`.
   - Avoid generic `_name` values like `risk.module` for new production modules.
4. Scaffold only the directories needed for the requested behavior.
5. Keep backend views, website templates, assets, security, and Python logic separated.
6. Validate Python, XML, JS, and manifest references before finishing.

For the full recommended tree and file responsibilities, read `references/scalable_structure.md`.

## Recommended Addon Tree

Use this baseline for website-enabled modules:

```text
addon_name/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── record_controller.py
├── models/
│   ├── __init__.py
│   └── record.py
├── security/
│   ├── ir.model.access.csv
│   └── groups.xml
├── static/
│   └── src/
│       ├── css/record.css
│       └── js/record.js
└── views/
    ├── record_views.xml
    ├── record_menus.xml
    └── website_record_templates.xml
```

Skip `controllers/`, `website_*`, and frontend assets when the module is backend-only.

## Manifest Pattern

Use `data` for backend/security/templates and `assets` for CSS/JS:

```python
{
    "name": "Human Module Name",
    "version": "19.0.1.0.0",
    "category": "Custom",
    "summary": "Short business summary",
    "depends": ["base", "website"],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/record_views.xml",
        "views/record_menus.xml",
        "views/website_record_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "addon_name/static/src/css/record.css",
            "addon_name/static/src/js/record.js",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
```

Order security before views. Load actions before menus that reference them.

## File Responsibilities

- `models/*.py`: define fields, constraints, computed fields, state transitions, and ORM business logic.
- `controllers/*.py`: define website/HTTP routes, session flow, request validation, and calls into ORM.
- `security/ir.model.access.csv`: grant model permissions by group. Avoid `perm_unlink=1` for sensitive submissions unless requested.
- `views/*_views.xml`: backend list/form/search/kanban views.
- `views/*_menus.xml`: actions and menuitems.
- `views/website_*_templates.xml`: website QWeb templates only.
- `static/src/css/*.css`: frontend styling.
- `static/src/js/*.js`: frontend behavior, modals, progressive disclosure, client-side affordances.

Do not leave inline CSS/JS in XML unless the request is a tiny throwaway prototype.

## Website Form Pattern

For public website forms:

1. Use `auth="public"`, `website=True`, and `csrf=True` for POST routes unless there is a concrete reason not to.
2. Store multi-step draft data in `request.session`.
3. Maintain an allowlist of accepted fields per step.
4. Use server-side validation for required gates such as terms acceptance.
5. Create records with `sudo()` only for the final write, and only with allowlisted fields.
6. Clear the session after successful submission.

Never trust JavaScript-only validation for legal acceptance or required fields.

## Security Defaults

Prefer explicit groups for real modules:

```text
addon_name.group_record_user
addon_name.group_record_manager
```

Use `base.group_user` only for simple internal prototypes. For sensitive data, set `perm_unlink` to `0` by default.

Be careful with passwords, IDs, personal data, GPS credentials, bank data, and legal authorizations. If the form stores sensitive values, mention the risk and restrict backend access.

## Validation Checklist

Run these checks when applicable:

```bash
python3 -m py_compile __init__.py models/*.py controllers/*.py
python3 - <<'PY'
from xml.etree import ElementTree as ET
for f in ["views/record_views.xml", "views/record_menus.xml", "views/website_record_templates.xml"]:
    ET.parse(f)
    print(f, "ok")
PY
node --check static/src/js/record.js
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
```

Also verify the manifest references every created XML and asset file exactly.
