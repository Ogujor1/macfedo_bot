import json
import re
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Customer, Order, Conversation, MessageLog
from django.utils import timezone

CATALOGUE_LINK = "https://drive.google.com/drive/folders/1FyE3JkmnMxduMJ9AmBXIGMOwaxfqVqcR"
SHOP_LINK = "https://macfedowears.com/shop"
AGENT_PHONE = "+234 803 579 6380"

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
    print(f"API: {r.status_code} - {r.json()}")
    return r.json()

def send_template(phone, template_name, components):
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
            "components": components
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"Template API: {r.status_code} - {r.json()}")
    return r.json()

def get_price(size):
    try:
        s = int(size)
    except:
        return "38,999.99"
    if s <= 35:
        return "25,999.99"
    elif s <= 38:
        return "37,000.00"
    elif s <= 45:
        return "38,999.99"
    else:
        return "43,999.99"

def get_delivery(text):
    t = text.lower()
    if 'lagos' in t:
        return ('Lagos', '3,999.99')
    elif 'international' in t or 'abroad' in t or 'outside' in t:
        return ('International', '24,999.99')
    else:
        return ('Other States', '4,999.99')

def calc_total(price, fee):
    try:
        return f"{float(price.replace(',','')) + float(fee.replace(',',''))  :,.2f}"
    except:
        return "0.00"

def parse_order_details(text):
    details = {}
    lines = text.strip().split('\n')
    for line in lines:
        line_lower = line.lower()
        if 'size' in line_lower:
            match = re.search(r'\d+', line)
            if match:
                details['size'] = match.group()
        elif 'leather' in line_lower:
            details['material'] = 'Leather'
        elif 'suede' in line_lower:
            details['material'] = 'Suede'
        elif 'nubuck' in line_lower:
            details['material'] = 'Nubuck'
        elif 'color' in line_lower or 'colour' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                details['color'] = parts[1].strip()
        elif 'address' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                details['address'] = parts[1].strip()
        elif 'delivery' in line_lower or 'location' in line_lower or 'lagos' in line_lower or 'international' in line_lower:
            if 'address' not in line_lower:
                details['location'] = line.split(':', 1)[-1].strip() if ':' in line else line.strip()
    return details

def get_missing(details):
    required = ['size', 'material', 'color', 'address', 'location']
    missing = []
    labels = {
        'size': 'Size (e.g. 40)',
        'material': 'Material (Leather / Suede / Nubuck)',
        'color': 'Color (e.g. Black, Brown)',
        'address': 'Address (Street, Area, City, State)',
        'location': 'Delivery (Lagos / Other State / International)'
    }
    for r in required:
        if r not in details or not details[r]:
            missing.append(labels[r])
    return missing

FAQS = (
    "❓ *FAQs — Macfedo Foot Wears*\n\n"
    "📦 *Delivery:*\n"
    "• Lagos: ₦3,999.99 (1-2 days)\n"
    "• Other states: ₦4,999.99 (2-5 days)\n"
    "• International: ₦24,999.99 (7-14 days)\n\n"
    "👟 *Prices:*\n"
    "• Kids size 27-35: ₦25,999.99\n"
    "• Women size 36-38: ₦37,000\n"
    "• Men/Unisex 39-45: ₦38,999.99\n"
    "• Men/Unisex 46-47: ₦43,999.99\n\n"
    "💳 *Payment:* Palmpay bank transfer\n"
    "🔄 *Returns:* 48hrs, unused condition\n"
    "📸 *Images:* Team confirms within 1hr\n\n"
    "Type *AGENT* for human help\n"
    "Type *Hi* to place an order"
)

def welcome(phone, name=None):
    greeting = f"Welcome back *{name}*!" if name else "Welcome to *Macfedo Foot Wears!*"
    return send_message(phone,
        f"👟 {greeting}\n\n"
        "Premium footwear — Halfshoes, Slippers, Sandals & more\n"
        "Materials: Leather | Suede | Nubuck\n\n"
        "Browse our products:\n"
        f"🖼️ {CATALOGUE_LINK}\n"
        f"🌐 {SHOP_LINK}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📸 *Send us an image of what you want!*\n\n"
        "_Type *FAQ* for help | *AGENT* to talk to us_"
    )

