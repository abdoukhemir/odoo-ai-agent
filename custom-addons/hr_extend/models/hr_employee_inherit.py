from odoo import models, fields

class HREmployee(models.Model):
    _inherit = 'hr.employee'

    emergency_contact = fields.Char(string="Emergency Contact")

