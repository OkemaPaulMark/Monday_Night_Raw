from rest_framework import serializers

from players.models import Player


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = (
            'id',
            'name',
            'email',
            'profile_photo',
            'is_active',
            'user',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')


class PlayerWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ('name', 'email', 'profile_photo', 'is_active', 'user')


class PlayerPhotoUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ('profile_photo',)

    def validate_profile_photo(self, value):
        if value is None:
            raise serializers.ValidationError('A photo file is required.')
        max_bytes = 5 * 1024 * 1024
        if value.size > max_bytes:
            raise serializers.ValidationError('Photo must be 5MB or smaller.')
        content_type = getattr(value, 'content_type', '') or ''
        if content_type and not content_type.startswith('image/'):
            raise serializers.ValidationError('File must be an image.')
        return value
