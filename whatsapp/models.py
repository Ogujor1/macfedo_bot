from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, unique=True)
    location = models.CharField(max_length=255, blank=True)
    tag = models.CharField(max_length=100, default='customer')
    last_product = models.CharField(max_length=255, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

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
    sent_to = models.IntegerField(default=0)
    date_sent = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.date_sent}"