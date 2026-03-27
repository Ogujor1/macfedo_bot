import json
import re
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from .models import Customer, Order, Conversation, MessageLog

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

def calc_total(price, fee):
    try:
        return f"{float(price.replace(',','')) + float(fee.replace(',',''))  :,.2f}"
    except:
        return "0.00"

def welcome(phone, name=None):
    greeting = f"Welcome back *{name}!*" if name and name != phone else "Welcome to *Macfedo Foot Wears!*"
    return send_message(phone,
        f"👟 {greeting}\n\n"
        "Premium footwear — Halfshoes, Slippers, Sandals & more\n"
        "Materials: Leather | Suede | Nubuck\n\n"
        "Browse our products:\n"
        f"🖼️ {CATALOGUE_LINK}\n"
        f"🌐 {SHOP_LINK}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📸 *Send us an image of what you want to order!*\n\n"
        "_Type *FAQ* for help | *AGENT* to talk to us_"
    )

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

def process_message(phone, message, msg_type='text', image_id=None, image_url=''):
    msg = message.strip() if msg_type == 'text' else ''
    msg_lower = msg.lower()

    # Get or create customer
    customer, created = Customer.objects.get_or_create(
        phone=phone,
        defaults={'name': phone, 'phone': phone, 'tag': 'unknown'}
    )

    conv, _ = Conversation.objects.get_or_create(customer=customer)
    step = conv.step

    # GLOBAL COMMANDS - always available
    if msg_type == 'text':
        if msg_lower == '00':
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                "Thank you for shopping with *Macfedo Foot Wears!* 👟\n"
                "Type *Hi* anytime to order again. 😊"
            )

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

        if msg_lower == 'stop':
            customer.is_active = False
            customer.tag = 'unsubscribed'
            customer.save()
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                "You have been unsubscribed from Macfedo broadcasts.\n\n"
                "You can still order anytime by sending Hi.\n"
                "To resubscribe just send Hi again."
            )

        # Hi always resubscribes and welcomes
        if msg_lower in ['hi', 'hello', 'hey', 'start', '0']:
            # Resubscribe if unsubscribed
            if customer.tag == 'unsubscribed' or not customer.is_active:
                customer.tag = 'customer'
                customer.is_active = True
                customer.save()
            conv.step = 'waiting_image'
            conv.context = {}
            conv.save()
            # Ask for name if new customer
            if created or customer.name == phone:
                conv.step = 'get_name'
                conv.save()
                return send_message(phone,
                    "👟 *Welcome to Macfedo Foot Wears!*\n\n"
                    "What's your *first name*? 😊"
                )
            return welcome(phone, customer.name)

    # GET NAME
    if step == 'get_name':
        if msg_type == 'text' and len(msg) > 1:
            customer.name = msg.strip().capitalize()
            customer.tag = 'customer'
            customer.is_active = True
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
        return send_message(phone, "Please tell me your first name 😊")

    # IMAGE RECEIVED
    if msg_type == 'image':
        # Check if this is a payment proof (customer has pending order)
        pending_orders = Order.objects.filter(customer=customer, status='pending').order_by('-date_ordered')
        if step == 'start' and pending_orders.exists():
            # Save payment proof to most recent pending order
            order = pending_orders.first()
            order.notes = order.notes + f" | Payment proof: {image_url}"
            order.status = 'confirmed'
            order.save()
            return send_message(phone,
                "✅ *Payment proof received!*\n\n"
                f"Order #{order.id} is now being processed.\n\n"
                "🕒 Our team will verify and process within *1 hour*.\n\n"
                "We'll notify you once your order is on its way! 🚚\n\n"
                "_Type *Hi* to place another order_"
            )

        conv.context['image_id'] = image_id or 'received'
        conv.context['image_url'] = image_url or ''
        conv.step = 'get_size'
        conv.save()
        name = customer.name if customer.name != phone else ''
        greeting = f"{name}! " if name else ""
        return send_message(phone,
            f"📸 *Image received {greeting}*✅\n\n"
            "Our team confirms within *1 hour* if we produce this style.\n"
            "If not — full refund guaranteed! 💯\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "What *size* do you need?\n"
            "_(e.g. 36, 38, 40, 42, 44, 46)_\n\n"
            "_Type *0* to restart | *AGENT* for help_"
        )

    # WAITING FOR IMAGE
    if step in ['start', 'waiting_image']:
        return send_message(phone,
            "📸 Please *send an image* of what you want to order.\n\n"
            f"Browse first: {CATALOGUE_LINK}\n\n"
            "_Type *AGENT* for help | *FAQ* for questions_"
        )

    # GET SIZE
    elif step == 'get_size':
        size_match = re.search(r'\b(2[7-9]|3[0-9]|4[0-7])\b', msg)
        if not size_match:
            return send_message(phone,
                "Please enter a valid size.\n"
                "_(e.g. 36, 38, 40, 42, 44, 46)_"
            )
        size = size_match.group()
        price = get_price(size)
        conv.context['size'] = size
        conv.context['price'] = price
        conv.step = 'get_material'
        conv.save()
        return send_message(phone,
            f"Size *{size}* ✅  |  Price: *₦{price}*\n\n"
            "What *material* do you prefer?\n\n"
            "1️⃣ Leather\n"
            "2️⃣ Suede\n"
            "3️⃣ Nubuck"
        )

    # GET MATERIAL
    elif step == 'get_material':
        m = {
            '1': 'Leather', '2': 'Suede', '3': 'Nubuck',
            'leather': 'Leather', 'suede': 'Suede', 'nubuck': 'Nubuck'
        }
        material = m.get(msg_lower)
        if not material:
            return send_message(phone,
                "Please reply:\n1 for Leather\n2 for Suede\n3 for Nubuck"
            )
        conv.context['material'] = material
        conv.step = 'get_color'
        conv.save()
        return send_message(phone,
            f"*{material}* ✅\n\n"
            "What *color* do you prefer?\n"
            "_(e.g. Black, Brown, Tan, White, Nude, Burgundy)_"
        )

    # GET COLOR
    elif step == 'get_color':
        conv.context['color'] = msg.strip().capitalize()
        conv.step = 'get_delivery'
        conv.save()
        return send_message(phone,
            f"*{msg.strip().capitalize()}* ✅\n\n"
            "🚚 *Delivery location?*\n\n"
            "1️⃣ Lagos — ₦3,999.99\n"
            "2️⃣ Other Nigerian States — ₦4,999.99\n"
            "3️⃣ International — ₦24,999.99"
        )

    # GET DELIVERY
    elif step == 'get_delivery':
        delivery_map = {
            '1': ('Lagos', '3,999.99'),
            '2': ('Other States', '4,999.99'),
            '3': ('International', '24,999.99'),
            'lagos': ('Lagos', '3,999.99'),
            'international': ('International', '24,999.99'),
        }
        loc_data = delivery_map.get(msg_lower)
        if not loc_data:
            if any(x in msg_lower for x in ['abuja', 'ph', 'port harcourt', 'kano', 'ibadan', 'enugu', 'warri', 'other', 'state', 'delta', 'anambra', 'rivers', 'ogun']):
                loc_data = ('Other States', '4,999.99')
            else:
                return send_message(phone,
                    "Please reply:\n1 for Lagos\n2 for Other States\n3 for International"
                )
        loc, fee = loc_data
        conv.context['location'] = loc
        conv.context['delivery_fee'] = fee
        conv.step = 'get_address'
        conv.save()
        return send_message(phone,
            f"*{loc}* ✅  |  Fee: ₦{fee}\n\n"
            "📍 *Full delivery address?*\n"
            "_(Street, Area, City, State)_"
        )

    # GET ADDRESS
    elif step == 'get_address':
        conv.context['address'] = msg.strip()
        # Save first item to items list
        items = conv.context.get('items', [])
        items.append({
            'image_id': conv.context.get('image_id', 'N/A'),
            'image_url': conv.context.get('image_url', ''),
            'size': conv.context.get('size', ''),
            'material': conv.context.get('material', ''),
            'color': conv.context.get('color', ''),
            'price': conv.context.get('price', ''),
        })
        conv.context['items'] = items
        conv.step = 'add_more'
        conv.save()
        return send_message(phone,
            f"Address noted! ✅\n\n"
            f"You have *{len(items)} item(s)* in your cart.\n\n"
            "Would you like to add another pair?\n\n"
            "1️⃣ Yes - add another pair\n"
            "2️⃣ No - proceed to payment\n"
            "3️⃣ I need 5+ pairs - talk to agent\n\n"
            "_Reply *0* to restart_"
        )

    # ADD MORE ITEMS
    elif step == 'add_more':
        if msg_lower == '1':
            items = conv.context.get('items', [])
            if len(items) >= 4:
                return send_message(phone,
                    f"You already have *{len(items)} pairs* in your cart.\n\n"
                    "For 5+ pairs, our agent will assist you personally:\n\n"
                    f"📱 WhatsApp: {AGENT_PHONE}\n"
                    "Hours: 9am - 8pm daily\n\n"
                    "Or reply *2* to proceed with your current order."
                )
            conv.step = 'get_size'
            conv.context['image_id'] = 'new_item'
            conv.save()
            return send_message(phone,
                f"Adding item {len(items) + 1}! 👟\n\n"
                "📸 Send an image of the next pair you want.\n\n"
                f"Browse: {CATALOGUE_LINK}"
            )
        elif msg_lower == '2':
            conv.step = 'confirm'
            conv.save()
            ctx = conv.context
            items = ctx.get('items', [])
            # Calculate subtotal
            subtotal = sum(float(i['price'].replace(',','')) for i in items)
            fee = float(ctx.get('delivery_fee', '0').replace(',',''))
            total = f"{subtotal + fee:,.2f}"
            conv.context['total'] = total
            conv.save()
            # Build items summary
            summary = ""
            for i, item in enumerate(items, 1):
                summary += f"*Item {i}:* Size {item['size']} | {item['material']} | {item['color']} | ₦{item['price']}\n"
            return send_message(phone,
                f"📋 *Order Summary:*\n\n"
                f"{summary}\n"
                f"Delivery: {ctx['location']} — ₦{ctx['delivery_fee']}\n"
                f"Address: {ctx['address']}\n"
                f"💳 *TOTAL: ₦{total}*\n\n"
                "Reply *YES* to confirm ✅\n"
                "Reply *NO* to cancel ❌\n"
                "Reply *EDIT* to change details"
            )
        elif msg_lower == '3':
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                "👤 *For 5+ pairs, our agent will assist you:*\n\n"
                f"📱 WhatsApp: {AGENT_PHONE}\n"
                "Hours: 9am - 8pm daily\n\n"
                "Our team responds within minutes!\n\n"
                "Type *Hi* to return to bot anytime."
            )
        else:
            return send_message(phone,
                "Please reply:\n1 to add another pair\n2 to proceed to payment\n3 for 5+ pairs"
            )

    # EDIT
    elif step == 'confirm' and msg_lower == 'edit':
        conv.step = 'get_size'
        conv.save()
        return send_message(phone,
            "No problem! Let's update your order.\n\n"
            "What *size* do you need?\n"
            "_(e.g. 36, 38, 40, 42, 44, 46)_"
        )

    # CONFIRM ORDER
    elif step == 'confirm':
        if msg_lower == 'yes':
            ctx = conv.context
            items = ctx.get('items', [])
            customer.tag = 'customer'
            customer.save()
            order_ids = []
            for item in items:
                order = Order.objects.create(
                    customer=customer,
                    product="Custom order - image submitted",
                    material=item.get('material', '').lower(),
                    size=item.get('size', ''),
                    color=item.get('color', ''),
                    address=ctx.get('address', ''),
                    status='pending',
                    image_url=item.get('image_url', ''),
                    notes=f"Image: {item.get('image_id','N/A')} | {ctx.get('location','')} | Fee: {ctx.get('delivery_fee','')}"
                )
                order_ids.append(str(order.id))
            conv.step = 'start'
            conv.context = {}
            conv.save()
            name = customer.name if customer.name != phone else ''
            ids = ', '.join([f'#{i}' for i in order_ids])
            summary = ""
            for i, item in enumerate(items, 1):
                summary += f"Item {i}: Size {item['size']} | {item['material']} | {item['color']}\n"
            return send_message(phone,
                f"✅ *Order Confirmed!*\n\n"
                f"Order ID(s): *{ids}*\n\n"
                f"{summary}\n"
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
                f"Thank you{' ' + name if name else ''}! 🙏👟\n\n"
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
                "Reply *EDIT* to change your details."
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

                # Auto-capture name from WhatsApp profile
                if 'contacts' in value:
                    contact = value['contacts'][0]
                    wa_name = contact.get('profile', {}).get('name', '')
                    if wa_name:
                        customer, _ = Customer.objects.get_or_create(
                            phone=phone,
                            defaults={'name': wa_name, 'phone': phone, 'tag': 'unknown'}
                        )
                        if customer.name == phone or customer.name == 'Customer':
                            customer.name = wa_name
                            customer.save()

                if msg_type == 'text':
                    process_message(phone, msg_data['text']['body'], 'text')
                elif msg_type == 'image':
                    image_data = msg_data.get('image', {})
                    image_id = image_data.get('id', '')
                    # Fetch actual image URL from Meta API
                    try:
                        img_response = requests.get(
                            f"https://graph.facebook.com/v18.0/{image_id}",
                            headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}
                        )
                        img_json = img_response.json()
                        image_url = img_json.get('url', '')
                    except:
                        image_url = ''
                    process_message(phone, '', 'image', image_id, image_url)

            if 'statuses' in value:
                for status_data in value['statuses']:
                    msg_id = status_data.get('id', '')
                    status = status_data.get('status', '')
                    phone = status_data.get('recipient_id', '')
                    try:
                        customer = Customer.objects.get(phone=phone)
                        log = MessageLog.objects.filter(
                            customer=customer,
                            message_id=msg_id
                        ).first()
                        if log:
                            if status == 'delivered':
                                log.status = 'delivered'
                                log.delivered_at = timezone.now()
                            elif status == 'read':
                                log.status = 'read'
                                log.read_at = timezone.now()
                            elif status == 'failed':
                                log.status = 'failed'
                            log.save()
                    except Customer.DoesNotExist:
                        pass

        except Exception as e:
            print(f"Error: {e}")
        return JsonResponse({'status': 'ok'})
