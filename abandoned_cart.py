import os
import sys
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'macfedo.settings')
sys.path.insert(0, '/home/macfedo_bot')
django.setup()

import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from whatsapp.models import Customer, Conversation, Order

def send_message(phone, message):
    url = f"https://graph.facebook.com/v18.0/{settings.PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    r = requests.post(url, headers=headers, json=data)
    return r.status_code == 200

def send_template(phone, template_name, name):
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
                    "parameters": [{"type": "text", "text": name}]
                }
            ]
        }
    }
    r = requests.post(url, headers=headers, json=data)
    return r.status_code == 200

now = timezone.now()
two_hours_ago = now - timedelta(hours=2)
twenty_four_hours_ago = now - timedelta(hours=24)

# Find abandoned carts — customers who:
# 1. Interacted with bot in last 24hrs
# 2. Have an incomplete conversation (not at start)
# 3. Have NO confirmed/pending order in last 24hrs
# 4. Are active customers

abandoned = []

conversations = Conversation.objects.filter(
    customer__is_active=True,
    customer__last_interaction__gte=twenty_four_hours_ago,
    customer__last_interaction__lte=two_hours_ago,
).exclude(
    step='start'
).exclude(
    step='waiting_image'
).select_related('customer')

for conv in conversations:
    customer = conv.customer
    # Skip if customer has a recent confirmed order
    recent_order = Order.objects.filter(
        customer=customer,
        status__in=['confirmed', 'shipped', 'delivered'],
        date_ordered__gte=twenty_four_hours_ago
    ).exists()
    if recent_order:
        continue
    # Skip if customer has sent payment proof (pending but recently updated)
    recent_pending = Order.objects.filter(
        customer=customer,
        status='pending',
        date_ordered__gte=two_hours_ago
    ).exists()
    if recent_pending:
        continue
    abandoned.append((customer, conv))

print(f"Found {len(abandoned)} abandoned carts")

sent = 0
for customer, conv in abandoned:
    name = customer.name if customer.name != customer.phone else 'there'
    step = conv.step

    # Customize message based on where they dropped off
    if step in ['get_size', 'get_quantity', 'get_material', 'get_color']:
        stage = "selecting your product details"
    elif step in ['get_delivery', 'get_address']:
        stage = "entering your delivery details"
    elif step in ['add_more', 'confirm', 'get_discount']:
        stage = "completing your order"
    else:
        stage = "placing your order"

    success = send_template(
        customer.phone,
        'macfedo_new_ordering_line',
        name
    )

    if success:
        sent += 1
        print(f"✅ Sent to {customer.name} (abandoned at: {step})")
        # Reset conversation so they start fresh
        conv.step = 'start'
        conv.context = {}
        conv.save()
    else:
        print(f"❌ Failed for {customer.phone}")
    time.sleep(0.5)

print(f"\nDone! Sent {sent} abandoned cart reminders")
