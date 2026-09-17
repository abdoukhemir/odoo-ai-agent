import requests
import logging
from odoo import models, api
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _is_n8n_ai(self):
        """Check if this is the N8N Assistant channel"""
        is_n8n = self.name and self.name.strip() == "N8N Assistant"
        _logger.info(f"Channel check - Name: {self.name}, Is N8N: {is_n8n}")
        return is_n8n

    def _call_n8n(self, message):
        """Call N8N webhook and get reply"""
        try:
            _logger.info(f"Calling N8N with message: {message[:100]}")
            response = requests.post(
                "https://n8ninstance.abderrahmenkhemir.me/webhook-test/cf308c07-a4b1-4323-893c-b0797cdb639f",
                json={
                    "message": message,
                    "channel_id": self.id,
                },
                timeout=30,
            )
            _logger.info(f"N8N Response Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                reply = data.get("reply")
                _logger.info(f"N8N Reply: {reply}")
                return reply
            else:
                _logger.error(f"N8N Request failed with status: {response.status_code}")
                return None
        except requests.exceptions.Timeout as e:
            _logger.error("N8N Request Timeout: %s", e)
            return None
        except requests.exceptions.RequestException as e:
            _logger.error("N8N Request Error: %s", e)
            return None
        except Exception as e:
            _logger.error("N8N Error: %s", e)
            return None

    def message_post(self, **kwargs):
        """Intercept message posting to handle N8N AI replies"""
        # First, post the message normally
        msg = super().message_post(**kwargs)
        
        # Skip processing if not the N8N channel
        if not self._is_n8n_ai():
            return msg

        _logger.info("Processing N8N channel message")

        # Get message body
        body = kwargs.get("body", "").strip()
        if not body:
            _logger.warning("Empty message body, skipping N8N processing")
            return msg

        # Prevent infinite loops: don't reply to system/notification messages
        message_type = kwargs.get("message_type", "comment")
        if message_type in ("notification", "auto_subscribe"):
            _logger.info(f"Skipping message type: {message_type}")
            return msg

        # Prevent infinite loops: check if this is a bot response
        if kwargs.get("subtype_xmlid") == "mail.mt_notification":
            _logger.info("Skipping notification subtype")
            return msg

        try:
            # Call N8N to get reply
            reply = self._call_n8n(body)

            # Post the reply
            if reply:
                _logger.info(f"Posting N8N reply: {reply[:100]}")
                self.message_post(
                    body=html_escape(reply),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            else:
                _logger.warning("No reply received from N8N")
        except Exception as e:
            _logger.error("N8N Reply Error: %s", e)

        return msg