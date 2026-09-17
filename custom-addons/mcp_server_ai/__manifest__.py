{
    'name': 'MCP Server',
    'version': '19.0.1.0.0',
    'author': 'Dheeraj Chauhan',
    'category': 'Technical',
    'summary': 'Model Context Protocol Server for AI Assistant Integration',
    'description': """
MCP Server - AI Assistant Integration for Odoo
================================================

Enables AI assistants (Claude, Cursor, VS Code Copilot, etc.)
to securely access and interact with Odoo data via the Model Context Protocol.

Features:
---------
* REST API endpoints with Bearer token authentication
* XML-RPC proxy with MCP permission checks
* Fine-grained per-model CRUD access control
* Field-level access restrictions
* Complete audit trail logging
* Configurable rate limiting
* Response caching with per-model TTL
* LLM-optimized output formatting
* IP whitelisting
* YOLO development mode
* Smart field defaults (excludes binary fields)
* Summary generator for browse/search results
    """,
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/mcp_security.xml',
        'security/ir.model.access.csv',
        'data/default_data.xml',
        'views/mcp_model_access_views.xml',
        'views/mcp_audit_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    "images": ["static/description/banner.png"],
    'installable': True,
    'application': False,
    'auto_install': False,
}
