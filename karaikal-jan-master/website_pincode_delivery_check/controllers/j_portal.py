# -*- coding: utf-8 -*-
from odoo.http import request
from odoo.osv import expression
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class JCustomerPortal(CustomerPortal):
    """Override portal order list to bypass the multi-company record rule.

    Orders placed through in-store pickup are assigned to the outlet's company_id,
    which differs from the main website company.  Without sudo(), Odoo's
    multi-company record rule hides those orders from portal users who only
    belong to the main company.  We re-run the search with sudo() so every
    order that belongs to the customer's partner is visible.
    """

    def _prepare_sale_portal_rendering_values(
        self, page=1, date_begin=None, date_end=None,
        sortby=None, quotation_page=False, **kwargs
    ):
        # Run super() first so all other values (layout, searchbars, etc.) are set.
        values = super()._prepare_sale_portal_rendering_values(
            page=page, date_begin=date_begin, date_end=date_end,
            sortby=sortby, quotation_page=quotation_page, **kwargs
        )

        partner = request.env.user.partner_id

        # Build the same partner + state domain as the standard controller,
        # but execute it with sudo() so the company rule does not apply.
        domain = [
            ('partner_id', 'child_of', [partner.commercial_partner_id.id]),
            ('state', '=', 'sent' if quotation_page else 'sale'),
        ]
        if date_begin and date_end:
            domain += [
                ('create_date', '>', date_begin),
                ('create_date', '<=', date_end),
            ]

        searchbar_sortings = self._get_sale_searchbar_sortings()
        sort_order = searchbar_sortings.get(
            sortby or 'date',
            list(searchbar_sortings.values())[0]
        )['order']

        SaleOrder = request.env['sale.order'].sudo()

        total = SaleOrder.search_count(domain)
        pager_values = portal_pager(
            url='/my/quotes' if quotation_page else '/my/orders',
            total=total,
            page=page,
            step=self._items_per_page,
            url_args={'date_begin': date_begin, 'date_end': date_end},
        )
        orders = SaleOrder.search(
            domain,
            order=sort_order,
            limit=self._items_per_page,
            offset=pager_values['offset'],
        )

        # Replace the orders / quotations and pager with the sudo() results.
        if quotation_page:
            values.update({'quotations': orders, 'pager': pager_values})
        else:
            values.update({'orders': orders, 'pager': pager_values})

        return values

    # ------------------------------------------------------------------
    # Invoice portal — same multi-company bypass as orders above
    # ------------------------------------------------------------------

    def _prepare_my_invoices_values(
        self, page, date_begin, date_end, sortby, filterby, domain=None, url='/my/invoices'
    ):
        values = super()._prepare_my_invoices_values(
            page, date_begin, date_end, sortby, filterby, domain=domain, url=url
        )

        partner = request.env.user.partner_id
        AccountInvoice = request.env['account.move'].sudo()

        # Rebuild the same domain as the parent but add partner filter so
        # sudo() doesn't expose other customers' invoices.
        partner_domain = [('partner_id', 'child_of', [partner.commercial_partner_id.id])]
        base_domain = expression.AND([
            partner_domain,
            domain or [],
            self._get_invoices_domain(),
        ])

        searchbar_sortings = self._get_account_searchbar_sortings()
        order = searchbar_sortings.get(sortby or 'date', list(searchbar_sortings.values())[0])['order']

        searchbar_filters = self._get_account_searchbar_filters()
        full_domain = base_domain + searchbar_filters.get(filterby or 'all', {}).get('domain', [])

        if date_begin and date_end:
            full_domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        total = AccountInvoice.search_count(full_domain)

        # Replace the lambda and pager with sudo()-based versions.
        values.update({
            'invoices': lambda pager_offset: [
                invoice._get_invoice_portal_extra_values()
                for invoice in AccountInvoice.search(
                    full_domain, order=order,
                    limit=self._items_per_page, offset=pager_offset,
                )
            ],
            'pager': {
                'url': url,
                'url_args': {
                    'date_begin': date_begin, 'date_end': date_end,
                    'sortby': sortby, 'filterby': filterby,
                },
                'total': total,
                'page': page,
                'step': self._items_per_page,
            },
        })
        return values

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        partner_domain = [('partner_id', 'child_of', [partner.commercial_partner_id.id])]
        AccountInvoice = request.env['account.move'].sudo()

        if 'invoice_count' in counters:
            domain = expression.AND([partner_domain, self._get_invoices_domain('out')])
            values['invoice_count'] = AccountInvoice.search_count(domain, limit=1)

        if 'overdue_invoice_count' in counters:
            domain = expression.AND([partner_domain, self._get_overdue_invoices_domain()])
            values['overdue_invoice_count'] = AccountInvoice.search_count(domain)

        return values