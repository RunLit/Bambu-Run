from django.urls import include, path

urlpatterns = [
    path("", include("bambu_run.urls")),
]
