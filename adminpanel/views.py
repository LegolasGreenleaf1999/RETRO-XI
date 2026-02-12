from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from user.models import Customer,Profile,Order,OrderItem,Wallet,ReferralReward
from decimal import Decimal
from product.models import Category,JerseyProduct,ProductImage,Review,Offer,JerseyVariant
from django.core.paginator import Paginator,EmptyPage,PageNotAnInteger
from django.db.models import Q,Avg,Sum,Min,Max,Count
from django.http import JsonResponse 
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required 
from django.views.decorators.cache import never_cache 
from PIL import Image
from django.db import transaction
from product.models import Coupon 
from django.utils import timezone
from .forms import CouponForm,OfferForm
from user.utils import process_referral_reward 
from django.utils.timezone import now
from datetime import timedelta
from django.utils.text import slugify
from .utils import admin_required
from django.utils.dateparse import parse_date
# Create your views here.            
@never_cache
@login_required(login_url='my_login')
def admin_logout(request):
    logout(request) 
    request.session.flush() 
    return redirect('my_login')    
@never_cache
def admin_login(request):
    if request.user.is_authenticated:
        print("DEBUG: Already authenticated, user:", request.user)
        return redirect('dashboard')
    print("DEBUG: Anonymous user attempting login")
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        print(f"DEBUG: email='{email}', password length={len(password) if password else 0}")
        user = authenticate(request, username=email, password=password) 
        print(f"DEBUG: authenticate() returned: {user}")
        if user:
            print(f"DEBUG: user.is_superuser={user.is_superuser}, is_active={user.is_active}")
        if user is not None and user.is_superuser:
            login(request, user)
            print(f"DEBUG AFTER LOGIN - Session keys: {list(request.session.keys())}")
            print(f"DEBUG: _auth_user_id={request.session.get('_auth_user_id')}")
            request.session.set_expiry(0)
            return redirect('dashboard')
        messages.error(request, 'invalid admin credentials', extra_tags='admin')
    return render(request, 'admin/my_login.html')
@never_cache
@admin_required
def user_list(request): 
    if not request.user.is_superuser:
        return redirect('my_login')
    search_query=request.GET.get('search','')
    users=Customer.objects.filter(is_superuser=False).order_by('-id') 
    if search_query:
        users=users.filter(Q(email__icontains=search_query)|Q(first_name__icontains=search_query)) 
    paginator=Paginator(users,5) 
    page=request.GET.get('page') 
    users_page=paginator.get_page(page)
    return render(request,'admin/user_list.html',{'users':users_page,'search_query':search_query}) 
@never_cache
@admin_required
def block_user_ajax(request): 
    if request.method=='POST': 
        user_id=request.POST.get('user_id')
        if request.user.id==int(user_id):
            return JsonResponse({'status':'error','message':'you cannot block yourself'})
        try:
            user=Customer.objects.get(id=user_id) 
        except Customer.DoesNotExist: 
            return JsonResponse({'status':'error','message':'user not found'})        
        user.is_blocked=True 
        user.save() 
        return JsonResponse({'status':'success','message':'user blocked successfully'}) 
    return JsonResponse({'status':'error','message':'invalid request'})
@never_cache
@admin_required
def unblock_user_ajax(request):  
    if request.method=='POST':
        user_id=request.POST.get('user_id')   
        try:
            user=Customer.objects.get(id=user_id)  
        except Customer.DoesNotExist:
            return JsonResponse({'status':'error','message':'user not found'})
        user.is_blocked=False 
        user.save() 
        return JsonResponse({'status':'success','message':'user unblocked successfully'})   
    return JsonResponse({'status':'error','message':'invalid request'})
