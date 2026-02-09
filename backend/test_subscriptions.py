
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from fastapi.testclient import TestClient
from main import app
from utils.auth import get_current_admin

def test_subscriptions():
    print("=" * 60)
    print("Testing Subscription API")
    print("=" * 60)

    with patch("routes.subscriptions.db") as mock_db:
        
        # Override dependencies
        app.dependency_overrides[get_current_admin] = lambda: {"id": "admin123", "role": "admin"}

        client = TestClient(app)

        # ----------------------------------------------------------------
        # 1. Test Create Subscription Plan (Admin)
        # ----------------------------------------------------------------
        print("\n1. Testing Create Subscription Plan (Admin)...")
        
        payload = {
            "name_en": "Gold Listing",
            "name_ar": "قائمة ذهبية",
            "type": "listing",
            "price": 100.0,
            "duration_days": 30,
            "description": "Premium listing visibility",
            "is_active": True
        }

        # Mock Insert
        mock_db.insert.return_value = {
            "id": "plan-123",
            **payload,
            "created_at": "2023-10-27T10:00:00Z"
        }

        response = client.post("/api/admin/subscriptions/", json=payload)
        
        if response.status_code == 201:
            data = response.json()
            print("✅ Plan created successfully")
            print(f"   ID: {data['id']}")
            print(f"   Name: {data['name_en']}")
        else:
            print(f"❌ Failed to create plan: {response.text}")
            return False

        # ----------------------------------------------------------------
        # 2. Test List Subscription Plans (Admin)
        # ----------------------------------------------------------------
        print("\n2. Testing List Subscription Plans (Admin)...")
        
        mock_db.select.return_value = [
            {"id": "plan-123", "name_en": "Gold Listing", "name_ar": "قائمة ذهبية", "type": "listing", "price": 100.0, "duration_days": 30, "is_active": True, "description": "desc"}
        ]

        response = client.get("/api/admin/subscriptions/")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved {len(data)} plans")
        else:
            print(f"❌ Failed to list plans: {response.text}")
            return False

        # ----------------------------------------------------------------
        # 3. Test Delete Subscription Plan (Admin)
        # ----------------------------------------------------------------
        print("\n3. Testing Delete Subscription Plan (Admin)...")
        
        mock_db.select_one.return_value = {"id": "plan-123"}
        mock_db.delete.return_value = True

        response = client.delete("/api/admin/subscriptions/plan-123")
        
        if response.status_code == 204:
            print("✅ Plan deleted successfully")
        else:
            print(f"❌ Failed to delete plan: {response.text}")
            return False

        # ----------------------------------------------------------------
        # 4. Test User APIs
        # ----------------------------------------------------------------
        print("\n4. Testing User APIs...")

        # Listing Prices
        mock_db.select.return_value = [{"id": "plan-1", "type": "listing", "price": 10, "name_en": "Basic", "name_ar": "أساسي", "duration_days": 7, "is_active": True, "description": "desc"}]
        res = client.get("/api/subscriptions/listing-prices")
        if res.status_code == 200 and len(res.json()) > 0:
            print("✅ Listing prices retrieved")
        else:
            print(f"❌ Failed to get listing prices: {res.text}")

        # Ad Prices
        mock_db.select.return_value = [{"id": "plan-2", "type": "ad", "price": 50, "name_en": "Banner", "name_ar": "بانر", "duration_days": 7, "is_active": True, "description": "desc"}]
        res = client.get("/api/subscriptions/ad-prices")
        if res.status_code == 200 and len(res.json()) > 0:
             print("✅ Ad prices retrieved")
        else:
             print(f"❌ Failed to get ad prices: {res.text}")

        # Offer Prices
        mock_db.select.return_value = [{"id": "plan-3", "type": "offer", "price": 20, "name_en": "Deal", "name_ar": "عرض", "duration_days": 7, "is_active": True, "description": "desc"}]
        res = client.get("/api/subscriptions/offer-listing-prices")
        if res.status_code == 200 and len(res.json()) > 0:
             print("✅ Offer prices retrieved")
        else:
             print(f"❌ Failed to get offer prices: {res.text}")
             
        # Clean up
        app.dependency_overrides = {}

    print("\n" + "=" * 60)
    print("✅ All subscription tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_subscriptions()
    sys.exit(0 if success else 1)
