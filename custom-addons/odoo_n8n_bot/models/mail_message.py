import requests
import logging
from odoo import models
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    # --------------------------------------------------
    # 1. Detect AI channel
    # --------------------------------------------------
    def _is_ai_channel(self):
        return self.name and "ai" in self.name.lower()

    # --------------------------------------------------
    # 2. Send message to n8n
    # --------------------------------------------------
    def _send_to_n8n(self, message):
        payload = {
            "message": message,
            "channel_id": self.id,
        }

        _logger.info("Sending to n8n: %s", payload)

        response = requests.post(
            "https://n8ninstance.abderrahmenkhemir.me/webhook-test/cf308c07-a4b1-4323-893c-b0797cdb639f",
            json=payload,
            timeout=60,
        )

        data = response.json() if response else {}
        return data.get("reply")

    # --------------------------------------------------
    # 3. Hook into chat
    # --------------------------------------------------
    def message_post(self, **kwargs):

        message = super().message_post(**kwargs)

        try:
            body = kwargs.get("body") or ""

            # REMOVE HTML if needed
            clean_body = body.lower()

            # ONLY AI CHANNELS
            if not self._is_ai_channel():
                return message

            # Avoid bot replying to itself (important)
            if kwargs.get("message_type") == "notification":
                return message

            # Send to n8n
            reply = self._send_to_n8n(body)

            # Post reply
            if reply:
                self.message_post(
                    body=html_escape(reply),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )

        except Exception as e:
            _logger.error("N8N BOT ERROR: %s", e)

        return message