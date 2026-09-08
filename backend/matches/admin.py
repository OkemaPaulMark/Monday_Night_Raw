from django.contrib import admin

from .models import GoalEvent, Match, MatchAvailability, MatchParticipant


class MatchParticipantInline(admin.TabularInline):
    model = MatchParticipant
    extra = 0
    autocomplete_fields = ('player',)


class MatchAvailabilityInline(admin.TabularInline):
    model = MatchAvailability
    extra = 0
    autocomplete_fields = ('player',)


class GoalEventInline(admin.TabularInline):
    model = GoalEvent
    extra = 0
    autocomplete_fields = ('scorer', 'assister')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        'match_date',
        'status',
        'finalized_at',
    )
    list_filter = ('status',)
    search_fields = ('match_date', 'notes')
    date_hierarchy = 'match_date'
    inlines = [
        MatchAvailabilityInline,
        MatchParticipantInline,
        GoalEventInline,
    ]


@admin.register(MatchParticipant)
class MatchParticipantAdmin(admin.ModelAdmin):
    list_display = ('match', 'player')
    autocomplete_fields = ('player', 'match')


@admin.register(GoalEvent)
class GoalEventAdmin(admin.ModelAdmin):
    list_display = ('match', 'order', 'scorer', 'assister')
    autocomplete_fields = ('match', 'scorer', 'assister')
