import requests
import logging
from odoo import models, api
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

# Configuration (should be moved to settings/config parameters)
N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/cf308c07-a4b1-4323-893c-b0797cdb639f"
REQUEST_TIMEOUT = None


def get_bot_partner(env):
    """Retrieve the AI Bot partner from config parameters"""
    try:
        param = env['ir.config_parameter'].sudo().get_param(
            'chatbot.ai_bot_partner_id'
        )
        if param:
            partner = env['res.partner'].browse(int(param))
            if partner.exists():
                return partner
    except (ValueError, TypeError):
        _logger.warning("Invalid AI bot partner ID in config")
    return None


def get_bot_user(env):
    """Retrieve the AI Bot user"""
    bot_partner = get_bot_partner(env)
    if not bot_partner:
        return None
    
    bot_user = env['res.users'].search([
        ('partner_id', '=', bot_partner.id)
    ], limit=1)
    return bot_user if bot_user else None


def can_perform(env, action, model_name=None):
    """Check if AI Bot has permission to perform an action on a model
    
    Args:
        env: Odoo environment
        action: Permission to check ('read', 'create', 'write', 'unlink')
        model_name: Optional model name (e.g., 'sale.order')
    
    Returns:
        bool: True if permission is granted, False otherwise
    """
    bot_user = get_bot_user(env)
    if not bot_user:
        _logger.debug("AI Bot user not found")
        return False

    domain = [('user_id', '=', bot_user.id)]

    if model_name:
        model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if model:
            domain.append(('model_id', '=', model.id))
        else:
            _logger.debug(f"Model '{model_name}' not found in ir.model")
            return False

    rules = env['ai.bot.access'].search(domain)
    if not rules:
        _logger.debug(f"No AI Bot access rules found for user {bot_user.id}")
        return False

    for rule in rules:
        if action == "read" and rule.allow_read:
            return True
        if action == "create" and rule.allow_create:
            return True
        if action == "write" and rule.allow_write:
            return True
        if action == "unlink" and rule.allow_unlink:
            return True

    _logger.debug(f"AI Bot permission denied for action '{action}'")
    return False


class Chatbot(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger AI Bot logic when new messages are created"""
        records = super().create(vals_list)
        
        bot_partner = get_bot_partner(self.env)
        if not bot_partner:
            _logger.warning("AI Bot partner not configured")
            return records

        for record in records:
            try:
                self._process_message_for_bot(record, bot_partner)
            except Exception as e:
                _logger.error(f"Chatbot processing error: {e}", exc_info=True)

        return records

    def _process_message_for_bot(self, record, bot_partner):
        """Process a message and trigger bot if conditions are met"""
        # Only process messages in discuss channels
        if record.model != "discuss.channel":
            return

        # Don't process messages from the bot itself
        if record.author_id and record.author_id.id == bot_partner.id:
            _logger.debug("Skipping message from bot")
            return

        # Get the channel
        channel = self.env["discuss.channel"].browse(record.res_id)
        if not channel.exists():
            _logger.debug(f"Channel {record.res_id} not found")
            return

        # Check if bot is in channel or mentioned
        is_bot_in_channel = bot_partner in channel.channel_partner_ids
        message_text = (record.body or "").lower()
        is_bot_mentioned = "ai bot" in message_text

        if not is_bot_in_channel and not is_bot_mentioned:
            _logger.debug("Bot not in channel and not mentioned")
            return

        # Check permissions
        if not can_perform(self.env, "read"):
            _logger.warning("AI Bot lacks read permission")
            return

        # Send message to N8N and process response
        self._send_to_n8n_and_reply(record, channel, bot_partner)

    def _send_to_n8n_and_reply(self, record, channel, bot_partner):
        """Send message to N8N webhook and post reply"""
        attachments = self._prepare_attachments(record)
        
        payload = {
            "message": record.body or "",
            "channel_id": record.res_id,
            "user_id": record.author_id.id if record.author_id else None,
            "attachments": attachments
        }

        try:
            _logger.debug(f"Sending message to N8N: {payload}")
            response = requests.post(
                N8N_WEBHOOK_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()

            data = response.json() if response.text else {}
            reply = data.get("reply")

            if reply:
                channel.message_post(
                    body=html_escape(reply),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    author_id=bot_partner.id,
                )
                _logger.info(f"Bot replied to message in channel {channel.id}")
            else:
                _logger.debug("No reply received from N8N")

        except requests.RequestException as e:
            _logger.error(f"N8N webhook request failed: {e}")
        except ValueError as e:
            _logger.error(f"Invalid JSON response from N8N: {e}")

    @staticmethod
    def _prepare_attachments(record):
        """Prepare attachment data for N8N payload"""
        attachments = []
        for att in record.attachment_ids:
            attachments.append({
                "id": att.id,
                "name": att.name,
                "mimetype": att.mimetype,
                "url": f"/web/content/{att.id}?download=true"
            })
        return attachments