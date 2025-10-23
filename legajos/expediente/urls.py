from django.urls import path
from . import views

urlpatterns = [
    path('legajos/', views.LegajoListView.as_view(), name='legajo_list'),
    path('legajos/nuevo/', views.LegajoCreateView.as_view(), name='legajo_create'),
    path('legajos/<int:pk>/toggle-bloqueo/', views.legajo_toggle_bloqueo_view, name='legajo_toggle_bloqueo'),
    path('solicitudes/', views.SolicitudListView.as_view(), name='solicitud_list'),
    path('solicitudes/gestion/', views.SolicitudAdminListView.as_view(), name='solicitud_admin_list'),
    path('solicitudes/nueva/', views.SolicitudCreateView.as_view(), name='solicitud_create'),
    path('solicitudes/<int:pk>/', views.SolicitudDetailView.as_view(), name='solicitud_detail'),
    path('prestamos/<int:pk>/entregar/', views.prestamo_entregar_view, name='prestamo_entregar'),
    path('prestamos/<int:pk>/devolver/', views.prestamo_devolver_view, name='prestamo_devolver'),
]