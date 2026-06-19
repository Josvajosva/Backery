{
    "name": "Helpdesk WhatsApp Integration",
    "summary": """
        Helpdesk""",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Rajeeth T",
    "depends": ["mail", "portal", "helpdesk", 'base', 'point_of_sale', 'contacts', 'maintenance', 'pos_loyalty', 'hr'],
    "data": [
        "security/ir.model.access.csv",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_ticket_type_views.xml",
        'views/res_partner.xml',
        'views/res_partner_pos_form.xml',
        "views/wa_reply_template_views.xml",
        'views/loyalty_program_views.xml',
        'views/loyalty_rule_views.xml',
        'views/hr_department.xml',
        "wizard/whatsapp_send_message_views.xml"
    ],
    "demo": [],
    'assets': {
        'point_of_sale._assets_pos': [
            # Quick customer creation files
            'helpdesk_whatsapp_integration/static/src/js/partner_list_override.js',
            'helpdesk_whatsapp_integration/static/src/xml/partner_list_override.xml',
            'helpdesk_whatsapp_integration/static/src/js/exclusive_rule.js',
            'helpdesk_whatsapp_integration/static/src/js/payment_screen_patch.js',
        ],
        'point_of_sale.assets': [
            # FontAwesome for icons
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css',
            
            # Your custom files
            #'helpdesk_whatsapp_integration/static/src/js/pos_redeem.js',
            #'helpdesk_whatsapp_integration/static/src/xml/pos_redeem.xml',
        ],
    },
    'qweb': [
        'static/src/xml/pos_redeem.xml',
    ],
    "application": True,
    "installable": True,
}
