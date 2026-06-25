=================
DUB Treasury Base
=================

Foundation for treasury management: treasury accounts, credit lines, financial
instruments and installments. Integrates with Odoo accounting and banking.

Features
========

* **Treasury accounts**: bank, cash and internal accounts.
* **Credit lines**: overdrafts, invoice advances, bill discounts, factoring.

  * **Usage priority** (``sequence``) to order facilities by preference
    (e.g. preferred bank first). Informational ordering only.
  * **Projected availability at date**: answer *"at date D, how much of this
    facility is left given the expected flow until that day?"* via
    ``get_available_at_date`` / ``get_available_at_dates`` and the
    *Availability Projection* wizard (pivot, configurable day/week/month
    granularity). The snapshot ``available_amount`` keeps its "today" meaning.
  * **Tiered interest rates**: optional interest-rate tiers by utilization
    threshold and validity dates (``get_applicable_rate``); falls back to the
    flat ``interest_rate`` when no tier matches.

* **Financial instruments**: loans, mortgages, leasing, partner loans.
* **Covenants**: financial conditions with automatic value computation.

Configuration
=============

Availability projection
----------------------

*Treasury > Accounts > Availability Projection*. Choose the date range,
granularity and (optionally) the credit lines, then *Compute* to open a pivot
of limit / used / available per bank and date.

* Overdraft usage is derived from the projected bank balance (cashflow items on
  the line's journal up to the target date).
* Advance/discount/SBF/factoring usage sums the residual of linked invoices due
  on or before the target date.

Rate tiers
----------

Open a credit line, tab *Rate Tiers*, and define ``from``/``to`` utilization
amounts with the applicable rate (and optional validity window). When tiers are
present they override the flat interest rate.
