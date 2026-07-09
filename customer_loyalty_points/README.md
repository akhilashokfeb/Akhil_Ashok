# Customer Loyalty Points

This module lets customers earn loyalty points from posted customer invoices and redeem those points as discounts on sale orders.

## Workflow

### 1. Configure Loyalty Settings

Go to **Settings > Companies** or the related configuration view and set the loyalty values for the company.

Configure:

- **Amount Required for 1 Point**: invoice amount needed to earn one loyalty point.
- **Value of 1 Point**: discount value of one loyalty point when redeemed on a sale order.

Example:

- Amount Required for 1 Point = `10.00`
- Value of 1 Point = `0.50`

If a customer invoice is posted for `100.00`, the customer earns `10` points.
If the customer redeems `10` points, the sale order gets a discount of `5.00`.

### 2. Customer Earns Points

Create and post a customer invoice.

When the invoice is posted:

1. The module checks the invoice total.
2. It calculates loyalty points using the company setting.
3. It creates a loyalty transaction with type **Earned**.
4. The earned points become available for the customer's commercial partner.
5. The earned points get an expiration date after one year.

Only posted customer invoices earn points.

### 3. View Customer Points

Open the customer form.

The module shows the customer's available loyalty points. These points are calculated from loyalty transactions that still have remaining points.

Use the **Loyalty Points** smart button to view the customer's loyalty transaction history.

The transaction list shows:

- transaction date
- customer
- company
- transaction type
- total points
- remaining points
- expiration date
- description

### 4. Redeem Points on a Sale Order

Create a sale order for a customer who has available points.

If the customer has points, the sale order shows the available loyalty points and a **Redeem Now** button.

Click **Redeem Now**:

1. Enter the number of points to redeem.
2. The wizard calculates the discount amount.
3. Apply the redemption.
4. The module adds a negative sale order line for the loyalty discount.

The redemption line uses the loyalty redemption product created by the module.

### 5. Confirm the Sale Order

When the sale order is confirmed:

1. The module checks that redeemed points do not exceed available points.
2. It checks that the discount is not greater than the sale order subtotal.
3. It consumes the customer's available points using FIFO order.
4. It creates loyalty transactions with type **Redeemed**.
5. The sale order is marked as having loyalty points deducted.

FIFO means the oldest available points are used first.

### 6. Cancel a Sale Order

If a confirmed sale order with redeemed points is cancelled:

1. The module restores the redeemed points.
2. It creates loyalty transactions with type **Restored**.
3. The restored points become available again.
4. The redemption line is removed from the sale order.
5. The sale order redeemed points are reset to zero.

### 7. Customer Credit Notes

When a customer credit note is posted:

1. The module calculates how many points should be recovered.
2. It consumes available points from the customer.
3. It creates loyalty transactions with type **Refunded**.

### 8. Reset Invoice or Credit Note to Draft

If a posted customer invoice is reset to draft:

1. The module reverses the points awarded by that invoice.
2. It creates loyalty transactions with type **Reset To Draft**.

If a posted customer credit note is reset to draft:

1. The module restores the points that were recovered by the credit note.
2. It creates loyalty transactions with type **Restored**.

### 9. Expire Loyalty Points Automatically

The module includes a daily scheduled action named **Expire Loyalty Points**.

This scheduled action:

1. Finds earned or restored points that still have remaining points.
2. Checks whether the expiration date has passed.
3. Sets the remaining points to zero.
4. Creates loyalty transactions with type **Expired**.

Only available points can expire.

### 10. Expire Selected Points Manually

From the loyalty transactions list, select transactions and run the **Expire Loyalty Points** server action.

The server action:

1. Reads the selected transaction records.
2. Expires only selected transactions with type **Earned** or **Restored**.
3. Ignores transactions that have no remaining points.
4. Creates loyalty transactions with type **Expired**.

## Important Rules

- Points are calculated per company.
- Customer points are stored against the commercial partner.
- Only **Earned** and **Restored** transactions can have available remaining points.
- **Redeemed**, **Refunded**, **Reset To Draft**, and **Expired** transactions reduce or record point movement, but they do not create new available points.
- Loyalty points are valid for one year from the earning or restoring date.
- The oldest available points are consumed first.

## Module Dependencies

This module depends only on standard Odoo addons:

- `base`
- `account`
- `portal`
- `sale_management`

No external Python package or third-party service is required.
