# Scalable Odoo Module Structure

## Purpose

Use this reference when creating or refactoring an Odoo addon into a maintainable structure.

## Full Tree

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
│   ├── groups.xml
│   └── ir.model.access.csv
├── static/
│   └── src/
│       ├── css/
│       │   └── record.css
│       └── js/
│           └── record.js
└── views/
    ├── record_views.xml
    ├── record_menus.xml
    └── website_record_templates.xml
```

## Minimal Backend Module

```text
addon_name/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── record.py
├── security/
│   └── ir.model.access.csv
└── views/
    ├── record_views.xml
    └── record_menus.xml
```

## Naming

- Addon folder: `snake_case`, no hyphen.
- Python file: business object name, such as `risk_submission.py`.
- Class: PascalCase, such as `RiskSubmission`.
- Odoo `_name`: dotted business noun, such as `risk.submission`.
- XML IDs: prefix with the model purpose:
  - `view_risk_submission_list`
  - `view_risk_submission_form`
  - `action_risk_submission`
  - `menu_risk_submission_root`

## Security

Create `security/groups.xml` for production modules:

```xml
<odoo>
    <record id="group_record_user" model="res.groups">
        <field name="name">Record User</field>
    </record>

    <record id="group_record_manager" model="res.groups">
        <field name="name">Record Manager</field>
        <field name="implied_ids" eval="[(4, ref('group_record_user'))]"/>
    </record>
</odoo>
```

Example access CSV:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_record_user,record.user,model_addon_record,addon_name.group_record_user,1,1,1,0
access_record_manager,record.manager,model_addon_record,addon_name.group_record_manager,1,1,1,1
```

## Website Multi-Step Controller Skeleton

```python
from odoo import http
from odoo.http import request


STEP_FIELDS = {
    1: ("name", "email"),
    2: ("message",),
}


class RecordController(http.Controller):
    @http.route("/record", type="http", auth="public", website=True, sitemap=True)
    def start(self, **kwargs):
        request.session["record_form"] = {}
        return self._render_step(1)

    @http.route("/record/<int:step>", type="http", auth="public", website=True, sitemap=False)
    def show_step(self, step=1, **kwargs):
        return self._render_step(step)

    @http.route("/record/submit/<int:step>", type="http", auth="public", website=True, methods=["POST"], csrf=True)
    def submit_step(self, step=1, **post):
        data = request.session.get("record_form", {})
        for field in STEP_FIELDS.get(step, ()):
            data[field] = post.get(field, "").strip()
        request.session["record_form"] = data

        if step < max(STEP_FIELDS):
            return request.redirect("/record/%s" % (step + 1))

        record = request.env["addon.record"].sudo().create(data)
        request.session["record_form"] = {}
        return request.render("addon_name.record_success", {"record": record})

    def _render_step(self, step):
        if step not in STEP_FIELDS:
            return request.redirect("/record")
        return request.render("addon_name.record_form", {
            "step": step,
            "data": request.session.get("record_form", {}),
        })
```

## Refactor Rule

When refactoring an existing module that may already have database records, do not rename `_name` unless the user explicitly accepts a migration. Renaming `_name` changes the model identity and can break access XML IDs, views, and existing data.
