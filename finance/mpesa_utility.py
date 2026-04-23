# finance/mpesa_utility.py

import requests
import base64
import datetime
from .mpesa_credentials import CONSUMER_KEY, CONSUMER_SECRET, PASSKEY, SHORTCODE, CALLBACK_URL


def get_access_token():
    """Get OAuth access token from Safaricom"""
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    credentials = f"{CONSUMER_KEY}:{CONSUMER_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {'Authorization': f'Basic {encoded_credentials}'}
    
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"Error getting token: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None


def stk_push(phone_number, amount, reg_number, transaction_desc):
    """
    Send STK push to customer's phone
    """
    access_token = get_access_token()
    if not access_token:
        return {"error": "Failed to get access token", "ResponseCode": "1"}
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    # FIXED: Use PASSKEY, not PASSWORD
    password = base64.b64encode(f"{SHORTCODE}{PASSKEY}{timestamp}".encode()).decode()
    
    # Format phone number (ensure it starts with 254)
    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif phone_number.startswith('+'):
        phone_number = phone_number[1:]
    
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(float(amount)),
        "PartyA": phone_number,
        "PartyB": SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": reg_number,
        "TransactionDesc": transaction_desc[:50]
    }
    
    # FIXED: Actually send the request
    try:
        response = requests.post(api_url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        print(f"STK Push error: {e}")
        return {"error": str(e), "ResponseCode": "1"}