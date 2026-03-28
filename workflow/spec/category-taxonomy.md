# NovaScan Category Taxonomy

Categories and subcategories are assigned by AI during receipt extraction. Users can override assignments and create custom categories.

If AI confidence is low, it defaults to **Other > Uncategorized**.

---

## Predefined Categories

### Groceries & Food (`groceries-food`)

| Subcategory | Slug |
|-------------|------|
| Supermarket / Grocery | `supermarket-grocery` |
| Produce | `produce` |
| Meat & Seafood | `meat-seafood` |
| Breads & Bakery | `breads-bakery` |
| Deli & Prepared Food | `deli-prepared-food` |
| Dairy, Cheese & Eggs | `dairy-cheese-eggs` |
| Frozen Food | `frozen-food` |
| Snacks | `snacks` |
| Pantry | `pantry` |
| Beverages | `beverages` |
| Specialty Food & Beverage | `specialty-food-beverage` |
| Convenience Store | `convenience-store` |
| Farmers Market / Bakery | `farmers-market-bakery` |

### Dining (`dining`)

| Subcategory | Slug |
|-------------|------|
| Fast Food / Quick Service | `fast-food-quick-service` |
| Restaurant / Dine-In | `restaurant-dine-in` |
| Delivery & Takeout | `delivery-takeout` |
| Coffee & Cafe | `coffee-cafe` |
| Bar & Nightlife | `bar-nightlife` |

### Retail & Shopping (`retail-shopping`)

| Subcategory | Slug |
|-------------|------|
| Electronics & Technology | `electronics-technology` |
| Clothing & Apparel | `clothing-apparel` |
| Arts, Crafts & Hobbies | `arts-crafts-hobbies` |
| Home & Garden | `home-garden` |
| General Merchandise / Discount | `general-merchandise-discount` |
| Sporting Goods | `sporting-goods` |
| Books & Media | `books-media` |

### Automotive & Transit (`automotive-transit`)

| Subcategory | Slug |
|-------------|------|
| Fuel & EV Charging | `fuel-ev-charging` |
| Auto Maintenance & Service | `auto-maintenance-service` |
| Rideshare & Public Transit | `rideshare-public-transit` |
| Parking & Tolls | `parking-tolls` |
| Auto Parts & Accessories | `auto-parts-accessories` |

### Health & Wellness (`health-wellness`)

| Subcategory | Slug |
|-------------|------|
| Pharmacy | `pharmacy` |
| Personal Care | `personal-care` |
| Medical & Dental | `medical-dental` |
| Vision & Optical | `vision-optical` |
| Fitness & Gym | `fitness-gym` |

### Entertainment & Travel (`entertainment-travel`)

| Subcategory | Slug |
|-------------|------|
| Event Tickets & Shows | `event-tickets-shows` |
| Lodging & Hotels | `lodging-hotels` |
| Flights & Travel Services | `flights-travel-services` |
| Attractions & Activities | `attractions-activities` |

### Home & Utilities (`home-utilities`)

| Subcategory | Slug |
|-------------|------|
| Utilities (Electric, Gas, Water) | `utilities-electric-gas-water` |
| Internet & Phone | `internet-phone` |
| Home Maintenance & Repair | `home-maintenance-repair` |
| Cleaning & Laundry | `cleaning-laundry` |

### Education (`education`)

| Subcategory | Slug |
|-------------|------|
| Courses & Tuition | `courses-tuition` |
| Books & Supplies | `books-supplies` |
| Professional Development | `professional-development` |

### Pets (`pets`)

| Subcategory | Slug |
|-------------|------|
| Veterinary | `veterinary` |
| Pet Food & Supplies | `pet-food-supplies` |
| Grooming & Boarding | `grooming-boarding` |

### Gifts & Donations (`gifts-donations`)

| Subcategory | Slug |
|-------------|------|
| Gifts | `gifts` |
| Charitable Donations | `charitable-donations` |

### Financial & Insurance (`financial-insurance`)

| Subcategory | Slug |
|-------------|------|
| Bank & Service Fees | `bank-service-fees` |
| Insurance Premiums | `insurance-premiums` |

### Office & Business (`office-business`)

| Subcategory | Slug |
|-------------|------|
| Office Supplies | `office-supplies` |
| Postage & Shipping | `postage-shipping` |
| Subscriptions & SaaS | `subscriptions-saas` |
| Printing & Copying | `printing-copying` |

