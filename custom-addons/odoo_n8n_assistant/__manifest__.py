{
    "name": "Odoo N8N Assistant (OdooBot Clone)",
    "version": "1.0",
    "depends": ["mail", "web"],
    "data": [
        "data/default_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "odoo_n8n_assistant/static/src/css/discuss_bot.css",
            "odoo_n8n_assistant/static/src/js/discuss_patch.js",
        ],
    },
    "installable": True,
}