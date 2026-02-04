from django.urls import path 
from .views import payment_failed,verify_razorpay,start_payment
urlpatterns=[
    path('start/<uuid:order_uuid>/',start_payment,name='start_payment'),
    path('verify/',verify_razorpay,name='verify_razorpay'),
    path('failed/<uuid:payment_id>/',payment_failed,name='payment_failed'),
]