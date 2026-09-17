from odoo import models, fields

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    custom_reference = fields.Char(string="Custom Reference")
