from django.conf import settings
from django.db import models


class Player(models.Model):
    """
    Persistent football player record.

    Players are NOT recreated each Monday. Match-specific team membership
    is handled via MatchTeamPlayer, not on this model.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='player_profile',
    )
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True, default='')
    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name'],
                name='unique_player_name',
            ),
        ]

    def __str__(self) -> str:
        return self.name