@never_cache
@admin_required
def admin_dashboard(request): 
    print('admin dashboard view hit') 
    if not request.user.is_superuser:
        return redirect('my_login')
    today=now().date()
    last_30_days=today-timedelta(days=30)
    completed_orders=Order.objects.filter(status='delivered',payment__status='success')
    print("Total orders:", Order.objects.count())
    print("Delivered orders:", Order.objects.filter(status='delivered').count())
    print("Delivered + paid:", Order.objects.filter(status='delivered', payment__status='success').count())
    context={
        'total_revenue':completed_orders.aggregate(total=Sum('total'))['total'] or 0,
        'new_orders':completed_orders.filter(created_at__date__gte=last_30_days).count(),
        'avg_order_value':completed_orders.aggregate(avg=Avg('total'))['avg'] or 0,
        'new_customers':completed_orders.filter(created_at__date__gte=last_30_days).values('user').distinct().count(),
        'recent_orders':completed_orders.order_by('-created_at')[:10],
    }
    return render(request,'admin/dashboard.html',context) 
@never_cache
@admin_required
def admin_category_list(request):  
    search=request.GET.get('search','').strip()    
    categories=Category.objects.annotate(active_product_count=Count('category',filter=Q(category__is_active=True))) 
    if search:      
        categories=categories.filter(name__icontains=search) 
    paginator=Paginator(categories,10) 
    page_number=request.GET.get('page')  
    page_obj=paginator.get_page(page_number)           
    return render(request,'admin/category_list.html',{'page_obj':page_obj,'search':search,})  
def toggle_category(request,id): 
    category=Category.objects.get(id=id) 
    category.is_active=not category.is_active 
    category.save() 
    return redirect('admin_category_list')  
@never_cache
@admin_required
def admin_product_list(request): 
    search=request.GET.get('search','')  
    products = (
        JerseyProduct.objects
        .filter(is_active=True)
        .annotate(
            active_variant_count=Count(
                'variants',
                filter=Q(variants__is_active=True)
            ),
            min_price=Min(
                'variants__price',
                filter=Q(variants__is_active=True)
            ),
            max_price=Max(
                'variants__price',
                filter=Q(variants__is_active=True)
            ),
            total_stock=Sum(
                'variants__stock',
                filter=Q(variants__is_active=True)
            ),
        )
        .filter(active_variant_count__gt=0)  
        .select_related('category')
        .prefetch_related('variants')
        .order_by('-id')
    )
    if search: 
        products=products.filter(
            Q(team__icontains=search) | 
            Q(player_name__icontains=search) | 
            Q(variants__sku__icontains=search) 
        ).distinct()
    paginator=Paginator(products,10)
    page_number=request.GET.get('page') 
    page_obj=paginator.get_page(page_number)    
    return render(request,'admin/product_list.html',{'page_obj':page_obj,'search':search,}) 
@never_cache
@admin_required
def toggle_product(request,id):
    product=get_object_or_404(JerseyProduct,id=id)
    product.is_active=not product.is_active
    product.save()  
    return redirect('product_list')  
def generate_unique_slug(base_slug,exclude_id=None): 
    slug=base_slug
    counter=1
    qs=JerseyProduct.objects.all()
    if exclude_id: 
        qs=qs.exclude(id=exclude_id)
    while qs.filter(slug=slug).exists():
        slug=f'{base_slug}-{counter}'
        counter+=1
    return slug
