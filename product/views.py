from django.shortcuts import render,redirect,get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator 
from .models import Category,JerseyProduct,ProductImage,Review,Coupon,JerseyVariant
from PIL import Image
from django.db.models import Q,Min,Max,Count,Sum,Prefetch
from decimal import Decimal,ROUND_HALF_UP 
from django.contrib.auth.decorators import login_required
from .forms import ReviewForm 
from django.db.models import Avg  
from user.models import Profile,Address,Order,OrderItem,Wishlist,Wallet
from django.db import transaction 
from django.contrib.admin.views.decorators import staff_member_required   
from django.views.decorators.cache import never_cache    
from django.utils import timezone 
from django.http import JsonResponse
from .services import get_best_offer,calculate_discount_amount 
from user.utils import get_referral_discount,user_only
import json
# Create your views here.
@login_required
@user_only
def product_list(request):
    q = request.GET.get('q')
    category = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort = request.GET.get('sort')
    products = (
        JerseyProduct.objects
        .filter(is_active=True, variants__is_active=True,variants__stock__gt=0)
        .annotate(min_price=Min('variants__price',filter=Q(variants__is_active=True,variants__stock__gt=0)),
                  max_price=Max('variants__price',filter=Q(variants__is_active=True,variants__stock__gt=0)))
        .prefetch_related(
            Prefetch(
                'variants',
                queryset=JerseyVariant.objects.filter(is_active=True,stock__gt=0).order_by('id'),
                to_attr='active_variants'
            )
        )
        .distinct()
    )
    if q:
        products = products.filter(
            Q(team__icontains=q) |
            Q(season__icontains=q) |
            Q(player_name__icontains=q) |
            Q(variants__sku__icontains=q)
        )
    if category and category != 'None':
        try:
            selected_category = Category.objects.get(slug=category, is_active=True)

            if selected_category.parent is None:
            
                products = products.filter(Q(category=selected_category) |Q(category__parent=selected_category))
            else:
            
                products = products.filter(category=selected_category)

        except Category.DoesNotExist:
            pass
    try:
        if min_price:
            products = products.filter(variants__price__gte=Decimal(min_price))
        if max_price:
            products = products.filter(variants__price__lte=Decimal(max_price))
    except:
        pass
    if sort == 'price_low':
        products = products.order_by('min_price')
    elif sort == 'price_high':
        products = products.order_by('-min_price')
    elif sort == 'az':
        products = products.order_by('team')
    elif sort == 'za':
        products = products.order_by('-team')
    else:
        products = products.order_by('-id')
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'products': page_obj,
        'categories': Category.objects.filter(is_active=True, parent=None).prefetch_related(Prefetch('subcategories',queryset=Category.objects.filter(is_active=True))),
        'selected_category': category,
        'sort': sort,
        'q': q,
        'min_price': min_price,
        'max_price': max_price,
    }

    return render(request, 'user/product_list.html', context)
@login_required
@user_only
def product_detail(request,slug,uuid):        
    product=get_object_or_404(JerseyProduct,uuid=uuid,is_active=True) 
    if product.slug!=slug:
        return redirect('productdetail',slug=product.slug,uuid=product.uuid)     
    reviews=product.reviews.filter(is_approved=True) 
    avg_rating=reviews.aggregate(avg=Avg('rating'))['avg'] 
    variants=JerseyVariant.objects.filter(product=product,is_active=True)
    variant_id=request.GET.get('variant')
    if variant_id:
        selected_variant=get_object_or_404(JerseyVariant,id=variant_id,product=product)
    else:
        selected_variant=variants.filter(stock__gt=0).first()
    recommended_products=JerseyProduct.objects.filter(team=product.team,is_active=True).exclude(id=product.id)[:4] 
    is_wishlisted=False 
    if request.user.is_authenticated:
        is_wishlisted=Wishlist.objects.filter(user=request.user,jersey=product).exists() 
    other_images = product.images.all()[:2]
    context={
        'product':product,
        'variants':variants,
        'selected_variant':selected_variant,
        'avg_rating':avg_rating,
        'review_count':reviews.count(),
        'recommended_products':recommended_products,
        'is_wishlisted':is_wishlisted,
        'other_images':other_images,
    }                  
    return render(request,'user/product_detail.html',context) 
@login_required 
def product_reviews(request,uuid):
    product=get_object_or_404(JerseyProduct,uuid=uuid) 
    reviews=product.reviews.filter(is_approved=True)  
    avg_rating=reviews.aggregate(avg=Avg('rating'))['avg'] 
    context={
        'product':product, 
        'reviews':reviews,
        'avg_rating':avg_rating,
    }
    return render(request,'user/product_review.html',context)
@login_required 
def add_review(request,uuid):
    product=get_object_or_404(JerseyProduct,uuid=uuid) 
    if Review.objects.filter(product=product,user=request.user).exists(): 
        messages.error(request,'you have already reviewed this product')  
        return redirect('productdetail',slug=product.slug,uuid=product.uuid)
    if request.method=='POST': 
        form=ReviewForm(request.POST) 
        if form.is_valid(): 
            review=form.save(commit=False)
            review.product=product
            review.user=request.user
            review.save()
            messages.success(request,'thank you for your review')
    return redirect('productdetail',slug=product.slug,uuid=product.uuid)  
