from django.contrib import admin
from . models import Customer,ReferralReward

admin.site.register(Customer)

# Register your models here.
@admin.register(ReferralReward)
class ReferralRewardAdmin(admin.ModelAdmin): 
    list_display=(
        'referrer',
        'referred_user',
        'order',
        'reward_amount',
        'status',
        'created_at',
    )
    list_filter=('status',) 
    search_fields=('referrer__email','referred_user__email')