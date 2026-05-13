from backend.schemas.events import Actor

CAMEO_ROLE_MAP: dict[str, str] = {
    "GOV": "state_military",
    "MIL": "state_military",
    "REB": "nonstate_armed",
    "OPP": "protesters",
    "CVL": "civilians",
    "COP": "police",
    "MED": "civilians",
    "EDU": "civilians",
    "BUS": "civilians",
    "JUD": "state_military",
    "IGO": "international_org",
    "NGO": "international_org",
    "UNK": "unknown",
}


def cameo_to_actor(cameo_code: str, name: str | None = None) -> Actor:
    """Convierte un codigo CAMEO a un Actor canonico (F-NORM-ACTORS).

    Si el codigo no esta en el diccionario el rol se marca como unknown
    preservando el nombre original para no perder informacion de la fuente.

    Args:
        cameo_code: Codigo CAMEO de 2-3 letras del actor.
        name: Nombre original del actor en la fuente.

    Returns:
        Actor canonico con rol normalizado.
    """
    role = CAMEO_ROLE_MAP.get(cameo_code.upper(), "unknown")
    return Actor(
        role=role,
        name=name or cameo_code,
        cameo_code=cameo_code.upper(),
    )