@never_cache
@login_required
@user_only
def cart_view(request):
    TWOPLACES = Decimal('0.01')
    coupon_error = request.session.pop('coupon_error', None)
    cart = request.session.get('cart', {})
    cart_items = []
    subtotal = Decimal('0.00')
    offer_discount=Decimal('0.00') 
    offer_type=None
    offer_name=None
    for variant_id, item in cart.items():
        variant = get_object_or_404(
            JerseyVariant,
            id=variant_id,
            is_active=True,
            stock__gt=0
        )
        product = variant.product

        quantity = min(item['qty'], product.max_quantity_per_order, variant.stock)
        offer_data=get_best_offer(variant)
        unit_price=offer_data['final_price']
        total_price = unit_price * quantity
        subtotal += total_price
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
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping': shipping,
        'tax': tax,
        'discount': discount,
        'grand_total': grand_total,
        'applied_coupon': coupon,
        'coupon_error': coupon_error,
        'referral_discount':referral_discount,
        'offer_discount':offer_discount,
        'offer_type':offer_type,
        'offer_name':offer_name,
    }

    return render(request, 'user/cart.html', context)
@login_required
def add_to_cart(request, variant_id):
    variant = get_object_or_404(
        JerseyVariant,
        id=variant_id,
        is_active=True,
        product__is_active=True
    )
    

    cart = request.session.get('cart', {})
    key = str(variant.id)
    current_qty = cart.get(key, {}).get('qty', 0)

    if current_qty >= variant.stock:
        return JsonResponse({
            'status': 'error',
            'message': f'Only {variant.stock} units available'
        })

    cart[key] = {'qty': current_qty + 1}
    request.session['cart'] = cart
    request.session.modified = True

    total_items = sum(item['qty'] for item in cart.values())

    return JsonResponse({
        'status': 'success',
        'qty': cart[key]['qty'],
        'total_items': total_items
    })
@login_required
def update_cart(request, variant_id):
    cart = request.session.get('cart', {})
    key = str(variant_id)

    if key not in cart:
        return JsonResponse({'status': 'error', 'message': 'Item not in cart'})

    variant = get_object_or_404(JerseyVariant, id=variant_id, is_active=True)
    product = variant.product

    action = request.GET.get('action')
    qty = cart[key]['qty']

    if action == 'inc':
        if qty >= variant.stock:
            return JsonResponse({'status': 'error', 'message': 'Stock limit reached'})
        if qty >= product.max_quantity_per_order:
            return JsonResponse({'status': 'error', 'message': 'Max limit reached'})
        cart[key]['qty'] += 1

    elif action == 'dec':
        if qty > 1:
            cart[key]['qty'] -= 1
        else:
            del cart[key]
            request.session['cart'] = cart
            request.session.modified = True
            return JsonResponse({'status': 'removed'})

    request.session['cart'] = cart
    request.session.modified = True

    return JsonResponse({'status': 'success', 'qty': cart.get(key, {}).get('qty', 0)})
@login_required
def remove_from_cart(request, variant_id):
    cart = request.session.get('cart', {})
    key = str(variant_id)

    if key in cart:
        del cart[key]

    request.session['cart'] = cart
    request.session.modified = True

    return JsonResponse({'status': 'success', 'message': 'Item removed'})
@login_required
def set_shipping(request):
    data=json.loads(request.body)
    request.session['shipping_method']=data.get('shipping','standard')
    request.session.modified=True
    return JsonResponse({'status':'ok'})
