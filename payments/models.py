from django.db import models
from user.models import Order 
import uuid
# Create your models here.
class Payment(models.Model): 
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    order=models.ForeignKey(Order,on_delete=models.CASCADE)
    gateway=models.CharField(max_length=20)  
    transaction_id=models.CharField(max_length=200,blank=True,null=True) 
    amount=models.DecimalField(max_digits=10,decimal_places=2)
    status=models.CharField(max_length=20,default='initiated') 
    created_at=models.DateTimeField(auto_now_add=True)