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

## Sign-in integration

`index.html` loads `login.js`, which posts account requests to these same-origin HTTPS endpoints:

- `POST /api/auth/signup` accepts `{ name, company, email, password, acceptTerms }`. Return `{"created":true}` after the account is securely created, or `{"authenticated":true}` if signup also creates a session.
- `POST /api/auth/login` accepts `{ email, password, remember }`. Return `{"authenticated":true}` only after verifying the password and establishing a session.
- `POST /api/auth/password-reset` accepts `{ email }`. Return `{"accepted":true}` and send reset instructions through the server.

The browser never saves passwords. Implement these endpoints on the server: hash passwords with Argon2id or bcrypt, issue `Secure`, `HttpOnly`, `SameSite` session cookies, validate requests and terms server-side, rate-limit authentication attempts, and protect the document pages and APIs by checking the session. The standalone HTML files do not provide server-side authentication or access control; run the site over HTTPS, not by opening `index.html` as a local file.