@never_cache
@admin_required
def add_product(request):
    categories = Category.objects.filter(is_active=True)
    if request.method=='POST': 
        images=request.FILES.getlist('images')  
        main_index=int(request.POST.get('main_index',0))
        if len(images)!=3: 
            messages.error(request,'please upload exactly 3 images',extra_tags='admin')             
            return redirect('add_product') 
        if main_index not in (0,1,2):
            messages.error(request,'invalid main image selection',extra_tags='admin')
            return redirect('add_product')
        team=request.POST.get('team','').strip()
        season=request.POST.get('season','').strip()
        category=get_object_or_404(Category,id=request.POST.get('category'),is_active=True)
        player_name=request.POST.get('player_name','').strip()
        description=request.POST.get('description','').strip()
        raw_slug=request.POST.get('slug','').strip()
        raw_sizes=request.POST.getlist('sizes[]')
        raw_prices=request.POST.getlist('prices[]')
        raw_stocks=request.POST.getlist('stocks[]') 
        is_featured=request.POST.get('is_featured')=='on'
        variants=[]
        for size,price,stock in zip(raw_sizes,raw_prices,raw_stocks):
            if not size or not price or not stock:
                continue
            try:
                variants.append((size,Decimal(price),int(stock)))
            except (ValueError,TypeError):
                messages.error(request,'invalid price or stock value',extra_tags='admin')
                return redirect('add_product')
        if not variants: 
            messages.error(request,'at least 1 variant is required',extra_tags='admin')
            return redirect('add_product')
        for size,_,_ in variants:
            sku = f"{team[:3].upper()}-{season}-{size}-{player_name[:3].upper()}"
            if JerseyVariant.objects.filter(sku=sku).exists():
                messages.error(request,f'Duplicate sku detected:{sku}',extra_tags='admin')
                return redirect('add_product')
        raw_slug = request.POST.get('slug', '').strip()
        auto_slug = slugify("-".join([team, player_name, season]))
        if raw_slug and raw_slug != f"{team}-":
            base_slug = slugify(raw_slug)
        else:
            base_slug = auto_slug
        slug=generate_unique_slug(base_slug)
        with transaction.atomic():
            product=JerseyProduct.objects.create(
                category=category,
                description=description,  
                team=team,             
                season=season,
                player_name=player_name,
                slug=slug,
                is_active=True,
                is_featured=is_featured,
        )
            for size, price, stock in variants:
                sku = f"{team[:3].upper()}-{season}-{size}-{player_name[:3].upper()}"
                JerseyVariant.objects.create(
                product=product,
                sku=sku,
                size=size,
                price=price,
                stock=stock,
            )
        
            product.main_img=images[main_index]
            product.save()
            for i,img in enumerate(images):    
                if i!=main_index:
                    ProductImage.objects.create(jersey=product,img=img)   
        messages.success(request,'product and variant added successfully',extra_tags='admin')    
        return redirect('product_list') 
    return render(request,'admin/add_product.html',{'categories':categories})   
@admin_required  
def add_variant(request,product_id): 
    product=get_object_or_404(JerseyProduct,id=product_id)
    if request.method=='POST':
        size=request.POST.get('size')
        try:
            price = Decimal(request.POST.get('price'))
            stock = int(request.POST.get('stock'))
        except (TypeError, ValueError):
            messages.error(request, "Invalid price or stock",extra_tags='admin')
            return redirect('edit_product', id=product.id)
        is_active = request.POST.get('is_active')
        is_active = True if is_active is None else is_active == '1'
        if not size or not price or not stock:
            messages.error(request,'all variant fields are required',extra_tags='admin')
            return redirect('edit_product',id=product.id)
        if product.variants.filter(size=size).exists():
            messages.error(request,f'Variant for size {size} already exists',extra_tags='admin')
            return redirect('edit_product',id=product.id)
        sku=f'{product.team[:3].upper()}-{product.season}-{size}-{product.id}'
        JerseyVariant.objects.create(product=product,size=size,price=price,stock=stock,sku=sku,is_active=is_active)
        messages.success(request,'variant added successfully',extra_tags='admin')
        return redirect('edit_product',id=product.id)
def resize_image(image): 
    img=Image.open(image)        
    img=img.resize((800,800))   
    img.save(image.path)    
