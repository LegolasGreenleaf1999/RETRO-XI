from django.shortcuts import render,get_object_or_404,redirect
from user.models import Order
import razorpay
from .models import Payment
from django.conf import settings
from .razorpay import create_razorpay_order
from user.utils import deduct_stock_for_order
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
client=razorpay.Client(auth=(settings.RAZORPAY_KEY_ID,settings.RAZORPAY_KEY_SECRET))
# Create your views here.
@never_cache
@login_required
def start_payment(request,order_uuid): 
    order=get_object_or_404(Order,pk=order_uuid)      
    payment=Payment.objects.create(order=order,gateway='razorpay',amount=order.total,status='initiated')
    receipt=f'ord_{str(order.id)[:8]}'     
    razorpay_order=client.order.create({
        'amount':int(order.total*100),
        'currency':'INR',
        'receipt':receipt,
        'payment_capture':1
    })
    payment.transaction_id=razorpay_order['id']
    payment.save()
    context={
        'order':order, 
        'payment':payment,
        'razorpay_key':settings.RAZORPAY_KEY_ID,
        'razorpay_order_id':razorpay_order['id'],
        'amount':int(order.total*100),
    } 
    return render(request,'user/razorpay_checkout.html',context)
@never_cache
@login_required
def verify_razorpay(request): 
    if request.method!='POST':
        return redirect('checkout')
    razorpay_order_id=request.POST.get('razorpay_order_id')
    razorpay_payment_id=request.POST.get('razorpay_payment_id')
    razorpay_signature=request.POST.get('razorpay_signature') 
    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        return redirect('payment_failed', 1) 
    payment=get_object_or_404(Payment,transaction_id=razorpay_order_id)
    params={
        'razorpay_payment_id':razorpay_payment_id, 
        'razorpay_order_id':razorpay_order_id,
        'razorpay_signature':razorpay_signature,  
    } 
    try: 
        client.utility.verify_payment_signature(params)
        payment.status='success'
        payment.save() 
        order=payment.order
        order.status='paid' 
        order.save() 
    except Exception as e:
        print("RAZORPAY VERIFY ERROR:", e)
        payment.status='failed'
        payment.save()
        return redirect('payment_failed',payment.id)
    deduct_stock_for_order(order)
    request.session['cart']={}
    request.session.modified=True
    return redirect('order_success',order.id)
@never_cache
@login_required
def payment_failed(request,payment_id):
    payment=get_object_or_404(Payment,pk=payment_id)
    if payment.status!='failed':
        payment.status='failed'
        payment.save()
    context={
        'payment':payment, 
        'order':payment.order, 
    }
    return render(request,'user/failure.html',context)