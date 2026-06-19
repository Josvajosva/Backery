from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_view_price_history(self):
        """Variant form merges template UI; delegate when price-history (or similar) is installed."""
        self.ensure_one()
        tmpl = self.product_tmpl_id
        if hasattr(tmpl, 'action_view_price_history'):
            return tmpl.action_view_price_history()
        return {'type': 'ir.actions.act_window_close'}

    def button_bom_cost(self):
        res = super().button_bom_cost()
        factory_company = self.env.company
        if factory_company.parent_id or not factory_company.child_ids:
            return res
        for product in self:
            tmpl = product.product_tmpl_id
            if tmpl.product_variant_count != 1 or not tmpl.bom_count:
                continue
            tmpl._sync_branch_vendor_price_from_factory(factory_company, self.env.company)
        return res

    @staticmethod
    def _coerce_standard_price_write_value(value):
        if value is False or value is None:
            return 0.0
        return float(value)

    def _propagate_standard_price_to_child_companies_sql(self, product_ids, parent_cost=None):
        """Merge child-company standard_price into JSONB for given variant ids.

        :param parent_cost: If set, this value is written for every child company (use after
            write/create so we do not rely on DB flush). If None, each row's cost for the
            current (parent) company is read from JSONB (bulk button).
        """
        if not product_ids:
            return
        parent_company = self.env.company
        child_companies = parent_company.child_ids
        if not child_companies:
            return

        child_ids = child_companies.ids
        product_ids = list(product_ids)

        if parent_cost is not None:
            query = """
                UPDATE product_product AS p
                SET standard_price = COALESCE(p.standard_price, '{}'::jsonb) || sub.patch
                FROM (
                    SELECT
                        p2.id,
                        (
                            SELECT COALESCE(
                                jsonb_object_agg(
                                    c.child_id::text,
                                    to_jsonb(%s::double precision)
                                ),
                                '{}'::jsonb
                            )
                            FROM unnest(%s::int[]) AS c(child_id)
                        ) AS patch
                    FROM product_product AS p2
                    WHERE p2.id = ANY(%s)
                ) AS sub
                WHERE p.id = sub.id
            """
            self.env.cr.execute(
                query,
                [parent_cost, child_ids, product_ids],
            )
        else:
            parent_key = str(parent_company.id)
            defaults = (
                self.env['ir.default']
                .sudo()
                .with_company(parent_company)
                ._get_model_defaults('product.product')
                or {}
            )
            fallback_cost = float(defaults.get('standard_price') or 0.0)
            query = """
                UPDATE product_product AS p
                SET standard_price = COALESCE(p.standard_price, '{}'::jsonb) || sub.patch
                FROM (
                    SELECT
                        p2.id,
                        (
                            SELECT COALESCE(
                                jsonb_object_agg(c.child_id::text, to_jsonb(pc.parent_cost)),
                                '{}'::jsonb
                            )
                            FROM unnest(%s::int[]) AS c(child_id),
                            LATERAL (
                                SELECT COALESCE(
                                    (COALESCE(p2.standard_price, '{}'::jsonb) ->> %s)::double precision,
                                    %s::double precision
                                ) AS parent_cost
                            ) AS pc
                        ) AS patch
                    FROM product_product AS p2
                    WHERE p2.id = ANY(%s)
                ) AS sub
                WHERE p.id = sub.id
            """
            self.env.cr.execute(
                query,
                [child_ids, parent_key, fallback_cost, product_ids],
            )

        self.env['product.product'].invalidate_model(['standard_price'])

    def write(self, vals):
        res = super().write(vals)
        if (
            self.env.context.get('skip_cost_propagate_to_children')
            or 'standard_price' not in vals
            or not self.env.company.child_ids
        ):
            return res
        parent_cost = self._coerce_standard_price_write_value(vals['standard_price'])
        self._propagate_standard_price_to_child_companies_sql(self.ids, parent_cost=parent_cost)
        self.product_tmpl_id._sync_branch_vendor_price_from_factory(self.env.company, self.env.company)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        if self.env.context.get('skip_cost_propagate_to_children'):
            return products
        if not self.env.company.child_ids:
            return products
        for product, vals in zip(products, vals_list):
            if 'standard_price' not in vals:
                continue
            parent_cost = self._coerce_standard_price_write_value(vals['standard_price'])
            product._propagate_standard_price_to_child_companies_sql(
                [product.id], parent_cost=parent_cost
            )

        return products

    def update_cost_price(self):
        """Button: sync all active variants from current (parent) company to child companies."""
        parent_company = self.env.company
        child_companies = parent_company.child_ids

        if not child_companies:
            return True

        Product = self.env['product.product']
        Product.check_access('write')

        products = Product.search([('active', '=', True)])
        if not products:
            return True

        products._propagate_standard_price_to_child_companies_sql(products.ids, parent_cost=None)

        for tmpl in products.mapped('product_tmpl_id'):
            tmpl._sync_branch_vendor_price_from_factory(parent_company, self.env.company)

        return True
