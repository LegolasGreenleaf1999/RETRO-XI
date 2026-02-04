from django.contrib import admin
from .models import JerseyProduct, Category


@admin.register(JerseyProduct)
class JerseyAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('team', 'season')
    


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
