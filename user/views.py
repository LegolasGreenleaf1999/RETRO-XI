from django.shortcuts import render,redirect 
from django.contrib.auth.hashers import make_password,check_password
from django.contrib.auth import login,authenticate,logout
from django.contrib.auth import update_session_auth_hash
from .forms import SignupForm,ReturnItemForm 
from django.core.mail import send_mail 
from django.utils import timezone 
from datetime import timedelta
import random  
from django.db import transaction
from .models import Profile,Address,PasswordChangeOTP,EmailChangeOTP,OTP,Wishlist 
from product.models import JerseyProduct,Coupon,JerseyVariant     
from django.dispatch import receiver 
from django.shortcuts import get_object_or_404             
from django.db.models.signals import post_save  
from .models import Customer,Profile,Wallet,Address,Order,OrderItem
from django.contrib import messages 
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse  
from django.views.decorators.http import require_GET 
from django.views.decorators.cache import never_cache     
from decimal import Decimal     
from datetime import timedelta
from django.core.exceptions import ValidationError 
from django.contrib.auth.password_validation import validate_password
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,Spacer,TableStyle
from PIL import Image
import re 
from django.core.paginator import Paginator
from .utils import generate_referral_code,user_only
from payments.models import Payment
from django.views.decorators.csrf import csrf_protect
from django.db.models import Min,Max,Q,Prefetch
from django.core.validators import validate_email
# Create your views here.     
@never_cache
def user_logout(request):     
    logout(request)   
    request.session.flush()       
    return redirect('login')             
@never_cache
@login_required 
@user_only
def wallet_page(request):
    wallet,_=Wallet.objects.get_or_create(user=request.user)
    transactions=(wallet.transaction_set.all().order_by('-created_at') if hasattr(wallet,'transaction_set') else [])  
    context={
        'wallet':wallet,  
        'transactions':transactions,
        'balance':wallet.balance,
    }   
    return render(request,'user/wallet.html',context)     
@login_required            
def verify_password_otp(request):  
    print("Session keys:", list(request.session.keys()))      
    print("new_password:", repr(request.session.get('new_password')))
    print("Session exists:", bool(request.session.session_key))
    print("All session keys:", list(request.session.keys()))      
    print("new_password value:", request.session.get('new_password'))
    if request.method=='POST':
        user_otp=request.POST.get('otp','').strip()  
        try:
            record=PasswordChangeOTP.objects.filter(user=request.user,otp=user_otp).latest('created_at')  
        except PasswordChangeOTP.DoesNotExist:
            messages.error(request,'invalid otp') 
            return redirect('passotp')   
        if record.is_expired():      
            messages.error(request,'otp expired')
            return redirect('changepassword')      
        new_password=request.session.get('new_password')    
        new_password = request.session.get('new_password')
        if new_password:
            request.user.set_password(new_password)
        else:
            messages.error(request, 'No new password found in session')
            return redirect('passotp')
        request.user.save()         
        print("NEW PASSWORD FROM SESSION:", request.session.get('new_password'))
        print("STORED PASSWORD HASH:", request.user.password)
        update_session_auth_hash(request,request.user)  
        del request.session['new_password']
        record.delete() 
        messages.success(request,'password changed')     
        return redirect('profile') 
    return render(request,'user/passotp.html')    
@never_cache
@login_required
def verify_email_otp(request):
    if request.method=='POST':
        user_otp=request.POST.get('otp','').strip()       
        try:
            record=EmailChangeOTP.objects.filter(
                user=request.user,
                otp=user_otp
            ).latest('created_at') 
        except EmailChangeOTP.DoesNotExist:
            messages.error(request,'invalid otp') 
            return redirect('emailotp') 
        if record.is_expired():
            messages.error(request,'otp expired. please request a new one')  
            record.delete() 
            return redirect('changeemail')  
        request.user.email=record.new_email  
        request.user.username = record.new_email         
        request.user.save()
        record.delete()     
        messages.success(request,'email updated successfully')   
        return redirect('profile')   
    return render(request,'user/emailotp.html')         
