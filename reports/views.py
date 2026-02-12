from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum,Avg
from .utils import (daily_sales,weekly_sales,yearly_sales,custom_sales_report,successful_orders,)
from django.http import HttpResponse
from django.template.loader import render_to_string
import openpyxl
from xhtml2pdf import pisa
from django.template.loader import get_template
from io import BytesIO
from django.views.decorators.cache import never_cache
from adminpanel.utils import admin_required
from datetime import datetime
# Create your views here.
@never_cache
@admin_required
def sales_report_view(request): 
    report_type=request.GET.get('type','daily')
    export_type=request.GET.get('export')
    context={
        'type':report_type,
    }
    if report_type=='weekly':
        rows=weekly_sales()
        context['rows']=rows 
        context['label']='week'
    elif report_type=='yearly': 
        rows=yearly_sales()
        context['rows']=rows
        context['label']='year'
    elif report_type=='custom':
        start=request.GET.get('start')
        end=request.GET.get('end')
        rows=None 
        if start and end:
            try:
                start_date = datetime.strptime(start, "%Y-%m-%d").date()
                end_date = datetime.strptime(end, "%Y-%m-%d").date()

            
                if start_date > end_date:
                    context['error'] = "Start date cannot be after end date"
                    context['custom'] = None
                else:
                    context['custom'] = custom_sales_report(start_date, end_date)
                    context['start'] = start
                    context['end'] = end

            except Exception as e:
                print("Custom report error:", e)
                context['custom'] = None
        else:
            context['custom'] = None 
    else:
        rows=daily_sales()
        context['rows']=rows
        context['label']='date'
    qs=successful_orders()
    context.update({
        'orders_count':qs.count(),
        'revenue':qs.aggregate(total=Sum('total'))['total'] or 0,
        'gross_sales':qs.aggregate(total=Sum('subtotal'))['total'] or 0,
        'discounts':qs.aggregate(total=Sum('discount'))['total'] or 0,
    })
    if export_type=='excel' and rows is not None:
        wb=openpyxl.Workbook()
        ws=wb.active
        ws.title='Sales Report'
        ws.append([
            'Period',
            'Orders',
            'Gross Sales',
            'Discounts',
            'Net Revenue'
        ])
        for row in rows:
            period=(
                row.get('date') or
                row.get('week') or
                row.get('year')
            )
            ws.append([
                str(period),
                row['orders'],
                float(row['gross_sales']),
                float(row['discounts']),
                float(row['net_sales']),
            ])
        response=HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition']='attachment; filename="sales_report.xlsx"'
        wb.save(response)
        return response
    if export_type=='pdf' and rows is not None: 
        template = get_template('admin/reports_pdf.html')
        html = template.render({'rows': rows, 'type': report_type})

        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)

        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="sales_report.pdf"'
            return response

        return HttpResponse("Error generating PDF", status=500)

    return render(request,'admin/reports.html',context)