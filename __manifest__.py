{
    "name": "Risk Module",
    "version": "19.0.1.0.0",
    "category": "Custom",
    "summary": "Modulo para el departamento de riesgo en Impocoma",
    "depends": ["base", "website"],
    "data": [
        "security/ir.model.access.csv",
        "views/risk_submission_report.xml",
        "views/risk_submission_views.xml",
        "views/risk_submission_menus.xml",
        "views/website_risk_submission_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "risk_module/static/src/css/risk_submission.css",
            "risk_module/static/src/js/risk_submission_terms.js",
            "risk_module/static/src/js/risk_submission_signatures.js",
            "risk_module/static/src/js/risk_submission_print.js",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
