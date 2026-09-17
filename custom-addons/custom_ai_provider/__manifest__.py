{
    'name': 'Custom AI Provider',
    'version': '19.0.1.0.0',
    'category': 'Tools/AI',
    'summary': 'Add Custom Provider support to Odoo AI Topics',
    'description': '''
        Adds a "Custom Provider" option to Odoo AI Topics, allowing you to configure
        any OpenAI-compatible API endpoint with URL and API key.
        
        Perfect for N8N workflows or any custom LLM APIs.
    ''',
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'ai',
    ],
    'data': [
        'views/ai_topic_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