@login_required
@user_only
def change_email(request): 
    if request.method=='POST':  
        new_email=request.POST.get('new_email')  
        confirm_email=request.POST.get('confirm_email')  
        if new_email!=confirm_email:
            messages.error(request,'new email and confirm email do not match') 
            return redirect('changeemail') 
        otp=f'{random.randint(100000,999999)}'
        expires=timezone.now()+timedelta(minutes=10)          
        EmailChangeOTP.objects.create(
            user=request.user,
            new_email=new_email,
            otp=otp,
            expires_at=expires
        ) 
        send_mail(
            subject='Your email change OTP', 
            message=f'OTP for changing your email is {otp}', 
            from_email='ashwincsanthosh@gmail.com', 
            recipient_list=[new_email], 
            fail_silently=False,
        )           
        messages.success(request,'OTP has been sent to your email') 
        return redirect('emailotp')
    return render(request,'user/changeemail.html')
@never_cache
@login_required
@require_GET
@user_only
def address_detail(request,id):                                                             
    addr=get_object_or_404(Address,id=id,user=request.user)  
    return JsonResponse({
        'id':addr.id,  
        'address_line':addr.address_line,
        'city':addr.city,
        'pincode':addr.pincode,
        'is_default':addr.is_default
    }) 
@never_cache
@login_required
@user_only
def profile(request):       
    user=request.user  
    profile,created=Profile.objects.get_or_create(user=user)  
    default_address=(Address.objects.filter(user=user,is_default=True).first())        
    context={
        'user':user,
        'profile':profile,
        'default_address':default_address
    }
    return render(request,'user/profile.html',context)   
@never_cache
@login_required
@user_only
def edit_profile(request): 
    profile,created=Profile.objects.get_or_create(user=request.user)  
    if request.method=='POST':
        first_name=request.POST.get('first_name')
        name_error=is_valid_name(first_name)
        if name_error:
            return render(request,'user/editprofile.html',{'profile':profile,'error':name_error})   
        request.user.first_name=first_name.strip() 
        request.user.save()
        profile.phone=request.POST.get('phone')  
        profile.address=request.POST.get('address') 
        try: 
            profile.full_clean() 
        except ValidationError as e:
            return render(
                request, 
                'user/editprofile.html',
                {
                    'profile':profile, 
                    'error':e.message_dict.get('phone',['invalid phone number'])[0]
                }
            )
        if 'profile_image' in request.FILES:
            image=request.FILES['profile_image']
            try: 
                img=Image.open(image)
                img.verify()
            except Exception:
                return render(request,'user/editprofile.html',{'profile':profile,'error':'only image files are allowed(jpg,png,...)'})
            profile.profile_image=image
        profile.save() 
        return redirect('profile')
    return render(request,'user/editprofile.html',{'profile':profile}) 
@never_cache
@login_required
@user_only
def addresses(request): 
    addresses=Address.objects.filter(user=request.user)          
    return render(request,'user/addresses.html',{'addresses':addresses}) 
@never_cache
@login_required
@user_only
def add_address(request):
    if request.method=='POST':
        address_line=request.POST.get('address_line') 
        city=request.POST.get('city')
        pincode=request.POST.get('pincode')
        is_default=request.POST.get('is_default')=='on'    
        if is_default:
            Address.objects.filter(user=request.user).update(is_default=False)    
        addr=Address.objects.create(
            user=request.user,
            address_line=address_line,
            city=city,
            pincode=pincode,
            is_default=is_default
        )    
        return JsonResponse({'status':'success','message':'address added'}) 
    return JsonResponse({'status':'error','message':'invalid request'}) 
