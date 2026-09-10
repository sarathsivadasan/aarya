# Bank Reconciliation Pro (Tally Style) – Odoo 18 Community
## Complete Installation & Usage Guide

---

## 📁 Module Structure

```
bank_reconciliation_pro/
├── __manifest__.py                  ← Module descriptor
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── bank_reco_line.py            ← Core data model
│   └── bank_reco_session.py         ← RPC server methods
├── views/
│   ├── bank_reco_views.xml          ← Client action + fallback views
│   └── menu.xml                     ← Menu items
├── security/
│   ├── security.xml                 ← Groups (User / Manager)
│   └── ir.model.access.csv          ← Model-level ACLs
├── data/
│   └── demo_data.xml                ← 8 sample transactions
└── static/src/
    ├── css/
    │   └── bank_reco.css            ← Full custom stylesheet
    ├── js/
    │   └── bank_reco_action.js      ← OWL component (JS logic)
    └── xml/
        └── bank_reco_templates.xml  ← OWL QWeb template (HTML structure)
```

---

## ⚙️ Step-by-Step Installation

### 1. Copy the module

```bash
cp -r bank_reconciliation_pro /path/to/odoo/addons/
# or place in your custom addons path
```

### 2. Restart Odoo

```bash
./odoo-bin --addons-path=addons,/your/custom/path -d YOUR_DB
# or if using systemd:
sudo systemctl restart odoo
```

### 3. Update App List

- Go to **Settings → Apps → Update Apps List**

### 4. Install the Module

- Search for "**Bank Reconciliation Pro**"
- Click **Install**

### 5. Assign User Roles

- Go to **Settings → Users → [Select User]**
- Under "**Bank Reconciliation Pro**" set:
  - **User** – View + Reconcile
  - **Manager** – Full access (reset, adjustments)

### 6. Access the Screen

- Navigate to **Accounting → Bank Reconciliation Pro → Reconcile**

---

## 🚀 Usage Guide

### Starting a Session

1. **Select Bank Account** – dropdown in the top bar (shows all bank/cash journals)
2. **Set Reconciliation Date** – defaults to today
3. The summary dashboard and transaction table auto-load

### Reading the Dashboard

| Field | Description |
|-------|-------------|
| Opening Balance | Net cleared amount up to the previous day |
| Total Debit | Sum of all debit lines for the period |
| Total Credit | Sum of all credit lines for the period |
| Cleared Amount | Sum of reconciled entries |
| Pending Amount | Sum of unreconciled entries |
| Difference | = Total Debit − Total Credit − Cleared Amount |

> **Mismatch** badge (red) appears when Difference ≠ 0

### Reconciling Entries

#### Single Entry
- Click **Reconcile** on any row  
- The Bank Date in the right panel is used automatically

#### Bulk Reconciliation
1. Check individual rows OR click the header checkbox for **Select All**
2. The right panel shows count and total
3. Fill in **Bank Date** (required), Reference, Notes
4. Click **Reconcile** → entries disappear (moved to reconciled)

### Filters

| Filter | Effect |
|--------|--------|
| Unreconciled Only | Default – hides reconciled entries |
| All Entries | Shows everything |
| Reconciled Only | Shows already-cleared entries |
| All Journals | No journal filter |
| All Partners | No partner filter |
| Search box | Searches Reference, Partner, Amount |

### Fetch Transactions
- Click **Fetch Transactions** to pull `account.move.line` entries from Odoo accounting into the reconciliation table automatically

### Create Adjustment
- When **Difference ≠ 0**, click **Create Adjustment**
- Automatically posts an `account.move` for the difference amount
- Uses the journal's default and suspense accounts

### Reset
- Clears all filters and reloads the table with defaults

---

## 🗄️ Models Reference

