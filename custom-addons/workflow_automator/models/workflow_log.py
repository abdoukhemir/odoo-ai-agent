from odoo import models, fields

class WorkflowLog(models.Model):
    _name = 'workflow.log'
    _description = 'Workflow Execution Log'

    workflow_id = fields.Many2one('workflow.definition', string='Workflow', required=True)
    execution_date = fields.Datetime(string='Execution Date', default=fields.Datetime.now)
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ], string='Status', default='pending')
    duration = fields.Float(string='Duration (seconds)')
    details = fields.Text(string='Details')
