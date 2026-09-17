from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    custom_note = fields.Char(string="Internal Note")
