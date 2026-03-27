import os
import sys
import django
import argparse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'macfedo.settings')
sys.path.insert(0, '/home/macfedo_bot')
django.setup()

import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from whatsapp.models import Customer, Broadcast

def send_template(phone, template_name, name, product="", price=""):
    url = f"https://graph.facebook.com/v18.0/{settings.PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
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
                    "parameters": [
                        {"type": "text", "text": name},
                        {"type": "text", "text": product},
                        {"type": "text", "text": price}
                    ]
                }
            ]
        }
    }
    r = requests.post(url, headers=headers, json=data)
    return r.status_code == 200

parser = argparse.ArgumentParser()
parser.add_argument('--days', type=int, required=True, help='7, 14 or 28')
parser.add_argument('--template', required=True, help='Template name to use')
parser.add_argument('--product', default='Premium Footwear')
parser.add_argument('--price', default='36,999.99')
args = parser.parse_args()

now = timezone.now()
cutoff = now - timedelta(days=args.days)

if args.days == 7:
    # 7 days: unsubscribed customers
    customers = Customer.objects.exclude(tag='unreachable').filter(
        tag='unsubscribed',
        date_added__lte=cutoff
    )
    subject = "7-day re-engagement"
elif args.days == 14:
    # 14 days: inactive customers (no order in 14 days)
    from whatsapp.models import Order
    recent_buyers = Order.objects.filter(
        date_ordered__gte=cutoff
    ).values_list('customer_id', flat=True)
    customers = Customer.objects.exclude(tag='unreachable').filter(
        is_active=True,
        tag='customer'
    ).exclude(id__in=recent_buyers)
    subject = "14-day win-back"
elif args.days == 28:
    # 28 days: all inactive customers
    customers = Customer.objects.exclude(tag='unreachable').filter(
        is_active=True,
        date_added__lte=cutoff,
        tag__in=['customer', 'enquiry']
    )
    subject = "28-day re-engagement"

total = customers.count()
sent = 0
failed = 0

print(f"Sending {subject} to {total} customers...")

import time
for i, customer in enumerate(customers, 1):
    name = customer.name if customer.name != customer.phone else 'Customer'
    success = send_template(
        customer.phone, args.template, name, args.product, args.price
    )
    if success:
        sent += 1
        print(f"[{i}/{total}] ✅ {customer.name}")
    else:
        failed += 1
        print(f"[{i}/{total}] ❌ {customer.phone}")
    time.sleep(0.3)

Broadcast.objects.create(
    title=f"{subject} - {args.days} days",
    template_name=args.template,
    message=f"Re-engagement: {args.days} days | Product: {args.product}",
    sent_to=sent
)

print(f"\nDone! Sent: {sent} | Failed: {failed}")
