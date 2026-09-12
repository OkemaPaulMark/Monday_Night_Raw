from django.conf import settings
from django.db import models


class Player(models.Model):
    """
    Persistent football player record.

    Players are NOT recreated each Monday.
    """

    class Position(models.TextChoices):
        DEFENDER = 'DEFENDER', 'Defender'
        MIDFIELDER = 'MIDFIELDER', 'Midfielder'
        STRIKER = 'STRIKER', 'Striker'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='player_profile',
    )
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True, default='')
    position = models.CharField(
        max_length=20,
        choices=Position.choices,
        null=True,
        blank=True,
        help_text='Required for new registrations; existing players may not have one set yet.',
    )
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
