from odoo import models, fields

class SaleProduct(models.Model):
    _name = 'sale.custom.product'
    _description = 'Custom Product'

    name = fields.Char(string="Product Name", required=True)
    description = fields.Text(string="Description")
    unit_price = fields.Float(string="Unit Price", required=True)
