from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_open_mcp_model_access(self):
        return self.env.ref('mcp_server_ai.action_mcp_model_access').read()[0]

    def action_open_mcp_audit_log(self):
        return self.env.ref('mcp_server_ai.action_mcp_audit_log').read()[0]

    mcp_enabled = fields.Boolean(
        string='Enable MCP Server',
        config_parameter='mcp_server_ai.enabled',
        default=False,
    )
    mcp_logging_enabled = fields.Boolean(
        string='Enable Audit Logging',
        config_parameter='mcp_server_ai.logging_enabled',
        default=True,
    )
    mcp_rate_limit = fields.Integer(
        string='Rate Limit (req/min)',
        config_parameter='mcp_server_ai.rate_limit',
        default=10,
        help='Maximum API requests per user per minute. Set 0 to disable.',
    )
    mcp_log_retention_days = fields.Integer(
        string='Log Retention (days)',
        config_parameter='mcp_server_ai.log_retention_days',
        default=90,
        help='Number of days to keep audit logs. Older logs are auto-deleted.',
    )
    mcp_allowed_ips = fields.Char(
        string='IP Whitelist',
        config_parameter='mcp_server_ai.allowed_ips',
        help='Comma-separated IP addresses. Leave empty to allow all IPs.',
    )
    mcp_max_records_per_request = fields.Integer(
        string='Max Records Per Request',
        config_parameter='mcp_server_ai.max_records_per_request',
        default=1000,
        help='Maximum number of records returned in a single API request.',
    )
    mcp_cache_enabled = fields.Boolean(
        string='Enable Response Caching',
        config_parameter='mcp_server_ai.cache_enabled',
        default=False,
    )
    mcp_default_cache_ttl = fields.Integer(
        string='Default Cache TTL (seconds)',
        config_parameter='mcp_server_ai.default_cache_ttl',
        default=300,
        help='Default cache time-to-live in seconds for read operations.',
    )
    mcp_yolo_mode = fields.Selection(
        [
            ('disabled', 'Disabled (Production)'),
            ('read_only', 'Read Only (Dev)'),
            ('full', 'Full Access (Dev)'),
        ],
        string='YOLO Mode',
        config_parameter='mcp_server_ai.yolo_mode',
        default='disabled',
        help='WARNING: YOLO mode bypasses MCP permissions. '
             'NEVER enable in production!',
    )
