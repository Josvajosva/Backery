{
    'name': 'KIFL Loyalty Report',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Export Loyalty History Report to Excel',
    'description': 'Provides a wizard to export Loyalty History grouped by customer and filtered by date range and type.',
    'author': 'KIFL',
    'depends': ['loyalty', 'sale', 'pos_loyalty'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/loyalty_report_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
