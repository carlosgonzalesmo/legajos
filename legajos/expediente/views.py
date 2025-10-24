from django import forms
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
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
        fields = ['codigo', 'nombre', 'descripcion']


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
            )
        return redirect('solicitud_detail', pk=solicitud.pk)


class SolicitudDetailView(SolicitanteRequiredMixin, DetailView):
    model = Solicitud
    template_name = 'solicitud_detail.html'
    context_object_name = 'solicitud'

    def get_queryset(self):
        if es_administrador(self.request.user):
            return Solicitud.objects.all()
        return Solicitud.objects.filter(usuario=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitud = context['solicitud']
        usuario = self.request.user
        es_admin = es_administrador(usuario)
        prestamos_pendientes = solicitud.prestamos.filter(estado=Prestamo.ESTADO_PENDIENTE)
        context.update(
            es_admin=es_admin,
            prestamos_pendientes=prestamos_pendientes,
            puede_preparar=es_admin and solicitud.estado == Solicitud.ESTADO_PENDIENTE and prestamos_pendientes.exists(),
            puede_confirmar_entrega=
                (solicitud.usuario == usuario)
                and solicitud.prestamos.filter(estado=Prestamo.ESTADO_LISTO).exists()
                and solicitud.estado in (Solicitud.ESTADO_PREPARADA, Solicitud.ESTADO_PENDIENTE),
            estado_entregado=Prestamo.ESTADO_ENTREGADO,
        )
        return context


@user_passes_test(es_administrador)
def solicitud_preparar_view(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if request.method != 'POST':
        return redirect('solicitud_detail', pk=solicitud.pk)
    prestamos = list(solicitud.prestamos.filter(estado=Prestamo.ESTADO_PENDIENTE))
    seleccionados = {int(value) for value in request.POST.getlist('prestamos_listos')}
    with transaction.atomic():
        for prestamo in prestamos:
            if prestamo.pk in seleccionados:
                prestamo.marcar_listo()
            else:
                prestamo.marcar_extraviado()
        solicitud.marcar_preparada(bool(seleccionados))
    return redirect('solicitud_detail', pk=solicitud.pk)


@login_required
def solicitud_confirmar_entrega_view(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if not (solicitud.usuario == request.user or es_administrador(request.user)):
        return HttpResponseForbidden('No autorizado')
    if request.method != 'POST':
        return redirect('solicitud_detail', pk=solicitud.pk)
    prestamos_listos = list(solicitud.prestamos.filter(estado=Prestamo.ESTADO_LISTO))
    if not prestamos_listos:
        return redirect('solicitud_detail', pk=solicitud.pk)
    with transaction.atomic():
        for prestamo in prestamos_listos:
            prestamo.marcar_entregado()
        solicitud.marcar_entregada()
    return redirect('solicitud_detail', pk=solicitud.pk)


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
    legajo.save()
    return redirect('legajo_list')

# Create your views here.
