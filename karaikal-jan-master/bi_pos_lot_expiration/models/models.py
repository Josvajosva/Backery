# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class PosConfig(models.Model):
	_inherit = "pos.config"

	allow_expiry_warning = fields.Boolean(string="Allow Lot Expiry Warning")
	restrict_creating_lot = fields.Boolean(string="Restrict User from Creating New Lot")


class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	pos_allow_expiry_warning = fields.Boolean(related='pos_config_id.allow_expiry_warning',readonly=False)
	pos_restrict_creating_lot = fields.Boolean(related='pos_config_id.restrict_creating_lot',readonly=False)

class StockLot(models.Model):
	_inherit = 'stock.lot'


	@api.model
	def _load_pos_data_fields(self, config_id):
		return ['name','product_id','alert_date','expiration_date','removal_date','product_qty']

	def _load_pos_data(self, data):
		domain = [('product_qty', '>', 0)]
		fields = self._load_pos_data_fields(data['pos.config']['data'][0]['id'])
		data = self.search_read(domain, fields, load=False)
		return {
			'data': data,
			'fields': fields
		}


class POSOrderLoad(models.Model):
	_inherit = 'pos.session'

	@api.model
	def _load_pos_data_models(self, config_id):
		data = super()._load_pos_data_models(config_id)
		model = 'stock.lot'
		if model not in data:
			data += ['stock.lot']
		return data
