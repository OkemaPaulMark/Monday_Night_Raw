from django.contrib import admin

from .models import Award, AwardRecipient


class AwardRecipientInline(admin.TabularInline):
    model = AwardRecipient
    extra = 0
    autocomplete_fields = ('player',)


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = (
        'award_type',
        'match',
        'year',
        'month',
        'is_confirmed',
        'created_at',
    )
    list_filter = ('award_type', 'is_confirmed', 'year', 'month')
    search_fields = ('award_type', 'notes')
    inlines = [AwardRecipientInline]


@admin.register(AwardRecipient)
class AwardRecipientAdmin(admin.ModelAdmin):
    list_display = ('award', 'player', 'performance_score', 'rank')
    autocomplete_fields = ('award', 'player')
