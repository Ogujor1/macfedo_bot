import os
import sys
import django
import time
import argparse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'macfedo.settings')
sys.path.insert(0, '/home/macfedo_bot')
django.setup()

import requests
from django.conf import settings
from whatsapp.models import Customer, Broadcast

def send_template_message(phone, template_name, customer_name, product="", price=""):
    url = f"https://graph.facebook.com/v18.0/{settings.PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    # Build parameters based on what template expects
    parameters = [{"type": "text", "text": customer_name}]
    if product:
        parameters.append({"type": "text", "text": product})
    if price:
        parameters.append({"type": "text", "text": price})

    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": parameters
                }
            ]
        }
    }
    r = requests.post(url, headers=headers, json=data)
    return r.status_code == 200

parser = argparse.ArgumentParser()
parser.add_argument('--template', required=True)
parser.add_argument('--product', default='')
parser.add_argument('--price', default='')
parser.add_argument('--title', default='Broadcast')
parser.add_argument('--tag', default='all')
parser.add_argument('--image_url', default='')
args = parser.parse_args()

if args.tag == 'all':
    customers = Customer.objects.filter(is_active=True).exclude(tag='unreachable')
else:
    customers = Customer.objects.filter(is_active=True, tag=args.tag).exclude(tag='unreachable')

total = customers.count()
sent = 0
failed = 0

print(f"Starting broadcast to {total} customers...")

for i, customer in enumerate(customers, 1):
    name = customer.name if customer.name != customer.phone else 'Customer'
    success = send_template_message(
        customer.phone, args.template, name, args.product, args.price
    )
    if success:
        sent += 1
        print(f"[{i}/{total}] ✅ Sent to {customer.name}")
    else:
        failed += 1
        print(f"[{i}/{total}] ❌ Failed for {customer.phone}")
    time.sleep(0.3)

Broadcast.objects.create(
    title=args.title,
    template_name=args.template,
    message=f"Product: {args.product} | Price: {args.price}",
    sent_to=sent
)

print(f"\n✅ Done! Sent: {sent} | Failed: {failed}")
