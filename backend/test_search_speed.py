import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_search_speed():
    # Searching for a specific word instead of 'T' which matches almost everything
    url_t = f"/api/listings/?search=T"
    url_specific = f"/api/listings/?search=iphone"
    
    print(f"Testing GET {url_t}")
    start = time.time()
    res1 = client.get(url_t)
    end = time.time()
    
    print(f"Status: {res1.status_code}")
    print(f"Time taken (T): {end - start:.4f} seconds")
    print(f"Results matched: {len(res1.json())}")
    
    print(f"\nTesting GET {url_specific}")
    start2 = time.time()
    res2 = client.get(url_specific)
    end2 = time.time()
    
    print(f"Status: {res2.status_code}")
    print(f"Time taken (Specific): {end2 - start2:.4f} seconds")
    print(f"Results matched: {len(res2.json()) if res2.status_code == 200 else 0}")
    
if __name__ == "__main__":
    test_search_speed()
