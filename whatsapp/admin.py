from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
from django.utils.html import format_html
import requests
from django.conf import settings
from .models import Customer, Order, Conversation, Broadcast, MessageLog, DiscountCode, DiscountUsage, MessageTemplate
import time

def send_template_message(phone, template_name, customer_name, product="", price=""):
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
                        {"type": "text", "text": customer_name},
                        {"type": "text", "text": product},
                        {"type": "text", "text": price}
                    ]
                }
            ]
        }
    }
    r = requests.post(url, headers=headers, json=data)
    return r.status_code == 200

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'tag', 'is_active', 'date_added']
    search_fields = ['name', 'phone']
    list_filter = ['tag', 'is_active']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'product', 'material', 'size', 'color', 'status', 'date_ordered', 'show_image', 'show_payment_proof']
    search_fields = ['customer__name', 'product']
    list_filter = ['status', 'material']
    readonly_fields = ['date_ordered', 'show_image', 'show_payment_proof']

    def show_payment_proof(self, obj):
        notes = obj.notes or ''
        if '| Payment:' in notes:
            url = notes.split('| Payment:')[1].strip().split('|')[0].strip()
            if url and url.startswith('http'):
                return format_html(
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="width:80px;height:80px;object-fit:cover;border-radius:4px;border:2px solid green;" />'
                    '</a>', url, url
                )
        if obj.status == 'confirmed':
            return '✅ Confirmed'
        return '⏳ Awaiting'
    show_payment_proof.short_description = 'Payment Proof'

    def show_image(self, obj):
        notes = obj.notes or ''
        if 'Image:' in notes:
            image_id = notes.split('Image:')[1].split('|')[0].strip()
            if image_id and image_id != 'N/A':
                url = f"https://graph.facebook.com/v18.0/{image_id}?access_token={settings.WHATSAPP_TOKEN}"
                return format_html('<a href="{}" target="_blank">📸 View Image</a>', url)
        return "No image"
    show_image.short_description = 'Customer Image'

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'step', 'last_updated']
    search_fields = ['customer__name']

@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ['customer', 'status', 'sent_at', 'delivered_at', 'read_at']
    list_filter = ['status']
    search_fields = ['customer__name']
    readonly_fields = ['sent_at', 'delivered_at', 'read_at', 'replied_at']

@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ['title', 'template_name', 'sent_to', 'date_sent']
    readonly_fields = ['sent_to', 'date_sent']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send/', self.admin_site.admin_view(self.send_broadcast_view), name='send_broadcast'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['send_broadcast_url'] = 'send/'
        return super().changelist_view(request, extra_context=extra_context)

    def send_broadcast_view(self, request):
        if request.method == 'POST':
            template_name = request.POST.get('template_name')
            product = request.POST.get('product', '')
            price = request.POST.get('price', '')
            tag_filter = request.POST.get('tag_filter', 'all')
            title = request.POST.get('title', 'Broadcast')

            # Get num_variables from template
            try:
                tmpl = MessageTemplate.objects.get(name=template_name)
                num_vars = tmpl.num_variables
            except:
                num_vars = 1

            image_url = request.POST.get('image_url', '').strip()

            if tag_filter == 'all':
                customers = Customer.objects.filter(is_active=True).exclude(tag='unreachable')
            elif tag_filter == 'unsubscribed':
                customers = Customer.objects.filter(tag='unsubscribed')
            else:
                customers = Customer.objects.filter(is_active=True, tag=tag_filter).exclude(tag='unreachable')

            sent = 0
            failed = 0

            import requests as req
            for customer in customers:
                name = customer.name if customer.name != customer.phone else 'Customer'
                # Build parameters based on num_variables
                parameters = [{"type": "text", "text": name}]
                if num_vars >= 2 and product:
                    parameters.append({"type": "text", "text": product})
                if num_vars >= 3 and price:
                    parameters.append({"type": "text", "text": price})

                # Build components
                components = [{"type": "body", "parameters": parameters}]
                if image_url:
                    components.insert(0, {
                        "type": "header",
                        "parameters": [{"type": "image", "image": {"link": image_url}}]
                    })

                api_url = f"https://graph.facebook.com/v18.0/{settings.PHONE_NUMBER_ID}/messages"
                headers = {
                    "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
                    "Content-Type": "application/json"
                }
                data = {
                    "messaging_product": "whatsapp",
                    "to": customer.phone,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": "en"},
                        "components": components
                    }
                }
                r = req.post(url=api_url, headers=headers, json=data)
                if r.status_code == 200:
                    sent += 1
                else:
                    failed += 1
                time.sleep(0.3)

            Broadcast.objects.create(
                title=title,
                template_name=template_name,
                message=f"Product: {product} | Price: {price}",
                sent_to=sent
            )

            self.message_user(
                request,
                f"Broadcast complete! ✅ Sent: {sent} | ❌ Failed: {failed}",
                messages.SUCCESS
            )
            return HttpResponseRedirect('../')

        customers_count = Customer.objects.filter(is_active=True).exclude(tag='unreachable').count()
        templates = MessageTemplate.objects.filter(is_active=True)
        context = {
            'title': 'Send Broadcast',
            'customers_count': customers_count,
            'templates': templates,
            'opts': self.model._meta,
            'has_permission': True,
        }
        return render(request, 'admin/send_broadcast.html', context)


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'percentage', 'expiry_date', 'max_uses_per_customer', 'is_active', 'total_uses']
    list_editable = ['is_active']

    def total_uses(self, obj):
        return DiscountUsage.objects.filter(code=obj).count()
    total_uses.short_description = 'Total Uses'

@admin.register(DiscountUsage)
class DiscountUsageAdmin(admin.ModelAdmin):
    list_display = ['customer', 'code', 'order_id', 'used_at']
    search_fields = ['customer__name', 'code__code']
    list_filter = ['code']


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'num_variables', 'variables', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
