from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("geocode", views.GeocodeView.as_view(), name="geocode"),
    path("weather-provider", views.WeatherProviderView.as_view(), name="weather-provider"),
    path("trips/plan", views.TripPlanView.as_view(), name="trip-plan"),
    path("trips/<str:plan_id>/heatmap", views.HeatmapView.as_view(), name="trip-heatmap"),
]
