from odoo import models, fields

class WorkflowTask(models.Model):
    _name = 'workflow.task'
    _description = 'Workflow Task'

    name = fields.Char(string='Task Name', required=True)
    action_type = fields.Selection([
        ('send_email', 'Send Email'),
        ('create_record', 'Create Record'),
        ('update_field', 'Update Field'),
        ('external_call', 'External API Call'),
    ], string='Action Type', required=True)
    
    sequence = fields.Integer(string='Sequence', default=10)
    workflow_id = fields.Many2one('workflow.definition', string='Workflow', required=True)
    