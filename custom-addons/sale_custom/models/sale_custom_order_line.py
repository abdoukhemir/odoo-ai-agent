from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _name = 'sale.custom.order.line'
    _description = 'Custom Sales Order Line'

    order_id = fields.Many2one(
        'sale.custom.order',
        string="Order",
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'sale.custom.product',
        string="Product",
        required=True
    )

    quantity = fields.Integer(string="Quantity", default=1)

    # Unit price comes from product but can be overridden
    unit_price = fields.Float(
        string="Unit Price",
        related="product_id.unit_price",
        store=True,
        readonly=False
    )

    subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_subtotal",
        store=True,
        readonly=True   # ✅ readonly so user cannot edit
    )

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
