{
    'name': 'Workflow Automator',
    'version': '1.0',
    'summary': 'Intelligent workflow automation with chatbot and visual editor',
    'description': 'Module for creating, managing, and monitoring automated workflows across Odoo modules.',
    'author': 'Abderrahmen Khemir',
    'category': 'Tools',
    'depends': ['base', 'mail'],  # base for ORM, mail for chatter/logging
    'data': [
        'security/ir.model.access.csv',
        'views/workflow_definition_views.xml',
        'views/workflow_task_views.xml',
        'views/workflow_log_views.xml',
        'views/base_menu.xml',
    ],
    'demo': [ 'data/workflow_demo.xml', ],
    'installable': True,
    'application': True,
}
