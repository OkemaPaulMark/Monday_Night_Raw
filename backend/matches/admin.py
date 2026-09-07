from django.contrib import admin

from .models import (
    GoalEvent,
    Match,
    MatchAvailability,
    MatchParticipant,
    MatchTeam,
    MatchTeamPlayer,
)


class MatchParticipantInline(admin.TabularInline):
    model = MatchParticipant
    extra = 0
    autocomplete_fields = ('player',)


class MatchAvailabilityInline(admin.TabularInline):
    model = MatchAvailability
    extra = 0
    autocomplete_fields = ('player',)


class MatchTeamInline(admin.TabularInline):
    model = MatchTeam
    extra = 0


class GoalEventInline(admin.TabularInline):
    model = GoalEvent
    extra = 0
    autocomplete_fields = ('scorer', 'assister', 'scoring_team')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        'match_date',
        'status',
        'team_a_score',
        'team_b_score',
        'finalized_at',
    )
    list_filter = ('status',)
    search_fields = ('match_date', 'notes')
    date_hierarchy = 'match_date'
    inlines = [
        MatchAvailabilityInline,
        MatchParticipantInline,
        MatchTeamInline,
        GoalEventInline,
    ]


class MatchTeamPlayerInline(admin.TabularInline):
    model = MatchTeamPlayer
    extra = 0
    autocomplete_fields = ('player',)


@admin.register(MatchTeam)
class MatchTeamAdmin(admin.ModelAdmin):
    list_display = ('match', 'side')
    list_filter = ('side',)
    search_fields = ('match__match_date', 'side')
    inlines = [MatchTeamPlayerInline]


@admin.register(MatchParticipant)
class MatchParticipantAdmin(admin.ModelAdmin):
    list_display = ('match', 'player')
    autocomplete_fields = ('player', 'match')


@admin.register(MatchTeamPlayer)
class MatchTeamPlayerAdmin(admin.ModelAdmin):
    list_display = ('team', 'player')
    autocomplete_fields = ('team', 'player')


@admin.register(GoalEvent)
class GoalEventAdmin(admin.ModelAdmin):
    list_display = ('match', 'order', 'scoring_team', 'scorer', 'assister')
    autocomplete_fields = ('match', 'scoring_team', 'scorer', 'assister')
