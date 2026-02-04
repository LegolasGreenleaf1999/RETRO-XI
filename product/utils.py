from decimal import Decimal
from django.utils.timezone import now
from .models import Offer
def calculate_best_offer_price(product):
    today=now().date()
    base_price=product.price
    product_offer=Offer.objects.filter(scope='product',product=product,status='active',start_date__lte=today,end_date__gte=today,is_active=True).first()
    category_offer=Offer.objects.filter(scope='category',category=product.category,status='active',start_date__lte=today,end_date__gte=today,is_active=True).first()
    discounts=[] 
    for offer in (product_offer,category_offer): 
        if not offer: 
            continue
        if offer.discount_type=='percentage':
            discount=base_price*(offer.discount_value/Decimal('100'))
        else:
            discount=offer.discount_value
        discounts.append(discount)
    max_discount=max(discounts,default=Decimal('0')) 
    return max(base_price-max_discount,Decimal('0'))