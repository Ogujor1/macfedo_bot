import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'macfedo.settings')

import sys
sys.path.insert(0, '/home/macfedo_bot')
django.setup()

import csv
from whatsapp.models import Customer

count = 0
skipped = 0

with open('/home/macfedo_bot/customers_clean.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        phone = str(row.get('Phone', '')).strip()
        name = str(row.get('Name', 'Customer')).strip()
        
        if not phone or len(phone) < 10:
            skipped += 1
            continue
            
        customer, created = Customer.objects.get_or_create(
            phone=phone,
            defaults={'name': name, 'tag': 'customer'}
        )
        if created:
            count += 1
        else:
            skipped += 1

print(f"Imported: {count} new customers")
print(f"Skipped: {skipped} (duplicates or invalid)")
print(f"Total in database: {Customer.objects.count()}")
