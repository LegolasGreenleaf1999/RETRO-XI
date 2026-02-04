from user.models import Order
from payments.models import Payment 
from django.db.models import Sum,Count
from django.db.models.functions import TruncDate,TruncWeek,TruncYear
def successful_orders():
    return Order.objects.filter(payment__status='success')
def daily_sales():
    return (successful_orders().annotate(date=TruncDate('created_at')).values('date').annotate(gross_sales=Sum('subtotal'),orders=Count('id'),discounts=Sum('discount'),net_sales=Sum('total'),).order_by('date'))
def weekly_sales():
    return (successful_orders().annotate(week=TruncWeek('created_at')).values('week').annotate(gross_sales=Sum('subtotal'),orders=Count('id'),discounts=Sum('discount'),net_sales=Sum('total'),).order_by('week'))
def yearly_sales():
    return (successful_orders().annotate(year=TruncYear('created_at')).values('year').annotate(gross_sales=Sum('subtotal'),orders=Count('id'),discounts=Sum('discount'),net_sales=Sum('total'),).order_by('year'))
def custom_sales_report(start_date,end_date): 
    qs=successful_orders().filter(created_at__date__range=[start_date,end_date]) 
    return {
        'orders':qs.count(),
        'net_sales':qs.aggregate(total=Sum('total'))['total'] or 0,
        'gross_sales':qs.aaggregate(total=Sum('subtotal'))['total'] or 0,
        'discounts':qs.aaggregate(total=Sum('discount'))['total'] or 0,
    }