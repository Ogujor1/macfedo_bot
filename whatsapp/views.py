import json
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Customer, Order, Conversation


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
    response = requests.post(url, headers=headers, json=data)
    print(f"WhatsApp API Response: {response.status_code} - {response.json()}")
    return response.json()


def process_message(phone, message):
    message_lower = message.strip().lower()

    customer, created = Customer.objects.get_or_create(
        phone=phone,
        defaults={'name': 'Customer', 'phone': phone}
    )

    conv, _ = Conversation.objects.get_or_create(customer=customer)
    step = conv.step

    # STEP: START
    if step == 'start' or message_lower in ['hi', 'hello', 'hey', 'start']:
        conv.step = 'menu'
        conv.save()
        return send_message(phone,
            "👟 Welcome to *Macfedo Foot Wears Store!*\n\n"
            "We specialize in premium sandals and luxury footwear.\n\n"
            "Please choose an option:\n"
            "1️⃣ Browse Products\n"
            "2️⃣ Place an Order\n"
            "3️⃣ Track my Order\n"
            "4️⃣ Contact Us\n\n"
            "Reply with a number (1-4)"
        )

    # STEP: MENU
    elif step == 'menu':
        if message_lower == '1':
            conv.step = 'start'
            conv.save()
            return send_message(phone,
                "👟 *Our Products:*\n\n"
                "Visit our website to see all products:\n"
                "🌐 www.macfedowears.com\n\n"
                "Popular categories:\n"
                "• Birkenstock-style sandals\n"
                "• Luxury slides\n"
                "• Casual footwear\n\n"
                "Reply *2* to place an order"
            )
        elif message_lower == '2':
            conv.step = 'get_product'
            conv.save()
            return send_message(phone,
                "Great! Let's place your order. 🛍️\n\n"
                "What product are you interested in?\n"
                "(e.g. Black Birkenstock sandals, Brown slides)"
            )
        elif message_lower == '3':
            conv.step = 'start'
            conv.save()
            orders = Order.objects.filter(
                customer=customer
            ).order_by('-date_ordered')[:1]
            if orders:
                order = orders[0]
                return send_message(phone,
                    f"📦 *Your Latest Order:*\n\n"
                    f"Product: {order.product}\n"
                    f"Material: {order.get_material_display()}\n"
                    f"Size: {order.size}\n"
                    f"Status: {order.status.upper()}\n"
                    f"Date: {order.date_ordered.strftime('%d %b %Y')}"
                )
            else:
                return send_message(phone,
                    "You have no orders yet. Reply *2* to place an order."
                )
        elif message_lower == '4':
            conv.step = 'start'
            conv.save()
            return send_message(phone,
                "📞 *Contact Macfedo Foot Wears:*\n\n"
                "📱 WhatsApp: +234 803 579 6380\n"
                "🌐 Website: www.macfedowears.com\n"
                "📸 Instagram: @macfedowears\n\n"
                "We typically reply within minutes!"
            )
        else:
            return send_message(phone,
                "Please reply with a number between 1 and 4."
            )

    # STEP: GET PRODUCT
    elif step == 'get_product':
        conv.context['product'] = message.strip()
        conv.step = 'get_material'
        conv.save()
        return send_message(phone,
            f"Got it! *{message.strip()}* 👍\n\n"
            "What material do you prefer?\n\n"
            "1️⃣ Leather\n"
            "2️⃣ Suede\n"
            "3️⃣ Nubuck\n\n"
            "Reply with a number (1-3)"
        )

    # STEP: GET MATERIAL
    elif step == 'get_material':
        material_map = {
            '1': 'leather',
            '2': 'suede',
            '3': 'nubuck',
            'leather': 'leather',
            'suede': 'suede',
            'nubuck': 'nubuck',
        }
        material = material_map.get(message_lower)
        if not material:
            return send_message(phone,
                "Please reply with 1 for Leather, 2 for Suede, or 3 for Nubuck."
            )
        conv.context['material'] = material
        conv.step = 'get_size'
        conv.save()
        return send_message(phone,
            f"*{material.capitalize()}* selected! ✅\n\n"
            "What size do you need?\n"
            "(e.g. 38, 39, 40, 41, 42, 43, 44)"
        )

    # STEP: GET SIZE
    elif step == 'get_size':
        conv.context['size'] = message.strip()
        conv.step = 'get_color'
        conv.save()
        return send_message(phone,
            f"Size *{message.strip()}* noted! ✅\n\n"
            "What color do you prefer?\n"
            "(e.g. Black, Brown, Tan, White)"
        )

    # STEP: GET COLOR
    elif step == 'get_color':
        conv.context['color'] = message.strip()
        conv.step = 'get_address'
        conv.save()
        return send_message(phone,
            f"Color *{message.strip()}* noted! ✅\n\n"
            "Please send your delivery address:\n"
            "(Include street, area, and city)"
        )

    # STEP: GET ADDRESS
    elif step == 'get_address':
        conv.context['address'] = message.strip()
        conv.step = 'confirm_order'
        conv.save()
        ctx = conv.context
        return send_message(phone,
            f"📋 *Order Summary:*\n\n"
            f"Product: {ctx.get('product', '')}\n"
            f"Material: {ctx.get('material', '').capitalize()}\n"
            f"Size: {ctx.get('size', '')}\n"
            f"Color: {ctx.get('color', '')}\n"
            f"Address: {ctx.get('address', '')}\n\n"
            "Reply *YES* to confirm or *NO* to cancel"
        )

    # STEP: CONFIRM ORDER
    elif step == 'confirm_order':
        if message_lower == 'yes':
            ctx = conv.context
            order = Order.objects.create(
                customer=customer,
                product=ctx.get('product', ''),
                material=ctx.get('material', ''),
                size=ctx.get('size', ''),
                color=ctx.get('color', ''),
                address=ctx.get('address', ''),
                status='pending'
            )
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                f"✅ *Order Confirmed!*\n\n"
                f"Order ID: #{order.id}\n"
                f"Product: {order.product}\n"
                f"Material: {order.get_material_display()}\n"
                f"Size: {order.size}\n"
                f"Color: {order.color}\n\n"
                "*Payment Details:*\n"
                "Bank: First Bank\n"
                "Account: 1234567890\n"
                "Name: Macfedo Foot Wears\n\n"
                "Send proof of payment here and we'll process your order immediately. 🙏"
            )
        else:
            conv.step = 'start'
            conv.context = {}
            conv.save()
            return send_message(phone,
                "Order cancelled. Reply *Hi* to start again. 😊"
            )

    else:
        conv.step = 'start'
        conv.save()
        return send_message(phone, "Reply *Hi* to start. 👋")


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
                message_data = value['messages'][0]
                phone = message_data['from']
                msg_type = message_data['type']

                if msg_type == 'text':
                    message = message_data['text']['body']
                    process_message(phone, message)

        except Exception as e:
            print(f"Error: {e}")

        return JsonResponse({'status': 'ok'})