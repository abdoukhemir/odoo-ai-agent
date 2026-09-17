"""
Override base model methods to enforce AI Bot access control
"""
from odoo import models, api
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)

# Cache for bot user to avoid repeated searches
_bot_user_cache = {}


def _get_cached_bot_user(env):
    """Get AI Bot user with caching"""
    db_name = env.cr.dbname
    if db_name not in _bot_user_cache:
        bot_user = env['res.users'].search([
            ('login', '=', 'ai.bot@yourdomain.com')
        ], limit=1)
        _bot_user_cache[db_name] = bot_user.id if bot_user else None
    return _bot_user_cache[db_name]


def _check_bot_access(env, action, model_name):
    """Check if current user (if AI Bot) has permission for action on model
    
    Strategy: Only enforce permissions for models that have explicit rules.
    If no rule exists, allow the operation (for auto-generated/internal models).
    
    Returns: True if allowed or not AI Bot user, False if denied
    """
    current_user_id = env.user.id
    bot_user_id = _get_cached_bot_user(env)
    
    # Only enforce for AI Bot user
    if not bot_user_id or current_user_id != bot_user_id:
        return True
    
    try:
        # Get the permission rule for this model
        model = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if not model:
            # Model doesn't exist in ir.model - allow (likely internal)
            _logger.debug(f"Model '{model_name}' not found in ir.model - allowing")
            return True
        
        rule = env['ai.bot.access'].sudo().search([
            ('user_id', '=', bot_user_id),
            ('model_id', '=', model.id)
        ], limit=1)
        
        # If no rule exists for this model, ALLOW the operation
        # This handles all auto-generated/internal models automatically
        if not rule:
            _logger.debug(f"No AI Bot access rule for model '{model_name}' - allowing")
            return True
        
        # Rule exists - enforce it
        if action == 'read':
            return rule.allow_read
        elif action == 'create':
            return rule.allow_create
        elif action == 'write':
            return rule.allow_write
        elif action == 'unlink':
            return rule.allow_unlink
        
        return False
    
    except Exception as e:
        _logger.error(f"Error checking AI Bot access: {e}", exc_info=True)
        # Allow on error to prevent bot from being completely blocked
        return True


def _patch_model_create(original_create):
    """Wrap create method to check AI Bot permissions"""
    @api.model_create_multi
    def patched_create(self, vals_list):
        if not _check_bot_access(self.env, 'create', self._name):
            raise AccessError(
                f"AI Bot is not allowed to create '{self._name}' records. "
                f"Please configure permissions in Settings > AI Bot Permissions."
            )
        return original_create(self, vals_list)
    return patched_create


def _patch_model_write(original_write):
    """Wrap write method to check AI Bot permissions"""
    def patched_write(self, vals):
        if not _check_bot_access(self.env, 'write', self._name):
            raise AccessError(
                f"AI Bot is not allowed to edit '{self._name}' records. "
                f"Please configure permissions in Settings > AI Bot Permissions."
            )
        return original_write(self, vals)
    return patched_write


def _patch_model_unlink(original_unlink):
    """Wrap unlink method to check AI Bot permissions"""
    def patched_unlink(self):
        if not _check_bot_access(self.env, 'unlink', self._name):
            raise AccessError(
                f"AI Bot is not allowed to delete '{self._name}' records. "
                f"Please configure permissions in Settings > AI Bot Permissions."
            )
        return original_unlink(self)
    return patched_unlink


def patch_odoo_models():
    """Apply AI Bot access control patches to Odoo models"""
    try:
        original_create = models.BaseModel.create
        original_write = models.BaseModel.write
        original_unlink = models.BaseModel.unlink
        
        models.BaseModel.create = _patch_model_create(original_create)
        models.BaseModel.write = _patch_model_write(original_write)
        models.BaseModel.unlink = _patch_model_unlink(original_unlink)
        
        _logger.info("✓ AI Bot access control enforcement activated")
    except Exception as e:
        _logger.error(f"Failed to apply AI Bot patches: {e}", exc_info=True)
