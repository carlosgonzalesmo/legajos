from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Legajo(models.Model):
	"""Representa un legajo físico que puede ser solicitado y prestado."""

	codigo = models.CharField(max_length=50, unique=True)
	titulo = models.CharField(max_length=255)
	descripcion = models.TextField(blank=True)
	bloqueado = models.BooleanField(default=False, help_text="Marcado si no se encuentra físicamente / extraviado")
	creado_en = models.DateTimeField(auto_now_add=True)
	actualizado_en = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.codigo} - {self.titulo}"

	@property
	def disponible(self) -> bool:
		"""Indica si el legajo está disponible para ser solicitado.
		Está disponible si no está bloqueado y no tiene un préstamo activo.
		"""
		return (not self.bloqueado) and (not Prestamo.objects.filter(legajo=self, activo=True).exists())


class Solicitud(models.Model):
	"""Solicitud de uno o varios legajos por parte de un usuario.
	Estados:
	- pendiente: creada y aún no preparada por el administrador
	- preparada: administrador procesó y generó los prestamos correspondientes (parciales)
	- cancelada: no se pudo satisfacer (todos bloqueados / usuario cancela)
	- entregada: usuario confirmó recepción de los legajos prestados
	- cerrada: todos los legajos fueron devueltos
	"""

	ESTADO_PENDIENTE = 'pendiente'
	ESTADO_PREPARADA = 'preparada'
	ESTADO_CANCELADA = 'cancelada'
	ESTADO_ENTREGADA = 'entregada'
	ESTADO_CERRADA = 'cerrada'
	ESTADOS = [
		(ESTADO_PENDIENTE, 'Pendiente'),
		(ESTADO_PREPARADA, 'Preparada'),
		(ESTADO_CANCELADA, 'Cancelada'),
		(ESTADO_ENTREGADA, 'Entregada'),
		(ESTADO_CERRADA, 'Cerrada'),
	]

	usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitudes')
	estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE)
	creado_en = models.DateTimeField(auto_now_add=True)
	actualizado_en = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"Solicitud #{self.id} - {self.usuario} - {self.estado}"

	def puede_prepararse(self):
		return self.estado == self.ESTADO_PENDIENTE

	def marcar_preparada(self):
		if self.puede_prepararse():
			self.estado = self.ESTADO_PREPARADA
			self.save(update_fields=['estado'])

	def marcar_entregada(self):
		if self.estado in (self.ESTADO_PREPARADA, self.ESTADO_PENDIENTE):  # soporta confirmación directa
			self.estado = self.ESTADO_ENTREGADA
			self.save(update_fields=['estado'])

	def marcar_cerrada_si_corresponde(self):
		if not Prestamo.objects.filter(solicitud=self, activo=True).exists():
			self.estado = self.ESTADO_CERRADA
			self.save(update_fields=['estado'])


class SolicitudItem(models.Model):
	"""Legajo solicitado dentro de una solicitud (intención)."""

	solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name='items')
	legajo = models.ForeignKey(Legajo, on_delete=models.PROTECT, related_name='solicitudes')
	disponible_al_crear = models.BooleanField(default=True)

	def __str__(self):
		return f"Item solicitud {self.solicitud_id} - {self.legajo.codigo}"


class Prestamo(models.Model):
	"""Préstamo de un legajo a un usuario derivado de una solicitud."""

	solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name='prestamos')
	legajo = models.ForeignKey(Legajo, on_delete=models.PROTECT, related_name='prestamos')
	usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='prestamos')
	activo = models.BooleanField(default=True)
	bloqueado_en_prep = models.BooleanField(default=False, help_text="Marcado si el legajo estaba bloqueado/extraviado en preparación")
	creado_en = models.DateTimeField(auto_now_add=True)
	entregado_en = models.DateTimeField(null=True, blank=True)
	devuelto_en = models.DateTimeField(null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['legajo'], condition=models.Q(activo=True), name='unico_prestamo_activo_por_legajo'),
		]

	def __str__(self):
		return f"Prestamo {self.id} - {self.legajo.codigo} ({'activo' if self.activo else 'cerrado'})"

	def marcar_entregado(self):
		if not self.entregado_en:
			self.entregado_en = timezone.now()
			self.save(update_fields=['entregado_en'])
			# Si todos los préstamos de la solicitud están entregados se actualiza estado
			if not Prestamo.objects.filter(solicitud=self.solicitud, entregado_en__isnull=True).exists():
				self.solicitud.marcar_entregada()

	def marcar_devuelto(self):
		if self.activo:
			self.devuelto_en = timezone.now()
			self.activo = False
			self.save(update_fields=['devuelto_en', 'activo'])
			# Actualizar estado de la solicitud si corresponde
			self.solicitud.marcar_cerrada_si_corresponde()

