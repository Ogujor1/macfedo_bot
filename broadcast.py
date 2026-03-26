import os
import django
import sys
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'macfedo.settings')
sys.path.insert(0, '/home/macfedo_bot')
django.setup()

import requests
from django.conf import settings
from whatsapp.models import Customer, Broadcast

def send_broadcast(message, limit=None):
    customers = Customer.objects.filter(is_active=True)
    if limit:
        customers = customers[:limit]
    
    sent = 0
    failed = 0
    
    for customer in customers:
        try:
            url = f"https://graph.facebook.com/v18.0/{settings.PHONE_NUMBER_ID}/messages"
            headers = {
                "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
                "Content-Type": "application/json"
            }
            data = {
                "messaging_product": "whatsapp",
                "to": customer.phone,
                "type": "text",
                "text": {"body": message}
            }
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                sent += 1
                print(f"Sent to {customer.name} ({customer.phone})")
            else:
                failed += 1
                print(f"Failed for {customer.phone}: {response.json()}")
            time.sleep(0.5)
        except Exception as e:
            failed += 1
            print(f"Error for {customer.phone}: {e}")
    
    Broadcast.objects.create(
        title="Broadcast",
        message=message,
        sent_to=sent
    )
    
    print(f"\nDone! Sent: {sent} | Failed: {failed}")

message = """Hi! 👋

This is Macfedo Foot Wears Store.

We now have a NEW dedicated ordering line!

📱 Save this number for easy ordering:
+2348126975697

Simply send *Hi* to place your order for:
👟 Premium sandals
👞 Luxury slides
🥾 Quality footwear

We deliver across Nigeria! 🇳🇬

www.macfedowears.com"""

send_broadcast(message, limit=1)
