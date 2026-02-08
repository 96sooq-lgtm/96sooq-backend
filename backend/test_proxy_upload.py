import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from io import BytesIO

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from fastapi.testclient import TestClient
from main import app
from utils.storage import S3Client

def test_proxy_upload():
    print("=" * 60)
    print("Testing Proxy Upload API Integration")
    print("=" * 60)

    # Mock the S3 client where it is used in routes
    with patch("routes.storage.s3_client") as mock_s3:
        # Mock upload_file return value
        mock_s3.upload_file.return_value = "https://your-cloudfront.net/uploads/test.jpg"

        client = TestClient(app)

        # Test 1: Proxy Upload
        print("\n1. Testing Proxy Upload...")
        
        # Create a dummy file
        file_content = b"fake image content"
        files = {
            "file": ("test.jpg", BytesIO(file_content), "image/jpeg")
        }
        
        response = client.post("/storage/upload", files=files)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Proxy Upload successful")
            print(f"   URL: {data['url']}")
            print(f"   File Path: {data['file_path']}")
            
            # Verify the mock was called correctly
            mock_s3.upload_file.assert_called()
        else:
            print(f"❌ Failed to upload file: {response.text}")
            return False
            
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_proxy_upload()
    sys.exit(0 if success else 1)
