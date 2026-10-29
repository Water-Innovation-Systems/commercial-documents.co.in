**Commercial Document Management**

Create, manage, and organize professional commercial documents with ease. From quotations and purchase orders to tax invoices, proforma invoices, delivery challans, sales orders, payment receipts, and credit or debit notes, streamline your business documentation with accurate, consistent, and professional formatting.

Generate customized documents with company details, customer information, product descriptions, quantities, pricing, applicable taxes, payment terms, delivery details, and authorized signatures. Maintain clear transaction records, improve documentation accuracy, and simplify your daily business operations with an efficient and organized document management system.

**Supported Commercial Documents:**
- **Quotation:** Provide customers with product pricing, specifications, taxes, and commercial terms.
- **Purchase Order (PO):** Document the formal purchase of goods or services from suppliers.
- **Tax Invoice:** Generate invoices with applicable GST details, taxable values, and tax calculations.
- **Proforma Invoice:** Share preliminary pricing and payment details before issuing the final invoice.
- **Sales Order:** Record and manage confirmed customer orders.
- **Delivery Challan:** Document the movement or delivery of goods.
- **Payment Receipt:** Provide confirmation of payments received.
- **Credit Note:** Record eligible reductions in previously invoiced amounts.
- **Debit Note:** Document applicable increases in amounts payable or other adjustments.
- **Purchase Invoice:** Record supplier invoices for goods or services purchased.
- **Work Order:** Define the scope, terms, and requirements of a job or service.
- **Service Report:** Document installation, maintenance, inspection, and repair activities.

**Key Benefits:**
- Professional, company-branded document templates.
- Automatic calculation of totals, discounts, and applicable taxes.
- Customer, supplier, and product information management.
- Unique document numbering and date tracking.
- Print-ready layouts and PDF export.
- Organized commercial records for easy reference.
- Improved accuracy, efficiency, and consistency across business transactions.

## Run the signup and login portal

The authentication API and static website are served together so sign-in works
on the same origin. From this folder, run:

```powershell
python auth_server.py
```

Open `http://127.0.0.1:8000/index.html` in your browser. **Do not open
`index.html` as a `file://` URL.** New accounts are saved to a local SQLite
database, and successfully signing up or signing in redirects to
`Mainpage.html`. The dashboard and document pages redirect unauthenticated
visitors to the sign-in page. The “Keep me signed in” checkbox controls session
duration.

On Windows, the default account database is stored outside the repository at
`%LOCALAPPDATA%\WaterInnovationSystems\accounts.sqlite3`. To select a different
database for local testing, set `WIS_AUTH_DB` before starting the server.
Accounts persist when the server restarts; password hashes, never plaintext
passwords, are stored in the database.

`login.js` sends same-origin requests to the server's signup, login and
password-reset endpoints. Signup and login are implemented. Password reset
returns a clear “email delivery is not configured” error until an email
provider is set up.

For production, deploy behind a properly configured HTTPS application server
and reverse proxy, set `WIS_COOKIE_SECURE=1`, and review the session, database
backup, and rate-limiting configuration. Python's built-in development server
is intended for local use, not direct public deployment.

Run the authentication tests with:

```powershell
python -m unittest -v test_auth_server.py
```
