# Town Mart Inventory

Offline Android inventory monitoring app for Town Mart and Coffee Shop Tagpuan (Tuban, Santa Cruz, Davao del Sur).
Prototype for the proposal "Development of a Web-Based Inventory Monitoring System for Town Mart and Coffee Shop Tagpuan".

- Two sections: Mini-mart and Coffee shop
- Item records: category, unit, reorder level, cost, selling price, supplier, expiry, SKU
- Stock in, stock out (with reason) and physical count, with a stock card per item
- Dashboard: low stock, out of stock, expiring in 7 days, stock value
- Reports: stock levels, movements, low stock, value by category and losses; share as CSV
- Backup and restore; sample data for demos

The whole interface is `app/src/main/assets/index.html`; the Android shell is `MainActivity.java`.
Every push to `main` builds the APK with GitHub Actions and publishes it under Releases.
