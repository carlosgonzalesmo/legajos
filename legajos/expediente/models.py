from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class Legajo(models.Model):
	"""Representa un legajo físico que puede ser solicitado y prestado."""

	codigo = models.CharField(max_length=50, unique=True)
	nombre = models.CharField(max_length=255)
	descripcion = models.TextField(blank=True)
	bloqueado = models.BooleanField(default=False, help_text="Marcado si no se encuentra físicamente / extraviado")
	creado_en = models.DateTimeField(auto_now_add=True)
	actualizado_en = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:
		return f"{self.codigo} - {self.nombre}"

	@property
	def disponible(self) -> bool:
		"""Indica si está disponible para una nueva solicitud."""

		if self.bloqueado:
			return False
		return not Prestamo.objects.filter(
			legajo=self,
			estado__in=Prestamo.ESTADOS_ACTIVOS,
		).exists()


class Solicitud(models.Model):
	"""Solicitud de uno o varios legajos por parte de un usuario."""

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

	def __str__(self) -> str:
		return f"Solicitud #{self.id} - {self.usuario} - {self.estado}"

	def marcar_preparada(self, tiene_legajos_listos: bool) -> None:
		if self.estado != self.ESTADO_PENDIENTE:
			return
		self.estado = self.ESTADO_PREPARADA if tiene_legajos_listos else self.ESTADO_CANCELADA
		self.save()

	def marcar_entregada(self) -> None:
		if self.estado not in (self.ESTADO_PREPARADA, self.ESTADO_PENDIENTE):
			return
		pendientes = self.prestamos.filter(
			estado__in=[Prestamo.ESTADO_PENDIENTE, Prestamo.ESTADO_LISTO],
		)
		if pendientes.exists():
			return
		self.estado = self.ESTADO_ENTREGADA
		self.save()

	def marcar_cerrada_si_corresponde(self) -> None:
		if self.prestamos.filter(estado=Prestamo.ESTADO_ENTREGADO).exists():
			return
		if self.prestamos.filter(estado=Prestamo.ESTADO_LISTO).exists():
			return
		self.estado = self.ESTADO_CERRADA
		self.save()


class SolicitudItem(models.Model):
	"""Legajo solicitado dentro de una solicitud (intención)."""

	solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name='items')
	legajo = models.ForeignKey(Legajo, on_delete=models.PROTECT, related_name='solicitudes')
	disponible_al_crear = models.BooleanField(default=True)

	def __str__(self) -> str:
		return f"Item solicitud {self.solicitud_id} - {self.legajo.codigo}"


class Prestamo(models.Model):
	"""Préstamo de un legajo a un usuario derivado de una solicitud."""

	ESTADO_PENDIENTE = 'pendiente'
	ESTADO_LISTO = 'listo'
	ESTADO_EXTRAVIADO = 'extraviado'
	ESTADO_ENTREGADO = 'entregado'
	ESTADO_DEVUELTO = 'devuelto'
	ESTADOS = [
		(ESTADO_PENDIENTE, 'Pendiente'),
		(ESTADO_LISTO, 'Listo para entrega'),
		(ESTADO_EXTRAVIADO, 'Extraviado'),
		(ESTADO_ENTREGADO, 'Entregado'),
		(ESTADO_DEVUELTO, 'Devuelto'),
	]
	ESTADOS_ACTIVOS = [ESTADO_PENDIENTE, ESTADO_LISTO, ESTADO_ENTREGADO]

	solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name='prestamos')
	legajo = models.ForeignKey(Legajo, on_delete=models.PROTECT, related_name='prestamos')
	usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='prestamos')
	estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE)
	activo = models.BooleanField(default=True)
	creado_en = models.DateTimeField(auto_now_add=True)
	entregado_en = models.DateTimeField(null=True, blank=True)
	devuelto_en = models.DateTimeField(null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=['legajo'],
				condition=models.Q(activo=True),
				name='unico_prestamo_activo_por_legajo',
			),
		]

	def __str__(self) -> str:
		return f"Prestamo {self.id} - {self.legajo.codigo} ({self.estado})"

	def marcar_listo(self) -> None:
		if self.estado != self.ESTADO_PENDIENTE:
			return
		self.estado = self.ESTADO_LISTO
		self.activo = True
		self.entregado_en = None
		self.devuelto_en = None
		self.save()
		if self.legajo.bloqueado:
			self.legajo.bloqueado = False
			self.legajo.save()

	def marcar_extraviado(self) -> None:
		if self.estado not in (self.ESTADO_PENDIENTE, self.ESTADO_LISTO):
			return
		self.estado = self.ESTADO_EXTRAVIADO
		self.activo = False
		self.entregado_en = None
		self.devuelto_en = None
		self.save()
		if not self.legajo.bloqueado:
			self.legajo.bloqueado = True
			self.legajo.save()

	def marcar_entregado(self) -> None:
		if self.estado != self.ESTADO_LISTO:
			return
		self.estado = self.ESTADO_ENTREGADO
		self.activo = True
		self.entregado_en = timezone.now()
		self.save()

	def marcar_devuelto(self) -> None:
		if self.estado != self.ESTADO_ENTREGADO:
			return
		self.estado = self.ESTADO_DEVUELTO
		self.activo = False
		self.devuelto_en = timezone.now()
		self.save()
		if self.legajo.bloqueado:
			self.legajo.bloqueado = False
			self.legajo.save()
		self.solicitud.marcar_cerrada_si_corresponde()

