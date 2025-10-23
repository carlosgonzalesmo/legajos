"""Helpers de autorización específicos del dominio expediente."""

ADMIN_GROUP_NAME = 'Administradores'
USERS_GROUP_NAME = 'Solicitantes'


def es_administrador(usuario) -> bool:
    """Indica si el usuario pertenece al grupo Administradores o tiene flag de staff."""

    if not usuario.is_authenticated:
        return False
    return usuario.is_staff or usuario.groups.filter(name=ADMIN_GROUP_NAME).exists()


def es_solicitante(usuario) -> bool:
    """Indica si el usuario pertenece al grupo de solicitantes (o es administrador)."""

    if not usuario.is_authenticated:
        return False
    return es_administrador(usuario) or usuario.groups.filter(name=USERS_GROUP_NAME).exists()