### Other (`other`)

| Subcategory | Slug |
|-------------|------|
| Uncategorized | `uncategorized` |

---

## Line-Item Subcategories

Line items on any receipt can be tagged with a `subcategory` from the parent category's subcategory list. This is most useful for **Groceries & Food** receipts, where individual items belong to different product departments.

For grocery receipts, the product-type subcategories serve dual purpose:
1. **Receipt-level subcategory** — classifies the store type (e.g., a butcher shop → `meat-seafood`, a general supermarket → `supermarket-grocery`)
2. **Line-item subcategory** — classifies individual products (e.g., "Chicken Breast" → `meat-seafood`, "Milk" → `dairy-cheese-eggs`)

The subcategory slugs used at both levels are the same (see Groceries & Food subcategories above). For non-grocery receipts, line-item subcategory is optional and typically null.

---

## Custom Categories

Users can create custom categories via `POST /api/categories`.

### Storage

Custom categories are stored in DynamoDB in the same single table, under the user's partition:
- `PK = USER#{userId}`, `SK = CUSTOMCAT#{slug}`, `entityType = CUSTOMCAT`

Each custom category is its own entity. Not stored in the user profile. Not in a separate table.

### Rules

- Slug auto-generated from display name (lowercase, spaces → hyphens, special chars removed)
- Slugs must be unique per user (across predefined and custom categories)
- Can optionally specify a `parentCategory` (must be a predefined category slug)
- User-scoped — not shared between users
- Included in the AI extraction prompt — the pipeline queries the user's custom categories and appends them to the predefined taxonomy
- Deleting a custom category does not update receipts already assigned to it

### UX Flow (MVP)

**Entry point:** From the receipt detail page (no standalone category management page for MVP).

1. User opens a receipt detail page
2. User taps the category picker dropdown
3. Dropdown shows predefined categories + user's custom categories (from `GET /api/categories`)
4. At the bottom of the dropdown: "Create Custom Category" option
5. Modal opens: display name input + optional parent category dropdown (predefined categories only)
6. User submits → `POST /api/categories` → API generates slug, creates `CUSTOMCAT#{slug}` in DynamoDB → returns new category
7. New category appears in the dropdown, selected
8. User saves the receipt → `PUT /api/receipts/{id}` with the new category slug

**Delete flow:** From the same category picker, custom categories show a delete icon. Tapping it calls `DELETE /api/categories/{slug}`. Receipts already assigned to the deleted category retain the orphaned slug (displayed as-is in the UI).

### Pipeline Relationship

The OCR pipeline **includes** custom categories in the AI extraction prompt. Before the parallel pipeline branches execute, a `LoadCustomCategories` step queries the user's custom categories from DynamoDB (`PK = USER#{userId}, SK begins_with CUSTOMCAT#`) and appends them to the predefined taxonomy in the structured JSON prompt sent to both pipelines.

- **Latency:** Single DynamoDB query, ~5–10ms. Negligible against a 2–5s Textract call.
- **Cost:** One additional read per receipt. Fractions of a cent at MVP scale.
- **Behavior:** If the AI recognizes a match to a custom category, it assigns it directly during extraction. No manual reassignment needed. If the user has no custom categories, the query returns empty and only the predefined taxonomy is used.

---

## AI Assignment Rules

The AI extraction prompt includes the predefined taxonomy and the user's custom categories (if any). Rules:

1. The full predefined category and subcategory list with slugs
2. The user's custom categories with slugs and optional parent category (appended to the taxonomy)
3. Instruction to default to `other` / `uncategorized` when confidence is below 0.5
4. Instruction to infer the category from merchant name and line items (e.g., "Whole Foods" → Groceries & Food, "Shell" → Automotive & Transit > Fuel & EV Charging)
5. Instruction to prefer custom categories when they are a more specific match than predefined ones (e.g., if user has a custom "Costco" category and the receipt is from Costco, assign "Costco" instead of generic "Groceries")
6. For grocery receipts from general supermarkets: assign `supermarket-grocery` as the receipt subcategory and tag each line item with the appropriate subcategory (e.g., "Chicken Breast" → `meat-seafood`, "Milk" → `dairy-cheese-eggs`)
7. For non-grocery receipts: line-item `subcategory` is optional (null if not applicable)
