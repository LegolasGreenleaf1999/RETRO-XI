from django.urls import path 
from .views import user_list,block_user_ajax,unblock_user_ajax,admin_dashboard,admin_login
urlpatterns=[
    path('users/',user_list,name='user_list'),
    path('users/block/',block_user_ajax,name='block_user'), 
    path('users/unblock/',unblock_user_ajax,name='unblock_user'),
    path('dashboard/',admin_dashboard,name='dashboard'),
    path('',admin_login,name='login')
]