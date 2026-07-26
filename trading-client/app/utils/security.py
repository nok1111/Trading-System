"""Helpers de seguridad para evitar fugas de credenciales."""


def mask_secret(value: str | None, visible: int = 4) -> str:
    """Oculta un secreto dejando visibles solo los primeros y últimos caracteres.

    Args:
        value: Secreto a enmascarar.
        visible: Número de caracteres visibles al inicio y al final.

    Returns:
        Cadena enmascarada o "not_set" si el valor es vacío.
    """
    if not value:
        return "not_set"
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}***{value[-visible:]}"
