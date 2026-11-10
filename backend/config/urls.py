from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def root(request):
    return JsonResponse(
        {
            "service": "Weather-Aware Truck Routing API",
            "endpoints": {"health": "/api/health/", "plan": "POST /api/plan/"},
        }
    )


urlpatterns = [
    path("", root),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]