### `bank.reco.line`

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Reference (INV/2026/001 etc.) |
| date | Date | Transaction date |
| partner_id | Many2one | Partner |
| journal_id | Many2one | Bank/cash journal |
| debit | Monetary | Debit amount |
| credit | Monetary | Credit amount |
| is_reconciled | Boolean | Reconciled flag |
| cleared_date | Date | Set on reconciliation |
| bank_date | Date | Bank statement date |
| bank_reference | Char | Bank statement ref |
| status | Selection | pending / reconciled (computed) |
| move_line_id | Many2one | Link to account.move.line |
| payment_id | Many2one | Link to account.payment |

### `bank.reco.session` (TransientModel – RPC hub)

| Method | Description |
|--------|-------------|
| get_journals() | Returns bank/cash journal list |
| get_lines(journal_id, ...) | Returns filtered line data for OWL |
| reconcile_lines(ids, date, ...) | Bulk reconcile |
| fetch_transactions(journal_id) | Import from accounting |
| get_summary(journal_id) | Dashboard totals |
| reset_reconciliation(journal_id) | Manager: undo all |
| create_adjustment_entry(...) | Post adjustment move |

---

## 🎨 UI Component Architecture

```
BankRecoAction (OWL Component)
├── Top Bar
│   ├── Title + Journal Selector + Date
│   └── Action Buttons (Fetch / Reconcile / Adjustment / Reset)
├── Summary Bar (6 cards)
├── Content Area
│   ├── Filter Row
│   ├── Table + Panel Wrapper
│   │   ├── Table (left – flex 1)
│   │   │   ├── Header (sticky)
│   │   │   ├── Body (rows)
│   │   │   └── Footer
│   │   └── Right Panel (310px fixed)
│   │       ├── Panel Header
│   │       ├── Panel Body (fields + selection info)
│   │       └── Panel Footer (Reconcile + Clear)
│   └── Info Footer
└── Toast (fixed position)
```

---

## 🔐 Security Roles

### Bank Reconciliation Pro / User
- Read, Create, Write on `bank.reco.line`
- Cannot delete
- Inherits `account.group_account_user`

### Bank Reconciliation Pro / Manager
- Full CRUD on `bank.reco.line`
- Can reset reconciliation
- Can create adjustment entries
- Inherits User group

---

## 📊 Demo Data

8 transactions are loaded covering 01/04/2026 – 08/04/2026:

| Ref | Partner | Debit | Credit |
|-----|---------|-------|--------|
| INV/2026/001 | Al Noor Garage | 5,000 | — |
| PAY/2026/010 | Cash Deposit | — | 3,000 |
| INV/2026/002 | Ahmed Motors | 2,500 | — |
| PAY/2026/011 | Spare Parts Co. | — | 1,800 |
| EXP/2026/005 | Workshop Expenses | 1,200 | — |
| INV/2026/003 | Mohammed Car Care | 4,000 | — |
| PAY/2026/012 | Cash Deposit | — | 2,700 |
| INV/2026/004 | Quick Fix Auto | 3,600 | — |

**Total Debit:** 16,300 | **Total Credit:** 7,500

---

## 🐛 Troubleshooting

### Module not appearing
- Check `--addons-path` includes the parent directory
- Run `--update=bank_reconciliation_pro` flag

### OWL component not loading
- Check browser console for JS errors
- Ensure assets bundle was cleared: `Settings → Technical → Assets`
- Restart Odoo with `-u bank_reconciliation_pro`

### Demo data partner errors
- Demo data uses `account.bank_journal` which must exist
- If missing, create a Bank journal first, then reload demo data

### `account.bank_journal` ref not found
- Replace `ref="account.bank_journal"` in `demo_data.xml` with your actual journal XML ID
- Or comment out the demo data and create records manually

---

## 📝 Customization Tips

1. **Add columns** – extend `get_lines()` in `bank_reco_session.py` and add `<th>/<td>` in the OWL template
2. **Change currency** – `company_currency_id` is auto-set; update `formatAmt()` locale in JS for other currencies
3. **Performance** – `get_lines()` uses Odoo ORM with domain filters; for 10k+ records add `limit` + pagination
4. **Pagination** – add `offset`/`limit` params to `get_lines()` and implement prev/next buttons in OWL

---

*Tally Style Bank Reconciliation for Odoo 18 Community*
