from odoo import models, fields, api

class SaleOrder(models.Model):
    _name = 'sale.custom.order'
    _description = 'Custom Sales Order'

    name = fields.Char(string="Order Reference", required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('sale.custom.order'))

    customer_id = fields.Many2one(
    'res.partner',
    string="Customer",
    required=True,
)

    order_date = fields.Date(string="Order Date", default=fields.Date.today)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('delivered', 'Delivered'),
        ('invoiced', 'Invoiced'),
    ], default='draft', string="Status", readonly=True)

    total_amount = fields.Float(
        string="Total Amount",
        compute="_compute_total_amount",
        store=True,
        readonly=True
    )

    salesperson_id = fields.Many2one('res.users', string="Salesperson")
    order_line_ids = fields.One2many('sale.custom.order.line', 'order_id', string="Order Lines")

    @api.depends('order_line_ids.subtotal')
    def _compute_total_amount(self):
        for order in self:
            order.total_amount = sum(line.subtotal for line in order.order_line_ids)

    # Workflow actions
    def action_confirm(self):
        self.write({'status': 'confirmed'})

    def action_deliver(self):
        self.write({'status': 'delivered'})

    def action_invoice(self):
        self.write({'status': 'invoiced'})