@never_cache
@login_required
@user_only
def edit_address(request,id):           
    addr=get_object_or_404(Address,id=id,user=request.user) 
    if request.method=='POST':
        addr.address_line=request.POST.get('address_line')  
        addr.city=request.POST.get('city') 
        addr.pincode=request.POST.get('pincode')        
        make_default=request.POST.get('is_default')=='on'          
        if make_default:
            Address.objects.filter(user=request.user).update(is_default=False)         
            addr.is_default=True 
        addr.save() 
        return JsonResponse({'status':'success','message':'address updated'})
    return JsonResponse({'status':'error','message':'invalid request'})           
@never_cache  
@login_required  
def delete_address(request,id):
    addr=get_object_or_404(Address,id=id,user=request.user)         
    addr.delete() 
    return JsonResponse({'status':'success','message':'address deleted'})

@never_cache
def home_view(request):
    featured_products = (
        JerseyProduct.objects
        .filter(
            is_active=True,
            is_featured=True,
            variants__is_active=True,
            variants__stock__gt=0
        )
        .annotate(
            min_price=Min(
                'variants__price',
                filter=Q(variants__is_active=True, variants__stock__gt=0)
            ),
            max_price=Max(
                'variants__price',
                filter=Q(variants__is_active=True, variants__stock__gt=0)
            )
        )
        .prefetch_related(
            Prefetch(
                'variants',
                queryset=JerseyVariant.objects.filter(
                    is_active=True,
                    stock__gt=0
                ).order_by('id'),
                to_attr='active_variants'
            )
        )
        .distinct()
        .order_by('-created_at')[:8]
    )

    return render(request, 'user/home.html',{'featured_products':featured_products})

@never_cache
def forgot_pass(request):
    if request.method=='POST':
        email=request.POST.get('email') 
        user=Customer.objects.filter(email=email).first() 
        if user:
            otp=random.randint(100000,999999) 
            request.session['email']=email  
            request.session['otp']=str(otp) 
            request.session['forgotpassword']=True
            send_mail(
                subject='Password Reset OTP',
                message=f'Your OTP is {otp}',  
                from_email='ashwincsanthosh@gmail.com',
                recipient_list=[email],
            ) 
            messages.success(request,'OTP sent to email') 
            return redirect('otp') 
        else:
            messages.error(request,'email not registered!')
    return render(request,'user/forgotpassword.html')  
def is_valid_name(name):
    if not name:
        return 'name cannot be empty'
    name=name.strip()
    if len(name)<2:
        return 'name must be at least 2 characters long'
    if not re.match(r'^[A-Za-z ]+$',name):
        return 'name can contain only letters and spaces'
    return None
def validate_email_format(email):
    try:
        validate_email(email)
    except ValidationError:
        return 'enter a valid email address'
    return None
def is_strong_password(password): 
    if not re.search(r'[A-Z]',password):
        return 'password must contain at least one uppercase character'
    if not re.search(r'[0-9]',password):
        return 'password must contain at least one number'
    if not re.search(r'[#@$!%*?&]',password):
        return 'password must contain at least one special character'
@never_cache
def signup_view(request):
    if request.method=='POST':
        referral_input=request.POST.get('referral_code')
        fullname=request.POST.get('fullname')
        email=request.POST.get('email')
        name_error=is_valid_name(fullname)
        if name_error:
            messages.error(request,name_error) 
            return render(request,'user/register.html')
        email_error=validate_email_format(email)
        if email_error:
            messages.error(request,email_error)
            return render(request,'user/register.html')
        password=request.POST.get('password')
        confirm_password=request.POST.get('confirm_password')
        if password!=confirm_password:
            messages.error(request,'passwords do not match!')
            return render(request,'user/register.html')
        if Customer.objects.filter(email=email).exists():
            messages.error(request,'email already exists!') 
            return render(request,'user/register.html')  
        try:
            validate_password(password)
        except ValidationError as e:
            for error in e.messages: 
                messages.error(request,error) 
            return render(request,'user/register.html')
        error=is_strong_password(password) 
        if error: 
            messages.error(request,error)      
            return render(request,'user/register.html')
        user=Customer.objects.create_user(
            username=email,
            email=email,
            password=password
        ) 
        user.first_name=fullname  
        user.referral_code=generate_referral_code()
        if referral_input: 
            referrer=Customer.objects.filter(referral_code=referral_input).first()
            if referrer:
                if referrer!=user:
                    user.referred_by=referrer
                else: 
                    messages.warning(request,'you cannot refer yourself!')
            else:
                messages.warning(request,'invalid referral code ignored')
        user.save()
        otp=random.randint(100000,999999) 
        request.session['email']=email
        request.session['otp']=str(otp) 
        request.session['forgotpassword']=False 
        send_mail(
            subject='Your OTP Code',
            message=f'Your OTP is {otp}',
            from_email='ashwincsanthosh@gmail.com', 
            recipient_list=[email],
            fail_silently=False,
        )
        messages.success(request,'account created successfully!') 
        return redirect('otp')
    return render(request,'user/register.html')      
