from django.shortcuts import render,redirect
from django.contrib.auth import authenticate,login 
from django.contrib import messages
from user.models import Customer
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse 
from django.contrib.auth.decorators import login_required
# Create your views here.
def admin_login(request):
    if request.method=='POST':
        email=request.POST.get('email') 
        password=request.POST.get('password')  
        user=authenticate(request,email=email,password=password)
        if user is not None and user.is_superuser:
            login(request,user)
            return redirect('dashboard')
        messages.error(request,'invalid admin credentials')
    return render(request,'admin/my_login.html')
def user_list(request): 
    search_query=request.GET.get('search','')
    users=Customer.objects.filter(is_superuser=False).order_by('-id') 
    if search_query:
        users=users.filter(Q(email__icontains=search_query)|Q(first_name__icontains=search_query)) 
    paginator=Paginator(users,5) 
    page=request.GET.get('page') 
    users_page=paginator.get_page(page)
    return render(request,'admin/user_list.html',{'users':users_page,'search_query':search_query}) 
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
@login_required(login_url='login')
def admin_dashboard(request):  
    if not request.user.is_superuser:
        return redirect('login')
    return render(request,'admin/dashboard.html')