@never_cache
@login_required  
@user_only 
def checkout(request):
    TWOPLACES = Decimal('0.01')
    user=request.user
    cart=request.session.get('cart',{})   
    if request.method == 'GET' and not cart:
        return redirect('cart')
    profile,_=Profile.objects.get_or_create(user=user)
    default_address=Address.objects.filter(user=user,is_default=True).first()
    cart_items=[]    
    subtotal=Decimal('0.00')
    for variant_id,item in cart.items():  
        variant=get_object_or_404(JerseyVariant,id=variant_id,is_active=True)     
        requested_qty=item['qty']
        allowed_qty=min(requested_qty,variant.product.max_quantity_per_order,variant.stock)
        offer_data=get_best_offer(variant)
        unit_price=offer_data['final_price']
        discount=offer_data['discount']*allowed_qty
        offer=offer_data['offer']
        total_price=unit_price*allowed_qty
        subtotal+=total_price
        cart_items.append({
            'variant':variant,
            'product':variant.product,
            'size':variant.get_size_display(),
            'quantity':allowed_qty,
            'unit_price':unit_price,
            'original_price':variant.price,
            'total_price':total_price,
            'discount':discount,
            'applied_offer':offer,
        })
    shipping_method = (request.session.get('shipping_method', 'standard').strip().lower())
    if shipping_method not in ('standard', 'express'):
        shipping_method = 'standard'
    shipping = Decimal('15.00') if shipping_method == 'express' else Decimal('10.00')
    shipping = shipping.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    tax = (subtotal * Decimal('0.08')).quantize(TWOPLACES,rounding=ROUND_HALF_UP)
    shipping=shipping.quantize(TWOPLACES,rounding=ROUND_HALF_UP)
    from user.utils import get_referral_discount
    referral_discount=Decimal(str(request.session.get('referral_discount','0')))
    print("Referral discount:", referral_discount)
    coupon = None
    coupon_discount = Decimal('0.00')
    coupon_id = request.session.get('coupon_id')

    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id, is_active=True)

            if coupon.expires_at and coupon.expires_at < timezone.now():
                raise Exception("Coupon expired")

            if subtotal < coupon.min_order_value:
                raise Exception("Minimum order value not met")

            if coupon.discount_type == 'percent':
                coupon_discount = (coupon.discount_value / Decimal('100')) * subtotal
            else:
                coupon_discount = Decimal(str(coupon.discount_value))

            coupon_discount = min(coupon_discount, subtotal)

        except Exception:
            request.session.pop('coupon_id', None)
            coupon = None
            coupon_discount = Decimal('0.00')

    if any(item['applied_offer'] for item in cart_items):
        discount=sum(item['discount'] for item in cart_items)
    elif coupon_discount>0:
        discount=coupon_discount
    else:
        discount=referral_discount
    discount=discount.quantize(TWOPLACES,rounding=ROUND_HALF_UP)
    grand_total=subtotal+shipping+tax-discount
    grand_total=max(grand_total,Decimal('0.00'))
    if grand_total<0: 
        grand_total=Decimal('0.00') 
    grand_total=grand_total.quantize(TWOPLACES,rounding=ROUND_HALF_UP)
    if request.method=='POST':
        payment_method=request.POST.get('payment_method')
        first_name=request.POST.get('first_name')
        email=request.POST.get('email')
        phone=request.POST.get('phone')
        address=request.POST.get('address') 
        if not first_name or not email or not phone or not address:
            messages.error(request, "All fields are required.")
            return redirect('checkout')
        shipping_method = request.session.get('shipping_method', 'standard')
        shipping = Decimal('15.00') if shipping_method == 'express' else Decimal('10.00')

        grand_total = subtotal + shipping + tax - discount
        grand_total = max(grand_total, Decimal('0.00'))
        with transaction.atomic():
            order=Order.objects.create(
            user=user,
            first_name=first_name,
            email=email,
            phone=phone,
            address=address,
            subtotal=subtotal,
            shipping=shipping,
            tax=tax,
            discount=discount,
            total=grand_total,
            status='pending',
            payment_method=payment_method,
        )
            for item in cart_items:
                OrderItem.objects.create(
                order=order,
                product=item['product'],
                variant=item['variant'],
                quantity=item['quantity'],
                price=item['unit_price'],
                discount=item['discount']/item['quantity'] if item['quantity'] else 0,
                applied_offer=item['applied_offer']
            )  
        if payment_method=='wallet':
            wallet=getattr(user,'wallet',None)
            if not wallet or wallet.balance<grand_total:
                messages.error(request,'insufficient wallet balance') 
                transaction.set_rollback(True)
                return redirect('checkout') 
            wallet.withdraw(grand_total)
            order.status='paid'       
            order.save()
            return redirect('order_success',order.id)
        if payment_method=='razorpay':
            return redirect('start_payment',order_uuid=order.id) 
        else:
            order.status='pending'
            order.save()
            return redirect('order_success',order.id)
    context={
    'cart_items':cart_items,
    'subtotal':subtotal,
    'shipping':shipping, 
    'tax':tax,
    'grand_total':grand_total, 
    'shipping_method':shipping_method,
    'prefill_name':user.first_name,
    'prefill_email':user.email,
    'prefill_phone':profile.phone, 
    'prefill_address': (
    f"{default_address.address_line}, {default_address.city} - {default_address.pincode}"
    if default_address else ""
),
    }
    return render(request,'user/checkout.html',context) 
def new_arrivals(request):
    today=timezone.now().date()
    products=JerseyProduct.objects.filter(is_active=True,created_at__date=today,variants__is_active=True,variants__stock__gt=0).annotate(            min_price=Min(
                'variants__price',
                filter=Q(variants__is_active=True, variants__stock__gt=0)
            ),
            max_price=Max(
                'variants__price',
                filter=Q(variants__is_active=True, variants__stock__gt=0)
            )).prefetch_related(
            Prefetch(
                'variants',
                queryset=JerseyVariant.objects.filter(
                    is_active=True,
                    stock__gt=0
                ).order_by('id'),
                to_attr='active_variants'
            )
        ).distinct().order_by('-created_at')
    context={
        'products':products,
    }
    return render(request,'user/new_arrivals.html',context)