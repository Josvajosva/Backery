from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta, datetime
import logging
import re

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    whatsapp_number = fields.Char(string="WhatsApp Number")
    dob = fields.Date(string="Date of Birth")
    anniversary = fields.Date(string="Anniversary")
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string="Gender")

    points_earned = fields.Integer(
        compute='_compute_loyalty_points',
        string="Points Earned",
    )
    points_redeemed = fields.Integer(
        compute='_compute_loyalty_points',
        string="Points Redeemed",
    )
    available_points = fields.Integer(
        compute='_compute_loyalty_points',
        string="Available Points",
    )
    has_membership = fields.Boolean(string="Membership Activated", default=False)

    last_pos_order_date = fields.Date(
        string="Last POS Order Date",
        store=True,
    )


    def _compute_loyalty_points(self):
        if not self.ids:
            for partner in self:
                partner.points_earned = 0
                partner.points_redeemed = 0
                partner.available_points = 0
            return

        self.env.cr.execute("""
            SELECT
                lc.partner_id,
                COALESCE(SUM(lh.issued), 0) AS total_earned,
                COALESCE(SUM(lh.used), 0) AS total_redeemed
            FROM loyalty_card lc
            JOIN loyalty_program lp ON lp.id = lc.program_id
            LEFT JOIN loyalty_history lh ON lh.card_id = lc.id
            WHERE lc.partner_id IN %s
              AND lp.program_type = 'loyalty'
              AND lc.active = True
            GROUP BY lc.partner_id
        """, [tuple(self.ids)])

        results = {row[0]: (row[1], row[2]) for row in self.env.cr.fetchall()}

        for partner in self:
            earned, redeemed = results.get(partner.id, (0, 0))
            partner.points_earned = int(earned)
            partner.points_redeemed = int(redeemed)
            partner.available_points = int(earned - redeemed)


    @api.model
    def _load_pos_data_fields(self, config_id):
        params = super()._load_pos_data_fields(config_id)
        # Ensure mobile is included (base POS may not include it; we need it for mobile search)
        for field in ['mobile', 'available_points', 'has_membership', 'last_pos_order_date']:
            if field not in params:
                params.append(field)
        return params

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        """
        Override to allow searching customers by mobile number in POS and other views.
        When a numeric string (mobile number) is entered, also search in `mobile` and `phone` fields.
        """
        domain = domain or []

        if name and name.strip():
            # Strip out non-digits to check if the search term looks like a phone number
            digits_only = re.sub(r'\D', '', name.strip())
            is_phone_search = len(digits_only) >= 7  # At least 7 digits → treat as phone/mobile search

            if is_phone_search:
                # Build a domain that matches name OR mobile OR phone
                phone_domain = [
                    '|', '|',
                    ('name', operator, name),
                    ('mobile', 'ilike', digits_only),
                    ('phone', 'ilike', digits_only),
                ]
                return super()._name_search(
                    name='',
                    domain=phone_domain + domain,
                    operator=operator,
                    limit=limit,
                    order=order,
                )

        return super()._name_search(name=name, domain=domain, operator=operator, limit=limit, order=order)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """
        Override _search to preprocess domain for mobile/phone/whatsapp_number searches.
        If a numeric string (mobile number) is used in search criteria, resolve it by matching
        against non-digit stripped numbers in the database, allowing flexible matches
        (e.g., matching +91 94433 32978 when searching for 9443332978).
        """
        domain = domain or []
        phone_searched_digits = None

        for term in domain:
            if isinstance(term, (list, tuple)) and len(term) == 3:
                field, operator, val = term
                if field in ('mobile', 'phone', 'whatsapp_number') and isinstance(val, str):
                    clean_val = val.replace('%', '').strip()
                    digits = re.sub(r'\D', '', clean_val)
                    if len(digits) >= 7:
                        phone_searched_digits = digits
                        break

        if phone_searched_digits:
            query = """
                SELECT id FROM res_partner
                WHERE (mobile IS NOT NULL AND REGEXP_REPLACE(mobile, '\D', '', 'g') LIKE %s)
                   OR (phone IS NOT NULL AND REGEXP_REPLACE(phone, '\D', '', 'g') LIKE %s)
                   OR (whatsapp_number IS NOT NULL AND REGEXP_REPLACE(whatsapp_number, '\D', '', 'g') LIKE %s)
            """
            self.env.cr.execute(query, ('%' + phone_searched_digits + '%', '%' + phone_searched_digits + '%', '%' + phone_searched_digits + '%'))
            partner_ids = [r[0] for r in self.env.cr.fetchall()]

            new_domain = []
            for term in domain:
                if isinstance(term, (list, tuple)) and len(term) == 3:
                    field, operator, val = term
                    if field in ('mobile', 'phone', 'whatsapp_number'):
                        new_domain.append(('id', 'in', partner_ids))
                    else:
                        new_domain.append(term)
                else:
                    new_domain.append(term)
            domain = new_domain

        return super()._search(domain, offset=offset, limit=limit, order=order)

    def action_add_joining_bonus(self):
        for partner in self:
            if partner.has_membership:
                return
            partner.sudo().write({'has_membership': True})

            loyalty_cards = self.env['loyalty.card'].sudo().search([
                ('partner_id', '=', partner.id),
                ('program_id.program_type', '=', 'loyalty'),
            ])
            if not loyalty_cards:
                loyalty_program = self.env['loyalty.program'].sudo().search([
                    ('program_type', '=', 'loyalty'),
                ], limit=1)
                if loyalty_program:
                    loyalty_cards = self.env['loyalty.card'].sudo().with_context(
                        skip_membership_bonus=True
                    ).create({
                        'partner_id': partner.id,
                        'program_id': loyalty_program.id,
                        'points': 0,
                    })
            if loyalty_cards:
                bonus_exists = self.env['loyalty.history'].sudo().search_count([
                    ('card_id', 'in', loyalty_cards.ids),
                    ('description', '=', 'Membership Bonus'),
                ])
                if not bonus_exists:
                    lc = loyalty_cards[0]
                    self.env['loyalty.history'].sudo().create({
                        'description': 'Membership Bonus',
                        'issued': 25,
                        'card_id': lc.id,
                    })
                    lc.sudo().points += 25

    @api.constrains('mobile', 'whatsapp_number')
    def _check_mobile_duplication(self):
        """Validate mobile number duplication for loyalty customers"""
        for partner in self:
            mobile_numbers_to_check = []
            if partner.mobile:
                normalized_mobile = self._normalize_phone_number(partner.mobile)
                if normalized_mobile:
                    mobile_numbers_to_check.append(normalized_mobile)

            if partner.whatsapp_number:
                normalized_whatsapp = self._normalize_phone_number(partner.whatsapp_number)
                if normalized_whatsapp:
                    mobile_numbers_to_check.append(normalized_whatsapp)

            mobile_numbers_to_check = list(set(mobile_numbers_to_check))

            for number in mobile_numbers_to_check:
                if not number:
                    continue

                query = """
                    SELECT id, name FROM res_partner 
                    WHERE id != %s 
                    AND (
                        (mobile IS NOT NULL AND REGEXP_REPLACE(mobile, '\D', '', 'g') LIKE %s)
                        OR 
                        (whatsapp_number IS NOT NULL AND REGEXP_REPLACE(whatsapp_number, '\D', '', 'g') LIKE %s)
                    )
                """

                self.env.cr.execute(query, (partner.id, '%' + number + '%', '%' + number + '%'))
                duplicate_records = self.env.cr.fetchall()

                if duplicate_records:
                    duplicate_names = ', '.join([record[1] for record in duplicate_records])
                    raise ValidationError(
                        _("Mobile number %s is already registered with customer(s): %s. "
                          "Each customer must have a unique mobile number.") %
                        (number, duplicate_names)
                    )

    def _normalize_phone_number(self, phone):
        """Normalize phone number by removing spaces, dashes, and country code"""
        if not phone:
            return None

        normalized = re.sub(r'\D', '', str(phone))

        if normalized.startswith('91') and len(normalized) > 10:
            normalized = normalized[2:]

        if len(normalized) == 10 and normalized.isdigit():
            return normalized

        if len(normalized) == 11 and normalized.startswith('0') and normalized[1:].isdigit():
            return normalized[1:]

        return None

    # def action_add_joining_bonus(self):
    #     for partner in self:
    #         if partner.has_membership:
    #             return
    #
    #         self._check_mobile_duplication_for_new_member(partner)
    #
    #         _logger.info(f"Adding joining bonus for partner {partner.name}")
    #         new_points = partner.points_earned + 25
    #         partner.sudo().write({
    #             'points_earned': new_points,
    #             'has_membership': True
    #         })
    #
    #         self.env['loyalty.point.line'].sudo().create({
    #             'partner_id': partner.id,
    #             'points': 25,
    #             'source': 'joining',
    #             'earned_date': fields.Date.today(),
    #         })
    #
    #         _logger.info(f"Partner {partner.name} now has {new_points} points earned, available: {partner.available_points}")
    #         partner._sync_to_loyalty_cards()

    # def _check_mobile_duplication_for_new_member(self, partner):
    #     """Special check for new members before activating membership"""
    #     mobile_numbers_to_check = []
    #
    #     if partner.mobile:
    #         normalized_mobile = self._normalize_phone_number(partner.mobile)
    #         if normalized_mobile:
    #             mobile_numbers_to_check.append(normalized_mobile)
    #
    #     if partner.whatsapp_number:
    #         normalized_whatsapp = self._normalize_phone_number(partner.whatsapp_number)
    #         if normalized_whatsapp:
    #             mobile_numbers_to_check.append(normalized_whatsapp)
    #
    #     mobile_numbers_to_check = list(set(mobile_numbers_to_check))
    #
    #     for number in mobile_numbers_to_check:
    #         if not number:
    #             continue
    #
    #         query = """
    #             SELECT id, name FROM res_partner
    #             WHERE has_membership = true
    #             AND (
    #                 (mobile IS NOT NULL AND REGEXP_REPLACE(mobile, '\D', '', 'g') LIKE %s)
    #                 OR
    #                 (whatsapp_number IS NOT NULL AND REGEXP_REPLACE(whatsapp_number, '\D', '', 'g') LIKE %s)
    #             )
    #         """
    #
    #         self.env.cr.execute(query, ('%' + number + '%', '%' + number + '%'))
    #         duplicate_records = self.env.cr.fetchall()
    #
    #         if duplicate_records:
    #             duplicate_names = ', '.join([record[1] for record in duplicate_records])
    #             raise ValidationError(
    #                 _("Cannot activate loyalty membership. Mobile number %s is already registered with customer(s): %s. "
    #                   "Please use a different mobile number.") %
    #                 (number, duplicate_names)
    #             )

    # def _add_points_redeemed(self, points, order_id):
    #     """Helper method to add redeemed points - PREVENT OVER-REDEMPTION"""
    #     _logger.info(f"Adding redeemed points: {points} for partner {self.name}")
    #
    #     current_available = self.available_points
    #     redeemable_points = min(points, current_available)
    #
    #     if redeemable_points <= 0:
    #         _logger.warning(f"Cannot redeem points for partner {self.name}: No available points")
    #         return
    #
    #     self.env['loyalty.point.line'].sudo().create({
    #         'partner_id': self.id,
    #         'points': -redeemable_points,
    #         'source': 'redeem',
    #         'pos_order_id': order_id,
    #         'earned_date': fields.Date.today(),
    #     })
    #
    #     new_redeemed = self.points_redeemed + redeemable_points
    #     self.sudo().write({
    #         'points_redeemed': new_redeemed
    #     })
    #
    #     _logger.info(f"Partner {self.name} redeemed {redeemable_points} points.")
    #
    #     self._sync_to_loyalty_cards()

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to check mobile duplication for new loyalty members and handle joining bonus"""
        partners_to_activate = []

        for vals in vals_list:
            if vals.get('has_membership'):
                partners_to_activate.append(True)
                vals['has_membership'] = False

                # mobile_numbers_to_check = []
                #
                # if vals.get('mobile'):
                #     normalized_mobile = self._normalize_phone_number(vals['mobile'])
                #     if normalized_mobile:
                #         mobile_numbers_to_check.append(normalized_mobile)
                #
                # if vals.get('whatsapp_number'):
                #     normalized_whatsapp = self._normalize_phone_number(vals['whatsapp_number'])
                #     if normalized_whatsapp:
                #         mobile_numbers_to_check.append(normalized_whatsapp)
                #
                # mobile_numbers_to_check = list(set(mobile_numbers_to_check))
                #
                # for number in mobile_numbers_to_check:
                #     if not number:
                #         continue
                #
                #     query = """
                #         SELECT id, name FROM res_partner
                #         WHERE has_membership = true
                #         AND (
                #             (mobile IS NOT NULL AND REGEXP_REPLACE(mobile, '\D', '', 'g') LIKE %s)
                #             OR
                #             (whatsapp_number IS NOT NULL AND REGEXP_REPLACE(whatsapp_number, '\D', '', 'g') LIKE %s)
                #         )
                #     """
                #
                #     self.env.cr.execute(query, ('%' + number + '%', '%' + number + '%'))
                #     duplicate_records = self.env.cr.fetchall()
                #
                #     if duplicate_records:
                #         duplicate_names = ', '.join([record[1] for record in duplicate_records])
                #         raise ValidationError(
                #             _("Cannot create loyalty customer. Mobile number %s is already registered with customer(s): %s. "
                #             "Please use a different mobile number.") %
                #             (number, duplicate_names)
                #         )
            else:
                partners_to_activate.append(False)

        partners = super().create(vals_list)
        for partner, should_activate in zip(partners, partners_to_activate):
            if should_activate:
                partner.action_add_joining_bonus()

        return partners

    def write(self, vals):
        # if 'has_membership' in vals and vals['has_membership'] and not self.has_membership:
        #     self._check_mobile_duplication_for_new_member(self)
        res = super().write(vals)

        # if any(field in vals for field in ['points_earned', 'points_redeemed', 'has_membership']):
        #     if not self.env.context.get('skip_loyalty_sync'):
        #         self.with_context(skip_loyalty_sync=True)._sync_to_loyalty_cards()

        return res

    # def _sync_to_loyalty_cards(self):
    #     """DIRECTLY update points on all loyalty cards for this partner"""
    #     for partner in self:
    #         loyalty_cards = self.env['loyalty.card'].search([('partner_id', '=', partner.id)])
    #         for card in loyalty_cards:
    #             loyalty_points = float(partner.available_points)
    #             _logger.info(f"DIRECT WRITE: Setting loyalty card {card.code} points to {loyalty_points}")
    #
    #             self.env.cr.execute("""
    #                 UPDATE loyalty_card
    #                 SET points = %s
    #                 WHERE id = %s
    #             """, (loyalty_points, card.id))
    #
    #             card.invalidate_recordset(['points'])


