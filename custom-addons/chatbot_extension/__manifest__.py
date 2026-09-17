{
    'name': 'Chatbot Extension',
    'version': '2.0',
    'depends': ['mail', 'im_livechat'],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_bot_access_views.xml',
    ],
    'post_init_hook': 'create_ai_bot',
    'installable': True,
}   