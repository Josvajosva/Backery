from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    location_names = [
        "KZ/Stock",
        "NBS/Stock",
        "OBS/Stock",
        "NS/Stock",
        "SBI/Stock",
        "AD/Stock",
        "NG/Stock",
        "TV/Stock",
        "KL/Stock",
        "VL/Stock",
        "TP/Stock",
        "MG/Stock",
        "MP/Stock",
        "PVI/Stock",
        "PR/Stock",
        "TM/Stock",
        "TML/Stock",
        "koilvenni",
        "KVI/Stock",
        "WH/Stock/CENTRAL DISTRIBUTION HUB",
    ]

    locations = env['stock.location'].search([
        ('usage', '=', 'internal'),
        ('complete_name', 'in', location_names),
    ])
    if locations:
        locations.write({'barcode_stock_take_location': True})