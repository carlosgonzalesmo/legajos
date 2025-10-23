from django import forms
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, FormView, ListView

from .models import Legajo, Prestamo, Solicitud, SolicitudItem
from .permissions import es_administrador, es_solicitante


class AdministradorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe el acceso únicamente a usuarios administradores."""

    def test_func(self):
        return es_administrador(self.request.user)


class SolicitanteRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe el acceso a usuarios con rol solicitante o administradores."""

    def test_func(self):
        return es_solicitante(self.request.user)


class LegajoForm(forms.ModelForm):
    class Meta:
        model = Legajo
        fields = ['codigo', 'titulo', 'descripcion']


class SolicitudForm(forms.Form):
    legajos = forms.ModelMultipleChoiceField(
        queryset=Legajo.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label='Legajos a solicitar',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        disponibles = Legajo.objects.filter(bloqueado=False).order_by('codigo')
        self.fields['legajos'].queryset = disponibles

    def clean_legajos(self):
        qs = self.cleaned_data['legajos']
        no_disp = [legajo.codigo for legajo in qs if not legajo.disponible]
        if no_disp:
            raise forms.ValidationError(f"Legajos no disponibles: {', '.join(no_disp)}")
        return qs


class LegajoListView(AdministradorRequiredMixin, ListView):
    model = Legajo
    template_name = 'legajo_list.html'
    context_object_name = 'legajos'


class LegajoCreateView(AdministradorRequiredMixin, CreateView):
    model = Legajo
    form_class = LegajoForm
    template_name = 'legajo_form.html'

    def get_success_url(self):
        return reverse('legajo_list')


class SolicitudListView(SolicitanteRequiredMixin, ListView):
    model = Solicitud
    template_name = 'solicitud_list.html'
    context_object_name = 'solicitudes'

    def get_queryset(self):
        return Solicitud.objects.filter(usuario=self.request.user).order_by('-creado_en')


class SolicitudAdminListView(AdministradorRequiredMixin, ListView):
    model = Solicitud
    template_name = 'solicitud_admin_list.html'
    context_object_name = 'solicitudes'

    def get_queryset(self):
        return (
            Solicitud.objects.select_related('usuario')
            .prefetch_related('prestamos__legajo')
            .annotate(active_prestamos=Count('prestamos', filter=Q(prestamos__activo=True)))
            .order_by('-creado_en')
        )


class SolicitudCreateView(SolicitanteRequiredMixin, FormView):
    form_class = SolicitudForm
    template_name = 'solicitud_form.html'

    def form_valid(self, form):
        solicitud = Solicitud.objects.create(usuario=self.request.user)
        legajos = form.cleaned_data['legajos']
        for legajo in legajos:
            SolicitudItem.objects.create(
                solicitud=solicitud,
                legajo=legajo,
                disponible_al_crear=legajo.disponible,
            )
            Prestamo.objects.create(
                solicitud=solicitud,
                legajo=legajo,
                usuario=self.request.user,
                bloqueado_en_prep=not legajo.disponible,
            )
        solicitud.marcar_preparada()
        return redirect('solicitud_detail', pk=solicitud.pk)


class SolicitudDetailView(SolicitanteRequiredMixin, DetailView):
    model = Solicitud
    template_name = 'solicitud_detail.html'
    context_object_name = 'solicitud'

    def get_queryset(self):
        if es_administrador(self.request.user):
            return Solicitud.objects.all()
        return Solicitud.objects.filter(usuario=self.request.user)


@login_required
def prestamo_entregar_view(request, pk):
    prestamo = get_object_or_404(Prestamo, pk=pk)
    if not (prestamo.usuario == request.user or es_administrador(request.user)):
        return HttpResponseForbidden('No autorizado')
    prestamo.marcar_entregado()
    return redirect('solicitud_detail', pk=prestamo.solicitud.pk)


@login_required
def prestamo_devolver_view(request, pk):
    prestamo = get_object_or_404(Prestamo, pk=pk)
    if not (prestamo.usuario == request.user or es_administrador(request.user)):
        return HttpResponseForbidden('No autorizado')
    prestamo.marcar_devuelto()
    return redirect('solicitud_detail', pk=prestamo.solicitud.pk)


@user_passes_test(es_administrador)
def legajo_toggle_bloqueo_view(request, pk):
    legajo = get_object_or_404(Legajo, pk=pk)
    legajo.bloqueado = not legajo.bloqueado
    legajo.save(update_fields=['bloqueado'])
    return redirect('legajo_list')

# Create your views here.
