# -*- coding: utf-8 -*-
from odoo import fields, models, api
from ..controllers.main import *
import logging

_logger = logging.getLogger(__name__)


class helpdeskwaiSendMessage(models.TransientModel):
    """This model is used for sending WhatsApp messages through Odoo."""
    _name = 'helpdesk.wai.send.message'
    _description = "Whatsapp Wizard"

    ticket_id = fields.Many2one('helpdesk.ticket', string="Ticket")
    template_id = fields.Many2one('wa.reply.template', string="Template")
    mobile = fields.Char(related='ticket_id.partner_mobile', required=True)
    message = fields.Text(string="Message", required=True)

    @api.onchange('template_id')
    def _onchange_message(self):
        for msg in self:
            msg.message = msg.template_id.template

    def action_send_message(self):
        """This method is called to send the WhatsApp message using the
         provided details."""
        if self.message and self.mobile:
            if not self.ticket_id.ticket_response:
                api_return = HelpdeskTicket_WA().api_ticket_reply_wa(self.ticket_id, self.message)
                _logger.info("API Return Response: %s", api_return)
                if api_return and api_return.get('message'):
                    self.ticket_id.ticket_response = self.message
                return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": "Done",
                            "message": "WhatsApp message sent successfully.",
                            "type": "success",
                            "sticky": False,
                            "next": {"type": "ir.actions.act_window_close"},
                        }
                    }
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Whatsapp Message',
                    'res_model': 'whatsapp.message',
                    'view_mode': 'form',
                    'target': 'new',
                    'params': {
                        'view_type': 'form',
                    },
                }

            else:
                return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": "Warning",
                            "message": "WhatsApp message already sent to this ticket.",
                            "type": "error",
                            "sticky": False,
                            "next": {"type": "ir.actions.act_window_close"},
                        }
                    }
