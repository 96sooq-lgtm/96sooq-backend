import requests
import json
import hashlib
import hmac
from config.settings import settings
from fastapi import HTTPException

class PaymobManager:
    """
    Helper class for Paymob Payment Gateway Integration (Intention API).
    Docs: https://developers.paymob.com/paymob-docs/developers/intention-apis/overview
    """
    
    # Base URL for Oman (from Paymob docs: https://oman.paymob.com/)
    BASE_URL = "https://oman.paymob.com"
    # Intention API path (from Paymob docs: POST /v1/intention)
    INTENTION_PATH = "/v1/intention"
    
    def __init__(self):
        self.secret_key = settings.paymob_secret_key
        # We might still need HMAC secret for webhooks
        self.hmac_secret = settings.paymob_hmac_secret
        self.public_key = settings.paymob_api_key # Public Key is often used for client-side, but good to have.
        self.integration_id = settings.paymob_integration_id # Might be needed for specific methods or Intention payload

        if not self.secret_key:
            print("WARNING: Paymob Secret Key is missing!")

    def create_intention(self, amount_cents: int, currency: str, merchant_order_id: str, billing_data: dict, items: list = []) -> str:
        """
        Create a Payment Intention.
        Returns the redirection URL for the Unified Checkout.
        """
        url = f"{self.BASE_URL}{self.INTENTION_PATH}"
        
        headers = {
            "Authorization": f"Token {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": amount_cents,
            "currency": currency,
            "payment_methods": [int(self.integration_id)] if self.integration_id else [],
            "items": [
                {
                    "name": item if isinstance(item, str) else item.get("name", "Service"),
                    "amount": item.get("amount", amount_cents // len(items)) if isinstance(item, dict) else amount_cents // len(items),
                    "description": item if isinstance(item, str) else item.get("description", ""),
                    "quantity": 1
                }
                for item in items
            ] if items else [],
            "billing_data": {
                "first_name": billing_data.get("first_name", "User"),
                "last_name": billing_data.get("last_name", "Customer"),
                "phone_number": billing_data.get("phone_number", "NA"),
                "email": billing_data.get("email", "NA"),
                "apartment": "NA",
                "floor": "NA",
                "street": "NA",
                "building": "NA",
                "shipping_method": "NA",
                "postal_code": "NA",
                "city": "NA",
                "country": "OM",
                "state": "NA"
            },
            "special_reference": merchant_order_id,
        }
        
        try:
            print(f"DEBUG: Creating Intention at {url} with payload keys: {list(payload.keys())}")
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # The intention creation returns a client_secret and keys.
            # For Unified Checkout, we usually redirect to a URL constructed with the client secret 
            # OR the response contains a 'next_action' or similar.
            # Let's check the response structure for Paymob Intention.
            # Usually: https://accept.paymob.com/unifiedcheckout/?publicKey={public_key}&clientSecret={client_secret}
            
            client_secret = data.get("client_secret")
            if not client_secret:
                print(f"ERROR: No client_secret in response: {data}")
                raise HTTPException(status_code=500, detail="Payment Gateway Error (No Client Secret)")
            
            # Construct redirection URL
            # Note: The domain for checkout might be standard Paymob or Paymob Solutions.
            # Safest is standard Paymob for checkout UI? Or Paymob Solutions?
            # Let's try standard first as per docs, or use the one from response if available.
            
            checkout_url = f"https://oman.paymob.com/unifiedcheckout/?publicKey={settings.paymob_public_key}&clientSecret={client_secret}"
            return checkout_url

        except requests.exceptions.RequestException as e:
            print(f"Paymob Intention Error: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Paymob Response: {e.response.text}")
            raise HTTPException(status_code=500, detail=f"Payment Gateway Error (Intention): {str(e)}")

    def verify_hmac(self, data: dict, hmac_received: str) -> bool:
        """
        Verify the HMAC signature of the webhook callback.
        Paymob sorts keys lexicographically and concatenates values of specific keys.
        """
        # Keys to extract in order (as per Paymob docs)
        keys = [
            "amount_cents", "created_at", "currency", "error_occured", "has_parent_transaction",
            "id", "integration_id", "is_3d_secure", "is_auth", "is_capture", "is_refunded",
            "is_standalone_payment", "is_voided", "order", "owner", "pending", 
            "source_data.pan", "source_data.sub_type", "source_data.type", "success"
        ]
        
        concatenated_string = ""
        for key in keys:
            # Handle nested keys
            if "." in key:
                parent, child = key.split(".")
                value = data.get("source_data", {}).get(child, "")
            else:
                value = data.get(key, "")
            
            if isinstance(value, bool):
                value = "true" if value else "false"
                
            concatenated_string += str(value)
            
        # Calculate HMAC
        calculated_hmac = hmac.new(
            self.hmac_secret.encode("utf-8"),
            concatenated_string.encode("utf-8"),
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(calculated_hmac, hmac_received)

paymob = PaymobManager()
