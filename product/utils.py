from decimal import Decimal,ROUND_HALF_UP
from django.utils.timezone import now
from .models import Offer,JerseyVariant,Coupon
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .services import get_best_offer
from user.utils import get_referral_discount
from django.http import JsonResponse
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
def get_cart_items(request):
    cart = request.session.get('cart', {})
    cart_items = []
    offer_discount=Decimal('0.00') 
    offer_type=None
    offer_name=None
    for variant_id, item in cart.items():
        try:
            variant = get_object_or_404(
            JerseyVariant,
            id=variant_id,
            is_active=True,
            stock__gt=0
        )
        except JerseyVariant.DoesNotExist:
            continue
        product = variant.product

        quantity = min(item['qty'], product.max_quantity_per_order, variant.stock)
        offer_data=get_best_offer(variant)
        unit_price=offer_data['final_price']
        total_price = unit_price * quantity
        if offer_data['discount']>offer_discount:
            offer_discount=offer_data['discount']
            if offer_data['offer']:
                offer_type=offer_data['offer'].scope
                offer_name=offer_data['offer'].name
        cart_items.append({
            'variant': variant,
            'product': product,
            'quantity': quantity,
            'unit_price': unit_price,
            'original_price':variant.price,
            'total_price': total_price,
            'max_quantity': product.max_quantity_per_order,
        })
    return cart_items,offer_discount,offer_type,offer_name 
def calculate_cart_totals(request,cart_items,offer_discount,offer_type):
    TWOPLACES = Decimal('0.01')
    subtotal=sum(item['total_price'] for item in cart_items)
    subtotal=subtotal if subtotal else Decimal('0.00')
    request.session['cart_total'] = float(subtotal)

    shipping = Decimal('10.00') if subtotal > 0 else Decimal('0.00')
    tax = (subtotal * Decimal('0.08')).quantize(TWOPLACES,rounding=ROUND_HALF_UP)
    shipping = shipping.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    
    # ---------------- COUPONS ----------------
    coupon = None
    coupon_discount=Decimal('0.00')
    discount = Decimal('0.00')
    coupon_error = None
    coupon_id = request.session.get('coupon_id')

    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id, is_active=True)

            if coupon.expires_at and coupon.expires_at < timezone.now():
                raise Exception('Coupon expired')

            if subtotal < coupon.min_order_value:
                raise Exception(f'Minimum order ₹{coupon.min_order_value} required')

            if coupon.discount_type == 'percent':
                coupon_discount = (coupon.discount_value / Decimal('100')) * subtotal
            else:
                coupon_discount = coupon.discount_value

            discount = min(coupon_discount, subtotal)

        except Exception as e:
            coupon_error = str(e)
            request.session.pop('coupon_id', None)
            coupon = None
            coupon_discount=Decimal('0.00')
    referral_discount=get_referral_discount(request.user,subtotal)
    if offer_type is not None:
        discount = offer_discount
        coupon = None  

    elif coupon_discount > 0:
        discount = coupon_discount

    else:
        discount = referral_discount
    discount = discount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    grand_total = subtotal + shipping + tax - discount
    grand_total = max(grand_total, Decimal('0.00'))
    grand_total = grand_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return {
        'subtotal': subtotal,
        'shipping': shipping,
        'tax': tax,
        'discount': discount,
        'grand_total': grand_total,
        'applied_coupon': coupon,
        'coupon_error': coupon_error,
        'referral_discount':referral_discount,
    }
