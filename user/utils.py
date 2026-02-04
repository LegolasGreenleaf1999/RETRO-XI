import uuid
from .models import Customer
from decimal import Decimal
from product.models import JerseyVariant
from .models import Customer,Order,Wallet
from django.db import transaction 
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
REFERRAL_DISCOUNT_PERCENT=Decimal('10.00')
REFERRAL_MAX_DISCOUNT=Decimal('500.00')
def generate_referral_code():
    while True:
        code=uuid.uuid4().hex[:8].upper() 
        if not Customer.objects.filter(referral_code=code).exists(): 
            return code
def process_referral_reward(order):
    user=order.user
    if not user.referred_by:
        return
    delivered_orders=Order.objects.filter(user=user,status='delivered').count()
    if delivered_orders>1:
        return
    referrer=user.referred_by
    wallet,_=Wallet.objects.get_or_create(user=referrer)
    wallet.deposit(Decimal('100.00')) 
def get_referral_discount(user,subtotal): 
    if not user.referred_by: 
        return Decimal('0.00')
    if Order.objects.filter(user=user).exists():
        return Decimal('0.00')
    discount=(REFERRAL_DISCOUNT_PERCENT/Decimal('100.00'))*subtotal
    return min(discount,REFERRAL_MAX_DISCOUNT) 
def deduct_stock_for_order(order): 
    if order.stock_deducted: 
        return 
    with transaction.atomic():
        for item in order.item.all():
            variant = (
                JerseyVariant.objects
                .select_for_update()
                .get(pk=item.variant_id)
            )
            if item.quantity>variant.stock:
                raise ValueError(f'Insufficient stock for {variant.product}-{variant.get_size_display()}')
            variant.stock-=item.quantity
            variant.save() 
        order.stock_deducted=True
        order.save()
def user_only(view_func):
    @login_required
    def wrapper(request,*args,**kwargs):
        if request.user.is_staff or request.user.is_superuser:
            messages.error(request,'admins cannot access user pages')
            return redirect('/secret-admin-panel-1729/')
        return view_func(request,*args,**kwargs)
    return wrapper