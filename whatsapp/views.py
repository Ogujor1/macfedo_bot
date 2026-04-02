import json
import logging
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Customer, Conversation, Order, MessageLog

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
import os
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
AGENT_NUMBER    = "2348035796380"
BOT_NUMBER      = "2348126975697"

# Hero image — shown first to every new lead from ads
HERO_IMAGE_URL = "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-3-2.png"

# Catalogue images — sent when customer asks to view products
CATALOGUE_IMAGES = [
    "https://macfedowears.com/wp-content/uploads/2026/03/mf1.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-20.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-4-3.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-1-2.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-11-2.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-12.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-13.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-4-2.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-8-6.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-6-4.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-1-1.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/poIJ.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/g5.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-7-4.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-10-2.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-7-2.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Untitled-design-10-1.png",
    "https://macfedowears.com/wp-content/uploads/2026/03/Gemini_Generated_Image_z3k3zzz3k3zzz3k3.png",
]

CATALOGUE_LINK = "https://drive.google.com/drive/folders/1FyE3JkmnMxduMJ9AmBXIGMOwaxfqVqcR"
WEBSITE_LINK   = "https://macfedowears.com/shop"

DELIVERY_FEES = {
    "1": {"label": "Lagos",         "fee": 3000},
    "2": {"label": "Other States",  "fee": 5000},
    "3": {"label": "International", "fee": 15000},
}


