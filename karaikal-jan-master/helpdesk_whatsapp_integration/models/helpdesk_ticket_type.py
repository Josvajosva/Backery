from odoo import api, fields, models


class HelpdeskCategory(models.Model):
    _name = "helpdesk.ticket.type"
    _description = "Helpdesk Ticket Type"
    _order = "sequence, id"
    _rec_name = "complete_name"

    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
    )
    name = fields.Char(
        required=True,
        translate=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    
    whatsapp_option = fields.Char(string='WhatsApp Option', index=True)
    whatsapp_category = fields.Char(string='WhatsApp Category', index=True)
    complete_name = fields.Char(
        compute="_compute_complete_name",
        recursive=True,
        search="_search_complete_name",
    )
    team_id = fields.Many2one(
        "helpdesk.team",
        "Team",
        index=True,
    )

    def _search_complete_name(self, operator, value):
        records = self.search_fetch([], ["complete_name"]).filtered_domain(
            [("complete_name", operator, value)]
        )
        return [("id", "in", records.ids)]

    @api.depends("name")
    @api.depends_context("lang")
    def _compute_complete_name(self):
        for ttype in self:
            ttype.complete_name = ttype.name
