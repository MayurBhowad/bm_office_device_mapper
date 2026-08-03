from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("device/add/", views.device_add, name="device_add"),
    path("device/<int:pk>/edit/", views.device_edit, name="device_edit"),
    path("device/<int:pk>/delete/", views.device_delete, name="device_delete"),
    path("api/check/<int:pk>/", views.check_one, name="check_one"),
    path("api/check-all/", views.check_all, name="check_all"),
]