@never_cache
def verify_otp(request):
    if request.method=='POST':
        entered_otp=request.POST.get('otp')  
        session_otp=request.session.get('otp')  
        print("Entered OTP:", entered_otp)
        print("Session OTP:", session_otp)
        if entered_otp==session_otp:
            messages.success(request,'otp verified successfully!')  
            if request.session.get('forgotpassword')==True:
                email=request.session.get('email')  
                request.session['email']=email
                return redirect('resetpassword')
            return redirect('login')
        messages.error(request,'invalid otp. please try again') 
        return redirect('otp')
    return render(request,'user/otp.html') 
@csrf_protect
@never_cache
def login_view(request):   
    if request.method=='POST': 
        email=request.POST.get('email')
        password=request.POST.get('password') 
        print(f"email: {email} pass: {password}")
        user=authenticate(request,username=email,password=password)  
        if user:
            login(request,user) 
            messages.success(request,'login successful!')  
            return redirect('home') 
        messages.error(request,'invalid email or password!')  
    return render(request,'user/login.html') 
@never_cache
def send_otp(request):
    otp=random.randint(100000,999999)
    return HttpResponse(str(otp)) 
@never_cache
@login_required
def create_profile(sender,instance,created,**kwargs):
    if created:
        Profile.objects.create(user=instance)    
@never_cache
@login_required
def reset_pass(request):
    email=request.session.get('email')   
    print('reset password email from session=',email)
    if not email:
        messages.error(request,'session expired, please try again')  
        return redirect('forgotpassword')
    if request.method=='POST':
        new_password=request.POST.get('password1')  
        confirm_password=request.POST.get('password2')           
        print('new password=',new_password)        
        print('confirm password=',confirm_password)
        if new_password!=confirm_password:
            messages.error(request,'passwords do not match!') 
            return redirect('resetpassword')
        user=Customer.objects.get(email=email)      
        print('user found=',user.email)                
        print('old password hash=',user.password)
        user.set_password(new_password) 
        user.save()          
        print('new password check=',user.check_password(new_password))    
        print('new passowrd hash=',user.password)              
        request.session.pop('email',None)
        request.session.pop('otp',None)   
        request.session.pop('forgotpassword',None)
        messages.success(request,'password updated successfully')  
        return redirect('login')  
    return render(request,'user/resetpassword.html') 
def resend_otp(request):
    if request.method=='POST': 
        print('resend otp endpoint hit')
        otp=random.randint(100000,999999)      
        print('generated otp:',otp)
        request.session['otp']=str(otp)  
        email=request.session.get('email')
        print('sending otp to email')
        if not email:
            return JsonResponse({'message':'email not found in session'},status=400)
        send_mail(
            subject='new otp code',
            message=f'your new otp is {otp}', 
            from_email='ashwincsanthosh@gmail.com', 
            recipient_list=[email],
            fail_silently=False, 
        )
        return JsonResponse({'message':'a new otp has been sent'})  
    print('non post request received')
    return JsonResponse({'error':'invalid request'},status=400)  
