# Listing Payment & Approval Flow

## Business Rules

### 1. First Listing is FREE ✅
- User's first listing does not require payment
- No `plan_id` needed
- Still requires admin approval

### 2. Subsequent Listings Require Payment 💰
- 2nd listing onwards: `plan_id` is **required**
- User must select a pricing plan
- Payment must be completed before submission
- Still requires admin approval

### 3. All Listings Require Admin Approval 👨‍💼
- ALL listings (free or paid) start with `status = "pending_approval"`
- Admin reviews and approves/rejects
- Only `active` listings are visible to public

---

## Complete Flow

### Scenario 1: First Listing (FREE)

```
1. User clicks "Create Listing"
   ↓
2. User fills form (category, title, price, etc.)
   ↓
3. Frontend submits WITHOUT plan_id
   ↓
4. Backend checks: Is this user's first listing? YES
   ↓
5. Listing created with status = "pending_approval"
   ↓
6. Admin receives approval request
   ↓
7. Admin approves → Listing becomes "active"
```

**API Call:**
```javascript
POST /api/listings/
{
  "category_id": "cat-123",
  "title": "Toyota Camry 2020",
  "price": 75000,
  "plan_id": null,  // ← No plan needed for first listing
  // ... other fields
}

Response:
{
  "id": "listing-001",
  "status": "pending_approval",
  "message": "Your first listing is free! Waiting for admin approval."
}
```

---

### Scenario 2: Second Listing (PAID)

```
1. User clicks "Create Listing"
   ↓
2. Frontend checks: How many listings does user have?
   ↓
3. If > 0 listings: Show pricing plans selection
   ↓
4. User selects plan (e.g., "Standard - 30 days - AED 50")
   ↓
5. User completes payment via payment gateway
   ↓
6. Payment successful → Get plan_id
   ↓
7. User fills listing form
   ↓
8. Frontend submits WITH plan_id
   ↓
9. Backend checks: Is this user's first listing? NO
   ↓
10. Backend validates plan_id exists and is active
   ↓
11. Listing created with status = "pending_approval"
   ↓
12. Admin approves → Listing becomes "active"
```

**API Call:**
```javascript
// Step 1: Get pricing plans
GET /api/pricing-plans/?type=listing

Response:
[
  {
    "id": "plan-001",
    "name": "Basic",
    "duration_days": 30,
    "price": 50,
    "currency": "AED"
  },
  {
    "id": "plan-002",
    "name": "Featured",
    "duration_days": 30,
    "price": 150,
    "currency": "AED"
  }
]

// Step 2: User selects plan and pays
// (Payment gateway integration - Stripe, PayPal, etc.)

// Step 3: Submit listing with plan_id
POST /api/listings/
{
  "category_id": "cat-123",
  "title": "Honda Civic 2019",
  "price": 65000,
  "plan_id": "plan-001",  // ← Required for 2nd+ listing
  // ... other fields
}

Response (Success):
{
  "id": "listing-002",
  "status": "pending_approval",
  "plan_id": "plan-001",
  "plan_expires_at": "2026-03-04T10:00:00Z"
}

Response (Error - No Payment):
{
  "detail": "Payment required. This is not your first listing. Please select a pricing plan.",
  "status_code": 402
}
```

---

## Admin Approval Flow

**Existing endpoints work for all listings:**

### 1. View Pending Listings
```http
GET /api/admin/listings/?status=pending_approval
Authorization: Bearer <admin_token>

Response: Array of all pending listings (free + paid)
```

### 2. Approve Listing
```http
PUT /api/admin/listings/{listing_id}/approve
Authorization: Bearer <admin_token>

Response:
{
  "id": "listing-001",
  "status": "active"  ← Now visible to public
}
```

### 3. Reject Listing
```http
PUT /api/admin/listings/{listing_id}/reject?reason=Inappropriate%20content
Authorization: Bearer <admin_token>

Response:
{
  "id": "listing-001",
  "status": "rejected",
  "rejection_reason": "Inappropriate content"
}
```

---

## Frontend Implementation

### Check User's Listing Count

```javascript
async function getUserListingCount() {
  const response = await fetch('/api/listings/?user_id=' + currentUserId, {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  });
  
  const listings = await response.json();
  return listings.length;
}
```

### Show Payment Flow if Needed

```javascript
async function createListing(formData) {
  // Check if user needs to pay
  const listingCount = await getUserListingCount();
  
  if (listingCount === 0) {
    // First listing - FREE!
    await submitListing({
      ...formData,
      plan_id: null
    });
    showMessage('Your first listing is free! Waiting for admin approval.');
  } else {
    // 2nd+ listing - Show pricing plans
    const plans = await fetch('/api/pricing-plans/?type=listing');
    const pricingPlans = await plans.json();
    
    // Show pricing modal
    showPricingModal(pricingPlans, async (selectedPlan) => {
      // Process payment
      const paymentSuccess = await processPayment(selectedPlan);
      
      if (paymentSuccess) {
        // Submit with plan_id
        await submitListing({
          ...formData,
          plan_id: selectedPlan.id
        });
        showMessage('Listing submitted! Waiting for admin approval.');
      }
    });
  }
}

async function submitListing(data) {
  const response = await fetch('/api/listings/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
  
  if (response.status === 402) {
    // Payment required error
    throw new Error('Payment required');
  }
  
  return response.json();
}
```

---

## Pricing Plans API (To Be Implemented)

### Get Available Plans
```http
GET /api/pricing-plans/?type=listing

Response:
[
  {
    "id": "plan-001",
    "name": "Basic",
    "type": "listing",
    "duration_days": 30,
    "price": 50,
    "currency": "AED",
    "features": {
      "bump_ups": 0,
      "featured": false,
      "priority": "normal"
    }
  },
  {
    "id": "plan-002",
    "name": "Featured",
    "type": "listing",
    "duration_days": 30,
    "price": 150,
    "currency": "AED",
    "features": {
      "bump_ups": 5,
      "featured": true,
      "priority": "high"
    }
  }
]
```

---

## Error Responses

### 402 - Payment Required
```json
{
  "detail": "Payment required. This is not your first listing. Please select a pricing plan.",
  "status_code": 402
}
```

### 404 - Plan Not Found
```json
{
  "detail": "Pricing plan not found",
  "status_code": 404
}
```

### 400 - Inactive Plan
```json
{
  "detail": "Selected pricing plan is not active",
  "status_code": 400
}
```

---

## Status Flow Diagram

```
User Creates Listing
        |
        v
Is First Listing?
    /        \
  YES         NO
   |           |
FREE       PAID (plan_id required)
   |           |
   +-----+-----+
         |
         v
status = "pending_approval"
         |
         v
   Admin Reviews
      /    \
  Approve  Reject
     |        |
  "active"  "rejected"
     |
  Visible to Public
```

---

## Summary

✅ **First listing**: FREE, no plan_id, still needs approval  
💰 **2nd+ listings**: Requires plan_id (payment), still needs approval  
👨‍💼 **All listings**: Start as "pending_approval", admin must approve  
🔍 **Public visibility**: Only "active" listings are shown  

**Next Steps:**
1. Create pricing plans in database
2. Integrate payment gateway (Stripe/PayPal)
3. Build frontend pricing modal
4. Handle payment success/failure callbacks
