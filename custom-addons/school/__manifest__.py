{
    'name': 'School',
    'version': '1.0',
    'summary': 'Manage school operations and student information',
    'author': 'abdou',
    'icon' : '/school/static/description/icon.png',
    'depends': ['base', 'mail'],
    'data': [
        "security/security.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/base_menu.xml", 
        "views/student_view.xml",
        "views/course_view.xml",
        "views/enrollment_view.xml",
        "data/sequence.xml",
    ],

    'assets': {
        'web.assets_backend': [
            '/school/static/src/index.css'

        ]
        },



    'installable': True,
    'application': True,
    
}