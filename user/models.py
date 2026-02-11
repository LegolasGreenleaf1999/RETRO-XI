from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.contrib.auth import get_user_model  
from django.utils import timezone 
from datetime import timedelta 
from django.core.validators import RegexValidator
import uuid
from decimal import Decimal
class Customer(AbstractUser):
    email=models.EmailField(unique=True)
    is_blocked=models.BooleanField(default=False)
    referral_code=models.CharField(max_length=12,unique=True,blank=True,null=True)
    referred_by=models.ForeignKey('self',null=True,blank=True,on_delete=models.SET_NULL,related_name='referrals')

class PasswordChangeOTP(models.Model):
    user=models.ForeignKey(Customer,on_delete=models.CASCADE)  
    otp=models.CharField(max_length=10)  
    new_password_hash=models.CharField(max_length=128) 
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField() 
    def is_expired(self):
        return timezone.now()>self.expires_at 
class EmailChangeOTP(models.Model): 
    user=models.ForeignKey(Customer,on_delete=models.CASCADE)     
    new_email=models.EmailField()
    otp=models.CharField(max_length=10) 
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()        
    def is_expired(self):
        return timezone.now()>self.expires_at
class OTP(models.Model):
    user=models.ForeignKey(Customer,on_delete=models.CASCADE)   
    otp_code=models.CharField(max_length=6) 
    created_at=models.DateTimeField(auto_now_add=True)  
    is_used=models.BooleanField(default=False) 
phone_validator=RegexValidator(
    regex=r'^(?:\+91)?[6-9]\d{9}$',
    message='enter a valid phone number(10 digits, optional +91)'
)  
class Profile(models.Model):
    user=models.OneToOneField(Customer,on_delete=models.CASCADE)
    phone=models.CharField(max_length=13,validators=[phone_validator]) 
    profile_image=models.ImageField(upload_to='profileimages/',blank=True,null=True)
    def __str__(self):
        return self.user.first_name
class Address(models.Model):   
    user=models.ForeignKey(Customer,on_delete=models.CASCADE) 
    address_line=models.TextField()  
    city=models.CharField(max_length=50)  
    pincode=models.CharField(max_length=10) 
    is_default=models.BooleanField(default=False) 
class Wallet(models.Model):
    user=models.OneToOneField(Customer,on_delete=models.CASCADE,related_name='wallet')      
    balance=models.DecimalField(max_digits=10,decimal_places=2,default=0.00) 
    updated_at=models.DateTimeField(auto_now=True)      
    def __str__(self):
        return f"{self.user.first_name}'s Wallet" 
    def deposit(self,amount):
        if amount>0: 
            if not isinstance(amount,Decimal):
                amount=Decimal(str(amount))
            if not isinstance(self.balance,Decimal):
                self.balance=Decimal(str(self.balance))
            self.balance+=amount  
            self.save()
            return True
        return False
    def withdraw(self,amount):  
        if amount>0 and self.balance>=amount:
            self.balance-=amount 
            self.save()
            return True
        return False 
class Wishlist(models.Model):
    user=models.ForeignKey(Customer,on_delete=models.CASCADE,related_name='wishlist')
    jersey = models.ForeignKey(
    'product.JerseyProduct',
    on_delete=models.CASCADE
)
    created_at=models.DateTimeField(auto_now_add=True) 
    class Meta:
        unique_together=('user','jersey')
    def __str__(self):
        return f'{self.user}-{self.jersey}'
DELIVERY_MAP={
    'standard':5,
    'express':2,
}
class Order(models.Model):
    PAYMENT_CHOICES=(
        ('wallet','Wallet'),
        ('razorpay','Razorpay'),
        ('cod','Cash on Delivery'),
    )
    DELIVERY_CHOICES=[
        ('standard','Standard(5 days)'),
        ('express','Express(2 days)'),
    ]
    STATUS_CHOICES=(
        ('pending','Pending'), 
        ('paid','Paid'),
        ('cancelled','Cancelled'),
        ('shipped','Shipped'),
        ('delivered','Delivered'),
    )
    payment_method=models.CharField(max_length=20,choices=PAYMENT_CHOICES,blank=True,null=True)
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user=models.ForeignKey(Customer,on_delete=models.CASCADE,related_name='order')
    first_name=models.CharField(max_length=100)
    email=models.EmailField()
    phone=models.CharField(max_length=20)    
    address=models.TextField()     
    subtotal=models.DecimalField(max_digits=10,decimal_places=2)
    discount=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    shipping=models.DecimalField(max_digits=10,decimal_places=2)
    tax=models.DecimalField(max_digits=10,decimal_places=2)
    total=models.DecimalField(max_digits=10,decimal_places=2)
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending') 
    created_at=models.DateTimeField(auto_now_add=True) 
    delivery_days=models.PositiveIntegerField(default=5)
    delivery_type=models.CharField(max_length=20,choices=DELIVERY_CHOICES,default='standard')  
    stock_deducted=models.BooleanField(default=False)
    def __str__(self):
        return f'Order {self.id} {self.user.username}' 
class OrderItem(models.Model):
    RETURN_STATUS=(
        ('none','No Return'),
        ('requested','Requested'),
        ('approved','Approved'),
        ('rejected','Rejected'),
        ('refunded','Refunded'),
    )
    order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name='item')
    variant = models.ForeignKey(
    'product.JerseyVariant',
    on_delete=models.CASCADE,
    related_name='order_items',null=True,blank=True
)
    product=models.ForeignKey('product.JerseyProduct',on_delete=models.PROTECT,related_name='order_items')
    quantity=models.PositiveIntegerField()
    price=models.DecimalField(max_digits=10,decimal_places=2)
    discount=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    applied_offer=models.ForeignKey('product.Offer',null=True,blank=True,on_delete=models.SET_NULL)
    return_status=models.CharField(max_length=20,choices=RETURN_STATUS,default='none')
    returned_at=models.DateTimeField(null=True,blank=True) 
    return_reason=models.TextField(blank=True)
    return_notes=models.TextField(blank=True)
    cancelled=models.BooleanField(default=False)
    def __str__(self):
        return f'{self.product.team}({self.variant.get_size_display()})x{self.quantity}' 
class ReferralReward(models.Model):
    referrer=models.ForeignKey(Customer,on_delete=models.CASCADE,related_name='earned_referrals')
    referred_user=models.ForeignKey(Customer,on_delete=models.CASCADE,related_name='used_referral') 
    order=models.ForeignKey(Order,on_delete=models.CASCADE)
    reward_amount=models.DecimalField(max_digits=10,decimal_places=2)
    STATUS_CHOICES=(
        ('pending','Pending'),
        ('approved','Approved'),
        ('credited','Credited'),
        ('rejected','Rejected'),
    )
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending') 
    created_at=models.DateTimeField(auto_now_add=True)