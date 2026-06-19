{
    'name': 'Dynamic Company Sequence',
    'version': '18.0.1.0.0',
    'category': 'Administration',
    'summary': 'Automatically generate and manage company-wise sequences with configurable document types.',
    'depends': ['base', 'purchase', 'account', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/sequence_config_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
