from decimal import Decimal
from django.utils import timezone
from product.models import Offer 
from django.db.models import Q
def calculate_discount_amount(price,offer):
    if offer.discount_type=='percentage':
        return (price*offer.discount_value)/Decimal('100')
    return min(offer.discount_value,price) 
def get_best_offer(variant): 
    today=timezone.now().date()
    base_price=variant.price
    offers=Offer.objects.filter(
        Q(scope='product',product=variant.product)|
        Q(scope='category',category=variant.product.category),
        status='active',
        is_active=True,
        start_date__lte=today
    ).filter(
        Q(end_date__gte=today)|Q(end_date__isnull=True)
    )
    best_offer=None
    max_discount=Decimal('0.00')
    for offer in offers:
        if offer.discount_type=='percentage': 
            discount=base_price*(offer.discount_value/Decimal('100'))
        else:
            discount=offer.discount_value            
        discount=min(discount,base_price)
        if discount>max_discount:
            max_discount=discount
            best_offer=offer
    return {
        'offer':best_offer,
        'discount':max_discount,
        'final_price':base_price-max_discount
    }