@admin_required
def add_category(request):
    parents=Category.objects.filter(is_active=True,parent__isnull=True)          
    if request.method=='POST': 
        name=request.POST.get('name')
        slug=request.POST.get('slug') 
        description=request.POST.get('description') 
        parent_id=request.POST.get('parent')     
        if not name or not slug:
            messages.error(request,'name and slug are important',extra_tags='admin') 
            return redirect('add_category')      
        if Category.objects.filter(slug=slug).exists():  
            messages.error(request,'category already exists',extra_tags='admin')  
            return redirect('add_category')   
        parent=None 
        if parent_id and parent_id.isdigit():
            parent=Category.objects.get(id=int(parent_id))
        Category.objects.create(name=name,slug=slug,description=description,parent=parent if parent else None) 
        messages.success(request,'category added successfully',extra_tags='admin')
        return redirect('category_list') 
    return render(request,'admin/add_category.html',{'parents':parents})   
@admin_required  
def edit_category(request,id): 
    category=get_object_or_404(Category,id=id)       
    parent_categories=Category.objects.filter(is_active=True).exclude(id=category.id)  
    if request.method=='POST': 
        name=request.POST.get('name')
        slug=request.POST.get('slug') 
        description=request.POST.get('description')
        parent_id=request.POST.get('parent') 
        if not name or not slug: 
            messages.error(request,'name and slug are required',extra_tags='admin') 
            return redirect('edit_category',id=id) 
        if Category.objects.filter(slug=slug).exclude(id=category.id).exists(): 
            messages.error(request,'slug already exists',extra_tags='admin') 
            return redirect('edit_category',id=id)  
        category.name=name 
        category.slug=slug 
        category.description=description  
        if parent_id:
            category.parent=Category.objects.get(id=parent_id)
        else:
            category.parent=None
        category.save() 
        messages.success(request,'category updated successfully',extra_tags='admin') 
        return redirect('category_list')       
    return render(request,'admin/edit_category.html',{'category':category,'parent_categories':parent_categories})    
@admin_required
def edit_product(request,id):
    product=get_object_or_404(JerseyProduct,id=id)
    categories=Category.objects.filter(is_active=True) 
    if request.method=='POST':
        category_id = request.POST.get('category')
        if category_id:
            product.category = Category.objects.get(id=category_id)
        else:
            product.category = None   
        product.team=request.POST.get('team')
        product.season=request.POST.get('season')
        product.player_name=request.POST.get('player_name') 
        raw_slug=request.POST.get('slug','').strip()
        if raw_slug:
            base_slug=slugify(raw_slug)
        else:
            base_slug=slugify(f'{product.team}-{product.player_name}-{product.season}')
        product.slug=generate_unique_slug(base_slug,exclude_id=product.id)
        description = request.POST.get('description')
        product.description = description if description is not None else product.description
        if 'is_active' in request.POST:
            product.is_active = request.POST.get('is_active') == '1'
        if 'cropped_main' in request.FILES: 
            product.main_img=request.FILES['cropped_main'] 
        elif 'main_img' in request.FILES:
            product.main_img=request.FILES['main_img']
        images=request.FILES.getlist('images') 
        if images and len(images)<3:          
            messages.error(request,'minimum 3 images required',extra_tags='admin') 
            return redirect('edit_product',id=id) 
        with transaction.atomic():
            product.save()    
            for img in product.images.all():
                file_key=f'cropped_gallery_{img.id}'   
                if file_key in request.FILES:
                    img.img=request.FILES[file_key]
                    img.save()
            if images:
                ProductImage.objects.filter(jersey=product).delete()
                for img in images: 
                    ProductImage.objects.create(jersey=product,img=img)
        messages.success(request,'product updated successfully',extra_tags='admin')      
        return redirect('product_list') 
    return render(request,'admin/edit_product.html',{'product':product,'categories':categories,'images':product.images.all()}) 
@admin_required
def edit_variant(request,product_id,id):
    product=get_object_or_404(JerseyProduct,id=product_id)
    variant=get_object_or_404(JerseyVariant,id=id,product=product)
    if request.method=='POST': 
        try:
            variant.price=request.POST.get('price')
            variant.stock=int(request.POST.get('stock',0))
            variant.is_active=request.POST.get('is_active')=='1'
            variant.save()
            messages.success(request,'variant updated successfully',extra_tags='admin')
        except Exception:
            messages.success(request,'failed to update variant',extra_tags='admin')
    return redirect('edit_product',id=product.id)
