from odoo import models, fields
from odoo.exceptions import UserError

class WorkflowDefinition(models.Model):
    _name = 'workflow.definition'
    _description = 'Workflow Definition'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Workflow Name', required=True, tracking=True)

    trigger_type = fields.Selection([
        ('manual', 'Manual'),
        ('cron', 'Scheduled'),
        ('webhook', 'Webhook'),
        ('email', 'Email'),
    ], string='Trigger Type', default='manual', tracking=True)

    active = fields.Boolean(string='Active', default=True)
    task_ids = fields.One2many('workflow.task', 'workflow_id', string='Tasks')

    last_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], string="Last Status")

    last_run_date = fields.Datetime(string="Last Run Date")

    def run_workflow(self):
        details = []
        try:
            for task in self.task_ids.sorted(key=lambda t: t.sequence):
                if task.action_type == 'send_email':
                    self._execute_send_email(task)
                elif task.action_type == 'update_field':
                    self._execute_update_field(task)
                details.append(f'Task {task.name} executed')

            # Update workflow definition fields
            self.last_run_date = fields.Datetime.now()
            self.last_status = 'success'

            # Create one log entry
            self.env['workflow.log'].create({
                'workflow_id': self.id,
                'status': 'success',
                'details': "\n".join(details),
            })

            # Show popup notification (instead of raising an error)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Workflow',
                    'message': 'Workflow executed successfully!',
                    'type': 'success',  # green popup
                    'sticky': False,
                }
            }

        except Exception as e:
            self.last_status = 'failed'
            self.env['workflow.log'].create({
                'workflow_id': self.id,
                'status': 'failed',
                'details': str(e),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Workflow',
                    'message': f'Workflow failed: {str(e)}',
                    'type': 'danger',  # red popup
                    'sticky': True,
                }
            }

    def _execute_send_email(self, task):
        raise Exception("Email server not reachable")
        #return True

    def _execute_update_field(self, task):
        # Placeholder logic
        return True
