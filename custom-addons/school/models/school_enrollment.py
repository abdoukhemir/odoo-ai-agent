from odoo import models, fields

class SchoolEnrollment(models.Model):
    _name = 'school.enrollment'
    _description = 'School Enrollment'

    enrollment_date = fields.Date(string='Enrollment Date',default=fields.Date.today)
    grade = fields.Char(string='Grade')
    active= fields.Boolean(string='Active', default=True)
    student_id = fields.Many2one('school.student', string='Student', required=True) #Many enrollements can belong to one student
    course_id = fields.Many2one('school.course', string='Course', required=True)
    phone_number = fields.Integer(string='Student Number' ,related='student_id.phone_number')
