#!/usr/bin/env python3
"""
Тестовый файл для проверки raw HTTP подхода из бота.
Реплицирует _get_items_raw_v2 и _extract_enriched_product_data_v2 с детальным логированием.
"""

import json
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv
import os

# Load env
load_dotenv()

# Amazon credentials
ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
REGION = "eu-west-1"
HOST = "webservices.amazon.it"

# HTTP session
_http_session = None

def get_http_session():
    """Get or create a reusable HTTP session with retry logic."""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
        )
        _http_session.mount("https://", adapter)
    return _http_session

def sign_aws4_request(host: str, region: str, access_key: str, secret_key: str, 
                     payload: str, service: str = "ProductAdvertisingAPI") -> Dict[str, str]:
    """Create AWS Signature Version 4 headers for PA-API requests."""
    method = "POST"
    uri = "/paapi5/getitems"
    
    t = datetime.now(timezone.utc)
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    headers = {
        'content-encoding': 'amz-1.0',
        'content-type': 'application/json; charset=utf-8',
        'host': host,
        'x-amz-date': amz_date,
        'x-amz-target': 'com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems'
    }
    
    signed_headers = ';'.join(sorted(headers.keys()))
    canonical_headers = ''.join([f"{k}:{v}\n" for k, v in sorted(headers.items())])
    payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    canonical_request = f"{method}\n{uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    
    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
    
    k_date = sign(('AWS4' + secret_key).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, 'aws4_request')
    
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    authorization = f"{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    headers['Authorization'] = authorization
    
    return headers

def get_items_raw_v2(asins: List[str]) -> List[Dict[str, Any]]:
    """Fetch items using raw HTTP with OffersV2 resources - EXACTLY as in bot."""
    if not asins:
        return []
    
    # OffersV2 resources (exactly as in bot)
    offersv2_resources = [
        "OffersV2.Listings.Price",
        "OffersV2.Listings.Availability",
        "OffersV2.Listings.Condition",
        "OffersV2.Listings.IsBuyBoxWinner",
        "OffersV2.Listings.MerchantInfo",
    ]
    
    # Other useful resources (exactly as in bot)
    other_resources = [
        "ItemInfo.Title",
        "ItemInfo.Features",
        "Images.Primary.Large",
        "Images.Variants.Large",
        "BrowseNodeInfo.WebsiteSalesRank",
        "CustomerReviews.Count",
        "CustomerReviews.StarRating",
        "ParentASIN",
    ]
    
    payload = {
        "ItemIds": asins[:10],
        "PartnerTag": ASSOCIATE_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.it",
        "Resources": other_resources + offersv2_resources
    }
    
    payload_json = json.dumps(payload)
    print(f"\n{'='*70}")
    print(f"[REQUEST] PAYLOAD:")
    print(f"{'='*70}")
    print(json.dumps(payload, indent=2))
    print(f"{'='*70}\n")
    
    try:
        headers = sign_aws4_request(
            host=HOST,
            region=REGION,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            payload=payload_json
        )
        
        url = f"https://{HOST}/paapi5/getitems"
        session = get_http_session()
        response = session.post(url, headers=headers, data=payload_json, timeout=15)
        
        print(f"📥 RESPONSE STATUS: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n{'='*70}")
            print(f"📦 RAW RESPONSE (first item, full structure):")
            print(f"{'='*70}")
            
            if "ItemsResult" in data and "Items" in data["ItemsResult"]:
                items = data["ItemsResult"]["Items"]
                print(f"Total items: {len(items)}\n")
                
                if items:
                    # Show full structure of first item
                    first_item = items[0]
                    print(json.dumps(first_item, indent=2, ensure_ascii=False)[:5000])
                    if len(json.dumps(first_item, indent=2)) > 5000:
                        print("\n... (truncated)")
                    
                    print(f"\n{'='*70}")
                    print(f"🔍 KEY ANALYSIS:")
                    print(f"{'='*70}")
                    print(f"Item keys: {list(first_item.keys())}")
                    
                    # Check OffersV2
                    if "OffersV2" in first_item:
                        print(f"\n✅ OffersV2 key exists")
                        offers_v2 = first_item["OffersV2"]
                        print(f"   OffersV2 type: {type(offers_v2)}")
                        print(f"   OffersV2 keys: {list(offers_v2.keys()) if isinstance(offers_v2, dict) else 'not a dict'}")
                        
                        if isinstance(offers_v2, dict) and "Listings" in offers_v2:
                            listings = offers_v2["Listings"]
                            print(f"   Listings type: {type(listings)}, length: {len(listings) if isinstance(listings, list) else 'not a list'}")
                            if isinstance(listings, list) and listings:
                                listing = listings[0]
                                print(f"   Listing keys: {list(listing.keys()) if isinstance(listing, dict) else 'not a dict'}")
                                if isinstance(listing, dict):
                                    if "Availability" in listing:
                                        availability = listing["Availability"]
                                        print(f"   ✅ Availability exists: {availability}")
                                    else:
                                        print(f"   ❌ Availability key NOT found in listing")
                    else:
                        print(f"\n❌ OffersV2 key NOT found")
                    
                    # Check Offers (V1 fallback)
                    if "Offers" in first_item:
                        print(f"\n✅ Offers (V1) key exists")
                        offers_v1 = first_item["Offers"]
                        print(f"   Offers type: {type(offers_v1)}")
                        print(f"   Offers keys: {list(offers_v1.keys()) if isinstance(offers_v1, dict) else 'not a dict'}")
                    else:
                        print(f"\n⚠️ Offers (V1) key NOT found")
                    
                    # Check lowercase offers
                    if "offers" in first_item:
                        print(f"\n✅ offers (lowercase) key exists")
                    else:
                        print(f"\n⚠️ offers (lowercase) key NOT found")
                
                return items
            return []
        else:
            error_data = response.json() if response.text else {}
            print(f"\n❌ API ERROR {response.status_code}:")
            print(json.dumps(error_data, indent=2))
            return []
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []

