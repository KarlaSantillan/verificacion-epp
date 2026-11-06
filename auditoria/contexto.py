"""Quién está haciendo el cambio en este momento (TK08).

El middleware guarda el usuario de cada petición. Si no hay usuario (comandos,
procesos automáticos) o si el código lo pide con `como_sistema()`, el evento se
registra con el actor "Sistema" (RF16-CA02).
"""
from contextlib import contextmanager
from contextvars import ContextVar

_usuario = ContextVar("usuario_auditoria", default=None)
_sistema = ContextVar("actor_sistema", default=False)


def usuario_actual():
    if _sistema.get():
        return None
    usuario = _usuario.get()
    return usuario if usuario is not None and usuario.is_authenticated else None


def fijar_usuario(usuario):
    return _usuario.set(usuario)


def restaurar_usuario(token):
    _usuario.reset(token)


@contextmanager
def como_sistema():
    """Uso: with como_sistema(): ...  → los cambios se registran con el actor "Sistema"."""
    token = _sistema.set(True)
    try:
        yield
    finally:
        _sistema.reset(token)
