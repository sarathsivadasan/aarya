from odoo import models, fields, api
from datetime import datetime

class AgeingCustomerStatementWizard(models.TransientModel):
    _name = 'ageing.customer.statement.wizard'
    _description = 'Customer Statement of Account with Ageing Wizard'

    date_from = fields.Date(string="Start Date", required=True)
    date_to = fields.Date(string="End Date", required=True)
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)

    def _get_soa_a_report_base_filename(self):
        """Generates a filename in the format 'Lastname_Fullname_soa_YYYY-MM-DD'."""
        self.ensure_one()
        today_date = datetime.today().strftime('%Y-%m-%d')
        full_name = self.partner_id.name or ''
        filename = f"{full_name}_SOA_{today_date}"
        return filename

    def print_customer_statement(self):
        # Initialize the list for payment details
        transactions = [] 

        inv_objs = self.env['account.move'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'posted'),
            ('payment_state', '=', 'not_paid'),
            ('invoice_date_due', '<=', self.date_to),  # Invoices before the as of date
            ('move_type', '=', 'out_invoice')
        ])


        inv_objs = sorted(
            inv_objs,
            key=lambda x: (x.invoice_date)
        )

        due_current_amt = 0
        due_0130_amt = 0
        due_3160_amt = 0
        due_6190_amt = 0
        due_past90_amt = 0
        total_amount_due = 0
        running_balance = 0

        for rec in inv_objs:
            due_date = fields.Datetime.to_datetime(rec.invoice_date_due)
            days_past_due = (fields.Datetime.now() - due_date).days
            running_balance += rec.amount_residual
            vals={
                'invoice_date': rec.invoice_date.strftime('%m/%d/%Y'),
                'name': rec.name or '',
                'payment_term': rec.invoice_payment_term_id.name or '',
                'due_date': rec.invoice_date_due.strftime('%m/%d/%Y'),
                'amount': rec.amount_residual or 0.0,
                'running_balance':running_balance,
                'days_due': days_past_due
            }
            transactions.append(vals)

            if days_past_due == 0:
                due_current_amt += rec.amount_residual
            elif days_past_due >= 1 and days_past_due <= 30:
                due_0130_amt += rec.amount_residual
            elif days_past_due >= 31 and days_past_due <= 60:
                due_3160_amt += rec.amount_residual
            elif days_past_due >= 61 and days_past_due <= 90:
                due_6190_amt += rec.amount_residual
            elif days_past_due >= 91:
                due_past90_amt += rec.amount_residual

        total_amount_due = running_balance
         
        # Prepare data for the report
        data = {
            'form': {
                'partner_id': self.partner_id,
                'as_of': self.date_to.strftime('%B %d, %Y'), 
                'opening_balance': 0, 
                'amount_due': total_amount_due, 
                'due_current_amt' : due_current_amt,
                'due_0130_amt' : due_0130_amt,
                'due_3160_amt' : due_3160_amt,
                'due_6190_amt' : due_6190_amt,
                'due_past90_amt' : due_past90_amt,
                'total_amount_due': total_amount_due,   
                'transactions': transactions
            }
        }
        # # Pass data in the context
        return self.env.ref('mkl_soa_ageing_report_a.action_variable_month_ageing_customer_statement_report').with_context(data=data).report_action(self)