@never_cache 
@login_required
@user_only
def wishlist_view(request):
    wishlist_items=Wishlist.objects.filter(user=request.user).select_related('jersey').prefetch_related('jersey__variants')
    for item in wishlist_items: 
        item.default_variant=(item.jersey.variants.filter(is_active=True,stock__gt=0).first())
    return render(request,'user/wishlist.html',{'wishlist_items':wishlist_items})  
@never_cache
@login_required 
def toggle_wishlist(request,jersey_id):
    jersey=get_object_or_404(JerseyProduct,id=jersey_id)   
    wishlist_item,created=Wishlist.objects.get_or_create(
        user=request.user,
        jersey=jersey
    ) 
    if not created: 
        wishlist_item.delete()
        messages.info(request,'removed from the wishlist') 
    else:
        messages.success(request,'added to wishlist')
    return redirect(request.META.get('HTTP_REFERER','wishlist')) 
@never_cache
@login_required
def order_confirmation(request,order_uuid):
    order=get_object_or_404(Order,pk=order_uuid,user=request.user) 
    items=order.item.select_related('product')  
    request.session.pop('cart', None)
    request.session.pop('coupon_id', None)
    request.session.pop('referral_discount', None)
    request.session.modified = True
    context={
        'order':order,
        'items':items,
        'subtotal':order.subtotal,
        'shipping':order.shipping, 
        'tax':order.tax, 
        'total':order.total, 
        'payment_method':order.payment_method,
    }
    return render(request,'user/confirmation.html',context) 
@login_required
def apply_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').strip()

        try:
            coupon = Coupon.objects.get(code__iexact=code, is_active=True)

            if coupon.expires_at and coupon.expires_at < timezone.now():
                raise Exception("This coupon has expired")

            cart = request.session.get('cart', {})
            subtotal = Decimal('0.00')

            for variant_id, item in cart.items():
                variant = JerseyVariant.objects.get(id=variant_id)
                subtotal += variant.price * item['qty']

            if subtotal < coupon.min_order_value:
                raise Exception(
                    f"Minimum order value ₹{coupon.min_order_value} required"
                )

            # ✅ SAVE COUPON
            request.session['coupon_id'] = coupon.id
            request.session.modified = True

            print("COUPON SAVED:", coupon.code)

        except Coupon.DoesNotExist:
            request.session['coupon_error'] = "Invalid coupon code"

        except Exception as e:
            request.session['coupon_error'] = str(e)

    return redirect('cart')
@login_required
def remove_coupon(request):
    request.session.pop('coupon_id',None)
    return redirect('cart')
@never_cache
@login_required
def order_detail_view(request,order_uuid):
    order=get_object_or_404(Order,pk=order_uuid,user=request.user)
    order_items=OrderItem.objects.filter(order=order)
    subtotal=Decimal('0.00')
    for item in order_items:
        subtotal+=item.price*item.quantity
    shipping=order.shipping if order.shipping else Decimal('0.00') 
    tax=order.tax if order.tax else subtotal*Decimal('0.08') 
    grand_total=subtotal+shipping+tax 
    estimated_delivery=order.created_at+timedelta(days=order.delivery_days)
    context={
        'order':order,
        'order_items':order_items,
        'subtotal':subtotal,
        'shipping':shipping,
        'tax':tax,
        'grand_total':grand_total,
        'estimated_delivery':estimated_delivery,
    }
    return render(request,'user/orderdetails.html',context)
