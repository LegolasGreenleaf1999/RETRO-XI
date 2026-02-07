# middleware.py

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

class PreventAdminOnUserSiteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # If admin is logged in and trying to access user-side pages
        if request.user.is_authenticated and request.user.is_staff:
            if not request.path.startswith('/admin/'):
                logout(request)
                return redirect(reverse('login'))  # your user login page

        return self.get_response(request)
