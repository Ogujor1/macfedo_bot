import json
import re
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from .models import Customer, Order, Conversation, MessageLog, DiscountCode, DiscountUsage
from .utils import download_and_save_image
from django.conf import settings as django_settings

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

def calc_total(price, fee, quantity=1):
    try:
        return f"{(float(price.replace(',','')) * quantity) + float(fee.replace(',',''))  :,.2f}"
    except:
        return "0.00"

def calc_items_total(items, delivery_fee):
    try:
        subtotal = sum(float(i['price'].replace(',','')) * int(i.get('quantity', 1)) for i in items)
        return f"{subtotal + float(delivery_fee.replace(',',''))  :,.2f}"
    except:
        return "0.00"

def validate_discount(code_str, customer):
    from datetime import date
    try:
        code = DiscountCode.objects.get(code=code_str.upper(), is_active=True)
        # Check expiry
        if date.today() > code.expiry_date:
            return None, 'Sorry, this code has expired.'
        # Check customer usage
        uses = DiscountUsage.objects.filter(customer=customer, code=code).count()
        if uses >= code.max_uses_per_customer:
            return None, f'You have already used this code {uses} time(s). Maximum is {code.max_uses_per_customer}.'
        return code, 'valid'
    except DiscountCode.DoesNotExist:
        return None, 'Invalid discount code. Please check and try again.'

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

    customer, created = Customer.objects.get_or_create(
        phone=phone,
        defaults={'name': phone, 'phone': phone, 'tag': 'unknown'}
    )

    conv, _ = Conversation.objects.get_or_create(customer=customer)
    step = conv.step

    # Track last interaction
    customer.last_interaction = timezone.now()
    customer.save(update_fields=['last_interaction'])

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

        if msg_lower in ['hi', 'hello', 'hey', 'start', '0']:
            if customer.tag == 'unsubscribed' or not customer.is_active:
                customer.tag = 'customer'
                customer.is_active = True
                customer.save()
            conv.step = 'waiting_image'
            conv.context = {}
            conv.save()
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
        # Check if payment proof (pending order exists and step is start)
        pending_orders = Order.objects.filter(
            customer=customer, status='pending'
        ).order_by('-date_ordered')

        if step == 'start' and pending_orders.exists():
            order = pending_orders.first()
            local_url = download_and_save_image(image_id, settings.WHATSAPP_TOKEN, 'payment_proofs')
            payment_url = local_url or ''
            order.notes = (order.notes or '') + f" | Payment: {payment_url}"
            order.image_url = order.image_url  # keep product image
            order.status = 'confirmed'
            order.save()
            # Save payment proof URL in notes for admin display
            print(f"Payment proof saved: {payment_url}")
            return send_message(phone,
                "✅ *Payment proof received!*\n\n"
                f"Order #{order.id} is now confirmed.\n\n"
                "🕒 Our team will verify and process within *1 hour*.\n\n"
                "We'll notify you once your order is on its way! 🚚\n\n"
                "_Type *Hi* to place another order_"
            )

        # Download and save order image
        local_url = download_and_save_image(image_id, settings.WHATSAPP_TOKEN, 'order_images')
        conv.context['image_id'] = image_id or 'received'
        conv.context['image_url'] = local_url or image_url or ''
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
        conv.step = 'get_quantity'
        conv.save()
        return send_message(phone,
            f"Size *{size}* ✅  |  Price: *₦{price}* each\n\n"
            "How many pairs do you want?\n"
            "_(Enter a number e.g. 1, 2, 3)_\n\n"
            "_Max 4 pairs per order. For 5+ reply *AGENT*_"
        )

    # GET QUANTITY
    elif step == 'get_quantity':
        qty_match = re.search(r'\b([1-9])\b', msg)
        if not qty_match:
            return send_message(phone, "Please enter a number between 1 and 9.")
        qty = int(qty_match.group())
        if qty > 4:
            return send_message(phone,
                f"For {qty}+ pairs, our agent will assist you:\n\n"
                f"📱 WhatsApp: {AGENT_PHONE}\n"
                "Hours: 9am - 8pm daily\n\n"
                "Or reply with 1-4 to order via bot."
            )
        price = conv.context.get('price', '38,999.99')
        subtotal = f"{float(price.replace(',','')) * qty:,.2f}"
        conv.context['quantity'] = qty
        conv.context['subtotal'] = subtotal
        conv.step = 'get_material'
        conv.save()
        return send_message(phone,
            f"*{qty} pair(s)* ✅  |  Subtotal: *₦{subtotal}*\n\n"
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
        items = conv.context.get('items', [])
        items.append({
            'image_id': conv.context.get('image_id', 'N/A'),
            'image_url': conv.context.get('image_url', ''),
            'size': conv.context.get('size', ''),
            'quantity': conv.context.get('quantity', 1),
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

    # ADD MORE
    elif step == 'add_more':
        if msg_lower == '1':
            items = conv.context.get('items', [])
            if len(items) >= 4:
                return send_message(phone,
                    f"You have *{len(items)} pairs* in your cart.\n\n"
                    "For 5+ pairs contact our agent:\n\n"
                    f"📱 WhatsApp: {AGENT_PHONE}\n\n"
                    "Or reply *2* to proceed with current order."
                )
            conv.step = 'get_size'
            conv.context['image_id'] = ''
            conv.context['image_url'] = ''
            conv.save()
            return send_message(phone,
                f"Adding item {len(items) + 1}! 👟\n\n"
                "📸 Send an image of the next pair.\n\n"
                f"Browse: {CATALOGUE_LINK}"
            )
        elif msg_lower == '2':
            conv.step = 'get_discount'
            conv.save()
            return send_message(phone,
                "🎟️ Do you have a *discount code*?\n\n"
                "Enter your code or reply *SKIP* to continue without one."
            )
        elif msg_lower == '3':
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                "👤 *For 5+ pairs:*\n\n"
                f"📱 WhatsApp: {AGENT_PHONE}\n"
                "Hours: 9am - 8pm daily\n\n"
                "Type *Hi* to return to bot anytime."
            )
        else:
            return send_message(phone,
                "Please reply:\n1 to add another pair\n2 to proceed\n3 for 5+ pairs"
            )

    # GET DISCOUNT CODE
    elif step == 'get_discount':
        from datetime import date
        ctx = conv.context
        items = ctx.get('items', [])
        subtotal = calc_items_total(items, ctx.get('delivery_fee', '0'))

        if msg_lower == 'skip':
            conv.context['discount_code'] = ''
            conv.context['discount_amount'] = '0'
            conv.context['total'] = subtotal
            conv.step = 'confirm'
            conv.save()
            summary = ""
            for i, item in enumerate(items, 1):
                qty = item.get('quantity', 1)
                summary += f"*Item {i}:* Size {item['size']} | {item['material']} | {item['color']} | Qty: {qty} | ₦{item['price']} each\n"
            return send_message(phone,
                f"📋 *Order Summary:*\n\n"
                f"{summary}\n"
                f"Delivery: {ctx['location']} — ₦{ctx['delivery_fee']}\n"
                f"Address: {ctx['address']}\n"
                f"💳 *TOTAL: ₦{subtotal}*\n\n"
                "Reply *YES* to confirm ✅\n"
                "Reply *NO* to cancel ❌\n"
                "Reply *EDIT* to change details"
            )

        # Validate code
        code, message = validate_discount(msg.strip(), customer)
        if not code:
            return send_message(phone,
                f"❌ {message}\n\n"
                "Try another code or reply *SKIP* to continue."
            )

        # Apply discount on product only (not delivery fee)
        try:
            delivery_fee = float(ctx.get('delivery_fee', '0').replace(',', ''))
            raw_subtotal = float(subtotal.replace(',', '')) - delivery_fee
            discount_amount = raw_subtotal * code.percentage / 100
            discounted_total = raw_subtotal - discount_amount + delivery_fee
            discount_str = f"{discount_amount:,.2f}"
            total_str = f"{discounted_total:,.2f}"
        except:
            discount_str = '0'
            total_str = subtotal

        conv.context['discount_code'] = code.code
        conv.context['discount_amount'] = discount_str
        conv.context['total'] = total_str
        conv.step = 'confirm'
        conv.save()

        summary = ""
        for i, item in enumerate(items, 1):
            qty = item.get('quantity', 1)
            summary += f"*Item {i}:* Size {item['size']} | {item['material']} | {item['color']} | Qty: {qty} | ₦{item['price']} each\n"

        return send_message(phone,
            f"🎉 *Discount applied!* -{code.percentage}% off\n\n"
            f"📋 *Order Summary:*\n\n"
            f"{summary}\n"
            f"Delivery: {ctx['location']} — ₦{ctx['delivery_fee']}\n"
            f"Address: {ctx['address']}\n"
            f"Subtotal: ₦{subtotal}\n"
            f"Discount ({code.code}): -₦{discount_str}\n"
            f"💳 *TOTAL: ₦{total_str}*\n\n"
            "Reply *YES* to confirm ✅\n"
            "Reply *NO* to cancel ❌\n"
            "Reply *EDIT* to change details"
        )

    # EDIT
    elif step == 'confirm' and msg_lower == 'edit':
        conv.step = 'get_size'
        conv.save()
        return send_message(phone,
            "Let's update your order.\n\n"
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
            discount_code_str = ctx.get('discount_code', '')
            discount_amount = ctx.get('discount_amount', '0')
            for item in items:
                order = Order.objects.create(
                    customer=customer,
                    product="Custom order - image submitted",
                    material=item.get('material', '').lower(),
                    size=item.get('size', ''),
                    color=item.get('color', ''),
                    quantity=item.get('quantity', 1),
                    address=ctx.get('address', ''),
                    status='pending',
                    image_url=item.get('image_url', ''),
                    notes=f"Image: {item.get('image_id','N/A')} | {ctx.get('location','')} | Fee: {ctx.get('delivery_fee','')} | Discount: {discount_code_str} -₦{discount_amount}"
                )
                order_ids.append(str(order.id))
            # Record discount usage
            if discount_code_str:
                try:
                    code_obj = DiscountCode.objects.get(code=discount_code_str)
                    DiscountUsage.objects.create(
                        customer=customer,
                        code=code_obj,
                        order_id=int(order_ids[0]) if order_ids else 0
                    )
                except:
                    pass
            conv.step = 'start'
            conv.context = {}
            conv.save()
            name = customer.name if customer.name != phone else ''
            ids = ', '.join([f'#{i}' for i in order_ids])
            summary = ""
            for i, item in enumerate(items, 1):
                qty = item.get('quantity', 1)
                summary += f"Item {i}: Size {item['size']} | {item['material']} | {item['color']} | Qty: {qty}\n"
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
                f"📸 *Send payment screenshot here after transfer*\n\n"
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
                    image_id = msg_data.get('image', {}).get('id', '')
                    process_message(phone, '', 'image', image_id)

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
