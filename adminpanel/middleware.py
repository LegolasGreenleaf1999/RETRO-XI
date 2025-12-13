from django.http import HttpResponseForbidden  
ALLOWED_ADMIN_IPS=['10.10.11.110']  
class AdminIPRestrictionMiddleware:
    def __init__(self,get_response):
        self.get_response=get_response  
    def __call__(self,request):  
        if request.path.startswith('/secret-admin/'):  
            ip=request.meta.get('REMOTE_ADDR') 
            if ip not in ALLOWED_ADMIN_IPS:
                return HttpResponseForbidden('not allowed')
        return self.get_response(request)