@never_cache
@login_required
def download_invoice(request,order_uuid):
    order=get_object_or_404(Order,pk=order_uuid,user=request.user)
    order_items=order.item.select_related('product','variant')
    response=HttpResponse(content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="Invoice_{order.id}.pdf"'
    doc=SimpleDocTemplate(response,pagesize=A4,topmargin=40,bottommargin=40,rightmargin=40,leftmargin=40)
    styles=getSampleStyleSheet()
    elements=[]
    elements.append(Paragraph(f'<b>Invoice-Order #{order.id}</b>',styles['Title']))
    elements.append(Spacer(1,12))
    info_table=Table([
        ['Order id:',str(order.id)],
        ['Order date:',order.created_at.strftime('%d %b %Y')],
        ['Customer:',order.first_name],
        ['Email:',order.email],
        ['Delivery type:',order.delivery_type],
        ['Status:',order.status],
    ],colWidths=[2.5*inch,3.5*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1,20))
    data=[['Product','Size','Quantity','Unit Price','Total']]
    for item in order_items:
        variant=item.variant
        size=variant.get_size_display() if variant else '-'
        line_total=item.price*item.quantity
        data.append([
            str(item.product),
            size,
            str(item.quantity),
            f'Rs.{item.price}',
            f'Rs.{line_total}',
        ])
    items_table=Table(data,colWidths=[2.5 * inch, 1 * inch, 1 * inch, 1.2 * inch, 1.3 * inch]) 
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1,20))
    summary_table=Table([
        ['Subtotal',f'Rs.{order.subtotal}'],
        ['Shipping',f'Rs.{order.shipping}'],
        ['Tax',f'Rs.{order.tax}'],
        ['Grand total',f'Rs.{order.total}'],
    ],colWidths=[3*inch,3*inch])
    summary_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1,20))
    elements.append(Paragraph('<b>Shipping address</b>',styles['Heading3']))
    elements.append(Paragraph(order.address.replace('\n','<br/>'),styles['Normal']))
    doc.build(elements)
    return response
@login_required
def cancel_order(request,order_uuid): 
    order=get_object_or_404(Order,pk=order_uuid,user=request.user)
    if order.status in ['shipped','delivered','cancelled']: 
        messages.error(request,'this order cannot be cancelled')
        return redirect('orderdetails',order_uuid=order.pk)
    if request.method=='POST':
        with transaction.atomic():
            if order.stock_deducted:
                for item in order.item.select_related('variant'):
                    variant=item.variant
                    if variant:
                        variant.stock+=item.quantity
                        variant.save()   
                order.stock_deducted=False
                order.save()
            payment=Payment.objects.filter(order=order,status='success').first()
            if payment and payment.status!='refunded': 
                wallet,_=Wallet.objects.get_or_create(user=request.user)
                wallet.deposit(payment.amount)
                payment.status='refunded'
                payment.save()
            order.status='cancelled'
            order.save()
        messages.success(request,'your order has been cancelled successfully. refund is credited to your wallet')
        return redirect('orderdetails',order_uuid=order.pk)
    messages.warning(request,'invalid request')
    return redirect('orderdetails',order_id=order.id) 
@login_required
def cancel_order_item(request,item_id):
    item=get_object_or_404(OrderItem,id=item_id,order__user=request.user)
    order=item.order
    if order.status in ['shipped','cancelled','delivered']:
        messages.error(request,'this item cannot be cancelled')
        return redirect('orderdetails',order__uuid=order.pk)
    if item.cancelled:
        messages.warning(request,'item already cancelled')  
        return redirect('orderdetails',order__uuid=order.pk)
    if request.method=='POST':
        with transaction.atomic():
            if order.stock_deducted and item.variant: 
                variant=item.variant
                variant.stock+=item.quantity
                variant.save() 
            payment=Payment.objects.filter(order=order,status='success').first()
            if payment:
                refund_amount=item.price*item.quantity
                wallet,_=Wallet.objects.get_or_create(user=request.user)
                wallet.deposit(refund_amount) 
            item.cancelled=True
            item.save()
            remaining_items=order.item.filter(cancelled=False)
            if not remaining_items.exists():
                order.status='cancelled'
                order.stock_deducted=False
                order.save()
        messages.success(request,'item cancelled successfully. refund credited to your wallet')
        return redirect('orderdetails',order_uuid=order.pk)
    messages.warning(request,'invalid request')
    return redirect('orderdetails',order_uuid=order.pk)
