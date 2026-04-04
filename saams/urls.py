from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from pathlib import Path


def favicon_view(request):
    base_dir = Path(settings.BASE_DIR)
    icon_path = base_dir / "pwa_static" / "icons" / "icon-192.png"
    if not icon_path.exists():
        icon_path = base_dir / "pwa_static" / "logo.png"

    return HttpResponse(
        icon_path.read_bytes() if icon_path.exists() else b"",
        content_type="image/png",
    )


urlpatterns = [
    path("favicon.ico", favicon_view),

    path('admin/', admin.site.urls),

    path('', include('accounts.urls')),

    path('attendance/', include('attendance.urls')),

    path('results/', include('results.urls')),

    path('homework/', include('homework.urls')),

    path('notifications/', include('notifications.urls')),

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