def extract_product_data_v2(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract product data - EXACTLY as in bot's _extract_enriched_product_data_v2."""
    try:
        asin = item.get('ASIN', '')
        if not asin:
            return None

        product_data = {
            'asin': asin,
            'parent_asin': item.get('ParentASIN'),
            'title': '',
            'price': None,
            'currency': 'EUR',
            'rating': None,
            'review_count': None,
            'sales_rank': None,
            'image_urls': [],
            'affiliate_link': item.get('DetailPageURL', ''),
            'features': [],
            'description': '',
            'is_buy_box_winner': None,
            'merchant_name': None,
            'availability_type': None,
        }

        # Extract title
        item_info = item.get('ItemInfo', {})
        if item_info.get('Title'):
            product_data['title'] = item_info['Title'].get('DisplayValue', '')

        # Extract features
        if item_info.get('Features'):
            features = item_info['Features'].get('DisplayValues', [])
            product_data['features'] = features
            product_data['description'] = ' '.join(features[:3]) if features else ''

        print(f"\n{'='*70}")
        print(f"🔍 EXTRACTING DATA FOR ASIN: {asin}")
        print(f"{'='*70}")

        # Extract from OffersV2 (exactly as in bot)
        offers_v2 = item.get('OffersV2', {})
        listings = offers_v2.get('Listings', [])
        print(f"OffersV2 exists: {bool(offers_v2)}")
        print(f"Listings exists: {bool(listings)}, type: {type(listings)}, length: {len(listings) if isinstance(listings, list) else 'N/A'}")
        
        if listings:
            listing = listings[0]
            print(f"Listing type: {type(listing)}")
            print(f"Listing keys: {list(listing.keys()) if isinstance(listing, dict) else 'N/A'}")
            
            # Buy Box Winner
            product_data['is_buy_box_winner'] = listing.get('IsBuyBoxWinner')
            print(f"IsBuyBoxWinner: {product_data['is_buy_box_winner']}")
            
            # Availability (THIS IS WHAT WE'RE LOOKING FOR)
            availability = listing.get('Availability', {})
            print(f"Availability object: {availability}")
            print(f"Availability type: {type(availability)}")
            if isinstance(availability, dict):
                print(f"Availability keys: {list(availability.keys())}")
            product_data['availability_type'] = availability.get('Type') if isinstance(availability, dict) else None
            print(f"Extracted availability_type: {product_data['availability_type']}")
            
            # Merchant Info
            merchant_info = listing.get('MerchantInfo', {})
            product_data['merchant_name'] = merchant_info.get('Name') if isinstance(merchant_info, dict) else None
            
            # Price
            price_obj = listing.get('Price', {})
            money = price_obj.get('Money', {}) if isinstance(price_obj, dict) else {}
            if money and money.get('Amount') is not None:
                product_data['price'] = float(money['Amount'])
                product_data['currency'] = money.get('Currency', 'EUR')

        # Fallback to V1 (exactly as in bot)
        if product_data['price'] is None or product_data['availability_type'] is None:
            print(f"\n⚠️ V2 didn't provide price/availability, trying V1 fallback...")
            offers_v1 = item.get('Offers', {}) or item.get('offers', {})
            print(f"V1 offers exists: {bool(offers_v1)}")
            
            if offers_v1:
                listings_v1 = offers_v1.get('Listings', []) or offers_v1.get('listings', [])
                print(f"V1 listings exists: {bool(listings_v1)}, length: {len(listings_v1) if isinstance(listings_v1, list) else 'N/A'}")
                
                if listings_v1:
                    listing_v1 = listings_v1[0]
                    print(f"V1 listing keys: {list(listing_v1.keys()) if isinstance(listing_v1, dict) else 'N/A'}")
                    
                    # Availability fallback
                    if product_data['availability_type'] is None:
                        availability_v1 = listing_v1.get('Availability', {}) or listing_v1.get('availability', {})
                        print(f"V1 availability object: {availability_v1}")
                        if isinstance(availability_v1, dict):
                            product_data['availability_type'] = availability_v1.get('Type') or availability_v1.get('type')
                            print(f"Extracted V1 availability_type: {product_data['availability_type']}")

        print(f"\n✅ FINAL RESULT:")
        print(f"   availability_type: {product_data['availability_type']}")
        print(f"   is_in_stock (type=='Now'): {product_data['availability_type'] == 'Now'}")
        
        return product_data

    except Exception as e:
        print(f"\n❌ EXTRACTION ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test with some ASINs
    test_asins = ["B096MXH3YD", "B07L3GBRB5"]  # Из логов бота
    
    print(f"\n{'='*70}")
    print(f"TESTING RAW HTTP APPROACH (as in bot)")
    print(f"{'='*70}")
    
    items = get_items_raw_v2(test_asins)
    
    if items:
        print(f"\n{'='*70}")
        print(f"🔍 TESTING EXTRACTION (as in bot)")
        print(f"{'='*70}")
        
        for item in items:
            product_data = extract_product_data_v2(item)
            if product_data:
                print(f"\n{'='*70}")
                print(f"✅ EXTRACTED PRODUCT DATA:")
                print(f"{'='*70}")
                print(json.dumps({k: v for k, v in product_data.items() if k != 'features'}, indent=2, ensure_ascii=False))
    else:
        print("\n❌ No items retrieved")

