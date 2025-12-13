from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.contrib.auth import get_user_model  
from django.utils import timezone 
from datetime import timedelta
# Create your models here.  
# 
# class CustomerManager(UserManager):
#     def create_user(self, email, password=None, **extra_fields):
#         if not email:
#             raise ValueError("Email is required")
#         email = self.normalize_email(email)
#         return super().create_user(email=email, password=password, **extra_fields)

#     def create_superuser(self, email, password=None, **extra_fields):
#         extra_fields.setdefault("is_staff", True)
#         extra_fields.setdefault("is_superuser", True)
#         return self.create_user(email, password, **extra_fields)
                 
class Customer(AbstractUser):
    email=models.EmailField(unique=True)
    is_blocked=models.BooleanField(default=False)


# class Customer(AbstractUser):
#     USERNAME = None   

#     email = models.EmailField(unique=True)
#     is_blocked = models.BooleanField(default=False)

#     USERNAME_FIELD = 'email'
#     REQUIRED_FIELDS = []   

#     objects = CustomerManager()



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
class Profile(models.Model):
    user=models.OneToOneField(Customer,on_delete=models.CASCADE)
    phone=models.CharField(max_length=15) 
    address=models.TextField(blank=True)  
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