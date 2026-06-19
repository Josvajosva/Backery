# -*- coding: utf-8 -*-
from odoo import models, Command


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _prepare_opportunity_quotation_context(self):
        res = super()._prepare_opportunity_quotation_context()
        lead_attachments = self.env['ir.attachment'].search([('res_model', '=', 'crm.lead'), ('res_id', '=', self.id)])
        if lead_attachments:
            res['default_attachment_ids'] = [Command.link(attachment.id) for attachment in lead_attachments]
        return res
