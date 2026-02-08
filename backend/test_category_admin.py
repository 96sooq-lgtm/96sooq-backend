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

def test_category_admin_create():
    print("=" * 60)
    print("Testing Category Admin API (Manual Names)")
    print("=" * 60)

    # Mock DB interactions
    with patch("routes.categories.db") as mock_db:
        
        # Override the dependency
        app.dependency_overrides[get_current_admin] = lambda: {"id": "admin123", "role": "admin"}
        
        # Mock Insert
        mock_db.insert.return_value = {
            "id": "cat-123", 
            "name_en": "Cars", 
            "name_ar": "سيارات",
            "is_active": True
        }
        
        # Mock Select (for existence check)
        mock_db.select.return_value = [] 
        
        client = TestClient(app)

        # Test 1: Create Category with Manual Names
        print("\n1. Testing Create Category...")
        payload = {
            "name_en": "Cars",
            "name_ar": "سيارات",
            "image_url": "http://example.com/car.png",
            "is_active": True
        }
        
        response = client.post("/api/admin/categories/", json=payload)
        
        if response.status_code == 201:
            data = response.json()
            print("✅ Category created successfully")
            print(f"   Name EN: {data['name_en']}")
            print(f"   Name AR: {data['name_ar']}")
            
            # Verify mock call arguments
            args, _ = mock_db.insert.call_args
            inserted_data = args[1]
            if inserted_data["name_en"] == "Cars" and inserted_data["name_ar"] == "سيارات":
                 print("✅ Validated insertion data correct")
            else:
                 print(f"❌ Insertion data mismatch: {inserted_data}")
        else:
            print(f"❌ Failed to create category: {response.text}")
            return False

        # Test 2: Update Category with Manual Names
        print("\n2. Testing Update Category...")
        mock_db.select_one.return_value = {"id": "cat-123", "name_en": "Cars", "name_ar": "سيارات"}
        mock_db.update.return_value = {"id": "cat-123", "name_en": "Vehicles", "name_ar": "مركبات", "is_active": True}
        
        update_payload = {
            "name_en": "Vehicles",
            "name_ar": "مركبات"
        }
        
        response = client.put("/api/admin/categories/cat-123", json=update_payload)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Category updated successfully")
            print(f"   Name EN: {data['name_en']}")
            print(f"   Name AR: {data['name_ar']}")
        else:
             print(f"❌ Failed to update category: {response.text}")
             return False
        
        # Clean up
        app.dependency_overrides = {}
            
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_category_admin_create()
    sys.exit(0 if success else 1)
