from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from expediente.models import Legajo, Solicitud
from expediente.permissions import es_administrador


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        context['es_admin'] = es_administrador(usuario)
        if context['es_admin']:
            context['total_legajos'] = Legajo.objects.count()
            context['solicitudes_pendientes'] = Solicitud.objects.filter(estado=Solicitud.ESTADO_PENDIENTE).count()
            context['prestamos_activos'] = Solicitud.objects.filter(prestamos__activo=True).distinct().count()
        else:
            context['solicitudes_activas'] = usuario.solicitudes.exclude(estado=Solicitud.ESTADO_CERRADA).count()
            context['prestamos_activos'] = usuario.prestamos.filter(activo=True).count()
        return context
