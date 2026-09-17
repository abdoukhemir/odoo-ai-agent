from odoo import models, fields, api
from odoo.exceptions import AccessError

class AiBotAccess(models.Model):
    _name = "ai.bot.access"
    _description = "AI Bot Access Rights"
    _rec_name = "model_id"

    user_id = fields.Many2one(
        "res.users",
        string="Bot User",
        required=True,
        ondelete="cascade",
        compute="_compute_bot_user",
        store=True,
        readonly=True,
        help="Automatically set to the AI Bot"
    )

    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        help="The Odoo model this permission applies to"
    )

    allow_read = fields.Boolean(default=True, help="Allow the bot to read records")
    allow_create = fields.Boolean(help="Allow the bot to create records")
    allow_write = fields.Boolean(help="Allow the bot to edit records")
    allow_unlink = fields.Boolean(help="Allow the bot to delete records")

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to automatically set the bot user"""
        bot_user = self._get_bot_user(self.env)
        
        for vals in vals_list:
            if 'user_id' not in vals or not vals['user_id']:
                if bot_user:
                    vals['user_id'] = bot_user.id
        
        result = super().create(vals_list)
        self._clear_bot_cache()
        return result
    
    def write(self, vals):
        """Override write to clear cache when rules are updated"""
        result = super().write(vals)
        self._clear_bot_cache()
        return result
    
    def unlink(self):
        """Override unlink to clear cache when rules are deleted"""
        result = super().unlink()
        self._clear_bot_cache()
        return result
    
    @staticmethod
    def _clear_bot_cache():
        """Clear the bot user cache in base_model_override"""
        try:
            from . import base_model_override
            base_model_override._bot_user_cache.clear()
        except Exception:
            pass

    @staticmethod
    def _get_bot_user(env):
        """Get the AI Bot user"""
        bot_user = env['res.users'].search([
            ('login', '=', 'ai.bot@yourdomain.com')
        ], limit=1)
        return bot_user if bot_user else None

    @api.depends()
    def _compute_bot_user(self):
        """Compute bot user for stored field"""
        bot_user = self._get_bot_user(self.env)
        for record in self:
            record.user_id = bot_user.id if bot_user else False

    @classmethod
    def check_bot_permission(cls, env, action, model_name):
        """Check if AI Bot has permission for an action on a model
        
        Args:
            env: Odoo environment
            action: 'read', 'create', 'write', or 'unlink'
            model_name: Model name like 'sale.order'
        
        Returns:
            bool: True if allowed, False if not allowed
        
        Raises:
            AccessError: If AI Bot user and action is denied
        """
        current_user = env.user
        bot_user = cls._get_bot_user(env)
        
        # Only enforce for AI Bot user
        if not bot_user or current_user.id != bot_user.id:
            return True
        
        # Get the permission rule
        model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not model:
            return False
        
        rule = env['ai.bot.access'].search([
            ('user_id', '=', bot_user.id),
            ('model_id', '=', model.id)
        ], limit=1)
        
        if not rule:
            return False
        
        if action == 'read':
            return rule.allow_read
        elif action == 'create':
            return rule.allow_create
        elif action == 'write':
            return rule.allow_write
        elif action == 'unlink':
            return rule.allow_unlink
        
        return False