from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from accounts.models import User
from players.models import Player


class UserSerializer(serializers.ModelSerializer):
    player_id = serializers.IntegerField(
        source='player_profile.id',
        read_only=True,
        allow_null=True,
    )
    is_app_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'player_id',
            'is_app_admin',
        )
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs['username'],
            password=attrs['password'],
        )
        if user is None:
            raise serializers.ValidationError({'detail': 'Invalid credentials.'})
        if not user.is_active:
            raise serializers.ValidationError({'detail': 'User account is disabled.'})
        attrs['user'] = user
        return attrs

    def create(self, validated_data):
        user = validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return {'token': token.key, 'user': user}


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    name = serializers.CharField(max_length=120)
    password = serializers.CharField(write_only=True)
    position = serializers.ChoiceField(choices=Player.Position.choices)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('That username is already taken.')
        return value

    def validate_name(self, value):
        if Player.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(
                'A player with this name is already registered.'
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        name_parts = validated_data['name'].split()
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=name_parts[0] if name_parts else '',
            last_name=' '.join(name_parts[1:]),
            role=User.Role.PLAYER,
        )
        player = Player.objects.create(
            user=user,
            name=validated_data['name'],
            email=validated_data['email'],
            position=validated_data['position'],
            is_active=True,
        )
        token = Token.objects.create(user=user)
        return {'token': token.key, 'user': user, 'player': player}


class MeUpdateSerializer(serializers.Serializer):
    """Self-service profile edit: username/email live on User, name/email are
    mirrored onto the linked Player (if any) so both stay in sync."""

    username = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    name = serializers.CharField(max_length=120, required=False)
    position = serializers.ChoiceField(choices=Player.Position.choices, required=False)

    def validate_username(self, value):
        user = self.context['user']
        if User.objects.filter(username__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError('That username is already taken.')
        return value

    def validate_name(self, value):
        user = self.context['user']
        player = getattr(user, 'player_profile', None)
        qs = Player.objects.filter(name__iexact=value)
        if player is not None:
            qs = qs.exclude(pk=player.pk)
        if qs.exists():
            raise serializers.ValidationError('A player with this name is already registered.')
        return value

    @transaction.atomic
    def save(self):
        user = self.context['user']
        data = self.validated_data

        if 'username' in data:
            user.username = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'name' in data:
            parts = data['name'].split()
            user.first_name = parts[0] if parts else ''
            user.last_name = ' '.join(parts[1:])
        user.save()

        player = getattr(user, 'player_profile', None)
        if player is not None:
            update_fields = []
            if 'name' in data:
                player.name = data['name']
                update_fields.append('name')
            if 'email' in data:
                player.email = data['email']
                update_fields.append('email')
            if 'position' in data:
                player.position = data['position']
                update_fields.append('position')
            if update_fields:
                player.save(update_fields=[*update_fields, 'updated_at'])

        return user
