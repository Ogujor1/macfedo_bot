#!/usr/bin/env python3
"""
Macfedo Bot — Abandoned Cart Checker
=====================================
Runs every 2 hours via cron. Detects customers who dropped off
mid-order and sends an instant alert to the agent.

SETUP (run once in PuTTY):
  crontab -e

Add this line:
  0 */2 * * * /home/macfedo_bot/venv/bin/python /home/macfedo_bot/abandoned_cart.py >> /home/macfedo_bot/abandoned.log 2>&1

Test manually:
  cd /home/macfedo_bot
  source venv/bin/activate
  python abandoned_cart.py
"""

import os
import sys
import django
import requests
from datetime import timedelta

sys.path.insert(0, "/home/macfedo_bot")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "macfedo_bot.settings")
django.setup()

from django.utils import timezone
from whatsapp.models import Customer, Conversation

AGENT_NUMBER    = "2348035796380"
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")

STEP_LABELS = {
    "await_catalogue_choice": "Viewing catalogue",
    "await_order_image":      "Choosing style",
    "await_size":             "Selecting size",
    "await_quantity":         "Selecting quantity",
    "await_material":         "Selecting material",
    "await_color":            "Selecting color",
    "await_delivery":         "Selecting delivery zone",
    "await_address":          "Providing address",
    "await_discount":         "Discount code step",
    "await_confirmation":     "Reviewing order summary",
    "await_payment":          "Awaiting payment proof",
}

ABANDONED_STEPS = list(STEP_LABELS.keys())


def send_whatsapp(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message, "preview_url": False},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"Alert sent to agent for customer {to}")
    except Exception as e:
        print(f"Failed to send alert: {e}")


def check_abandoned():
    now         = timezone.now()
    two_hrs_ago = now - timedelta(hours=2)
    one_day_ago = now - timedelta(hours=24)

    abandoned = Conversation.objects.filter(
        step__in=ABANDONED_STEPS,
        last_updated__lte=two_hrs_ago,
        last_updated__gte=one_day_ago,
        customer__is_active=True,
    ).select_related("customer")

    if not abandoned.exists():
        print("No abandoned carts found.")
        return

    count = abandoned.count()
    print(f"Found {count} abandoned cart(s). Sending alerts...")

    for conv in abandoned:
        customer = conv.customer
        ctx      = conv.context or {}
        name     = customer.name or "Unknown"
        step     = STEP_LABELS.get(conv.step, conv.step)
        size     = ctx.get("size", "Not provided")
        color    = ctx.get("color", "Not provided")
        material = ctx.get("material", "Not provided")
        qty      = ctx.get("quantity", "Not provided")
        last_seen = conv.last_updated.strftime("%d %b %Y, %I:%M %p")

        msg = (
            f"UNSUCCESSFUL ORDER ALERT\n\n"
            f"Name: {name}\n"
            f"Number: +{customer.phone}\n"
            f"Dropped off at: {step}\n"
            f"Last active: {last_seen}\n\n"
            f"ORDER DETAILS SO FAR\n"
            f"Size: {size}\n"
            f"Color: {color}\n"
            f"Material: {material}\n"
            f"Quantity: {qty}\n\n"
            f"Follow up: wa.me/{customer.phone}"
        )

        send_whatsapp(AGENT_NUMBER, msg)

        # Reset conversation so customer can start fresh if they return
        conv.step    = "start"
        conv.context = {}
        conv.save()

    print(f"Done. {count} alert(s) sent to agent.")


if __name__ == "__main__":
    check_abandoned()