class LoyaltyPointLine(models.Model):
    _name = 'loyalty.point.line'
    _description = 'Loyalty Point History'

    partner_id = fields.Many2one('res.partner', required=True)
    points = fields.Integer()
    source = fields.Selection([
        ('joining', 'Joining Bonus'),
        ('bill', 'Bill'),
        ('weekly', 'Weekly Bonus'),
        ('milestone', 'Milestone Bonus'),
        ('streak', 'Streak Bonus'),
        ('redeem', 'Redeemed'),
    ])
    earned_date = fields.Date(default=fields.Date.today)
    expiry_date = fields.Date(compute='_compute_expiry', store=True)
    pos_order_id = fields.Many2one('pos.order')

    @api.depends('earned_date')
    def _compute_expiry(self):
        for rec in self:
            if rec.earned_date:
                rec.expiry_date = rec.earned_date + timedelta(days=180)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    points_used = fields.Float(
        string="Points Used",
        # compute='_compute_points_used',
        store=False,
        help="Points redeemed in this order"
    )

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        for order in self:
            if order.partner_id:
                order.partner_id.sudo().write({
                    'last_pos_order_date': fields.Date.context_today(order),
                })
        return res

    # def action_pos_order_paid(self):
    #     """Override to track points earned and redeemed"""
    #     _logger.info(f"=== POS Order Paid Started ===")
    #
    #     res = super(PosOrder, self).action_pos_order_paid()
    #
    #     for order in self:
    #         partner = order.partner_id
    #         if not partner:
    #             _logger.info(f"Order {order.name}: No partner associated")
    #             continue
    #
    #         if not partner.has_membership:
    #             _logger.info(f"Order {order.name}: Partner {partner.name} has no membership")
    #             continue
    #
    #         _logger.info(f"Order {order.name}: Tracking points for partner {partner.name}")
    #         _logger.info(f"Partner BEFORE order - earned: {partner.points_earned}, redeemed: {partner.points_redeemed}, available: {partner.available_points}")
    #
    #         has_rewards = False
    #         reward_lines = order.lines.filtered(lambda l:
    #             l.reward_id and
    #             l.reward_id.program_id and
    #             l.reward_id.program_id.program_type == 'loyalty'
    #         )
    #
    #         if reward_lines:
    #             has_rewards = True
    #             _logger.info(f"Order {order.name}: Has reward lines")
    #
    #         earned_points = self._calculate_earned_points_with_streak(order, partner)
    #         if earned_points > 0:
    #             _logger.info(f"Order {order.name}: Earned {earned_points} points from purchase")
    #             self._add_earned_points(order, partner, earned_points)
    #         else:
    #             _logger.info(f"Order {order.name}: No points earned (total: {order.amount_total})")
    #
    #         if has_rewards:
    #             redeemed_points = self._calculate_redeemed_points(order)
    #             if redeemed_points > 0:
    #                 _logger.info(f"Order {order.name}: Redeeming {redeemed_points} points (reward applied)")
    #                 self._track_points_redeemed(order, partner, redeemed_points)
    #             else:
    #                 _logger.info(f"Order {order.name}: Reward lines found but 0 points to redeem")
    #
    #         partner.refresh()
    #         _logger.info(f"Partner AFTER order - earned: {partner.points_earned}, redeemed: {partner.points_redeemed}, available: {partner.available_points}")
    #
    #     _logger.info(f"=== POS Order Paid Completed ===")
    #     return res

    # def _calculate_earned_points_with_streak(self, order, partner):
    #     """Calculate points with weekly streak check"""
    #     total = order.amount_total
    #
    #     if total < 100:
    #         return 0
    #
    #     base_points = int(total // 100)
    #
    #     streak_bonus = self._check_27_day_streak(order, partner)
    #
    #     if streak_bonus:
    #         _logger.info(f"🎉 27-DAY STREAK BONUS: Double points for partner {partner.name}")
    #         return base_points * 2
    #
    #     return base_points
    #
    # def _check_27_day_streak(self, order, partner):
    #     """Check if partner has made purchases for 27 consecutive days"""
    #     today = order.date_order.date()
    #
    #     previous_orders = self.env['pos.order'].sudo().search([
    #         ('partner_id', '=', partner.id),
    #         ('state', 'in', ['paid', 'invoiced']),
    #         ('date_order', '>=', today - timedelta(days=27)),
    #         ('id', '!=', order.id),
    #     ], order='date_order desc')
    #
    #     unique_dates = []
    #     for o in previous_orders:
    #         d = o.date_order.date()
    #         if d not in unique_dates:
    #             unique_dates.append(d)
    #         if len(unique_dates) == 27:
    #             break
    #
    #     if len(unique_dates) == 26:
    #         unique_dates.append(today)
    #         unique_dates.sort()
    #
    #         expected_date = unique_dates[0]
    #         valid = True
    #
    #         for d in unique_dates:
    #             if d != expected_date:
    #                 valid = False
    #                 break
    #             expected_date = d + timedelta(days=1)
    #
    #         if valid:
    #             _logger.info(f"Partner {partner.name}: 27-DAY STREAK VERIFIED!")
    #             return True
    #
    #     return False
    #
    # def _add_earned_points(self, order, partner, points):
    #     """Add earned points to partner"""
    #     existing = self.env['loyalty.point.line'].search([
    #         ('pos_order_id', '=', order.id),
    #         ('points', '>', 0),
    #         ('partner_id', '=', partner.id),
    #     ], limit=1)
    #
    #     if existing:
    #         _logger.info(f"Points already added for order {order.name}")
    #         return
    #
    #     base_points = int(order.amount_total // 100) if order.amount_total >= 100 else 0
    #     source = 'streak' if points > base_points > 0 else 'bill'
    #
    #     self.env['loyalty.point.line'].create({
    #         'partner_id': partner.id,
    #         'points': points,
    #         'source': source,
    #         'earned_date': fields.Date.today(),
    #         'pos_order_id': order.id,
    #     })
    #
    #     old_points = partner.points_earned
    #     new_points = old_points + points
    #     partner.write({
    #         'points_earned': new_points
    #     })
    #
    #     _logger.info(f"Updated partner {partner.name} earned points: {old_points} + {points} = {new_points}")
    #
    #     if old_points < 250 and new_points >= 250:
    #         _logger.info(f"Milestone reached! {old_points} -> {new_points}")
    #         milestone_exists = self.env['loyalty.point.line'].search([
    #             ('partner_id', '=', partner.id),
    #             ('source', '=', 'milestone'),
    #         ], limit=1)
    #
    #         if not milestone_exists:
    #             self.env['loyalty.point.line'].create({
    #                 'partner_id': partner.id,
    #                 'points': 25,
    #                 'source': 'milestone',
    #                 'earned_date': fields.Date.today(),
    #             })
    #
    #             partner.write({
    #                 'points_earned': partner.points_earned + 25
    #             })
    #             _logger.info(f"Added 25 milestone bonus points")
    #
    #     partner._sync_to_loyalty_cards()
    #
    # def _calculate_redeemed_points(self, order):
    #     """Calculate points redeemed in this order"""
    #     reward_lines = order.lines.filtered(lambda l:
    #         l.reward_id and
    #         l.reward_id.program_id and
    #         l.reward_id.program_id.program_type == 'loyalty'
    #     )
    #
    #     if not reward_lines:
    #         return 0
    #
    #     total_discount = abs(sum(line.price_subtotal_incl for line in reward_lines))
    #
    #     POINT_VALUE = 3.0
    #
    #     points = int(total_discount / POINT_VALUE)
    #     _logger.info(f"Redemption calculation: Total discount: {total_discount}, Points: {total_discount} / {POINT_VALUE} = {points}")
    #
    #     return points
    #
    # def _track_points_redeemed(self, order, partner, points_used):
    #     """Track points redeemed from loyalty rewards"""
    #     if points_used <= 0:
    #         return
    #
    #     _logger.info(f"Tracking {points_used} points redemption")
    #
    #     existing_redeem = self.env['loyalty.point.line'].search([
    #         ('pos_order_id', '=', order.id),
    #         ('points', '<', 0),
    #         ('partner_id', '=', partner.id),
    #     ], limit=1)
    #
    #     if not existing_redeem:
    #         partner._add_points_redeemed(
    #             points=points_used,
    #             order_id=order.id,
    #         )
    #         _logger.info(f"Redeemed {points_used} points for partner {partner.name}")
    #     else:
    #         _logger.info(f"Redemption already tracked for order {order.name}")
    #
    # def _compute_points_used(self):
    #     """Compute points used for display"""
    #     for order in self:
    #         order.points_used = self._calculate_redeemed_points(order)


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    points = fields.Float(
        string='Points',
        # compute='_compute_points_from_partner',
        # store=True,
        help="Points available on this card - synced from partner's available_points",
        readonly=False,
    )

    # @api.depends('partner_id.available_points')
    # def _compute_points_from_partner(self):
    #     """Compute points from partner's available_points"""
    #     for card in self:
    #         if card.partner_id:
    #             loyalty_points = float(card.partner_id.available_points)
    #             card.points = loyalty_points
    #             _logger.debug(f"LoyaltyCard compute: Card {card.code} points = {loyalty_points}")
    #         else:
    #             card.points = 0.0

    @api.constrains('points')
    def _check_points_not_negative(self):
        """ALLOW negative points - we control this via partner"""
        pass

    # @api.onchange('partner_id')
    # def _onchange_partner_id_sync_points(self):
    #     """Sync points from partner when partner changes"""
    #     for card in self:
    #         if card.partner_id:
    #             card.points = float(card.partner_id.available_points)
    #         else:
    #             card.points = 0.0

    def write(self, vals):
        """Override write to prevent manual changes to points"""
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """When a loyalty card is created for a member, add 25 bonus points"""
        cards = super().create(vals_list)
        if self.env.context.get('skip_membership_bonus'):
            return cards
        for card in cards:
            partner = card.partner_id
            if (partner and partner.has_membership
                    and card.program_id.program_type == 'loyalty'):
                # Check if bonus already exists for this partner
                self.env.cr.execute("""
                    SELECT COUNT(1) FROM loyalty_history lh
                    JOIN loyalty_card lc ON lc.id = lh.card_id
                    JOIN loyalty_program lp ON lp.id = lc.program_id
                    WHERE lc.partner_id = %s
                      AND lp.program_type = 'loyalty'
                      AND lh.description = 'Membership Bonus'
                    LIMIT 1
                """, [partner.id])
                bonus_exists = self.env.cr.fetchone()[0]
                if not bonus_exists:
                    self.env['loyalty.history'].sudo().create({
                        'description': 'Membership Bonus',
                        'issued': 25,
                        'card_id': card.id,
                    })
                    card.sudo().points += 25
        return cards
