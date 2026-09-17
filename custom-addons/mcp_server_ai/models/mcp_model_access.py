import json
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

BLOCKED_MODELS = [
    'res.users.apikeys',
    'res.users.apikeys.description',
    'res.users.apikeys.show',
    'ir.model.access',
    'ir.rule',
    'ir.config_parameter',
    'mcp.audit.log',
    'mcp.model.access',
]


class MCPModelAccess(models.Model):
    _name = 'mcp.model.access'
    _description = 'MCP Model Access Configuration'
    _order = 'model_name'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain=lambda self: [('model', 'not in', BLOCKED_MODELS)],
    )
    model_name = fields.Char(
        string='Model Name',
        related='model_id.model',
        store=True,
        readonly=True,
    )
    read_access = fields.Boolean(string='Read', default=True)
    write_access = fields.Boolean(string='Write', default=False)
    create_access = fields.Boolean(string='Create', default=False)
    delete_access = fields.Boolean(string='Delete', default=False)
    allowed_fields = fields.Text(
        string='Allowed Fields',
        help='JSON list of allowed field names. Leave empty to allow all fields. '
             'Example: ["name", "email", "phone"]',
    )
    active = fields.Boolean(string='Active', default=True)
    group_ids = fields.Many2many(
        'res.groups',
        'mcp_model_access_group_rel',
        'access_id',
        'group_id',
        string='Allowed Groups',
        help='Restrict access to specific user groups. '
             'Leave empty to allow all MCP users.',
    )
    cache_ttl = fields.Integer(
        string='Cache TTL (seconds)',
        default=0,
        help='Cache time-to-live for read operations. 0 = no caching.',
    )
    description = fields.Text(
        string='Notes',
        help='Admin notes about why this model is exposed via MCP.',
    )
    
    _unique_model = models.Constraint(                                                                                                                                     
        'UNIQUE(model_id)',                                                                                                                                                
        'Each model can only have one MCP access configuration.',                                                                                                          
    )

    @api.depends('model_id', 'model_id.name')
    def _compute_name(self):
        for record in self:
            if record.model_id:
                record.name = f"MCP: {record.model_id.name}"
            else:
                record.name = 'MCP: New'

    @api.constrains('model_id')
    def _check_blocked_models(self):
        for record in self:
            if record.model_id and record.model_name in BLOCKED_MODELS:
                raise ValidationError(
                    f"The model '{record.model_name}' is blocked for security reasons "
                    f"and cannot be exposed via MCP."
                )

    @api.constrains('allowed_fields')
    def _check_allowed_fields_json(self):
        for record in self:
            if record.allowed_fields:
                try:
                    fields_list = json.loads(record.allowed_fields)
                    if not isinstance(fields_list, list):
                        raise ValidationError(
                            "Allowed Fields must be a JSON list. "
                            'Example: ["name", "email", "phone"]'
                        )
                except (json.JSONDecodeError, TypeError):
                    raise ValidationError(
                        "Allowed Fields must be valid JSON. "
                        'Example: ["name", "email", "phone"]'
                    )

    def get_allowed_fields_list(self):
        """Return the list of allowed fields or empty list (meaning all allowed)."""
        self.ensure_one()
        if not self.allowed_fields:
            return []
        try:
            return json.loads(self.allowed_fields)
        except (json.JSONDecodeError, TypeError):
            return []

    def check_field_access(self, field_names):
        """Check if the requested fields are allowed. Returns filtered field list."""
        self.ensure_one()
        allowed = self.get_allowed_fields_list()
        if not allowed:
            return field_names
        return [f for f in field_names if f in allowed or f == 'id']

    def check_operation(self, operation):
        """Check if the given operation is allowed on this model access."""
        self.ensure_one()
        operation_map = {
            'read': self.read_access,
            'search': self.read_access,
            'search_read': self.read_access,
            'browse': self.read_access,
            'count': self.read_access,
            'fields': self.read_access,
            'write': self.write_access,
            'create': self.create_access,
            'unlink': self.delete_access,
            'delete': self.delete_access,
        }
        return operation_map.get(operation, False)

    def check_user_groups(self, user):
        """Check if user belongs to allowed groups. Returns True if no restriction or user matches."""
        self.ensure_one()
        if not self.group_ids:
            return True
        return bool(self.group_ids & user.group_ids)

    @api.model
    def get_access_for_model(self, model_name, user=None):
        """Get MCP access configuration for a model. Returns recordset or empty."""
        domain = [('model_name', '=', model_name), ('active', '=', True)]
        access = self.sudo().search(domain, limit=1)
        if access and user and not access.check_user_groups(user):
            return self.browse()
        return access
