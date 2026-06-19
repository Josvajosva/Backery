from odoo import api,fields, models
from datetime import datetime, timedelta



class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    sale_origin = fields.Char(string="Sale Origin",compute='_compute_sale_origin',copy=False,store=True)
    
    @api.depends('origin')
    def _compute_sale_origin(self):
        for picking in self:
            sale_origin = False
            if picking.origin:
                mrp_production = self.env['mrp.production'].search([('name', '=', picking.origin)], limit=1)
                if mrp_production and mrp_production.origin:
                    sale_order = self.env['sale.order'].search([('name', '=', mrp_production.origin)], limit=1)
                    if sale_order:
                        sale_origin = sale_order.name
            picking.sale_origin = sale_origin

class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    operation_batch_ids =fields.One2many('batch.operations','batch_id',string="Operations")
    partner_id = fields.Many2one('res.partner')
    
    def action_assign(self):
        self.batch_transfer()
        return super(StockPickingBatch, self).action_assign()
    
    def action_confirm(self):
        self.batch_transfer()
        return super(StockPickingBatch, self).action_confirm()
    
    def batch_transfer(self):
        for batch in self:
            product_data = {}

            for picking in batch.picking_ids:
                for move in picking.move_ids:
                    product_id = move.product_id.id
                    quantity = move.product_uom_qty  
                    demand = move.quantity

                    if product_id in product_data:
                        product_data[product_id]['quantity'] += quantity
                        product_data[product_id]['demand'] += demand
                    else:
                        product_data[product_id] = {
                            'product_id': product_id,
                            'transfer_id': picking.id,
                            'demand': demand,
                            'quantity': quantity,
                            'picked': False,  
                            'unit_of_measure': move.product_uom.id,
                        }

            self.env['batch.operations'].search([('batch_id', '=', batch.id)]).unlink()

            for data in product_data.values():
                self.env['batch.operations'].create({
                    'batch_id': batch.id,
                    'product_id': data['product_id'],
                    'transfer_id': data['transfer_id'],
                    'demand': data['demand'],
                    'qty': data['quantity'],
                    'picked': data['picked'],
                    'unit_of_measure': data['unit_of_measure'],
                })

            result_lines = [
                f"Product: {self.env['product.product'].browse(data['product_id']).name}, "
                f"Quantity: {data['quantity']}"
                for data in product_data.values()
            ]
            consolidated_data = "\n".join(result_lines)
         
class BatchOperations(models.Model):
    _name = 'batch.operations'
    _description = "Batch Operations"
    
    batch_id = fields.Many2one('stock.picking.batch',string="Batch")
    product_id = fields.Many2one('product.product',string="Product")
    transfer_id = fields.Many2one('stock.picking',string="Transfer")
    demand = fields.Float(string="Quantity",digits="Product Unit of Measure",)
    qty = fields.Float(string="Demand",digits="Product Unit of Measure",)
    picked = fields.Boolean(string="Picked")
    unit_of_measure = fields.Many2one('uom.uom',string="Unit Of Measure")
    
    
class StockLot(models.Model):
    _inherit = 'stock.lot'
        
    manufacturing_date = fields.Datetime(string="Manufacturing Date")
    product_expiry_status = fields.Selection(selection=[('near_expiry', 'Near Expiry'),('recall', 'Recall'),('expiry', 'Expired'), ],
    string="Product Expiry Status",store=True)

    activity_ids = fields.One2many('mail.activity', 'res_id', string="Activities", domain=[('res_model', '=', 'stock.lot')])


    def _check_product_expiry(self):
        today = fields.Date.today()
        records = self.search([('expiration_date', '!=', False)])

        for record in records:
            expiration_date = record.expiration_date.date()
            new_status = False

            if expiration_date <= today:
                new_status = 'expiry'
            elif expiration_date <= (today + timedelta(days=1)):
                new_status = 'recall'
            elif expiration_date <= (today + timedelta(days=2)):
                new_status = 'near_expiry'
            else:
                new_status = False  # No change

            if new_status and record.product_expiry_status != new_status:
                record.product_expiry_status = new_status
                self._update_activity(record)

    def _update_activity(self, record):
        """ Update activity: Remove old activities and create a new one """

        # Remove previous activities for this record
        old_activities = self.env['mail.activity'].search([
            ('res_model', '=', 'stock.lot'),
            ('res_id', '=', record.id)
        ])
        old_activities.unlink()

        expiry_status_string = dict(record._fields['product_expiry_status'].selection).get(record.product_expiry_status, '')

        activity_vals = {
            'res_model': 'stock.lot',
            'res_id': record.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'user_id': self.env.ref('base.user_admin').id, 
            'summary': expiry_status_string,
            'date_deadline': fields.Datetime.now(),
            'note': f'Product {record.product_id.display_name} is {expiry_status_string}.',
            'res_model_id': self.env['ir.model'].search([('model', '=', 'stock.lot')]).id
        }

        new_activity = self.env['mail.activity'].create(activity_vals)

        # Assign the latest activity to the record
        record.activity_ids = [(4, new_activity.id)]


class MrpProductions(models.Model):
    _inherit = "mrp.production"

    product_category = fields.Many2one(string='Product Category',related='product_id.categ_id')
    product_tag_ids = fields.Many2many(string="Tag",related='product_id.product_tag_ids')


    def button_mark_done(self):
        res = super(MrpProductions, self).button_mark_done()
        for production in self:
            if production.date_finished and production.lot_producing_id:
                production.lot_producing_id.manufacturing_date = production.date_finished

        return res
    
    
