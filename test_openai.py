#!/usr/bin/env python3
"""
Test script to debug OpenAI client initialization.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import conf

def test_openai_init():
    """Test OpenAI client initialization."""
    print("Testing OpenAI client initialization...")

    # Check API key
    api_key = conf.llm.api_key
    if not api_key:
        print("❌ No API key found")
        return

    print(f"✅ API key found (length: {len(api_key)})")
    print(f"Model: {conf.llm.model}")

    # Check environment variables
    proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'OPENAI_API_KEY']
    print("\nEnvironment variables:")
    for var in proxy_vars:
        value = os.environ.get(var, 'NOT SET')
        if 'proxy' in var.lower():
            print(f"  {var}: {value}")
        else:
            print(f"  {var}: {'SET' if value else 'NOT SET'}")

    # Try direct requests approach
    print("\nTesting OpenAI with direct requests...")

    try:
        import requests

        # Test direct API call
        session = requests.Session()
        session.proxies = {}
        session.trust_env = False

        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello, test message"}],
            "max_tokens": 10
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        response = session.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30
        )

        print(f"✅ HTTP Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ OpenAI API call successful")
            print(f"Response: {result['choices'][0]['message']['content']}")
        else:
            print(f"❌ API call failed: {response.text}")

    except Exception as e:
        print(f"❌ Direct requests test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_openai_init()
