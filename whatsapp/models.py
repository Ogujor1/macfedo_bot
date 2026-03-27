from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, unique=True)
    location = models.CharField(max_length=255, blank=True)
    tag = models.CharField(max_length=100, default='customer')
    last_product = models.CharField(max_length=255, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    last_interaction = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.phone}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    MATERIAL_CHOICES = [
        ('leather', 'Leather'),
        ('suede', 'Suede'),
        ('nubuck', 'Nubuck'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product = models.CharField(max_length=255)
    material = models.CharField(max_length=50, choices=MATERIAL_CHOICES, blank=True)
    size = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=50, blank=True)
    quantity = models.IntegerField(default=1)
    address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    date_ordered = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    image_url = models.TextField(blank=True)

    def __str__(self):
        return f"Order {self.id} - {self.customer.name} - {self.product}"

class Conversation(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    step = models.CharField(max_length=100, default='start')
    context = models.JSONField(default=dict)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer.name} - Step: {self.step}"

class Broadcast(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    template_name = models.CharField(max_length=100, blank=True)
    sent_to = models.IntegerField(default=0)
    date_sent = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.date_sent}"


class MessageLog(models.Model):
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('replied', 'Replied'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255, blank=True)
    broadcast = models.ForeignKey(Broadcast, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.customer.name} - {self.status} - {self.sent_at.strftime('%d %b %Y')}"


class DiscountCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    percentage = models.IntegerField(default=10)
    expiry_date = models.DateField()
    max_uses_per_customer = models.IntegerField(default=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.percentage}% off"

class DiscountUsage(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    code = models.ForeignKey(DiscountCode, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)
    order_id = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.customer.name} used {self.code.code} on {self.used_at.strftime('%d %b %Y')}"
