============
DUB Cashflow
============

Predictive cash flow management for Odoo.

Features
========

* Configure cashflow generation for any model with Python field mappings.
* Automatic create/update/delete of cashflow entries from source records.
* Scenarios to compare alternative forecasts side by side.
* **Categories** to group flows by nature (collections, payments, salaries,
  taxes, ...). The taxonomy is fully tenant-defined.
* **Recurring cashflows** for periodic flows that have no source document yet
  (salaries, F24, commissions, rents).
* **Treasury dashboard**: multi-bank projected cashflow, one column per bank.

Configuration
=============

Categories
----------

Go to *Accounting > Cashflow > Categories* and create your own taxonomy.
Categories support a parent/child hierarchy, a code (used by classifiers),
a color and multi-company scoping. No category is predefined; a small set of
generic examples is shipped as **demo data** only and can be deleted.

To classify generated entries, add a *Field Mapping* line on a
``cashflow.config`` with target field **Category (by code)** and a Python
expression returning a category code, e.g.::

    'fornitori' if record.move_type == 'in_invoice' else 'clienti'

If the returned code matches no category, a warning is logged and the entry is
left without a category (no category is created on the fly).

Recurring cashflows
-------------------

Go to *Accounting > Cashflow > Recurring*. Define the journal, amount, flow
type, recurrence (daily/weekly/monthly/quarterly/yearly), start/end dates and
horizon. A daily cron regenerates forecast entries idempotently; you can also
use the *Generate Entries* button on demand.

When a recurring definition is deactivated or deleted, its forecast entries are
removed; entries already promoted to *actual* are kept as historical record.

Treasury dashboard
-----------------

*Accounting > Cashflow > Treasury Dashboard* shows projected cashflow across all
bank journals side by side (one dynamic column per journal). Filter by horizon
(30/60/90 days), scenario, category and forecast/actual.
