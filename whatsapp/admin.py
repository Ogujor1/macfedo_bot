from django.contrib import admin
from .models import Customer, Order, Conversation, Broadcast

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'location', 'tag', 'date_added', 'is_active']
    search_fields = ['name', 'phone']
    list_filter = ['tag', 'is_active']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'product', 'material', 'size', 'color', 'status', 'date_ordered']
    search_fields = ['customer__name', 'product']
    list_filter = ['status', 'material']

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'step', 'last_updated']
    search_fields = ['customer__name']

@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ['title', 'sent_to', 'date_sent']
# Register your models here.
