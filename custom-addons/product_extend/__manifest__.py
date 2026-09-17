{
    'name': 'Product Extend',
    'version': '19.0.1.0.0',

    'summary': 'Ensure product API compatibility',
    'depends': ['product', 'sale'],
    'data': [  
        'views/product_product.xml',
        'views/base_menu.xml',
            ],
    'installable': True,
    'application': True,
}