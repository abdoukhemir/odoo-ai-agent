from odoo import fields, models,api 
from datetime import date
from odoo.exceptions import ValidationError

class SchoolStudent(models.Model):
    _name = 'school.student'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'School Student'

    name = fields.Char(string='Name', required=True , tracking=True)
   
    phone_number = fields.Integer(string='Phone Number' ,required=True , size = 8)
    
    date_of_birth = fields.Date(string='Date of Birth' )
    adress = fields.Text(string='Address')
    email = fields.Char(string='Email')
    age = fields.Integer(string='Age', compute='_compute_age', store=True) #compute is used to calculate the age based on the date of birth, store=True means that the age will be stored in the database and not calculated on the fly every time it is accessed.
    active = fields.Boolean(string='Active', default=True) # Used by Odoo to archive records instead of deleting them.
                                                           # If active = False -> record is hidden (archived) but still exists in DB.
    
    Image = fields.Binary(string='Image' , attachment=True) #attachment=True allows you to store the image as a file in the database, which can be more efficient for larger files. It also provides better performance when retrieving and displaying images in the Odoo interface.
    Gender = fields.Selection(string='Gender', selection=[('male', 'Male'), ('female', 'Female')])
   

    enrollment_ids = fields.One2many('school.enrollment', 'student_id', string='Enrollments')
    teacher_id = fields.Many2one("res.users" , string="Teacher") 
    
    parent_id = fields.Many2one("res.partner", string="Parent")
    
    std_ref = fields.Char(
        string='Student Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('student.seq') or 'New',
    )
    @api.depends('date_of_birth')
    def _compute_age(self):
        for rec in self:
            if rec.date_of_birth:
                today = date.today()
                rec.age = today.year - rec.date_of_birth.year
            else:
                rec.age = 0
    @api.constrains('age')
    def _check_age(self):
        for record in self:
            if record.age < 5:
                raise ValidationError("Student must be at least 5 years old.")
   # @api.constrains('phone_number')
    #def _check_phone_number(self): #self is the record of school.student
     #   for record in self:
      #      if  len(str(record.phone_number)) < 8 and len(str(record.phone_number)) > 8:
       #         raise models.ValidationError("Phone number must be 8 digits long.")

 #   @api.onchange('date_of_birth')
  #  def _onchange_date_of_birth(self):
   #     if self.date_of_birth:
    #        today = fields.Date.today()
     #       age = today.year - self.date_of_birth.year
      #      if age < 0:
                
       #         return {
        #            'warning': {
         #               'title': "Invalid Date of Birth",
          #              'message': "Date of Birth cannot be in the future.",
           #         }
            #    }


    _sql_constraints = [
        ('unique_name', 'unique(name)', 'The name must be unique.'),
        ('unique_phone_number', 'unique(phone_number)', 'The phone number must be unique.')

        ]
    

#ORM
    @api.model
    def create(self, vals):
        if 'phone_number' in vals:
            phone = str(vals.get('phone_number') or '')
            if not phone.isdigit() or len(phone) != 8:
                raise ValidationError("Phone number must be 8 digits long and contain only numbers.")
        record= super(SchoolStudent, self).create(vals)
        return record    
    
    def write(self, vals):
        if 'phone_number' in vals:
            phone = str(vals.get('phone_number') or '')
            if not phone.isdigit() or len(phone) != 8:
                raise ValidationError("Phone number must be 8 digits long and contain only numbers.")
        record = super(SchoolStudent, self).write(vals)
        return record
    
    def unlink(self):
        if not self.env.user.has_group('school.group_manager'):
            raise ValidationError("Only users with the Manager role can delete student records.")
        return super(SchoolStudent, self).unlink()
    #self.env.context is a dictionary that contains information about the current environment, such as the current user, language, and other contextual data.
# self.env['school.course'].create({'name': 'Mathematics', 'description': 'Basic math course'}) is an example of how to create a new record in the school.course model using the Odoo ORM. The create method takes a dictionary of field values as an argument and creates a new record in the database with those values. In this case, it creates a new course with the name "Mathematics" and the description "Basic math course".   
# self.env['school.course'].search([('name', '=', 'Mathematics')]) is an example of how to search for records in the school.course model using the Odoo ORM. The search method takes a list of domain filters as an argument and returns a recordset of matching records. In this case, it searches for courses where the name field is equal to "Mathematics" and returns the matching records.