@login_required
def return_item(request,item_id):
    item=get_object_or_404(OrderItem,id=item_id,order__user=request.user)
    order=item.order
    if order.status!='delivered':
        messages.error(request,'items can only be returned after order is delivered')
        return redirect('orderdetails',order_id=order.id)
    if item.return_status!='none':
        messages.warning(request,'this item already has a return request') 
        return redirect('orderdetails',order_id=order.id)
    if request.method=='POST':
        form=ReturnItemForm(request.POST)
        if form.is_valid():
            reason=form.cleaned_data['reason']
            notes=form.cleaned_data.get('notes','')
            item.return_status='requested' 
            item.returned_at=timezone.now()
            item.return_reason=f'{reason}:{notes}' if notes else reason 
            item.save()
            messages.success(request,f'{item.product} has been marked for return')
        else:
            messages.error(request,'please select a valid reason')
    return redirect('orderdetails',order_uuid=order.id) 
@login_required
@user_only
def my_orders(request):
    orders_list=Order.objects.filter(user=request.user).prefetch_related('item__product').order_by('-created_at')
    paginator=Paginator(orders_list,5)
    page_number=request.GET.get('page') 
    orders=paginator.get_page(page_number)
    context={
        'orders':orders
    }
    return render(request,'user/orderhistory.html',context)
@never_cache
@login_required
def verify_old_password(request): 
    if request.method=='POST':
        old_password=request.POST.get('old_password','').strip()
        if not old_password:
            messages.error(request,'please enter your old password')
            return redirect('verify_old_password')
        if not request.user.check_password(old_password): 
            messages.error(request,'old password is incorrect') 
            return redirect('verify_old_password') 
        request.session['password_verified']=True 
        return redirect('set_new_password')
    return render(request,'user/verify_old_password.html')
@never_cache
@login_required
def set_new_password(request): 
    if not request.session.get('password_verified'):
        messages.error(request,'please verify your old password first')
        return redirect('verify_old_password')  
    if request.method=='POST': 
        new1=request.POST.get('newpassword1','').strip() 
        new2=request.POST.get('newpassword2','').strip()
        if not new1 or not new2: 
            messages.error(request,'all fields are required') 
            return redirect('set_new_password')
        if new1!=new2: 
            messages.error(request,'new passwords do not match') 
            return redirect('set_new_password') 
        try:
            validate_password(new1,request.user)
        except ValidationError as e: 
            for error in e: 
                messages.error(request,error)
            return redirect('set_new_password')
        user=request.user
        user.set_password(new1)
        user.save()
        del request.session['password_verified']  
        messages.success(request,'password changed successfully, please log in again') 
        return redirect('login')
    return render(request,'user/changepassword.html')
@login_required
def refer_and_earn(request):
    user=request.user
    referral_code=user.referral_code
    referral_link=f'{request.scheme}://{request.get_host()}/signup?ref={referral_code}'  
    referred_users=user.referrals.all() 
    total_referrals=referred_users.count()
    successful_referrals=Order.objects.filter(user__in=referred_users,status='delivered').values('user').distinct().count()
    wallet=getattr(user,'wallet',None)
    total_rewards=wallet.balance if wallet else Decimal('0.00')
    pending_rewards=Decimal('0.00')
    context={
        'referral_code':referral_code,
        'referral_link':referral_link,
        'total_referrals':total_referrals,
        'successful_referrals':successful_referrals,
        'total_rewards':total_rewards,
        'pending_rewards':pending_rewards,
    }
    return render(request,'user/refer.html',context)
def ourstory(request):
    return render(request,'user/ourstory.html')
def sustainability(request):
    return render(request,'user/sustainability.html')
def press(request):
    return render(request,'user/press.html')
def contact(request):
    return render(request,'user/contact.html')
def faq(request):
    return render(request,'user/faq.html')
def shipping(request):
    return render(request,'user/shipping.html')