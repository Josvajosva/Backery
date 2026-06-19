# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TypeMaster(models.Model):
    _name = 'type.master'
    _description = 'Type Master'
    _order = 'name'

    name = fields.Char(string='Name', index=True)
    code = fields.Char(string='Code', index=True, copy=False)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Code must be unique!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code') is None:
                vals['code'] = vals.get('name')
        return super().create(vals_list)