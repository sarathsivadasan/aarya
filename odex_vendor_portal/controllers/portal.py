# -*- coding: utf-8 -*-
from werkzeug.exceptions import NotFound

from odoo import fields, http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.tools import float_round

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class VendorPortal(CustomerPortal):
    """Vendor Portal.

    Everything is scoped on the commercial partner of the logged in user and
    double checked server side:

    1. the route rejects any user without the Vendor Portal group,
    2. records are read with the user's own rights (record rules apply),
    3. an explicit ownership assertion runs before any sudo() read.
    """

    _vendor_items_per_page = 20

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _vendor_partner(self):
        user = request.env.user
        if user._is_public() or not user._is_vendor_portal_user():
            return request.env['res.partner']
        return user.partner_id.commercial_partner_id

    def _vendor_values(self, partner, page_name):
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': page_name,
            'partner': partner,
            'vendor_initials': partner.vendor_portal_initials(),
        })
        return values

    def _rfq_domain(self, partner):
        return [
            ('partner_id', 'child_of', partner.id),
            ('state', '=', 'sent'),
        ]

    def _order_domain(self, partner):
        return [
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ('purchase', 'done', 'cancel')),
        ]

    def _bill_domain(self, partner):
        return [
            ('partner_id', 'child_of', partner.id),
            ('move_type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
            ('state', '=', 'posted'),
        ]

    def _vendor_counters(self, partner):
        PurchaseOrder = request.env['purchase.order']
        AccountMove = request.env['account.move']
        bills = AccountMove.search(self._bill_domain(partner))
        open_bills = bills.filtered(
            lambda m: m.payment_state not in ('paid', 'reversed', 'invoicing_legacy'))
        return {
            'rfq_count': PurchaseOrder.search_count(self._rfq_domain(partner)),
            'order_count': PurchaseOrder.search_count(self._order_domain(partner)),
            'payment_count': len(open_bills),
            'payment_amount': float_round(
                sum(open_bills.mapped('amount_residual')), precision_digits=2),
            'vendor_currency': partner.property_account_payable_id.currency_id or request.env.company.currency_id,
        }

    def _vendor_owned_or_404(self, model_name, record_id, partner):
        """Ownership gate. Runs before any sudo() read."""
        try:
            record = self._document_check_access(model_name, int(record_id))
        except (AccessError, MissingError, ValueError):
            raise NotFound()
        owner = record.sudo().partner_id.commercial_partner_id
        if not owner or owner.id != partner.id:
            raise NotFound()
        return record

    def _vendor_recent_activity(self, partner, limit=8):
        activities = []
        orders = request.env['purchase.order'].search(
            [('partner_id', 'child_of', partner.id),
             ('state', 'in', ('sent', 'purchase', 'done', 'cancel'))],
            order='write_date desc', limit=limit)
        for order in orders:
            if order.state == 'sent':
                if order.vendor_portal_responded:
                    title = _('Quotation submitted')
                    subtitle = _('You responded to %s') % order.name
                else:
                    title = _('New request for quotation')
                    subtitle = _('%s is waiting for your quotation') % order.name
                icon, tone = 'fa-file-text-o', 'blue'
            elif order.state == 'purchase':
                title = _('Purchase order confirmed')
                subtitle = order.name
                icon, tone = 'fa-shopping-cart', 'green'
            elif order.state == 'done':
                title = _('Purchase order locked')
                subtitle = order.name
                icon, tone = 'fa-lock', 'green'
            else:
                title = _('Purchase order cancelled')
                subtitle = order.name
                icon, tone = 'fa-times-circle-o', 'red'
            activities.append({
                'title': title,
                'subtitle': subtitle,
                'date': order.write_date,
                'icon': icon,
                'tone': tone,
                'url': order.vendor_portal_url(),
            })

        bills = request.env['account.move'].search(
            self._bill_domain(partner), order='write_date desc', limit=limit)
        for bill in bills:
            state_key, state_label = bill.vendor_portal_payment_status()
            if state_key == 'paid':
                title, icon, tone = _('Payment received'), 'fa-check-circle-o', 'green'
            elif state_key == 'partial':
                title, icon, tone = _('Partial payment received'), 'fa-adjust', 'blue'
            elif state_key == 'overdue':
                title, icon, tone = _('Payment overdue'), 'fa-exclamation-circle', 'red'
            else:
                title, icon, tone = _('Payment pending'), 'fa-clock-o', 'blue'
            activities.append({
                'title': title,
                'subtitle': bill.name or _('Vendor Bill'),
                'date': bill.write_date,
                'icon': icon,
                'tone': tone,
                'url': '/my/vendor/payment/%s' % bill.id,
            })

        activities.sort(key=lambda a: a['date'] or fields.Datetime.now(), reverse=True)
        return activities[:limit]

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @http.route(['/my/vendor'], type='http', auth='user', website=True)
    def vendor_portal_home(self, **kw):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        values = self._vendor_values(partner, 'vendor_home')
        values.update(self._vendor_counters(partner))
        values['activities'] = self._vendor_recent_activity(partner, limit=6)
        return request.render('odex_vendor_portal.vendor_portal_home', values)

    @http.route(['/my/vendor/activity'], type='http', auth='user', website=True)
    def vendor_portal_activity(self, **kw):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        values = self._vendor_values(partner, 'vendor_activity')
        values['activities'] = self._vendor_recent_activity(partner, limit=40)
        return request.render('odex_vendor_portal.vendor_portal_activity', values)

    # ------------------------------------------------------------------
    # RFQs
    # ------------------------------------------------------------------
    @http.route(['/my/vendor/rfqs', '/my/vendor/rfqs/page/<int:page>'],
                type='http', auth='user', website=True)
    def vendor_portal_rfqs(self, page=1, sortby='date', **kw):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        PurchaseOrder = request.env['purchase.order']
        sortings = {
            'date': {'label': _('Newest'), 'order': 'date_order desc, id desc'},
            'name': {'label': _('Reference'), 'order': 'name desc'},
            'amount': {'label': _('Amount'), 'order': 'amount_total desc'},
        }
        if sortby not in sortings:
            sortby = 'date'
        domain = self._rfq_domain(partner)
        total = PurchaseOrder.search_count(domain)
        pager = portal_pager(
            url='/my/vendor/rfqs',
            url_args={'sortby': sortby},
            total=total,
            page=page,
            step=self._vendor_items_per_page,
        )
        orders = PurchaseOrder.search(
            domain, order=sortings[sortby]['order'],
            limit=self._vendor_items_per_page, offset=pager['offset'])
        values = self._vendor_values(partner, 'vendor_rfq')
        values.update({
            'orders': orders,
            'pager': pager,
            'sortby': sortby,
            'sortings': sortings,
            'default_url': '/my/vendor/rfqs',
        })
        return request.render('odex_vendor_portal.vendor_portal_rfqs', values)

    @http.route(['/my/vendor/rfq/<int:order_id>'], type='http', auth='user', website=True)
    def vendor_portal_rfq_detail(self, order_id, report_type=None, download=False, **kw):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        order = self._vendor_owned_or_404('purchase.order', order_id, partner)
        if order.state not in ('sent',):
            return request.redirect('/my/vendor/order/%s' % order.id)
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(
                model=order, report_type=report_type,
                report_ref='purchase.report_purchasequotation', download=download)
        values = self._vendor_values(partner, 'vendor_rfq')
        values.update({
            'order': order,
            'can_respond': order.state == 'sent',
            'error': kw.get('error'),
            'submitted': bool(kw.get('submitted')),
        })
        return request.render('odex_vendor_portal.vendor_portal_rfq_detail', values)

    @http.route(['/my/vendor/rfq/<int:order_id>/respond'], type='http', auth='user',
                methods=['POST'], website=True)
    def vendor_portal_rfq_respond(self, order_id, **post):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        order = self._vendor_owned_or_404('purchase.order', order_id, partner)
        if order.state != 'sent':
            raise NotFound()

        order_sudo = order.sudo()
        body_lines = []
        for line in order_sudo.order_line:
            if line.display_type:
                continue
            raw = post.get('price_%s' % line.id)
            if raw in (None, ''):
                continue
            try:
                price = float(str(raw).replace(',', '.'))
            except (TypeError, ValueError):
                return request.redirect(
                    '/my/vendor/rfq/%s?error=invalid_price' % order.id)
            if price < 0:
                return request.redirect(
                    '/my/vendor/rfq/%s?error=invalid_price' % order.id)
            if float_round(price, precision_digits=4) != float_round(line.price_unit, precision_digits=4):
                body_lines.append('%s: %s &rarr; %s' % (
                    line.name, line.price_unit, price))
                line.write({'price_unit': price})
            part_no = post.get('part_no_%s' % line.id)
            if part_no in (None, ''):
                continue
            line.write({'part_no': part_no})

        expected_date = post.get('expected_date')
        if expected_date:
            try:
                parsed = fields.Date.to_date(expected_date)
            except (TypeError, ValueError):
                parsed = None
            if parsed:
                order_sudo.order_line.filtered(lambda l: not l.display_type).write({
                    'date_planned': fields.Datetime.to_datetime(parsed),
                })
                body_lines.append(_('Expected date: %s') % parsed)

        note = (post.get('note') or '').strip()
        order_sudo.write({
            'vendor_portal_responded': True,
            'vendor_response_date': fields.Datetime.now(),
            'vendor_response_note': note or False,
        })

        body = _('Quotation submitted through the Vendor Portal by %s.') % partner.name
        if body_lines:
            body += '<br/>' + '<br/>'.join(body_lines)
        if note:
            body += '<br/><b>%s</b><br/>%s' % (_('Vendor note'), note)
        order_sudo.message_post(
            body=body,
            author_id=partner.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        return request.redirect('/my/vendor/rfq/%s?submitted=1' % order.id)

    # ------------------------------------------------------------------
    # Purchase orders
    # ------------------------------------------------------------------
    @http.route(['/my/vendor/orders', '/my/vendor/orders/page/<int:page>'],
                type='http', auth='user', website=True)
    def vendor_portal_orders(self, page=1, sortby='date', **kw):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        PurchaseOrder = request.env['purchase.order']
        sortings = {
            'date': {'label': _('Newest'), 'order': 'date_order desc, id desc'},
            'name': {'label': _('Reference'), 'order': 'name desc'},
            'amount': {'label': _('Amount'), 'order': 'amount_total desc'},
        }
        if sortby not in sortings:
            sortby = 'date'
        domain = self._order_domain(partner)
        total = PurchaseOrder.search_count(domain)
        pager = portal_pager(
            url='/my/vendor/orders',
            url_args={'sortby': sortby},
            total=total,
            page=page,
            step=self._vendor_items_per_page,
        )
        orders = PurchaseOrder.search(
            domain, order=sortings[sortby]['order'],
            limit=self._vendor_items_per_page, offset=pager['offset'])
        values = self._vendor_values(partner, 'vendor_orders')
        values.update({
            'orders': orders,
            'pager': pager,
            'sortby': sortby,
            'sortings': sortings,
            'default_url': '/my/vendor/orders',
        })
        return request.render('odex_vendor_portal.vendor_portal_orders', values)

    @http.route(['/my/vendor/order/<int:order_id>'], type='http', auth='user', website=True)
    def vendor_portal_order_detail(self, order_id, report_type=None, download=False, **kw):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        order = self._vendor_owned_or_404('purchase.order', order_id, partner)
        if order.state == 'sent':
            return request.redirect('/my/vendor/rfq/%s' % order.id)
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(
                model=order, report_type=report_type,
                report_ref='purchase.report_purchaseorder', download=download)
        values = self._vendor_values(partner, 'vendor_orders')
        values['order'] = order
        return request.render('odex_vendor_portal.vendor_portal_order_detail', values)

    # ------------------------------------------------------------------
    # Pending payments
    # ------------------------------------------------------------------
    @http.route(['/my/vendor/payments', '/my/vendor/payments/page/<int:page>'],
                type='http', auth='user', website=True)
    def vendor_portal_payments(self, page=1, sortby='date', filterby='open', **kw):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        AccountMove = request.env['account.move']
        sortings = {
            'date': {'label': _('Newest'), 'order': 'invoice_date desc, id desc'},
            'due': {'label': _('Due date'), 'order': 'invoice_date_due asc, id desc'},
            'name': {'label': _('Reference'), 'order': 'name desc'},
        }
        filters = {
            'open': {'label': _('Outstanding'),
                     'domain': [('payment_state', 'not in', ('paid', 'reversed'))]},
            'overdue': {'label': _('Overdue'),
                        'domain': [('payment_state', 'not in', ('paid', 'reversed')),
                                   ('invoice_date_due', '<', fields.Date.context_today(request.env.user))]},
            'paid': {'label': _('Paid'),
                     'domain': [('payment_state', 'in', ('paid', 'reversed'))]},
            'all': {'label': _('All'), 'domain': []},
        }
        if sortby not in sortings:
            sortby = 'date'
        if filterby not in filters:
            filterby = 'open'
        domain = self._bill_domain(partner) + filters[filterby]['domain']
        total = AccountMove.search_count(domain)
        pager = portal_pager(
            url='/my/vendor/payments',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=total,
            page=page,
            step=self._vendor_items_per_page,
        )
        bills = AccountMove.search(
            domain, order=sortings[sortby]['order'],
            limit=self._vendor_items_per_page, offset=pager['offset'])
        values = self._vendor_values(partner, 'vendor_payments')
        values.update({
            'bills': bills,
            'pager': pager,
            'sortby': sortby,
            'sortings': sortings,
            'filterby': filterby,
            'filters': filters,
            'default_url': '/my/vendor/payments',
            'total_due': float_round(
                sum(bills.filtered(
                    lambda m: m.payment_state not in ('paid', 'reversed')
                ).mapped('amount_residual')), precision_digits=2),
        })
        return request.render('odex_vendor_portal.vendor_portal_payments', values)

    @http.route(['/my/vendor/payment/<int:move_id>'], type='http', auth='user', website=True)
    def vendor_portal_payment_detail(self, move_id, **kw):
        partner = self._vendor_partner()
        if not partner:
            return request.redirect('/my/home')
        move = self._vendor_owned_or_404('account.move', move_id, partner)
        values = self._vendor_values(partner, 'vendor_payments')
        values['bill'] = move
        return request.render('odex_vendor_portal.vendor_portal_payment_detail', values)
