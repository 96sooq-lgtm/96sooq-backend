import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from fastapi.testclient import TestClient
from main import app
from utils.storage import S3Client

def test_storage_api():
    print("=" * 60)
    print("Testing Storage API Integration")
    print("=" * 60)

    # Mock the S3 client where it is used in routes
    with patch("routes.storage.s3_client") as mock_s3:
        # Configure the mock
        mock_s3.generate_presigned_post.return_value = {
            "url": "https://s3.amazonaws.com/test-bucket",
            "fields": {"key": "value"}
        }
        mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/test.jpg?signature=xyz"

        client = TestClient(app)

        # Test 1: Generate Upload URL
        print("\n1. Testing Upload URL Generation...")
        upload_payload = {
            "file_name": "test_image.jpg",
            "file_type": "image/jpeg",
            "folder": "user_uploads"
        }
        
        response = client.post("/storage/presigned-url/upload", json=upload_payload)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Upload URL generated successfully")
            print(f"   Upload URL: {data['upload_url']['url']}")
            print(f"   File Path: {data['file_path']}")
            
            # Verify the mock was called correctly
            mock_s3.generate_presigned_post.assert_called()
        else:
            print(f"❌ Failed to generate upload URL: {response.text}")
            return False

        # Test 2: Generate View URL
        print("\n2. Testing View URL Generation...")
        view_path = "user_uploads/test_image.jpg"
        
        response = client.get(f"/storage/presigned-url/view?file_path={view_path}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ View URL generated successfully")
            print(f"   View URL: {data['url']}")
            
            # Verify the mock was called correctly
            mock_s3.generate_presigned_url.assert_called_with(view_path)
        else:
            print(f"❌ Failed to generate view URL: {response.text}")
            return False
            
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_storage_api()
    sys.exit(0 if success else 1)