def process_message(phone, message, msg_type='text', image_id=None):
    msg = message.strip() if msg_type == 'text' else ''
    msg_lower = msg.lower()

    # Get or create customer
    customer, created = Customer.objects.get_or_create(
        phone=phone,
        defaults={'name': phone, 'phone': phone, 'tag': 'unknown'}
    )

    conv, _ = Conversation.objects.get_or_create(customer=customer)
    step = conv.step

    # GLOBAL COMMANDS
    if msg_type == 'text':
        if msg_lower == '00':
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                "Thank you for shopping with *Macfedo Foot Wears!* 👟\n"
                "Type *Hi* anytime to order again. 😊"
            )
        if msg_lower == 'stop':
            customer.is_active = False
            customer.tag = 'unsubscribed'
            customer.save()
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone, 'You have been unsubscribed from Macfedo broadcasts. You can still order anytime by sending Hi. To resubscribe reply START.')
        if msg_lower in ['start', 'hi', 'hello', 'hey'] and customer.tag == 'unsubscribed':
            customer.is_active = True
            customer.tag = 'customer'
            customer.save()
            return send_message(phone, 'Welcome back to Macfedo Foot Wears! You have been resubscribed. Type Hi to place an order.')
        if msg_lower == 'agent':
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                f"👤 *Talk to our team:*\n\n"
                f"📱 WhatsApp: {AGENT_PHONE}\n"
                "Hours: 9am - 8pm daily\n\n"
                "We respond within minutes!\n\n"
                "Type *Hi* to return to bot anytime."
            )
        if msg_lower == 'faq':
            return send_message(phone, FAQS)
        if msg_lower == '0':
            conv.step = 'waiting_image'
            conv.context = {}
            conv.save()
            return welcome(phone, customer.name if customer.name != phone else None)

    # NEW CUSTOMER - ASK FOR NAME
    if created or customer.name == phone or customer.name == 'Customer':
        if msg_type == 'text' and step != 'get_name':
            conv.step = 'get_name'
            conv.save()
            return send_message(phone,
                "👟 *Welcome to Macfedo Foot Wears!*\n\n"
                "Before we start, what's your *first name*? 😊"
            )

    # GET NAME
    if step == 'get_name':
        if msg_type == 'text' and len(msg) > 1:
            customer.name = msg.capitalize()
            customer.tag = 'customer'
            customer.save()
            conv.step = 'waiting_image'
            conv.context = {}
            conv.save()
            return send_message(phone,
                f"Nice to meet you *{customer.name}!* 🙏\n\n"
                "Browse our products:\n"
                f"🖼️ {CATALOGUE_LINK}\n"
                f"🌐 {SHOP_LINK}\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "📸 *Send us an image of what you want to order!*\n\n"
                "_Type *FAQ* for help | *AGENT* to talk to us_"
            )
        else:
            return send_message(phone,
                "Please tell me your first name so I can serve you better 😊"
            )

    # IMAGE RECEIVED
    if msg_type == 'image':
        conv.context['image_id'] = image_id or 'received'
        conv.step = 'get_details'
        conv.save()
        name = customer.name if customer.name != phone else ''
        greeting = f"{name}! " if name else ""
        return send_message(phone,
            f"📸 *Image received {greeting}*✅\n\n"
            "Our team confirms within *1 hour* if we produce this style.\n"
            "If not — full refund guaranteed! 💯\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Please send your order details *all at once*:\n\n"
            "Size: 40\n"
            "Material: Leather\n"
            "Color: Black\n"
            "Address: 5 Adeola St, Surulere, Lagos\n"
            "Delivery: Lagos\n\n"
            "_Materials: Leather / Suede / Nubuck_\n"
            "_Delivery: Lagos / Other State / International_\n\n"
            "_Type *AGENT* if you need help_"
        )

    # WAITING FOR IMAGE
    if step in ['start', 'waiting_image']:
        if msg_lower in ['hi', 'hello', 'hey', 'start']:
            conv.step = 'waiting_image'
            conv.context = {}
            conv.save()
            # Update tag if just enquiring
            if customer.tag == 'unknown':
                customer.tag = 'enquiry'
                customer.save()
            return welcome(phone, customer.name if customer.name != phone else None)
        elif msg_type == 'text':
            return send_message(phone,
                "📸 Please *send an image* of what you want to order.\n\n"
                f"Browse first: {CATALOGUE_LINK}\n\n"
                "_Type *AGENT* for help | *FAQ* for questions_"
            )

    # GET DETAILS
    elif step == 'get_details':
        details = parse_order_details(msg)
        missing = get_missing(details)
        if missing:
            missing_list = '\n'.join([f"• {m}" for m in missing])
            return send_message(phone,
                f"Almost there! Just need:\n\n"
                f"{missing_list}\n\n"
                "Send the missing info and I'll complete your order! 😊"
            )
        loc, fee = get_delivery(details.get('location', ''))
        price = get_price(details.get('size', '40'))
        total = calc_total(price, fee)

        # Update customer tag to customer
        customer.tag = 'customer'
        customer.last_product = details.get('material', '')
        customer.save()

        conv.context.update({
            'size': details['size'],
            'material': details['material'],
            'color': details['color'],
            'address': details['address'],
            'location': loc,
            'delivery_fee': fee,
            'price': price,
            'total': total
        })
        conv.step = 'confirm'
        conv.save()
        return send_message(phone,
            f"📋 *Order Summary:*\n\n"
            f"Size: {details['size']}\n"
            f"Material: {details['material']}\n"
            f"Color: {details['color']}\n"
            f"Address: {details['address']}\n"
            f"Delivery: {loc} — ₦{fee}\n"
            f"Product: ₦{price}\n"
            f"💳 *TOTAL: ₦{total}*\n\n"
            "Reply *YES* to confirm ✅\n"
            "Reply *NO* to cancel ❌\n"
            "Reply *EDIT* to change details"
        )

    elif step == 'confirm' and msg_lower == 'edit':
        conv.step = 'get_details'
        conv.save()
        return send_message(phone,
            "Send your corrected details:\n\n"
            "Size: \n"
            "Material: Leather / Suede / Nubuck\n"
            "Color: \n"
            "Address: \n"
            "Delivery: Lagos / Other State / International"
        )

    elif step == 'confirm':
        if msg_lower == 'yes':
            ctx = conv.context
            order = Order.objects.create(
                customer=customer,
                product="Custom order - image submitted",
                material=ctx.get('material', '').lower(),
                size=ctx.get('size', ''),
                color=ctx.get('color', ''),
                address=ctx.get('address', ''),
                status='pending',
                notes=f"Image: {ctx.get('image_id','N/A')} | {ctx.get('location','')} | Fee: {ctx.get('delivery_fee','')}"
            )
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                f"✅ *Order #{order.id} Confirmed!*\n\n"
                f"Size: {ctx['size']} | {ctx['material']} | {ctx['color']}\n"
                f"Delivery: {ctx['location']} — ₦{ctx['delivery_fee']}\n"
                f"Address: {ctx['address']}\n"
                f"💳 *Total: ₦{ctx['total']}*\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 *Pay now:*\n"
                f"Bank: Palmpay\n"
                f"Account: 8906621694\n"
                f"Name: Michael Ogujor\n"
                f"Amount: ₦{ctx['total']}\n\n"
                f"📸 *Send payment proof here after transfer*\n\n"
                f"🕒 We process within 1hr of payment!\n\n"
                f"Thank you *{customer.name}!* 🙏👟\n\n"
                f"_Type *Hi* to place another order_"
            )
        elif msg_lower == 'no':
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                "Order cancelled. 😊\n\nType *Hi* to start a new order."
            )
        else:
            return send_message(phone,
                "Please reply *YES* or *NO*.\n"
                "Reply *EDIT* to change details."
            )

    else:
        conv.step = 'start'
        conv.save()
        return welcome(phone, customer.name if customer.name != phone else None)


@csrf_exempt
def webhook(request):
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == settings.VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse('Forbidden', status=403)

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            entry = body['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            if 'messages' in value:
                msg_data = value['messages'][0]
                phone = msg_data['from']
                msg_type = msg_data['type']

                # Update customer name from WhatsApp profile
                if 'contacts' in value:
                    contact = value['contacts'][0]
                    wa_name = contact.get('profile', {}).get('name', '')
                    if wa_name:
                        customer, _ = Customer.objects.get_or_create(
                            phone=phone,
                            defaults={'name': wa_name, 'phone': phone}
                        )
                        if customer.name == phone or customer.name == 'Customer':
                            customer.name = wa_name
                            customer.save()

                if msg_type == 'text':
                    process_message(phone, msg_data['text']['body'], 'text')
                elif msg_type == 'image':
                    image_id = msg_data.get('image', {}).get('id', '')
                    process_message(phone, '', 'image', image_id)
        except Exception as e:
            print(f"Error: {e}")
        return JsonResponse({'status': 'ok'})
