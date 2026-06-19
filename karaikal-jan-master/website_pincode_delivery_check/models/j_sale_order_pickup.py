# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields


class SaleOrderPickupSchedule(models.Model):
    _inherit = 'sale.order'

    # pickup_type and scheduled_pickup_datetime already declared in sale_order.py

    # Estimated ready time — auto-set on confirmation, manually updatable by staff.
    ready_time = fields.Datetime(string='Ready Time')

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order.delivery_option != 'store_pickup' or order.ready_time:
                continue
            now = fields.Datetime.now()
            if order.pickup_type == 'asap':
                order.ready_time = now + timedelta(minutes=20)
            elif order.pickup_type == 'scheduled' and order.scheduled_pickup_datetime:
                scheduled = order.scheduled_pickup_datetime
                # If customer's selected time is within 20 min, add 20 min buffer.
                # If it's further away, their selected time is already the ready time.
                if scheduled <= now + timedelta(minutes=20):
                    order.ready_time = scheduled + timedelta(minutes=20)
                else:
                    order.ready_time = scheduled
        return res