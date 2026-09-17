import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MCPAuditLog(models.Model):
    _name = 'mcp.audit.log'
    _description = 'MCP Audit Log'
    _order = 'timestamp desc'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        readonly=True,
        index=True,
    )
    model_name = fields.Char(
        string='Model',
        required=True,
        readonly=True,
        index=True,
    )
    operation = fields.Selection(
        [
            ('create', 'Create'),
            ('read', 'Read'),
            ('write', 'Write'),
            ('unlink', 'Delete'),
            ('search', 'Search'),
            ('count', 'Count'),
            ('browse', 'Browse'),
            ('call', 'Method Call'),
            ('fields', 'Fields'),
            ('auth', 'Authentication'),
            ('system', 'System'),
        ],
        string='Operation',
        required=True,
        readonly=True,
        index=True,
    )
    method_name = fields.Char(
        string='Method',
        readonly=True,
    )
    record_ids = fields.Char(
        string='Record IDs',
        readonly=True,
        help='JSON list of affected record IDs.',
    )
    record_count = fields.Integer(
        string='Record Count',
        readonly=True,
        default=0,
    )
    request_data = fields.Text(
        string='Request Data',
        readonly=True,
        help='Sanitized request payload (truncated).',
    )
    response_status = fields.Selection(
        [
            ('success', 'Success'),
            ('error', 'Error'),
            ('denied', 'Denied'),
        ],
        string='Status',
        required=True,
        readonly=True,
        index=True,
    )
    error_message = fields.Text(
        string='Error Message',
        readonly=True,
    )
    ip_address = fields.Char(
        string='IP Address',
        readonly=True,
        index=True,
    )
    user_agent = fields.Char(
        string='User Agent',
        readonly=True,
    )
    duration_ms = fields.Float(
        string='Duration (ms)',
        readonly=True,
        default=0,
    )
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        index=True,
    )
    endpoint_type = fields.Selection(
        [
            ('rest', 'REST'),
            ('xmlrpc', 'XML-RPC'),
        ],
        string='Endpoint Type',
        readonly=True,
        default='rest',
    )

    _display_name_depends = ['model_name', 'operation', 'timestamp']

    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.model_name} / {record.operation} ({record.timestamp})"

    @api.model
    def log_request(self, vals):
        """Create an audit log entry. Truncates request_data to 5000 chars."""
        if vals.get('request_data'):
            data = vals['request_data']
            if isinstance(data, dict):
                data = json.dumps(data, default=str)
            if len(data) > 5000:
                data = data[:5000] + '... [truncated]'
            vals['request_data'] = data
        try:
            return self.sudo().create(vals)
        except Exception as e:
            _logger.error("Failed to write MCP audit log: %s", e)
            return self.browse()

    @api.model
    def _cron_cleanup_old_logs(self):
        """Cron job: delete audit logs older than configured retention days."""
        ICP = self.env['ir.config_parameter'].sudo()
        retention_days = int(ICP.get_param('mcp_server_ai.log_retention_days', '90'))
        if retention_days <= 0:
            return
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=retention_days)
        old_logs = self.sudo().search([('timestamp', '<', cutoff)])
        count = len(old_logs)
        if count:
            old_logs.unlink()
            _logger.info("MCP Audit Log cleanup: deleted %d records older than %d days.", count, retention_days)
