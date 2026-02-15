from django.urls import path
from . import views

app_name = "bambu_run"

urlpatterns = [
    path("", views.PrinterDashboardView.as_view(), name="printer_dashboard"),
    path("api/printer/", views.PrinterDataAPIView.as_view(), name="printer_api"),

    # Filament Inventory routes
    path("filaments/", views.FilamentListView.as_view(), name="filament_list"),
    path("api/filaments/<int:pk>/usage/", views.FilamentUsageDataAPIView.as_view(), name="filament_usage_api"),
    path("filaments/add/", views.FilamentCreateView.as_view(), name="filament_create"),
    path("filaments/<int:pk>/", views.FilamentDetailView.as_view(), name="filament_detail"),
    path("filaments/<int:pk>/edit/", views.FilamentUpdateView.as_view(), name="filament_update"),
    path("filaments/<int:pk>/delete/", views.FilamentDeleteView.as_view(), name="filament_delete"),

    # FilamentColor management routes
    path("filament-colors/", views.FilamentColorListView.as_view(), name="filament_color_list"),
    path("filament-colors/add/", views.FilamentColorCreateView.as_view(), name="filament_color_create"),
    path("filament-colors/<int:pk>/edit/", views.FilamentColorUpdateView.as_view(), name="filament_color_update"),
    path("filament-colors/<int:pk>/delete/", views.FilamentColorDeleteView.as_view(), name="filament_color_delete"),

    # FilamentType management routes
    path("filament-types/", views.FilamentTypeListView.as_view(), name="filament_type_list"),
    path("filament-types/add/", views.FilamentTypeCreateView.as_view(), name="filament_type_create"),
    path("filament-types/<int:pk>/edit/", views.FilamentTypeUpdateView.as_view(), name="filament_type_update"),
    path("filament-types/<int:pk>/delete/", views.FilamentTypeDeleteView.as_view(), name="filament_type_delete"),
]
