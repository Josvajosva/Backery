from odoo import models

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _has_discount_for_loyalty_check(self):
        self.ensure_one()
        for line in self.lines:
            if line.discount > 0:
                return True
            if line.price_subtotal < 0 and not line.is_reward_line:
                return True
        return False

    def confirm_coupon_programs(self, coupon_data):
        if self._has_discount_for_loyalty_check() and self.partner_id:
            # Prevent awarding new loyalty cards or new points
            new_data = {}
            for k, v in coupon_data.items():
                if int(k) < 0:
                    # Negative ID means a new card is to be created. We skip it entirely.
                    continue
                # For existing cards, prevent adding positive points (awarding)
                if v.get('points', 0) > 0:
                    v['points'] = 0
                new_data[k] = v
            coupon_data = new_data

        return super(PosOrder, self).confirm_coupon_programs(coupon_data)

    def add_loyalty_history_lines(self, coupon_data, coupon_updates):
        if self._has_discount_for_loyalty_check() and self.partner_id:
            # Also prevent the history log from showing issued points when a discount is applied
            new_data = []
            for coupon in coupon_data:
                # Nullify the 'won' points which are being issued
                if coupon.get('won', 0) > 0:
                    coupon['won'] = 0
                # If they didn't spend points, 'spent' is 0, 'won' is 0, so we just append.
                # Actually if it's purely a "won" coupon, we could skip it entirely,
                # but letting standard Odoo process it with 0 is safer to avoid KeyErrors.
                new_data.append(coupon)
            coupon_data = new_data

        return super(PosOrder, self).add_loyalty_history_lines(coupon_data, coupon_updates)
