#!/usr/bin/env python3
"""
Test Supabase connection
Run this script to verify your Supabase setup is correct
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from config.settings import settings
from db.supabase_client import db

def test_connection():
    """Test Supabase connection"""
    print("=" * 60)
    print("Testing Supabase Connection")
    print("=" * 60)
    
    # Check environment variables
    print("\n1. Checking Environment Variables...")
    if not settings.supabase_url:
        print("❌ SUPABASE_URL not set in .env")
        return False
    if not settings.supabase_key:
        print("❌ SUPABASE_KEY not set in .env")
        return False
    
    print(f"✅ SUPABASE_URL: {settings.supabase_url[:50]}...")
    print(f"✅ SUPABASE_KEY: {settings.supabase_key[:50]}...")
    
    # Try to connect
    print("\n2. Connecting to Supabase...")
    try:
        client = db.get_client()
        print("✅ Client created successfully")
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        return False
    
    # Try to query
    print("\n3. Testing database query...")
    try:
        result = db.select("users")
        print(f"✅ Successfully queried 'users' table")
        print(f"   Found {len(result)} users")
    except Exception as e:
        print(f"❌ Query failed: {e}")
        print("\n   Note: Table might not exist yet.")
        print("   Run the SQL commands from SUPABASE_SETUP_GUIDE.md")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! Supabase is properly configured.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
