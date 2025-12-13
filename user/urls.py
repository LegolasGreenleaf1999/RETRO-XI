from django.urls import path 
from .views import home_view,login_view,signup_view,verify_otp,forgot_pass,reset_pass,profile,edit_profile,addresses,add_address,edit_address,delete_address,address_detail,change_pass,verify_password_otp,wallet_page,change_email,verify_email_otp,resend_otp
urlpatterns=[
    path('',login_view,name='login'),
    path('register/',signup_view,name='register'), 
    path('home/',home_view,name='home'),
    path('otp/',verify_otp,name='otp'),  
    path('forgotpassword/',forgot_pass,name='forgotpassword'),
    path('resetpassword/',reset_pass,name='resetpassword'),
    path('profile/',profile,name='profile'),
    path('editprofile/',edit_profile,name='edit'),
    path('myaddresses/',addresses,name='addresses'),
    path('myaddresses/add',add_address,name='add_address'),
    path('myaddresses/edit/<int:id>/',edit_address,name='edit_address'),
    path('myaddresses/delete/<int:id>/',delete_address,name='delete_address'),
    path('myaddresses/detail/<int:id>/',address_detail,name='address_detail'), 
    path('changepassword/',change_pass,name='changepassword'),
    path('passotp/',verify_password_otp,name='passotp'),
    path('wallet/',wallet_page,name='wallet'), 
    path('changeemail/',change_email,name='changeemail'),
    path('emailotp/',verify_email_otp,name='emailotp'),
    path('resend-otp/',resend_otp,name='resend_otp')
]