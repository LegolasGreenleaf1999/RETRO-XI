from django.db import models
from django.core.exceptions import ValidationError
import uuid
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower
# Create your models here. 
class Category(models.Model):  
    name=models.CharField(max_length=50)  
    slug=models.SlugField(unique=True) 
    is_active=models.BooleanField(default=True) 
    created_at=models.DateTimeField(auto_now_add=True)  
    description=models.TextField(blank=True)                  
    parent=models.ForeignKey('self',on_delete=models.SET_NULL,null=True,blank=True,related_name='subcategories')         
    class Meta:
        ordering=['-created_at']
    def __str__(self):
        return self.name 
class JerseyProduct(models.Model):     
    uuid=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    slug=models.SlugField(unique=True,blank=True)
    category=models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,related_name='category')
    is_active=models.BooleanField(default=True)
    main_img=models.ImageField(upload_to='jersey_images/') 
    description=models.TextField() 
    team=models.CharField(max_length=50)             
    season=models.CharField(max_length=10) 
    player_name=models.CharField(max_length=50,blank=True,null=True)
    max_quantity_per_order=models.PositiveIntegerField(default=5,help_text='maximum units allowed per order')
    created_at=models.DateTimeField(auto_now_add=True)
    is_featured=models.BooleanField(default=False)
    def __str__(self):
        return f'{self.player_name} {self.team} {self.season}' 
    @property
    def first_available_variant(self):
        return self.variants.filter(is_active=True,stock__gt=0).first()    
class JerseyVariant(models.Model):
    SIZE_CHOICES = [
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
    ]

    product = models.ForeignKey(
        JerseyProduct,
        on_delete=models.CASCADE,
        related_name='variants'
    )

    sku = models.CharField(max_length=50, unique=True)
    size = models.CharField(max_length=1, choices=SIZE_CHOICES)

    price = models.DecimalField(max_digits=7, decimal_places=2)
    stock = models.PositiveIntegerField()

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('product', 'size')

    def __str__(self):
        return f"{self.product} - {self.get_size_display()}"
class ProductImage(models.Model): 
    jersey=models.ForeignKey(JerseyProduct,on_delete=models.CASCADE,related_name='images') 
    img=models.ImageField(upload_to='jersey_images/') 
class Review(models.Model):
    product=models.ForeignKey(JerseyProduct,on_delete=models.CASCADE,related_name='reviews') 
    user=models.ForeignKey('user.Customer',on_delete=models.CASCADE,related_name='reviews')
    rating=models.PositiveSmallIntegerField(choices=[(i,i) for i in range(1,6)]) 
    comment=models.TextField(blank=True) 
    is_approved=models.BooleanField(default=True) 
    created_at=models.DateTimeField(auto_now_add=True) 
    class Meta:
        ordering=['-created_at'] 
        unique_together=('product','user')
    def __str__(self):
        return f'{self.user} -{self.product} {self.rating}' 
class Coupon(models.Model): 
    code=models.CharField(max_length=20,unique=True)
    discount_type=models.CharField(max_length=10,choices=[('percent','Percent'),('fixed','Fixed')]) 
    discount_value=models.DecimalField(max_digits=10,decimal_places=2)
    min_order_value=models.DecimalField(max_digits=10,decimal_places=2,default=0) 
    is_active=models.BooleanField(default=True)
    expires_at=models.DateTimeField(null=True,blank=True) 
    class Meta:
        constraints=[
            UniqueConstraint(Lower('code'),name='unique_coupon_code_case_insensitive')
        ]
    def __str__(self):
        return self.code
class Offer(models.Model):
    OFFER_TYPE_CHOICES=(
        ('percentage','Percentage'),
        ('fixed','Fixed Amount'),
    )
    STATUS_CHOICES=(
        ('active','Active'),
        ('scheduled','Scheduled'),
        ('expired','Expired'),
    )
    OFFER_SCOPE=(
        ('product','Product'),
        ('category','Category'),
        ('referral','Referral'),
    )
    name=models.CharField(max_length=200)
    description=models.CharField(max_length=255,blank=True) 
    scope=models.CharField(max_length=20,choices=OFFER_SCOPE)
    product=models.ForeignKey(JerseyProduct,on_delete=models.CASCADE,null=True,blank=True)
    category=models.ForeignKey(Category,on_delete=models.CASCADE,null=True,blank=True)
    referral_code=models.CharField(max_length=50,null=True,blank=True,unique=True)
    discount_type=models.CharField(max_length=20,choices=OFFER_TYPE_CHOICES)
    discount_value=models.DecimalField(max_digits=10,decimal_places=2)  
    start_date=models.DateField()
    end_date=models.DateField() 
    status=models.CharField(max_length=20,choices=STATUS_CHOICES)  
    is_active=models.BooleanField(default=True)
    def clean(self):
        if self.scope=='product' and not self.product: 
            raise ValidationError('product offer must have a product')
        if self.scope=='category' and not self.category:
            raise ValidationError('category offer must have a category')
        if self.scope=='referral' and not self.referral_code:
            raise ValidationError('referral offer must have a referral code')