@admin_required
def delete_variant(request,product_id,id): 
    variant=get_object_or_404(JerseyVariant,id=id)
    product=variant.product
    if product.variants.count()==1:
        messages.error(request,'a product must have at least 1 variant',extra_tags='admin')
        return redirect('edit_product',id=product.id)
    variant.delete()
    messages.success(request,'variant deleted successfully',extra_tags='admin')
    return redirect('edit_product',id=product.id)
@never_cache
@admin_required 
def admin_review_dashboard(request):
    status=request.GET.get('status','all')       
    search=request.GET.get('q','')
    reviews=Review.objects.select_related('product','user')
    if status=='approved':
        reviews=reviews.filter(is_approved=True)  
    elif status=='pending':
        reviews=reviews.filter(is_approved=False)
    if search:
        reviews=reviews.filter(
            Q(product__team__icontains=search)|
            Q(product__season__icontains=search)|
            Q(product__player_name__icontains=search)|
            Q(user__email__icontains=search)
        )
    total_reviews=Review.objects.count() 
    approved_reviews=Review.objects.filter(is_approved=True).count() 
    pending_reviews=Review.objects.filter(is_approved=False).count()
    avg_rating=(Review.objects.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg']) or 0 
    paginator=Paginator(reviews,10)
    page_number=request.GET.get('page')
    page_obj=paginator.get_page(page_number)
    context={
        'reviews':page_obj, 
        'status':status,
        'search':search,
        'total_reviews':total_reviews,
        'approved_reviews':approved_reviews,
        'pending_reviews':pending_reviews,
        'avg_rating':round(avg_rating,1),
        'page_obj':page_obj,
    }
    return render(request,'admin/reviews.html',context) 
@never_cache
@admin_required
def coupon_list(request):
    query=request.GET.get('q','').strip()
    coupons=Coupon.objects.all().order_by('-id')
    if query:
        coupons=coupons.filter(code__icontains=query)
    paginator=Paginator(coupons,10)
    page_number=request.GET.get('page')
    page_obj=paginator.get_page(page_number)
    return render(request,'admin/coupons.html',{'coupons':page_obj,'page_obj':page_obj,'query':query})
def toggle_coupon(request,coupon_id):
    coupon=get_object_or_404(Coupon,id=coupon_id)
    coupon.is_active=not coupon.is_active
    coupon.save()
    return redirect('coupon_list')
@never_cache
@admin_required
def add_coupon(request): 
    if request.method=='POST': 
        form=CouponForm(request.POST)
        if form.is_valid():
            form.save() 
            return redirect('coupon_list')   
    else:
        form=CouponForm()
    return render(request,'admin/add_coupon.html',{'form':form})
@never_cache
@admin_required
def admin_orders_dashboard(request):
    search_query=request.GET.get('search','')
    status_filter=request.GET.get('status','')  
    payment_method=request.GET.get('payment_method','')
    date_from=request.GET.get('date_from','')
    date_to=request.GET.get('date_to','')
    min_amount=request.GET.get('min_amount','')
    max_amount=request.GET.get('max_amount','')
    orders=Order.objects.select_related('user').prefetch_related('item').order_by('-created_at')
    if search_query:
        orders=orders.filter(Q(id__icontains=search_query)|Q(email__icontains=search_query)|Q(first_name__icontains=search_query))
    if status_filter:
        orders=orders.filter(status=status_filter)
    if payment_method:
        orders=orders.filter(payment_method=payment_method) 
    if date_from:
        orders=orders.filter(created_at__date__gte=parse_date(date_from))
    if date_to:
        orders=orders.filter(created_at__date__lte=parse_date(date_to)) 
    if min_amount:
        orders=orders.filter(total__gte=min_amount)
    if max_amount:
        orders=orders.filter(total__lte=max_amount)
    paginator=Paginator(orders,10)
    page_number=request.GET.get('page') 
    page_obj=paginator.get_page(page_number)
    context={
        'orders':page_obj,
        'search_query':search_query,
        'status_filter':status_filter,
        'payment_method':payment_method,
        'date_from':date_from,
        'date_to':date_to,
        'min_amount':min_amount,
        'max_amount':max_amount, 
        'status_choices':Order.STATUS_CHOICES, 
        'payment_method_choices':Order.PAYMENT_CHOICES,

    }
    return render(request,'admin/order_list.html',context)
@admin_required
def admin_order_cancel(request,order_id):
    order=get_object_or_404(Order,pk=order_id)
    if request.method=='POST':
        if order.status=='cancelled':
            messages.warning(request,'this order is already cancelled',extra_tags='admin') 
        else:
            order.status='cancelled'
            order.save()
            messages.success(request,'order cancelled successfully',extra_tags='admin')
        return redirect('order_list')
@admin_required
def order_detail(request,order_id):
    order=get_object_or_404(Order,id=order_id)     
    order_items=order.item.select_related('product')  
    context={
        'order':order,
        'order_items':order_items,
    }
    return render(request,'admin/orderdetails.html',context)
@admin_required
def order_edit(request,order_id): 
    order=get_object_or_404(Order,id=order_id)
    old_status=order.status
    if request.method=='POST':
        new_status=request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status=new_status
            order.save()
            if old_status!='delivered' and new_status=='delivered': 
                process_referral_reward(order)
            messages.success(request,'order status updated successfully',extra_tags='admin')
            return redirect('order_detail',order_id=order.id)
        else:
            messages.error(request,'invalid status selected',extra_tags='admin')
    context={
        'order':order,
        'status_choices':Order.STATUS_CHOICES,
    }
    return render(request,'admin/orderdetails.html',context) 
@admin_required
def approve_return(request,item_id): 
    item=get_object_or_404(OrderItem,id=item_id,return_status='requested') 
    with transaction.atomic():
        item.return_status='approved'
        item.returned_at=timezone.now() 
        item.save()
        variant=item.variant
        if variant:
            variant.stock+=item.quantity
            variant.save()
    messages.success(request,'return approved and stock updated',extra_tags='admin')
    return redirect('admin_returns')
@admin_required
def reject_return(request,item_id):
    item=get_object_or_404(OrderItem,id=item_id,return_status='requested') 
    item.return_status='rejected'
    item.save() 
    messages.warning(request,'return request rejected',extra_tags='admin')
    return redirect('admin_returns')
@never_cache
@admin_required
def admin_returns(request): 
    status=request.GET.get('status')
    returns_qs=OrderItem.objects.exclude(return_status='none').select_related('order','order__user','product').order_by('-returned_at')
    if status:
        returns_qs=returns_qs.filter(return_status=status)
    paginator=Paginator(returns_qs,10)
    page=request.GET.get('page')
    try:
        returns=paginator.page(page)
    except PageNotAnInteger:
        returns=paginator.page(1)
    except EmptyPage:
        returns=paginator.page(paginator.num_pages)
    context={
        'returns':returns,
        'status':status,
        'total_requests':returns_qs.count(),
        'pending_count':returns_qs.filter(return_status='requested').count(),
        'approved_count':returns_qs.filter(return_status='approved').count(),
        'rejected_count':returns_qs.filter(return_status='rejected').count(),
        'refunded_count':returns_qs.filter(return_status='refunded').count(),
    }
    return render(request,'admin/returns.html',context)
@admin_required
def refund_to_wallet(request,item_id):
    item=get_object_or_404(OrderItem,id=item_id,return_status='approved')
    user=item.order.user
    wallet,created=Wallet.objects.get_or_create(user=user) 
    refund_amount=(item.price-item.discount)*item.quantity 
    refund_amount=Decimal(refund_amount)
    if wallet.deposit(refund_amount): 
        item.return_status='refunded' 
        item.returned_at=timezone.now() 
        item.save()
        messages.success(request,f'Rs.{refund_amount} refunded to {user.first_name} wallet',extra_tags='admin') 
    else: 
        messages.error(request,'wallet refund failed',extra_tags='admin')
    return redirect('admin_returns')
def approve_referral_reward(referral): 
    referral.status='approved'
    referral.save()
def credit_referral_reward(referral):
    wallet=referral.referrer.wallet
    wallet.deposit(referral.reward_amount)
    referral.status='created' 
    referral.save()
@never_cache
@admin_required
def admin_offers(request):
    today=now().date()
    search=request.GET.get('q','')
    offers=Offer.objects.all().order_by('-start_date')
    if search:
        offers=offers.filter(name__icontains=search)
    total_offers=offers.count()
    active_offers=offers.filter(status='active').count()
    scheduled_offers=offers.filter(status='scheduled').count()
    expired_offers=offers.filter(status='expired').count()
    paginator=Paginator(offers,10)
    page_number=request.GET.get('page')
    page_obj=paginator.get_page(page_number)
    context={
        'offers':page_obj,
        'total_offers':total_offers,
        'active_offers':active_offers,
        'scheduled_offers':scheduled_offers,
        'expired_offers':expired_offers,
        'search':search,
    }
    return render(request,'admin/offers.html',context)
@admin_required
def create_offer(request):
    if request.method=='POST':
        form=OfferForm(request.POST)
        if form.is_valid():
            offer=form.save(commit=False)
            today=now().date()
            if offer.is_active and offer.start_date<=today<=(offer.end_date or today): 
                offer.status='active'
            elif offer.start_date>today:
                offer.status='scheduled'
            else:
                offer.status='expired'
            offer.save()
            messages.success(request,'offer created successfully',extra_tags='admin')
            return redirect('admin_offers')
    else:
        form=OfferForm()
    return render(request,'admin/create_offer.html',{'form':form}) 
@admin_required
def edit_offer(request,offer_id):
    offer=get_object_or_404(Offer,id=offer_id)
    if request.method=='POST': 
        form=OfferForm(request.POST,instance=offer)
        if form.is_valid():
            form.save()
            return redirect('admin_offers')
    else:
        form=OfferForm(instance=offer) 
    return render(request,'admin/edit_offer.html',{'form':form,'offer':offer})
@admin_required
def delete_offer(request,offer_id):
    offer=get_object_or_404(Offer,id=offer_id) 
    offer.delete() 
    return redirect('admin_offers')
@never_cache
@admin_required
def referral_admin_dashboard(request):
    search_query=request.GET.get('q','').strip()
    referral_qs=(ReferralReward.objects.select_related('referrer','referred_user','order').order_by('-created_at')) 
    if search_query:
        referral_qs=referral_qs.filter(
            Q(referrer__username__icontains=search_query)|
            Q(referrer__email__icontains=search_query)|
            Q(referred_user__username__icontains=search_query)|
            Q(referred_user__email__icontains=search_query)|
            Q(referrer__referral_code__icontains=search_query)
        )
    paginator=Paginator(referral_qs,10)
    page_number=request.GET.get('page')
    referrals=paginator.get_page(page_number)
    total_referrers=(Customer.objects.filter(referrals__isnull=False).distinct().count())
    successful_referrals=ReferralReward.objects.filter(status='credited').count()
    total_rewards=(ReferralReward.objects.filter(status='credited').aggregate(total=Sum('reward_amount')))['total'] or 0
    pending_rewards=(ReferralReward.objects.filter(status='pending').aggregate(total=Sum('reward_amount')))['total'] or 0
    context={ 
        'referrals':referrals,
        'total_referrers':total_referrers,
        'successful_referrals':successful_referrals,
        'total_rewards':total_rewards,
        'pending_rewards':pending_rewards,
    }
    return render(request,'admin/referral.html',context)