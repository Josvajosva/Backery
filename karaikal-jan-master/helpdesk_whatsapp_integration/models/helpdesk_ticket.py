from odoo import api,fields, models, _


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"
    _order = 'id desc'

    type_id = fields.Many2one(
        comodel_name="helpdesk.ticket.type",
        string="Type",
        tracking=True,
    )
    employee_created = fields.Boolean(
        string="Employee Created Ticket?", copy=False,
        tracking=True,
    )
    partner_mobile = fields.Char(
        string="Mobile", copy=False,
        tracking=True,
    )
    store_location = fields.Char(
        string="Store Location", copy=False,
        tracking=True,
    )
    store_identifier = fields.Char(
        string="Store Identifier", copy=False,
        tracking=True,
    )
    equipment_id = fields.Many2one(
        comodel_name="maintenance.equipment",
        string="Equipment", copy=False,
        tracking=True,
    )
    equipment_name = fields.Char(
        string="Equipment/Machine Name", copy=False,
        tracking=True,
    )
    image_url = fields.Char(string="Cake Image", tracking=True)
    product_enquiry = fields.Char(string="Product Enquiry", copy=False, tracking=True)
    required_qty = fields.Char(string="Required Quantity", copy=False, tracking=True)
    expected_delivery = fields.Datetime(string="Expected Delivery Time", copy=False, tracking=True)
    complaint_regarding = fields.Char(string="Complaint Regarding", copy=False, tracking=True)
    critical_level = fields.Char(string="Critical Level", copy=False, tracking=True)
    material_category = fields.Char(string="Material Category", copy=False, tracking=True)
    shortage_material = fields.Char(string="Shortage Material Name", copy=False, tracking=True)
    affected_areas = fields.Char(string="Area / Process Affected", copy=False, tracking=True)
    quality_issue_type = fields.Char(string="Type of Quality Issue", copy=False, tracking=True)
    quality_issue_product = fields.Char(string="Product with Issue", copy=False, tracking=True)
    system_name = fields.Char(string="System / Device Name", copy=False, tracking=True)
    employee_details = fields.Char(string="Employee Code & Name", copy=False, tracking=True)
    grievance_category = fields.Char(string="Grievance Category", copy=False, tracking=True)
    ticket_response = fields.Char(string="Ticket Response", copy=False, tracking=True)
    whatsapp_option = fields.Char(
        compute="_compute_whatsapp_option",
        store=True,
    )
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department", copy=False,
        tracking=True,
    )


    @api.depends("type_id")
    def _compute_whatsapp_option(self):
        for tk in self:
            tk.whatsapp_option = tk.type_id.whatsapp_option


    def action_wa_send_msg(self):
        """This function is called when the user clicks the
         'Send WhatsApp Message' button on a ticket's form view. It opens a
          new wizard to compose and send a WhatsApp message."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Whatsapp Message',
            'res_model': 'helpdesk.wai.send.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_id': self.id},
        }








