import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'macfedo.settings')
sys.path.insert(0, '/home/macfedo_bot')
django.setup()

import requests
from django.conf import settings

url = f"https://graph.facebook.com/v18.0/{settings.PHONE_NUMBER_ID}/messages"
headers = {
    "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    "Content-Type": "application/json"
}
data = {
    "messaging_product": "whatsapp",
    "to": "2348035796380",
    "type": "template",
    "template": {
        "name": "macfedo_new_ordering_line",
        "language": {"code": "en"},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "Michael"},
                ]
            }
        ]
    }
}
r = requests.post(url, headers=headers, json=data)
print(r.status_code)
print(r.json())
