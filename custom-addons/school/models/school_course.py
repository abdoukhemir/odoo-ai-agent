from odoo import models, fields

class SchoolCourse(models.Model):
    _name = 'school.course'
    _description = 'School Course'

    name = fields.Char(string='Course Name', required=True)
    description = fields.Text(string='Course Description')
    active = fields.Boolean(string='Active', default=True) 
    enrollment_ids = fields.One2many('school.enrollment', 'course_id', string='Enrollments')


    state = fields.Selection(string='State', selection=[('draft', 'Draft'),
                                                         ('scheduled', 'Scheduled'), 
                                                         ('start', 'Started'),
                                                         ('done', 'Done'),
                                                         ('cancelled', 'Cancelled')], default='draft')
    
    def action_schedule(self):
        self.state = 'scheduled'

    def action_start(self):
        self.state = 'start'

    def action_done(self):
        self.state = 'done'
    def action_cancel(self):
        self.state = 'cancelled'
                