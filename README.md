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

## Sign up and sign in

For static hosting, `index.html` loads `login.js`. Open the site over HTTPS,
sign up, then sign in with the same email and password. Sign-up records are
saved in that browser's local storage; a successful sign-in opens
`Mainpage.html`. Accounts are specific to one browser and device.

Passwords are stored as salted, browser-generated PBKDF2 hashes rather than
readable passwords. This static demonstration is **not secure authentication**:
browser storage can be read or changed by the user, and the dashboard's HTML
files are still publicly accessible. Do not use it to protect commercial or
personal information. Use a server-side authentication service with a database
and sessions before deploying a production portal. Browser-only password resets
are not available.
