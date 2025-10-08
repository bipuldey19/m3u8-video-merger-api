#!/usr/bin/env python3
"""
Test script for Video Merger API
Usage: python test_api.py <API_URL>
Example: python test_api.py https://api.yourdomain.com
"""

import requests
import sys
import time
import json

def test_health(base_url):
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check passed:", response.json())
            return True
        else:
            print("❌ Health check failed:", response.status_code)
            return False
    except Exception as e:
        print("❌ Health check error:", str(e))
        return False

def test_merge(base_url):
    """Test video merge endpoint with sample data"""
    print("\n🎬 Testing video merge endpoint...")
    
    # Sample Reddit video data (use real URLs for actual testing)
    test_data = {
        "videos": [
            {
                "title": "Test Video 1 - Amazing Content",
                "author_fullname": "t2_test123",
                "secure_media": {
                    "reddit_video": {
                        "hls_url": "https://v.redd.it/example1/HLSPlaylist.m3u8"
                    }
                },
                "url": "https://v.redd.it/example1"
            },
            {
                "title": "Test Video 2 - More Great Content",
                "author_fullname": "t2_test456",
                "secure_media": {
                    "reddit_video": {
                        "hls_url": "https://v.redd.it/example2/HLSPlaylist.m3u8"
                    }
                },
                "url": "https://v.redd.it/example2"
            }
        ]
    }
    
    print("📤 Sending request with", len(test_data["videos"]), "videos...")
    print("⏳ This may take several minutes...")
    
    try:
        response = requests.post(
            f"{base_url}/merge",
            json=test_data,
            timeout=900  # 15 minutes timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Merge request successful!")
            print(json.dumps(result, indent=2))
            return result.get("output_file")
        else:
            print("❌ Merge request failed:", response.status_code)
            print(response.text)
            return None
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (processing took too long)")
        return None
    except Exception as e:
        print("❌ Merge request error:", str(e))
        return None

def test_download(base_url, filename):
    """Test video download endpoint"""
    if not filename:
        print("\n⚠️  No filename to download")
        return False
        
    print(f"\n⬇️  Testing download endpoint for: {filename}")
    
    try:
        response = requests.get(
            f"{base_url}/download/{filename}",
            timeout=300,
            stream=True
        )
        
        if response.status_code == 200:
            # Save file
            output_path = f"test_output_{filename}"
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✅ Download successful! Saved to: {output_path}")
            return True
        elif response.status_code == 404:
            print("❌ File not found (it may have been cleaned up)")
            return False
        else:
            print("❌ Download failed:", response.status_code)
            return False
            
    except Exception as e:
        print("❌ Download error:", str(e))
        return False

def test_invalid_input(base_url):
    """Test API with invalid input"""
    print("\n🧪 Testing error handling with invalid input...")
    
    test_cases = [
        {"name": "Empty videos list", "data": {"videos": []}},
        {"name": "Too many videos", "data": {"videos": [{"title": f"Video {i}"} for i in range(20)]}},
        {"name": "Missing required fields", "data": {"videos": [{"title": "Test"}]}},
    ]
    
    for test_case in test_cases:
        print(f"\n  Testing: {test_case['name']}")
        try:
            response = requests.post(
                f"{base_url}/merge",
                json=test_case['data'],
                timeout=10
            )
            
            if response.status_code >= 400:
                print(f"  ✅ Correctly rejected with status {response.status_code}")
            else:
                print(f"  ⚠️  Unexpected success (should have failed)")
                
        except Exception as e:
            print(f"  ❌ Error:", str(e))

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_api.py <API_URL>")
        print("Example: python test_api.py https://api.yourdomain.com")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    
    print("=" * 60)
    print("🚀 Video Merger API Test Suite")
    print("=" * 60)
    print(f"API URL: {base_url}\n")
    
    # Test 1: Health check
    if not test_health(base_url):
        print("\n❌ Health check failed. Stopping tests.")
        sys.exit(1)
    
    # Test 2: Invalid input (error handling)
    test_invalid_input(base_url)
    
    # Test 3: Video merge (comment out if you don't have real video URLs)
    print("\n" + "=" * 60)
    print("⚠️  IMPORTANT: The merge test requires valid video URLs")
    print("Replace the sample URLs in test_merge() with real URLs")
    print("=" * 60)
    
    proceed = input("\nProceed with merge test? (y/N): ")
    if proceed.lower() == 'y':
        output_file = test_merge(base_url)
        
        # Test 4: Download
        if output_file:
            time.sleep(2)  # Give server a moment
            test_download(base_url, output_file)
    
    print("\n" + "=" * 60)
    print("✨ Tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
