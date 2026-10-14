import datetime

from odoo import models, fields, api, _, Command
from num2words import num2words
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo.tools.misc import get_lang
from babel.dates import format_datetime, format_date
from odoo.tools import float_compare, float_round, float_repr
from collections import defaultdict


class AccountMove(models.Model):
    _inherit = "account.move"

    excess_amount_move_id = fields.Many2one("account.move", string="Invoice Excess Amount", copy=False)
    excess_amount_move_for_id = fields.Many2one("account.move", string="Invoice Excess Amount for", copy=False)
    partner_excess_amount = fields.Many2one("res.partner", string="Charged To", copy=False)
    excess_amount = fields.Monetary(string="Excess Amount", copy=False, readonly=0)
    cc_total_amount = fields.Monetary(string="Total Amount")
    # cc_total_amount = fields.Monetary(string="Total Amount", compute="depends_invoice_line_ids", store=True)
    insurance_invoice_created =fields.Boolean(default=False)

    def _get_excess_product(self):
        """Return the single 'Excess Amount' product (xml-id first, then fallback search)."""
        tmpl = self.env.ref('excess_amount_insurance.product_excess_amount', raise_if_not_found=False)
        product = tmpl.product_variant_id if tmpl else self.env['product.product']
        if not product:
            product = self.env['product.product'].search(
                [('active', '=', True), '|', ('default_code', '=', 'EA'), ('name', '=', 'Excess Amount')],
                limit=1)
        return product

    def _get_excess_lines(self):
        """All invoice lines that carry an Excess Amount product, whichever
        product record (xml-id one, or another named 'Excess Amount' / code EA)."""
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda l: l.product_id and (
                l.product_id.default_code == 'EA' or l.product_id.name == 'Excess Amount'
            )
        )

    # ------------------------------------------------------------------
    # Excess line is maintained SERVER-SIDE (create / write), not through an
    # onchange. Pushing a Command.create from an onchange into invoice_line_ids
    # (which is mirrored by line_ids on the form) is what produced the second,
    # zero-price "Spare Parts" Excess Amount row.
    # ------------------------------------------------------------------
    def _sync_excess_line(self, full=True):
        """Guarantee exactly ONE excess line on draft invoices.

        full=True : line follows excess_amount (create / update / delete).
        full=False: only de-duplicate (and drop zero-price excess lines when
                    no excess amount is set); never removes a priced line.
        """
        for move in self.with_context(skip_excess_sync=True):
            if move.state != 'draft' or not move.is_invoice(include_receipts=True):
                continue
            lines = move._get_excess_lines()
            amount = move.excess_amount if move.excess_amount and move.excess_amount > 0 else 0.0
            cmds = []
            if not amount:
                victims = lines if full else lines.filtered(lambda l: not l.price_unit)
                cmds = [Command.delete(l.id) for l in victims]
            else:
                product = move._get_excess_product()
                if not product:
                    raise ValidationError(_("Excess Amount Product does not exist!"))
                # keep the priced line (if any), drop every other one
                ordered = lines.sorted(key=lambda l: (not l.price_unit, l.id))
                keep, extra = ordered[:1], ordered[1:]
                cmds = [Command.delete(l.id) for l in extra]
                vals = {
                    'product_id': product.id,
                    'quantity': 1.0,
                    'price_unit': -amount,
                    'cost_type': 'labour',
                    'discount': 0.0,
                    'discount_fixed': 0.0,
                }
                if keep:
                    line = keep[0]
                    if (line.product_id != product or line.price_unit != -amount
                            or line.quantity != 1.0 or line.cost_type != 'labour'):
                        cmds.append(Command.update(line.id, vals))
                else:
                    accounts = product.product_tmpl_id.get_product_accounts(
                        fiscal_pos=move.fiscal_position_id)
                    account = accounts['expense'] if move.is_purchase_document() else accounts['income']
                    vals['name'] = product.display_name
                    if account:
                        vals['account_id'] = account.id
                    cmds.append(Command.create(vals))
            if cmds:
                move.write({'invoice_line_ids': cmds})

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        if not self.env.context.get('skip_excess_sync'):
            moves.filtered('excess_amount')._sync_excess_line(full=True)
        return moves

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_excess_sync'):
            if 'excess_amount' in vals:
                self._sync_excess_line(full=True)
            elif 'invoice_line_ids' in vals:
                self._sync_excess_line(full=False)
        return res

    # def _post(self, soft=True):
    #     """Post/Validate the documents.

    #     Posting the documents will give it a number, and check that the document is
    #     complete (some fields might not be required if not posted but are required
    #     otherwise).
    #     If the journal is locked with a hash table, it will be impossible to change
    #     some fields afterwards.

    #     :param soft (bool): if True, future documents are not immediately posted,
    #         but are set to be auto posted automatically at the set accounting date.
    #         Nothing will be performed on those documents before the accounting date.
    #     :return Model<account.move>: the documents that have been posted
    #     """
    #     # `user_has_group` won't be bypassed by `sudo()` since it doesn't change the user anymore.
    #     if not self.env.su and not self.env.user.has_group('account.group_account_invoice'):
    #         raise AccessError(_("You don't have the access rights to post an invoice."))
    #     excess_amount_move_id = []
    #     for move in to_post:
    #         if move.excess_amount_move_id:
    #             move.excess_amount_move_id.excess_amount_move_for_id = move.id
    #             excess_amount_move_id.append(move.excess_amount_move_id)

    #         if move.partner_bank_id and not move.partner_bank_id.active:
    #             raise UserError(
    #                 _("The recipient bank account link to this invoice is archived.\nSo you cannot confirm the invoice."))
    #         if move.state == 'posted':
    #             raise UserError(_('The entry %s (id %s) is already posted.') % (move.name, move.id))
    #         if not move.excess_amount_move_for_id:
    #             if not move.line_ids.filtered(lambda line: not line.display_type):
    #                 raise UserError(_('You need to add a line before posting.'))
    #         if move.auto_post and move.date > fields.Date.context_today(self):
    #             date_msg = move.date.strftime(get_lang(self.env).date_format)
    #             raise UserError(_("This move is configured to be auto-posted on %s", date_msg))
    #         if not move.journal_id.active:
    #             raise UserError(_(
    #                 "You cannot post an entry in an archived journal (%(journal)s)",
    #                 journal=move.journal_id.display_name,
    #             ))

    #         if not move.partner_id:
    #             if move.is_sale_document():
    #                 raise UserError(
    #                     _("The field 'Customer' is required, please complete it to validate the Customer Invoice."))
    #             elif move.is_purchase_document():
    #                 raise UserError(
    #                     _("The field 'Vendor' is required, please complete it to validate the Vendor Bill."))

    #         if move.is_invoice(include_receipts=True) and float_compare(move.amount_total, 0.0,
    #                                                                     precision_rounding=move.currency_id.rounding) < 0:
    #             raise UserError(
    #                 _("You cannot validate an invoice with a negative total amount. You should create a credit note instead. Use the action menu to transform it into a credit note or refund."))

    #         if move.display_inactive_currency_warning:
    #             raise UserError(_("You cannot validate an invoice with an inactive currency: %s",
    #                               move.currency_id.name))

    #         if move.line_ids.account_id.filtered(lambda account: account.deprecated):
    #             raise UserError(_("A line of this move is using a deprecated account, you cannot post it."))

    #         # Handle case when the invoice_date is not set. In that case, the invoice_date is set at today and then,
    #         # lines are recomputed accordingly.
    #         # /!\ 'check_move_validity' must be there since the dynamic lines will be recomputed outside the 'onchange'
    #         # environment.
    #         if not move.invoice_date:
    #             if move.is_sale_document(include_receipts=True):
    #                 move.invoice_date = fields.Date.context_today(self)
    #                 move.with_context(check_move_validity=False, force_onchange_currency=True)._onchange_invoice_date()
    #             elif move.is_purchase_document(include_receipts=True):
    #                 raise UserError(_("The Bill/Refund date is required to validate this document."))

    #         # When the accounting date is prior to a lock date, change it automatically upon posting.
    #         # /!\ 'check_move_validity' must be there since the dynamic lines will be recomputed outside the 'onchange'
    #         # environment.
    #         affects_tax_report = move._affect_tax_report()
    #         lock_dates = move._get_violated_lock_dates(move.date, affects_tax_report)
    #         if lock_dates:
    #             move.date = move._get_accounting_date(move.invoice_date or move.date, affects_tax_report)
    #             if move.move_type and move.move_type != 'entry':
    #                 move.with_context(check_move_validity=False)._onchange_currency()

    #     # Create the analytic lines in batch is faster as it leads to less cache invalidation.
    #     to_post.mapped('line_ids').create_analytic_lines()

    #     for move in to_post:
    #         # Fix inconsistencies that may occure if the OCR has been editing the invoice at the same time of a user. We force the
    #         # partner on the lines to be the same as the one on the move, because that's the only one the user can see/edit.
    #         wrong_lines = move.is_invoice() and move.line_ids.filtered(
    #             lambda aml: aml.partner_id != move.commercial_partner_id and not aml.display_type)
    #         if wrong_lines:
    #             wrong_lines.write({'partner_id': move.commercial_partner_id.id})

    #     to_post.write({
    #         'state': 'posted',
    #         'posted_before': True,
    #     })

    #     for move in to_post:
    #         move.message_subscribe([p.id for p in [move.partner_id] if p not in move.sudo().message_partner_ids])

    #     for move in to_post:
    #         if move.is_sale_document() \
    #                 and move.journal_id.sale_activity_type_id \
    #                 and (move.journal_id.sale_activity_user_id or move.invoice_user_id).id not in (
    #                 self.env.ref('base.user_root').id, False):
    #             move.activity_schedule(
    #                 date_deadline=min((date for date in move.line_ids.mapped('date_maturity') if date),
    #                                   default=move.date),
    #                 activity_type_id=move.journal_id.sale_activity_type_id.id,
    #                 summary=move.journal_id.sale_activity_note,
    #                 user_id=move.journal_id.sale_activity_user_id.id or move.invoice_user_id.id,
    #             )

    #     customer_count, supplier_count = defaultdict(int), defaultdict(int)
    #     for move in to_post:
    #         if move.is_sale_document():
    #             customer_count[move.partner_id] += 1
    #         elif move.is_purchase_document():
    #             supplier_count[move.partner_id] += 1
    #     for partner, count in customer_count.items():
    #         (partner | partner.commercial_partner_id)._increase_rank('customer_rank', count)
    #     for partner, count in supplier_count.items():
    #         (partner | partner.commercial_partner_id)._increase_rank('supplier_rank', count)

    #     # Trigger action for paid invoices in amount is zero
    #     to_post.filtered(
    #         lambda m: m.is_invoice(include_receipts=True) and m.currency_id.is_zero(m.amount_total)
    #     ).action_invoice_paid()

    #     # Force balance check since nothing prevents another module to create an incorrect entry.
    #     # This is performed at the very end to avoid flushing fields before the whole processing.
    #     to_post._check_balanced()
    #     return to_post

    # def action_post(self):
    #     res = super(AccountMove, self).action_post()
    #     if self.excess_amount and self.partner_excess_amount:
    #         excess_amount_move_id = self.excess_amount_move_id
    #         invoice = None
    #         product_id = self.env['product.product'].search(
    #             [('active', '=', True), ('name', '=', 'Excess Amount'), ('default_code', '=', 'EA')])
    #         lines = []
    #         vals = {
    #             'cost_type': "labour",
    #             'product_id': product_id.id,
    #             # 'product_id': 2,
    #             'name': product_id.name,
    #             'quantity': 1,
    #             'price_unit': self.excess_amount,
    #             'partner_id': self.partner_id.id,
    #             'account_id': product_id.property_account_expense_id.id,
    #             # 'company_id': self.env.company.id,
    #             'currency_id': self.env.user.company_id.currency_id.id,
    #             'tax_ids': product_id.taxes_id.ids if product_id.taxes_id else "",
    #         }
    #         lines.append((0, 0, vals))
    #         if excess_amount_move_id:
    #             # excess_amount_move_id.invoice_line_ids = [(5, 0, 0)]
    #             excess_amount_move_id.update({
    #                 'partner_id': self.partner_excess_amount.id,
    #                 'vehicle_id': self.vehicle_id.id if self.vehicle_id else "",
    #             })
    #             excess_amount_move_id.action_post()
    #         else:
    #             invoice = self.create({
    #                 'move_type': 'out_invoice',
    #                 'partner_id': self.partner_excess_amount.id,
    #                 'invoice_date': datetime.date.today(),
    #                 'vehicle_id': self.vehicle_id.id if self.vehicle_id else "",
    #                 # 'invoice_line_ids': lines
    #             })
    #             invoice.invoice_line_ids = lines
    #             invoice.invoice_line_ids = [(5, 0, 0)]
    #             invoice.invoice_line_ids = lines
    #             invoice.action_post()
    #             invoice.cc_total_amount = self.amount_untaxed + self.excess_amount
    #             # invoice._onchange_invoice_line_ids(
    #             self.excess_amount_move_id = invoice.id
    #     return res

    def action_insurance(self):
        if self.excess_amount and self.partner_excess_amount:
            excess_amount_move_id = self.excess_amount_move_id
            invoice = None
            product_id = self._get_excess_product()
            # Remove duplicated excess lines left on the source invoice (draft only)
            self._sync_excess_line(full=True)
            lines = []
            vals = {
                'cost_type': "labour",
                'product_id': product_id.id,
                # 'product_id': 2,
                'name': product_id.name,
                'quantity': 1,
                'price_unit': self.excess_amount,
                'partner_id': self.partner_id.id,
                'account_id': product_id.property_account_expense_id.id,
                # 'company_id': self.env.company.id,
                'currency_id': self.env.user.company_id.currency_id.id,
                'tax_ids': product_id.taxes_id.ids if product_id.taxes_id else "",
            }
            lines.append((0, 0, vals))
            if excess_amount_move_id:
                # excess_amount_move_id.invoice_line_ids = [(5, 0, 0)]
                excess_amount_move_id.update({
                    'partner_id': self.partner_excess_amount.id,
                    'vehicle_id': self.vehicle_id.id if self.vehicle_id else "",
                })
                excess_amount_move_id.action_post()
            else:
                invoice = self.create({
                    'move_type': 'out_invoice',
                    'partner_id': self.partner_excess_amount.id,
                    'invoice_date': datetime.date.today(),
                    'vehicle_id': self.vehicle_id.id if self.vehicle_id else "",
                    # 'invoice_line_ids': lines
                })
                invoice.invoice_line_ids = lines
                invoice.invoice_line_ids = [(5, 0, 0)]
                invoice.invoice_line_ids = lines
                invoice.action_post()
                invoice.cc_total_amount = self.amount_untaxed + self.excess_amount
                # invoice._onchange_invoice_line_ids(
                self.excess_amount_move_id = invoice.id
            self.insurance_invoice_created = True
    def button_draft(self):
        res = super(AccountMove, self).button_draft()
        if self.excess_amount_move_id:
            self.excess_amount_move_id.button_draft()
            # self.excess_amount_move_id.sudo().unlink()

        return res

    def num_convert_to_text(self, num):
        a = num2words(num)
        return a.upper()

    # def write(self, vals):
    #     rtn = super(AccountMove, self).write(vals)
    #     return rtn


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    discount_fixed = fields.Float(
        string="Excess Amount",
        digits="Product Price",
        default=0.00,
        help="Excess Amount",
    )
