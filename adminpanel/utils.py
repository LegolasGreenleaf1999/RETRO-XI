from django.contrib.auth.decorators import user_passes_test
from django.conf import settings
def admin_required(view_func):
    return user_passes_test(
        lambda u:u.is_authenticated and u.is_staff,
        login_url='my_login'
    )(view_func)