from django.urls import path
from .views import sales_report_view
urlpatterns=[
    path('sales-report/',sales_report_view,name='sales_report'),
]