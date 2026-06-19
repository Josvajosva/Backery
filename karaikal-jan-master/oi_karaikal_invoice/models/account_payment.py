# -*- coding: utf-8 -*-
from odoo import models,_

class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    def write(self, vals):
        res = super().write(vals)
        template_id = self.env.ref('oi_karaikal_invoice.mail_template_account_payment').id
        template = self.env['mail.template'].browse(template_id)
        for record in self:
            if record.state == 'paid' and record.payment_type == 'inbound':
              
                if template:
                    template.write({
                        'email_to': record.partner_id.email,
                        'email_from': self.env.user.email,
                        'subject': f'Payment Notification: {record.name}',
                    })
                        
                    template.send_mail(record.id, force_send=True)
        return res

    
