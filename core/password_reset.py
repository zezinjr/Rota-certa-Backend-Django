from __future__ import annotations

import re

from .models import AccessAccount, normalize_email


def normalize_phone_digits(value: str | None) -> str:
    """Apenas dígitos, para comparar telefones com ou sem máscara."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value))


def resolve_access_account_for_reset(
    *,
    email: str | None = None,
    phone: str | None = None,
) -> AccessAccount | None:
    """
    Localiza AccessAccount por e-mail da conta OU telefone da Person
    (exatamente um dos dois deve ser enviado na API).
    """
    has_email = bool((email or "").strip())
    has_phone = bool((phone or "").strip())
    if has_email == has_phone:
        return None

    if has_email:
        e = normalize_email(email or "")
        if not e:
            return None
        return (
            AccessAccount.objects.select_related("person")
            .filter(email=e, is_active=True, person__is_active=True)
            .first()
        )

    target = normalize_phone_digits(phone)
    if len(target) < 8:
        return None

    for acc in (
        AccessAccount.objects.select_related("person")
        .filter(is_active=True, person__is_active=True)
        .iterator(chunk_size=500)
    ):
        if normalize_phone_digits(acc.person.phone) == target:
            return acc

    return None
