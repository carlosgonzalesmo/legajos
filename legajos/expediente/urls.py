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
    path('solicitudes/<int:pk>/preparar/', views.solicitud_preparar_view, name='solicitud_preparar'),
    path('solicitudes/<int:pk>/confirmar-entrega/', views.solicitud_confirmar_entrega_view, name='solicitud_confirmar_entrega'),
    path('prestamos/<int:pk>/devolver/', views.prestamo_devolver_view, name='prestamo_devolver'),
]