"""
Test script for MB WAY payment integration
Run this after starting the server with: python manage.py runserver 8002
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8002"

# First, get a token (you'll need valid credentials)
print("=" * 60)
print("MB WAY PAYMENT INTEGRATION TEST")
print("=" * 60)

# Step 1: Login to get JWT token
print("\n1. Login to get authentication token...")
login_data = {
    "email": "professional@example.com",  # Replace with your professional email
    "password": "password123"  # Replace with actual password
}

try:
    response = requests.post(f"{BASE_URL}/api/user/login/", json=login_data)
    if response.status_code == 200:
        token = response.json().get('access')
        print(f"✓ Login successful! Token obtained.")
        headers = {"Authorization": f"Bearer {token}"}
    else:
        print(f"✗ Login failed: {response.status_code}")
        print(response.text)
        exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)

# Step 2: Get available packs
print("\n2. Fetching available packs...")
try:
    response = requests.get(f"{BASE_URL}/api/subscriptions/packs/", headers=headers)
    if response.status_code == 200:
        packs = response.json()
        if packs:
            print(f"✓ Found {len(packs)} pack(s):")
            for pack in packs:
                print(f"   - ID: {pack['id']}, Title: {pack['title']}, Price: €{pack['price']}, Hours: {pack['total_hours']}")
            pack_id = packs[0]['id']  # Use first pack for testing
        else:
            print("✗ No packs available")
            exit(1)
    else:
        print(f"✗ Failed to fetch packs: {response.status_code}")
        exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)

# Step 3: Test MultiBanco payment
print(f"\n3. Testing MULTIBANCO payment for pack ID {pack_id}...")
multibanco_data = {
    "payment_method": "multibanco"
}

try:
    response = requests.post(
        f"{BASE_URL}/api/subscriptions/packs/{pack_id}/subscribe/",
        json=multibanco_data,
        headers=headers
    )
    if response.status_code == 201:
        result = response.json()
        print("✓ MultiBanco payment created successfully!")
        print(f"   Entity: {result['payment_details']['entity']}")
        print(f"   Reference: {result['payment_details']['reference']}")
        print(f"   Amount: {result['payment_details']['amount']}")
        print(f"   Expiry: {result['payment_details']['expiry_date']}")
        multibanco_order_id = result['order']['id']
    else:
        print(f"✗ MultiBanco payment failed: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"✗ Error: {e}")

# Step 4: Test MB WAY payment
print(f"\n4. Testing MB WAY payment for pack ID {pack_id}...")
mbway_data = {
    "payment_method": "mbway",
    "phone_number": "351#912345678"  # Test phone number (sandbox mode)
}

try:
    response = requests.post(
        f"{BASE_URL}/api/subscriptions/packs/{pack_id}/subscribe/",
        json=mbway_data,
        headers=headers
    )
    if response.status_code == 201:
        result = response.json()
        print("✓ MB WAY payment created successfully!")
        print(f"   Phone: {result['payment_details']['phone_number']}")
        print(f"   Amount: {result['payment_details']['amount']}")
        print(f"   Status: {result['payment_details']['status']}")
        print(f"   Request ID: {result['payment_details']['request_id']}")
        print(f"   Timeout: {result['payment_details']['timeout']}")
        mbway_order_id = result['order']['id']
        
        # Step 5: Check MB WAY status
        print(f"\n5. Checking MB WAY payment status...")
        response = requests.get(
            f"{BASE_URL}/api/subscriptions/orders/{mbway_order_id}/check_mbway_status/",
            headers=headers
        )
        if response.status_code == 200:
            status_result = response.json()
            print("✓ Status check successful!")
            print(f"   Order ID: {status_result['order_id']}")
            print(f"   Payment Status: {status_result['payment_status']}")
            print(f"   MB WAY Status: {status_result['mbway_status']}")
            print(f"   Is Paid: {status_result['is_paid']}")
            print(f"   Is Rejected: {status_result['is_rejected']}")
            print(f"   Is Expired: {status_result['is_expired']}")
            print(f"   Message: {status_result['message']}")
        else:
            print(f"✗ Status check failed: {response.status_code}")
            print(response.text)
    else:
        print(f"✗ MB WAY payment failed: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"✗ Error: {e}")

# Step 6: Test invalid payment method
print(f"\n6. Testing invalid payment method (should fail)...")
invalid_data = {
    "payment_method": "invalid"
}

try:
    response = requests.post(
        f"{BASE_URL}/api/subscriptions/packs/{pack_id}/subscribe/",
        json=invalid_data,
        headers=headers
    )
    if response.status_code == 400:
        print("✓ Validation working correctly - invalid method rejected")
        print(f"   Error: {response.json().get('error')}")
    else:
        print(f"✗ Unexpected response: {response.status_code}")
except Exception as e:
    print(f"✗ Error: {e}")

# Step 7: Test MB WAY without phone number
print(f"\n7. Testing MB WAY without phone number (should fail)...")
invalid_mbway = {
    "payment_method": "mbway"
}

try:
    response = requests.post(
        f"{BASE_URL}/api/subscriptions/packs/{pack_id}/subscribe/",
        json=invalid_mbway,
        headers=headers
    )
    if response.status_code == 400:
        print("✓ Validation working correctly - missing phone number rejected")
        print(f"   Error: {response.json().get('error')}")
    else:
        print(f"✗ Unexpected response: {response.status_code}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("\nNOTE: In sandbox mode, you can simulate payment confirmation by:")
print("1. Using the callback URL manually")
print("2. Checking the terminal for email output")
print("3. Verifying order status in admin panel")
