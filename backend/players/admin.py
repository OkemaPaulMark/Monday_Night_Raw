from django.contrib import admin

from .models import Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'is_active', 'user', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'email')
    autocomplete_fields = ('user',)
