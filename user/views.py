from django.shortcuts import render,redirect 
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login,authenticate 
from django.contrib.auth import update_session_auth_hash
from .forms import SignupForm 
from django.core.mail import send_mail 
from django.utils import timezone 
from datetime import timedelta
import random  
from .models import Profile,Address,PasswordChangeOTP,EmailChangeOTP,OTP
from django.dispatch import receiver 
from django.shortcuts import get_object_or_404
from django.db.models.signals import post_save  
from .models import Customer,Profile,Wallet
from django.contrib import messages 
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse  
from django.views.decorators.http import require_GET 
from django.views.decorators.cache import never_cache
# Create your views here. 
@never_cache
@login_required 
def wallet_page(request):
    wallet=request.user.wallet 
    transactions=wallet.transaction_set.all().order_by('-created_at') if hasattr(wallet,'transaction_set') else None  
    context={
        'wallet':wallet,  
        'transactions':transactions,
    }   
    return render(request,'user/wallet.html',context)
@never_cache
@login_required
def verify_password_otp(request):
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
        request.user.password=record.new_password_hash               
        request.user.save()
        update_session_auth_hash(request,request.user) 
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
        request.user.save()
        record.delete()     
        messages.success(request,'email updated successfully')   
        return redirect('profile')   
    return render(request,'user/emailotp.html')         
@never_cache
@login_required
def change_pass(request): 
    if request.method=='POST':
        new1=request.POST.get('newpassword1') 
        new2=request.POST.get('newpassword2')
        if new1!=new2:  
            messages.error(request,'new passwords do not match')   
            return redirect('changepassword')   
        otp=f'{random.randint(100000,999999)}' 
        expires=timezone.now()+timedelta(minutes=10)
        PasswordChangeOTP.objects.create(
            user=request.user,
            otp=otp,
            new_password_hash=make_password(new1), 
            expires_at=expires
        )                                   
        send_mail(
            'Your password change OTP',
            f'Your OTP for changing password is {otp}',
            'ashwincsanthosh@gmail.com',
            [request.user.email],   
            fail_silently=False,
        ) 
        return redirect('passotp')         
    return render(request,'user/changepassword.html')   
@login_required
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
        return redirect('passotp')
    return render(request,'user/changeemail.html')
@never_cache
@login_required
@require_GET
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
def profile(request):       
    user=request.user  
    profile,created=Profile.objects.get_or_create(user=user)
    return render(request,'user/profile.html',{'user':user,'profile':profile})   
@never_cache
@login_required
def edit_profile(request): 
    profile,created=Profile.objects.get_or_create(user=request.user)  
    if request.method=='POST':
        request.user.first_name=request.POST.get('first_name')    
        request.user.save()
        profile.phone=request.POST.get('phone')  
        profile.address=request.POST.get('address') 
        if 'profile_image' in request.FILES:
            profile.profile_image=request.FILES['profile_image'] 
        profile.save() 
        return redirect('profile')
    return render(request,'user/editprofile.html',{'profile':profile}) 
@never_cache
@login_required
def addresses(request): 
    addresses=Address.objects.filter(user=request.user)          
    return render(request,'user/addresses.html',{'addresses':addresses}) 
@never_cache
@login_required
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
def home_view(request):
    return render(request,'user/home.html')  
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
@never_cache
def signup_view(request):
    if request.method=='POST':
        fullname=request.POST.get('fullname')
        email=request.POST.get('email')
        password=request.POST.get('password')
        print(f"pass: {password}")
        confirm_password=request.POST.get('confirm_password')
        if password!=confirm_password:
            messages.error(request,'passwords do not match!')
            return render(request,'user/register.html')
        if Customer.objects.filter(email=email).exists():
            messages.error(request,'email already exists!') 
            return render(request,'user/register.html')  
        user=Customer.objects.create_user(
            username=email,
            email=email,
            password=password
        ) 
        user.first_name=fullname  
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
@never_cache
def login_view(request):
    if request.method=='POST': 
        email=request.POST.get('email')
        password=request.POST.get('password') 
        print(f"email: {email} pass: {password}")
        user=authenticate(request,username=email,password=password)  
        if user:
            if user.is_blocked:   
                messages.error(request,'your account is blocked, contact admin')  
                return redirect('login')
            login(request,user) 
            messages.success(request,'login successful!')  
            return redirect('home') 
        else:
            print("no user")
        messages.error(request,'invalid email or password!')  
        return render(request,'user/login.html')
    return render(request,'user/login.html') 
@never_cache
def send_otp(request):
    otp=random.randint(100000,999999)
    return HttpResponse(str(otp)) 
@never_cache
def create_profile(sender,instance,created,**kwargs):
    if created:
        Profile.objects.create(user=instance)   
@never_cache
def delete_address(request,id):
    address=Address.objects.get(id=id) 
    address.delete() 
    return redirect('address_list')    
@never_cache
def reset_pass(request):
    email=request.session.get('email')   
    if not email:
        messages.error(request,'session expired, please try again')  
        return redirect('forgotpassword')
    if request.method=='POST':
        new_password=request.POST.get('password')  
        confirm_password=request.POST.get('confirm')  
        if new_password!=confirm_password:
            messages.error(request,'passwords do not match!') 
            return redirect('resetpassword')
        user=Customer.objects.get(email=email) 
        user.password=make_password(new_password)  
        user.save()  
        request.session.flush()  
        messages.success(request,'password updated successfully')  
        return redirect('login')  
    return render(request,'user/resetpassword.html') 
@login_required
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
            subject='your otp code',
            message=f'your new otp is {otp}', 
            from_email='ashwincsanthosh@gmail.com', 
            recipient_list=[email],
            fail_silently=False, 
        )
        return JsonResponse({'message':'a new otp has been sent'})  
    print('non post request received')
    return JsonResponse({'error':'invalid request'},status=400)