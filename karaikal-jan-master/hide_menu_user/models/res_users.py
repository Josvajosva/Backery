# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import fields, models


class ResUsers(models.Model):
    """
    Model to handle hiding specific menu items for certain users.
    """
    _inherit = 'res.users'

    def write(self, vals):
        """
         Write method for the ResUsers model.
         Ensure the menu will not remain hidden after removing it from the list.
           """
        res = super(ResUsers, self).write(vals)
        # Only sync menu restrictions when hide_menu_ids is explicitly being
        # changed. This prevents ir.ui.menu access during unrelated writes such
        # as portal user creation, group changes, or login hooks — those paths
        # do not have ir.ui.menu read access and would raise an AccessError.
        if 'hide_menu_ids' not in vals:
            return res
        IrUiMenu = self.env['ir.ui.menu'].sudo()
        internal_group = self.env.ref('base.group_user')
        for record in self:
            # Skip portal/public users — they have no backend menu restrictions
            if internal_group not in record.sudo().groups_id:
                continue
            for menu in record.sudo().hide_menu_ids:
                menu.sudo().write({
                    'restrict_user_ids': [fields.Command.link(record.id)]
                })
            # Handle unlinked menus (removed from hide_menu_ids)
            previous_menus = IrUiMenu.search(
                [('restrict_user_ids', 'in', [record.id])])
            removed_menus = previous_menus - record.sudo().hide_menu_ids
            for menu in removed_menus:
                menu.sudo().write({
                    'restrict_user_ids': [fields.Command.unlink(record.id)]
                })
        return res

    def _get_is_admin(self):
        """
        Compute method to check if the user is an admin.
        The Hide specific menu tab will be hidden for the Admin user form.
        """
        for rec in self:
            rec.is_admin = False
            if rec.id == self.env.ref('base.user_admin').id:
                rec.is_admin = True

    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', string="Hidden Menu",
        groups='base.group_user',
        store=True, help='Select menu items that need to '
                         'be hidden to this user.')
    is_admin = fields.Boolean(compute=_get_is_admin, string="Is Admin",
                              help='Check if the user is an admin.')



class IrUiMenu(models.Model):
    """
    Model to restrict the menu for specific users.
    """
    _inherit = 'ir.ui.menu'

    restrict_user_ids = fields.Many2many(
        'res.users', string="Restricted Users",
        groups='base.group_user',
        help='Users restricted from accessing this menu.')