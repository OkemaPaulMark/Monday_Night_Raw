from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Not "admin/" — the frontend's own admin section lives under that path
    # client-side (/admin, /admin/players, /admin/matches/...), and nginx
    # proxies /admin/ straight to Django in production. A full page load on
    # one of the frontend's admin URLs (refresh, bookmark, shared link)
    # would otherwise be intercepted before ever reaching the React app.
    path('django-admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/players/', include('players.urls')),
    path('api/matches/', include('matches.urls')),
    path('api/awards/', include('awards.urls')),
    path('api/', include('stats.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
