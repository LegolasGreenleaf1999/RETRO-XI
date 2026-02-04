from django.urls import path
from .views import product_list,product_detail,add_review,product_reviews,cart_view,add_to_cart,update_cart,remove_from_cart,checkout,set_shipping,new_arrivals
urlpatterns=[
    path('productlist/',product_list,name='productlist'),
    path('productdetail/<slug:slug>-<uuid:uuid>/',product_detail,name='productdetail'), 
    path('jersey/<uuid:uuid>/reviews/',product_reviews,name='product_review'),     
    path('jersey/<uuid:uuid>/reviews/add',add_review,name='add_review'),
    path('cart/',cart_view,name='cart'),
    path('cart/add/<int:variant_id>/',add_to_cart,name='add_to_cart'),
    path('cart/update/<int:variant_id>/',update_cart,name='update_cart'),
    path('cart/remove/<int:variant_id>/',remove_from_cart,name='remove_from_cart'),
    path('checkout/',checkout,name='checkout'),
    path('set-shipping/',set_shipping,name='set_shipping'),
    path('new-arrivals/',new_arrivals,name='new_arrivals'),
]