# ─────────────────────────────────────────────
# WEBHOOK VERIFICATION
# ─────────────────────────────────────────────
@csrf_exempt
def webhook(request):
    if request.method == "GET":
        mode      = request.GET.get("hub.mode")
        token     = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == "macfedo_verify_123":
            return HttpResponse(challenge, status=200)
        return HttpResponse("Forbidden", status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            _process_webhook(data)
        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
        return JsonResponse({"status": "ok"}, status=200)

    return HttpResponse("Method not allowed", status=405)


# ─────────────────────────────────────────────
# WEBHOOK PROCESSOR
# ─────────────────────────────────────────────
def _process_webhook(data):
    try:
        entry   = data["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]
    except (KeyError, IndexError):
        return

    if "statuses" in value:
        _handle_status_update(value["statuses"])
        return

    if "messages" not in value:
        return

    message  = value["messages"][0]
    from_num = message["from"]
    msg_type = message.get("type", "")

    if msg_type == "text":
        user_text = message["text"]["body"].strip()
    elif msg_type == "image":
        user_text = "__IMAGE__"
    elif msg_type == "button":
        user_text = message["button"]["payload"].strip()
    elif msg_type == "interactive":
        interactive = message.get("interactive", {})
        if interactive.get("type") == "button_reply":
            user_text = interactive["button_reply"]["id"].strip()
        elif interactive.get("type") == "list_reply":
            user_text = interactive["list_reply"]["id"].strip()
        else:
            user_text = ""
    else:
        user_text = ""

    customer, created = Customer.objects.get_or_create(
        phone=from_num,
        defaults={"tag": "unknown", "is_active": True}
    )

    conv, _ = Conversation.objects.get_or_create(
        customer=customer,
        defaults={"step": "start", "context": {}}
    )

    customer.last_interaction = timezone.now()
    customer.save(update_fields=["last_interaction"])

    text_upper = user_text.upper().strip()

    if text_upper in ["STOP", "UNSUBSCRIBE"]:
        customer.tag = "unsubscribed"
        customer.is_active = False
        customer.save()
        _send_text(from_num, "You've been unsubscribed from broadcasts. Reply *Hi* anytime to resubscribe. 👋")
        return

    if text_upper in ["AGENT", "HUMAN", "TALK TO HUMAN", "SPEAK TO HUMAN", "PERSON"]:
        _handle_agent_handoff(from_num, customer, conv)
        return

    if text_upper in ["FAQ", "FAQS"]:
        _send_faq(from_num)
        return

    if text_upper in ["0", "MENU", "MAIN MENU"]:
        conv.step = "main_menu"
        conv.context = {}
        conv.save()
        _send_main_menu(from_num, customer.name or "there")
        return

    if text_upper in ["00", "EXIT", "BYE", "GOODBYE"]:
        _send_text(from_num, "Thanks for reaching out to Macfedo Foot Wears! 👟\nWe're always here when you need us. Have a great day! 😊")
        conv.step = "start"
        conv.context = {}
        conv.save()
        return

    if text_upper in ["HI", "HELLO", "HEY", "START", "ORDER"]:
        if not customer.is_active:
            customer.is_active = True
            customer.tag = "unknown"
            customer.save()
        conv.step = "start"
        conv.context = {}
        conv.save()

    _handle_step(from_num, customer, conv, user_text)


# ─────────────────────────────────────────────
# STEP ROUTER
# ─────────────────────────────────────────────
def _handle_step(from_num, customer, conv, user_text):
    step = conv.step

    if step == "start":
        _step_welcome(from_num, customer, conv)
    elif step == "await_name":
        _step_save_name(from_num, customer, conv, user_text)
    elif step == "main_menu":
        _step_main_menu_choice(from_num, customer, conv, user_text)
    elif step == "await_catalogue_choice":
        _step_catalogue_choice(from_num, customer, conv, user_text)
    elif step == "await_order_image":
        _step_order_image(from_num, customer, conv, user_text)
    elif step == "await_size":
        _step_size(from_num, customer, conv, user_text)
    elif step == "await_quantity":
        _step_quantity(from_num, customer, conv, user_text)
    elif step == "await_material":
        _step_material(from_num, customer, conv, user_text)
    elif step == "await_color":
        _step_color(from_num, customer, conv, user_text)
    elif step == "await_delivery":
        _step_delivery(from_num, customer, conv, user_text)
    elif step == "await_address":
        _step_address(from_num, customer, conv, user_text)
    elif step == "await_discount":
        _step_discount(from_num, customer, conv, user_text)
    elif step == "await_confirmation":
        _step_confirmation(from_num, customer, conv, user_text)
    elif step == "await_payment":
        _step_payment(from_num, customer, conv, user_text)
    elif step == "handoff":
        _send_text(from_num,
            "Our team has your request and will reply shortly. 🙏\n\n"
            f"If urgent, WhatsApp us directly: wa.me/{AGENT_NUMBER}"
        )
    else:
        conv.step = "start"
        conv.context = {}
        conv.save()
        _step_welcome(from_num, customer, conv)


# ─────────────────────────────────────────────
# STEP 1 — WELCOME
# ─────────────────────────────────────────────
def _step_welcome(from_num, customer, conv):
    name = customer.name

    _send_image(from_num, HERO_IMAGE_URL,
        "👟 *Premium Halfshoes for the Distinguished Man*\n_Handcrafted. Lagos-made. Yours._"
    )

    if name:
        _send_main_menu(from_num, name)
        conv.step = "main_menu"
    else:
        _send_text(from_num,
            "Welcome to *Macfedo Foot Wears* 👟\n\n"
            "We craft premium halfshoes for the distinguished Nigerian man — "
            "starting from *₦36,999*.\n\n"
            "What's your *first name*? 😊"
        )
        conv.step = "await_name"

    conv.save()


# ─────────────────────────────────────────────
# STEP 2 — SAVE NAME
# ─────────────────────────────────────────────
def _step_save_name(from_num, customer, conv, user_text):
    name = user_text.strip().split()[0].title()

    if len(name) < 2 or not name.isalpha():
        _send_text(from_num, "Please send your first name (letters only). What shall we call you? 😊")
        return

    customer.name = name
    customer.tag  = "enquiry"
    customer.save()

    _notify_agent_new_lead(customer)

    _send_text(from_num,
        f"Nice to meet you, *{name}!* 🤝\n\n"
        "Macfedo has been dressing Lagos gentlemen in premium leather halfshoes. "
        "Every pair is handcrafted and made to order. 🙌"
    )

    _send_main_menu(from_num, name)
    conv.step = "main_menu"
    conv.save()


# ─────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────
def _send_main_menu(from_num, name):
    _send_interactive_buttons(from_num,
        header=f"What would you like to do, {name}?",
        body=(
            "Choose an option below 👇\n\n"
            "🛍 *Place an Order* — Choose your style\n"
            "📸 *View Catalogue* — See our latest designs\n"
            "💬 *Talk to a Person* — Chat with our team directly"
        ),
        footer="Reply 0 anytime to return here",
        buttons=[
            {"id": "ORDER_NOW",      "title": "Place Order"},
            {"id": "VIEW_CATALOGUE", "title": "View Catalogue"},
            {"id": "AGENT",          "title": "Talk to a Person"},
        ]
    )


def _step_main_menu_choice(from_num, customer, conv, user_text):
    choice = user_text.upper().strip()

    if choice in ["ORDER_NOW", "1", "ORDER", "PLACE ORDER"]:
        _start_order_flow(from_num, customer, conv)
    elif choice in ["VIEW_CATALOGUE", "2", "CATALOGUE"]:
        _send_catalogue(from_num, customer, conv)
    elif choice in ["AGENT", "3"]:
        _handle_agent_handoff(from_num, customer, conv)
    else:
        _send_text(from_num, "Please choose one of the options above, or reply *0* for the menu. 😊")


# ─────────────────────────────────────────────
# CATALOGUE
# ─────────────────────────────────────────────
def _send_catalogue(from_num, customer, conv):
    name = customer.name or "there"

    _send_text(from_num,
        f"Here are some of our latest styles, {name}! 📸\n\n"
        "Sending you a few now..."
    )

    # Send first 6 catalogue images
    for url in CATALOGUE_IMAGES[:6]:
        try:
            _send_image(from_num, url, "")
        except Exception:
            pass

    _send_interactive_buttons(from_num,
        header="See something you like?",
        body=(
            "Pick a style from the images above and tap *Place Order* to proceed.\n\n"
            "Don't see what you're looking for? Tap *Talk to Team* and we'll help you find the perfect pair! 😊"
        ),
        footer="Reply 0 to return to menu",
        buttons=[
            {"id": "ORDER_NOW", "title": "Place Order"},
            {"id": "AGENT",     "title": "Talk to Team"},
        ]
    )

    conv.step = "await_catalogue_choice"
    conv.save()


def _step_catalogue_choice(from_num, customer, conv, user_text):
    if user_text == "__IMAGE__":
        _start_order_flow(from_num, customer, conv, image_received=True)
    elif user_text.upper() in ["ORDER_NOW", "ORDER", "1"]:
        _start_order_flow(from_num, customer, conv)
    else:
        _send_interactive_buttons(from_num,
            header="Ready to order?",
            body="Would you like to place an order or talk to our team?",
            footer="",
            buttons=[
                {"id": "ORDER_NOW", "title": "Place Order"},
                {"id": "AGENT",     "title": "Talk to Team"},
            ]
        )


# ─────────────────────────────────────────────
# ORDER FLOW — START
# ─────────────────────────────────────────────
def _start_order_flow(from_num, customer, conv, image_received=False):
    name = customer.name or "there"

    if image_received:
        _send_text(from_num,
            f"Perfect! Got your style choice, {name}! 👟\n\n"
            "*What size do you need?*\n\n"
            "📏 Kids: Size 27-35\n"
            "📏 Women: Size 36-38\n"
            "📏 Men/Unisex: Size 39-45\n\n"
            "Just type your size number (e.g. *42*)"
        )
        conv.step = "await_size"
    else:
        _send_text(from_num,
            f"Let's get your order started, {name}! 🎉\n\n"
            "*Step 1 of 6 — Choose your style*\n\n"
            "Please send me a *photo* of the shoe you want from our catalogue above.\n\n"
            "_Not sure which style? Tap *Talk to Team* and we'll guide you personally._"
        )
        conv.step = "await_order_image"

    conv.context = {}
    conv.save()


# ─────────────────────────────────────────────
# ORDER STEP — IMAGE
# ─────────────────────────────────────────────
def _step_order_image(from_num, customer, conv, user_text):
    if user_text == "__IMAGE__":
        _send_text(from_num,
            "Got it! Beautiful choice 👟✨\n\n"
            "*Step 2 of 6 — Your size*\n\n"
            "📏 Kids: Size 27-35 — ₦25,999\n"
            "📏 Women: Size 36-38 — ₦37,000\n"
            "📏 Men/Unisex: Size 39-45 — ₦38,999\n\n"
            "Type your size number (e.g. *42*)"
        )
        conv.step = "await_size"
        conv.save()
    else:
        _send_text(from_num,
            "No problem! Let me connect you with our team. 😊\n\n"
            "They'll show you the perfect style personally."
        )
        _handle_agent_handoff(from_num, customer, conv)


# ─────────────────────────────────────────────
# ORDER STEP — SIZE
# ─────────────────────────────────────────────
def _step_size(from_num, customer, conv, user_text):
    try:
        size = int(user_text.strip())
    except ValueError:
        _send_text(from_num, "Please send your size as a number (e.g. *42*). What size do you need?")
        return

    if size < 27 or size > 50:
        _send_text(from_num, "Our sizes run from 27 to 45. What's your size?")
        return

    if 27 <= size <= 35:
        category, price = "Kids", 25999.99
    elif 36 <= size <= 38:
        category, price = "Women", 37000.00
    else:
        category, price = "Men/Unisex", 38999.99

    conv.context["size"]     = size
    conv.context["price"]    = price
    conv.context["category"] = category
    conv.step = "await_quantity"
    conv.save()

    _send_text(from_num,
        f"Size *{size}* ({category}) — ₦{price:,.0f} per pair ✅\n\n"
        "*Step 3 of 6 — Quantity*\n\n"
        "How many pairs would you like?\n"
        "Reply *1*, *2*, *3*, or *4*\n\n"
        "💡 *Order 4+ pairs and get 15% off!*"
    )


# ─────────────────────────────────────────────
# ORDER STEP — QUANTITY
# ─────────────────────────────────────────────
def _step_quantity(from_num, customer, conv, user_text):
    try:
        qty = int(user_text.strip())
    except ValueError:
        _send_text(from_num, "Please reply with a number (e.g. *1* or *2*). How many pairs?")
        return

    if qty < 1 or qty > 10:
        _send_text(from_num, "Please reply with a number between 1 and 10.")
        return

    price    = conv.context.get("price", 38999.99)
    discount = 0.15 if qty >= 4 else 0
    subtotal = price * qty * (1 - discount)

    conv.context["quantity"] = qty
    conv.context["discount"] = discount
    conv.context["subtotal"] = subtotal
    conv.step = "await_material"
    conv.save()

    discount_note = "\n🎉 *15% discount applied!*" if discount else ""

    _send_interactive_buttons(from_num,
        header="Step 4 of 6 — Material",
        body=(
            f"*{qty} pair(s) x ₦{price:,.0f} = ₦{subtotal:,.0f}*{discount_note}\n\n"
            "What material do you prefer?"
        ),
        footer="",
        buttons=[
            {"id": "LEATHER", "title": "Leather"},
            {"id": "SUEDE",   "title": "Suede"},
            {"id": "NUBUCK",  "title": "Nubuck"},
        ]
    )


# ─────────────────────────────────────────────
# ORDER STEP — MATERIAL
# ─────────────────────────────────────────────
def _step_material(from_num, customer, conv, user_text):
    material_map = {
        "LEATHER": "Leather", "1": "Leather",
        "SUEDE":   "Suede",   "2": "Suede",
        "NUBUCK":  "Nubuck",  "3": "Nubuck",
    }
    material = material_map.get(user_text.upper().strip())

    if not material:
        _send_text(from_num, "Please choose: *Leather*, *Suede*, or *Nubuck*")
        return

    conv.context["material"] = material
    conv.step = "await_color"
    conv.save()

    _send_text(from_num,
        f"*{material}* — great choice! 👌\n\n"
        "*Step 5 of 6 — Color*\n\n"
        "What color would you like?\n\n"
        "Popular: Black, Brown, Tan, Burgundy, Navy\n\n"
        "Type your preferred color 🎨"
    )


# ─────────────────────────────────────────────
# ORDER STEP — COLOR
# ─────────────────────────────────────────────
def _step_color(from_num, customer, conv, user_text):
    color = user_text.strip().title()

    if len(color) < 2:
        _send_text(from_num, "Please type your preferred color (e.g. Black, Brown, Tan)")
        return

    conv.context["color"] = color
    conv.step = "await_delivery"
    conv.save()

    _send_interactive_buttons(from_num,
        header="Step 6 of 6 — Delivery",
        body=f"*{color}* — noted! 🎨\n\nWhere are we delivering to?",
        footer="Flat rate delivery fees",
        buttons=[
            {"id": "DELIVERY_1", "title": "Lagos (3,000)"},
            {"id": "DELIVERY_2", "title": "Other States (5,000)"},
            {"id": "DELIVERY_3", "title": "International (15,000)"},
        ]
    )


# ─────────────────────────────────────────────
# ORDER STEP — DELIVERY
# ─────────────────────────────────────────────
def _step_delivery(from_num, customer, conv, user_text):
    delivery_map = {
        "DELIVERY_1": "1", "1": "1",
        "DELIVERY_2": "2", "2": "2",
        "DELIVERY_3": "3", "3": "3",
    }
    key = delivery_map.get(user_text.upper().strip())

    if not key:
        _send_text(from_num, "Please choose your delivery zone: Lagos, Other States, or International")
        return

    delivery = DELIVERY_FEES[key]
    conv.context["delivery_zone"] = delivery["label"]
    conv.context["delivery_fee"]  = delivery["fee"]
    conv.step = "await_address"
    conv.save()

    _send_text(from_num,
        f"*{delivery['label']}* delivery — ₦{delivery['fee']:,} ✅\n\n"
        "Please send your *full delivery address* 📍\n\n"
        "_(Include street name, area, and city)_"
    )


# ─────────────────────────────────────────────
# ORDER STEP — ADDRESS
# ─────────────────────────────────────────────
def _step_address(from_num, customer, conv, user_text):
    if len(user_text.strip()) < 10:
        _send_text(from_num, "Please send your full address including street, area and city. 📍")
        return

    conv.context["address"] = user_text.strip()
    conv.step = "await_discount"
    conv.save()

    _send_text(from_num,
        "Address saved! ✅\n\n"
        "Do you have a *discount code*?\n\n"
        "Type your code or reply *SKIP* to continue 👇"
    )


# ─────────────────────────────────────────────
# ORDER STEP — DISCOUNT
# ─────────────────────────────────────────────
def _step_discount(from_num, customer, conv, user_text):
    from .models import DiscountCode, DiscountUsage

    ctx      = conv.context
    subtotal = ctx.get("subtotal", 0)
    discount_applied = 0
    discount_code    = None

    if user_text.upper().strip() != "SKIP":
        code_str = user_text.upper().strip()
        try:
            code = DiscountCode.objects.get(code=code_str, is_active=True)
            if code.expiry_date and timezone.now().date() > code.expiry_date:
                _send_text(from_num, f"Sorry, the code *{code_str}* has expired. Reply *SKIP* to continue.")
                return

            uses = DiscountUsage.objects.filter(customer__phone=from_num, code=code).count()
            if uses >= code.max_uses_per_customer:
                _send_text(from_num, f"You've already used *{code_str}* the maximum number of times. Reply *SKIP* to continue.")
                return

            discount_applied = subtotal * (code.percentage / 100)
            subtotal         = subtotal - discount_applied
            discount_code    = code_str
            _send_text(from_num, f"Code *{code_str}* applied — *{code.percentage}% off!* ✅")
        except DiscountCode.DoesNotExist:
            _send_text(from_num, f"Code *{code_str}* is not valid. Reply *SKIP* to continue without a discount.")
            return

    ctx["discount_code"]    = discount_code
    ctx["discount_applied"] = discount_applied
    ctx["subtotal"]         = subtotal
    delivery_fee            = ctx.get("delivery_fee", 0)
    total                   = subtotal + delivery_fee
    ctx["total"]            = total
    conv.context            = ctx
    conv.step               = "await_confirmation"
    conv.save()

    size     = ctx.get("size", "-")
    qty      = ctx.get("quantity", 1)
    material = ctx.get("material", "-")
    color    = ctx.get("color", "-")
    address  = ctx.get("address", "-")
    zone     = ctx.get("delivery_zone", "-")
    price    = ctx.get("price", 0)

    discount_line = f"\nDiscount ({discount_code}): -₦{discount_applied:,.0f}" if discount_code else ""

    summary = (
        f"📋 *ORDER SUMMARY*\n"
        f"{'─' * 25}\n"
        f"👟 Size: {size}\n"
        f"🧵 Material: {material}\n"
        f"🎨 Color: {color}\n"
        f"📦 Quantity: {qty} pair(s)\n"
        f"{'─' * 25}\n"
        f"Subtotal: ₦{price * qty:,.0f}"
        f"{discount_line}\n"
        f"Delivery ({zone}): ₦{delivery_fee:,}\n"
        f"{'─' * 25}\n"
        f"💳 *TOTAL: ₦{total:,.0f}*\n"
        f"{'─' * 25}\n"
        f"📍 Address: {address}\n\n"
        f"Is this correct?"
    )

    _send_interactive_buttons(from_num,
        header="Confirm Your Order",
        body=summary,
        footer="Tap Yes to confirm",
        buttons=[
            {"id": "CONFIRM_YES",  "title": "Yes, Confirm"},
            {"id": "CONFIRM_EDIT", "title": "Edit Order"},
            {"id": "AGENT",        "title": "Talk to Team"},
        ]
    )


# ─────────────────────────────────────────────
# ORDER STEP — CONFIRMATION
# ─────────────────────────────────────────────
def _step_confirmation(from_num, customer, conv, user_text):
    choice = user_text.upper().strip()

    if choice in ["CONFIRM_YES", "YES", "Y", "CONFIRM"]:
        ctx = conv.context
        order = Order.objects.create(
            customer=customer,
            size=ctx.get("size"),
            material=ctx.get("material", ""),
            color=ctx.get("color", ""),
            quantity=ctx.get("quantity", 1),
            address=ctx.get("address", ""),
            status="pending",
            notes=(
                f"Delivery: {ctx.get('delivery_zone')} | "
                f"Fee: {ctx.get('delivery_fee', 0)} | "
                f"Total: {ctx.get('total', 0)} | "
                f"Discount: {ctx.get('discount_code') or 'None'}"
            )
        )

        customer.tag = "customer"
        customer.save(update_fields=["tag"])

        conv.step = "await_payment"
        conv.context["order_id"] = order.id
        conv.save()

        _send_text(from_num,
            "Order confirmed! Thank you 🎉\n\n"
            "*Payment Details:*\n"
            "Bank: *GTBank*\n"
            "Account Name: *Michael Ogujor*\n"
            "Account Number: *XXXXXXXXXX*\n\n"
            f"Amount: *₦{ctx.get('total', 0):,.0f}*\n\n"
            "After payment, please send a *screenshot of your receipt* here. 📸\n\n"
            "_Need help? Reply *AGENT* to speak with our team._"
        )

    elif choice in ["CONFIRM_EDIT", "EDIT", "NO", "N"]:
        conv.step = "start"
        conv.context = {}
        conv.save()
        _send_text(from_num, "No problem! Let's start over. 😊")
        _step_welcome(from_num, customer, conv)

    else:
        _send_text(from_num, "Please tap *Yes, Confirm*, *Edit Order*, or *Talk to Team*.")


# ─────────────────────────────────────────────
# ORDER STEP — PAYMENT
# ─────────────────────────────────────────────
def _step_payment(from_num, customer, conv, user_text):
    if user_text == "__IMAGE__":
        order_id = conv.context.get("order_id")
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order.status = "confirmed"
                order.save(update_fields=["status"])
            except Order.DoesNotExist:
                pass

        _notify_agent_payment(customer, conv.context)

        conv.step = "start"
        conv.context = {}
        conv.save()

        _send_text(from_num,
            "Payment received! ✅\n\n"
            f"Thank you, {customer.name or 'valued customer'}! Your order is now confirmed. 🎉\n\n"
            "Our team will review your payment and begin production within 24 hours.\n\n"
            "*Production time:* 3-5 working days\n"
            "*Delivery:* 1-3 days after production\n\n"
            "We'll keep you updated every step of the way. 📦\n\n"
            "_Questions? Reply *AGENT* to talk to our team._"
        )
    else:
        _send_text(from_num,
            "Please send a *screenshot* of your payment receipt to complete your order. 📸\n\n"
            "Or reply *AGENT* if you need help with payment."
        )


# ─────────────────────────────────────────────
# AGENT HANDOFF
# ─────────────────────────────────────────────
def _handle_agent_handoff(from_num, customer, conv):
    name    = customer.name or "A customer"
    step    = conv.step
    context = conv.context

    _send_text(from_num,
        "Connecting you with our team now! 🙌\n\n"
        "Michael or a team member will reply you shortly.\n\n"
        "We typically respond within *30 minutes* (Mon-Sat, 8am-8pm).\n\n"
        f"For urgent matters: wa.me/{AGENT_NUMBER}"
    )

    context_summary = ""
    if context:
        context_summary = "\n".join([f"  - {k}: {v}" for k, v in context.items()])

    agent_msg = (
        f"NEW LEAD FROM BOT\n\n"
        f"Name: {name}\n"
        f"Number: +{from_num}\n"
        f"Bot Step: {step}\n"
        f"Time: {timezone.now().strftime('%d %b %Y, %I:%M %p')}\n"
    )
    if context_summary:
        agent_msg += f"\nOrder Details:\n{context_summary}"

    agent_msg += f"\n\nReply to customer: wa.me/{from_num}"

    _send_text(AGENT_NUMBER, agent_msg)

    conv.step = "handoff"
    conv.save()


def _notify_agent_new_lead(customer):
    msg = (
        f"NEW LEAD CAPTURED\n\n"
        f"Name: {customer.name}\n"
        f"Number: +{customer.phone}\n"
        f"Time: {timezone.now().strftime('%d %b %Y, %I:%M %p')}\n"
        f"Source: WhatsApp Bot (Ad)\n\n"
        f"Chat: wa.me/{customer.phone}"
    )
    _send_text(AGENT_NUMBER, msg)


def _notify_agent_payment(customer, context):
    total = context.get("total", 0)
    msg = (
        f"PAYMENT RECEIVED\n\n"
        f"{customer.name} (+{customer.phone})\n"
        f"Amount: {total:,.0f}\n"
        f"Time: {timezone.now().strftime('%d %b %Y, %I:%M %p')}\n\n"
        f"Check admin panel to confirm.\n"
        f"wa.me/{customer.phone}"
    )
    _send_text(AGENT_NUMBER, msg)


# ─────────────────────────────────────────────
# FAQ
# ─────────────────────────────────────────────
def _send_faq(from_num):
    _send_text(from_num,
        "FREQUENTLY ASKED QUESTIONS\n\n"
        "*Q: How long does production take?*\n"
        "A: 3-5 working days after payment confirmation.\n\n"
        "*Q: Do you ship outside Lagos?*\n"
        "A: Yes! We deliver nationwide and internationally.\n\n"
        "*Q: What is your return policy?*\n"
        "A: We fix any defects within 30 days of delivery.\n\n"
        "*Q: Can I customize the color?*\n"
        "A: Absolutely! Most colors are available.\n\n"
        "*Q: Do you do bulk orders?*\n"
        "A: Yes, 4+ pairs get 15% discount automatically.\n\n"
        "More questions? Reply *AGENT* to talk to our team.\n"
        "Reply *0* for the main menu."
    )


# ─────────────────────────────────────────────
# STATUS UPDATES
# ─────────────────────────────────────────────
def _handle_status_update(statuses):
    for status_item in statuses:
        msg_id   = status_item.get("id")
        status   = status_item.get("status")
        from_num = status_item.get("recipient_id")

        if msg_id and status and from_num:
            try:
                log = MessageLog.objects.get(message_id=msg_id)
                if status == "delivered":
                    log.delivered_at = timezone.now()
                elif status == "read":
                    log.read_at = timezone.now()
                log.status = status
                log.save()
            except MessageLog.DoesNotExist:
                pass


# ─────────────────────────────────────────────
# WHATSAPP API SENDERS
# ─────────────────────────────────────────────
def _send_text(to, text):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }
    return _call_api(payload)


def _send_image(to, image_url, caption=""):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    return _call_api(payload)


def _send_interactive_buttons(to, header, body, footer, buttons):
    btn_list = [
        {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
        for b in buttons[:3]
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": header[:60]},
            "body":   {"text": body},
            "footer": {"text": footer[:60]} if footer else {},
            "action": {"buttons": btn_list},
        },
    }
    return _call_api(payload)


def _call_api(payload):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        data   = resp.json()
        msg_id = data.get("messages", [{}])[0].get("id")
        to_num = payload.get("to")

        if msg_id and to_num:
            try:
                customer = Customer.objects.get(phone=to_num)
                MessageLog.objects.create(
                    customer=customer,
                    message_id=msg_id,
                    status="sent",
                    sent_at=timezone.now()
                )
            except Customer.DoesNotExist:
                pass

        return data
    except requests.RequestException as e:
        logger.error(f"WhatsApp API error: {e}")
        return None
