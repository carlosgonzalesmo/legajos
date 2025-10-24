from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Legajo, Prestamo, Solicitud
from .permissions import USERS_GROUP_NAME


class WorkflowTests(TestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.admin = self.user_model.objects.create_user(
			username='admin', email='admin@example.com', password='secret', is_staff=True
		)
		self.user = self.user_model.objects.create_user(
			username='usuario', email='usuario@example.com', password='secret'
		)
		solicitantes, _ = Group.objects.get_or_create(name=USERS_GROUP_NAME)
		self.user.groups.add(solicitantes)

	def _crear_solicitud(self, cantidad=2):
		solicitud = Solicitud.objects.create(usuario=self.user)
		prestamos = []
		for idx in range(cantidad):
			legajo = Legajo.objects.create(codigo=f"L{idx}", titulo=f"Legajo {idx}")
			prestamos.append(
				Prestamo.objects.create(solicitud=solicitud, legajo=legajo, usuario=self.user)
			)
		return solicitud, prestamos

	def test_preparacion_admin_define_estado(self):
		solicitud, prestamos = self._crear_solicitud(2)

		self.client.force_login(self.admin)
		response = self.client.post(
			reverse('solicitud_preparar', args=[solicitud.pk]),
			{'prestamos_listos': [prestamos[0].pk]},
		)
		self.assertEqual(response.status_code, 302)

		solicitud.refresh_from_db()
		for prestamo in prestamos:
			prestamo.refresh_from_db()
			prestamo.legajo.refresh_from_db()

		self.assertEqual(prestamos[0].estado, Prestamo.ESTADO_LISTO)
		self.assertEqual(prestamos[1].estado, Prestamo.ESTADO_EXTRAVIADO)
		self.assertFalse(prestamos[0].legajo.bloqueado)
		self.assertTrue(prestamos[1].legajo.bloqueado)
		self.assertEqual(solicitud.estado, Solicitud.ESTADO_PREPARADA)

	def test_usuario_confirma_entrega_total(self):
		solicitud, prestamos = self._crear_solicitud(1)
		prestamo = prestamos[0]
		prestamo.marcar_listo()
		solicitud.marcar_preparada(True)

		self.client.force_login(self.user)
		response = self.client.post(reverse('solicitud_confirmar_entrega', args=[solicitud.pk]))
		self.assertEqual(response.status_code, 302)

		prestamo.refresh_from_db()
		solicitud.refresh_from_db()
		self.assertEqual(prestamo.estado, Prestamo.ESTADO_ENTREGADO)
		self.assertIsNotNone(prestamo.entregado_en)
		self.assertEqual(solicitud.estado, Solicitud.ESTADO_ENTREGADA)

	def test_devolucion_cierra_solicitud(self):
		solicitud, prestamos = self._crear_solicitud(1)
		prestamo = prestamos[0]
		prestamo.marcar_listo()
		solicitud.marcar_preparada(True)

		self.client.force_login(self.user)
		self.client.post(reverse('solicitud_confirmar_entrega', args=[solicitud.pk]))
		response = self.client.get(reverse('prestamo_devolver', args=[prestamo.pk]))
		self.assertEqual(response.status_code, 302)

		prestamo.refresh_from_db()
		solicitud.refresh_from_db()
		self.assertEqual(prestamo.estado, Prestamo.ESTADO_DEVUELTO)
		self.assertIsNotNone(prestamo.devuelto_en)
		self.assertEqual(solicitud.estado, Solicitud.ESTADO_CERRADA)
