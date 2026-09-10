# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomerCouponUsage(models.Model):
    _name = 'customer.coupon.usage'
    _description = 'Customer Coupon Usage History'
    _rec_name = 'name'
    _order = 'usage_date desc, id desc'

    name = fields.Char(
        string='Reference', readonly=True, copy=False, default='New',
    )
    coupon_id = fields.Many2one(
        'customer.coupon', string='Customer Coupon',
        required=True, ondelete='cascade',
    )
    customer_id = fields.Many2one(
        'res.partner', related='coupon_id.customer_id', store=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='coupon_id.currency_id', store=True,
    )
    usage_date = fields.Date(
        string='Usage Date', default=fields.Date.today, required=True,
    )
    amount = fields.Monetary(
        string='Amount Used', currency_field='currency_id', required=True,
    )
    job_id = fields.Many2one('project.task')
    invoice_id = fields.Many2one('account.move', string='Invoice',  ondelete='cascade')
    service_id = fields.Many2one('product.product', string='Service')
    notes = fields.Text(string='Notes')
    service_no = fields.Integer()
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('customer.coupon.usage') or 'New'
                )
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Usage amount must be greater than zero.'))


# ── Extend account.move ───────────────────────────────────────────────────────

class AccountMove(models.Model):
    _inherit = 'account.move'

    coupon_id = fields.Many2one(
        'customer.coupon', string='Customer Coupon', index=True, copy=False,
    )
    coupon_amount_used = fields.Monetary(
        string='Coupon Amount Used', currency_field='currency_id',
        compute='_compute_coupon_amount_used', store=True,
    )

    @api.depends('coupon_id', 'coupon_id.usage_ids.invoice_id',
                 'coupon_id.usage_ids.amount')
    def _compute_coupon_amount_used(self):
        for move in self:
            if move.job_id.customer_coupon_id:
                move.coupon_amount_used = sum(
                    u.amount for u in move.job_id.customer_coupon_id.usage_ids
                    if u.invoice_id == move
                )
            else:
                move.coupon_amount_used = 0.0

    def action_post(self):
        result = super().action_post()
        print("NI09UJOIKL")
        for move in self:
            print("NI09UcddJOIKL",move.job_id ,move.job_id.customer_coupon_id, move.move_type)
            if move.job_id and move.move_type == 'out_invoice':
                if move.job_id.customer_coupon_id and move.move_type == 'out_invoice':
                    move._recognize_coupon_revenue()
        return result

    def _recognize_coupon_revenue(self):
        """
        Revenue Recognition:
            Dr  Unearned Revenue / Coupon
            Cr  Sales Account / Coupon
            Cr  VAT Output  (optional)
        """
        self.ensure_one()
        if not self.job_id.customer_coupon_id:
            return

        coupon = self.job_id.customer_coupon_id


        # Record usage history
        if self.job_id:
            print("98UOIHJKN98UIHKJ",)
            coupon_lines = self.job_id.job_cost_sheet_ids.filtered(
                lambda l: l.coupon_line
            )

            for line in coupon_lines:
                self.env['customer.coupon.usage'].create({
                    'job_id': self.job_id.id,
                    'coupon_id': coupon.id,
                    'usage_date': self.invoice_date or fields.Date.today(),
                    'amount': line.price_unit,
                    'invoice_id': self.id,
                    'service_id': line.product_id.id,
                    'service_no': line.coupon_service_no,
                    'notes': _('Auto-recognized from Invoice %s') % self.name,
                })
        coupon._update_state_from_usage()

    # def _recognize_coupon_revenue(self):
    #     """
    #     Revenue Recognition:
    #         Dr  Unearned Revenue / Coupon
    #         Cr  Sales Account / Coupon
    #         Cr  VAT Output  (optional)
    #     """
    #     self.ensure_one()
    #     if not self.coupon_id:
    #         return
    #
    #     coupon = self.coupon_id
    #     config = coupon._get_accounting_config()
    #
    #     unearned_id = config['unearned_revenue_account']
    #     sales_id = config['coupon_sales_account']
    #
    #     if not unearned_id or not sales_id:
    #         return  # graceful skip if not configured
    #
    #     recognize = min(self.amount_untaxed, coupon.remaining_amount)
    #     if recognize <= 0:
    #         return
    #
    #     # Optional VAT
    #     vat_amount = 0.0
    #     vat_account_id = False
    #     vat_tax_id = config['vat_tax']
    #     if vat_tax_id:
    #         tax = self.env['account.tax'].browse(vat_tax_id).exists()
    #         if tax:
    #             tax_res = tax.compute_all(recognize)
    #             vat_amount = sum(t['amount'] for t in tax_res.get('taxes', []))
    #             rep_lines = tax.invoice_repartition_line_ids.filtered(
    #                 lambda l: l.repartition_type == 'tax'
    #             )
    #             if rep_lines and rep_lines[0].account_id:
    #                 vat_account_id = rep_lines[0].account_id.id
    #
    #     journal_id = config['default_journal'] or self.journal_id.id
    #
    #     lines = [
    #         (0, 0, {
    #             'account_id': unearned_id,
    #             'debit': recognize,
    #             'credit': 0.0,
    #             'name': _('Unearned Revenue Recognition - %s') % coupon.name,
    #             'partner_id': coupon.customer_id.id,
    #         }),
    #         (0, 0, {
    #             'account_id': sales_id,
    #             'debit': 0.0,
    #             'credit': recognize - vat_amount,
    #             'name': _('Coupon Sales Revenue - %s') % coupon.name,
    #             'partner_id': coupon.customer_id.id,
    #         }),
    #     ]
    #     if vat_amount and vat_account_id:
    #         lines.append((0, 0, {
    #             'account_id': vat_account_id,
    #             'debit': 0.0,
    #             'credit': vat_amount,
    #             'name': _('VAT Output - %s') % coupon.name,
    #             'partner_id': coupon.customer_id.id,
    #         }))
    #
    #     recog_move = self.env['account.move'].create({
    #         'move_type': 'entry',
    #         'journal_id': journal_id,
    #         'date': self.invoice_date or fields.Date.today(),
    #         'ref': _('Revenue Recognition - %s / %s') % (coupon.name, self.name),
    #         'coupon_id': coupon.id,
    #         'line_ids': lines,
    #     })
    #     recog_move.action_post()
    #
    #     # Record usage history
    #     if self.job_id:
    #         print("98UOIHJKN98UIHKJ")
    #         coupon_lines = self.job_id.job_cost_sheet_ids.filtered(
    #             lambda l: l.coupon_line
    #         )
    #
    #         for line in coupon_lines:
    #             self.env['customer.coupon.usage'].create({
    #                 'coupon_id': coupon.id,
    #                 'usage_date': self.invoice_date or fields.Date.today(),
    #                 'amount': line.price_unit,
    #                 'invoice_id': self.id,
    #                 'service_id': line.product_id.id,
    #                 'service_no': line.coupon_service_no,
    #                 'notes': _('Auto-recognized from Invoice %s') % self.name,
    #             })
    #     coupon._update_state_from_usage()
