from odoo import models, fields

class ResUsers(models.Model):
    _inherit = "res.users"

    ai_bot_access_ids = fields.One2many(
        "ai.bot.access",
        "user_id",
        string="AI Bot Access"
    )