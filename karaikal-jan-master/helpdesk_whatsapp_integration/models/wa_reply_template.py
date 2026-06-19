from odoo import api,fields, models, _


class WAReply_Template(models.Model):
    _name = "wa.reply.template"
    _description = "WAReply_Template"
    _order = 'id desc'
    _rec_name = "code"

    code = fields.Char(
        string="Code", copy=False, required=True
    )
    template = fields.Text(
        string="Template", copy=False, required=True
    )

