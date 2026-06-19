# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta, time as dt_time
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class POSchedulerConfig(models.Model):
    _name = 'po.scheduler.config'
    _description = 'Purchase Order Scheduler Configuration'
    _order = 'id desc'

    name = fields.Char(string='Name', required=True, default='PO Scheduler Configuration')
    active = fields.Boolean(default=True)
    cron_id = fields.Many2one('ir.cron', string='Cron', readonly=True)
    execution = fields.Datetime(
        string='Execution Date & Time',
        help='Set the date and time for the next execution. The cron will run at this time and repeat daily. After each run, it will automatically schedule the next day at the same time.'
    )
    type = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
    ])

    def create_po_order(self):
        self.ensure_one()
        self.cron_id.method_direct_trigger()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Notification',
                'message': 'The purchase order has been created successfully',
                'sticky': False
            }
        }

    def update_po_order(self):
        self.ensure_one()
        self.cron_id.method_direct_trigger()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Notification',
                'message': 'The purchase order has been updated successfully',
                'sticky': False
            }
        }


    def write(self, vals):
        if vals.get('execution'):
            self.cron_id.write({'nextcall': vals.get('execution')})
        return super(POSchedulerConfig, self).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(POSchedulerConfig, self).create(vals_list)
        if not res.execution:
            res.execution = res.cron_id.nextcall
        return res
