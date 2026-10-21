"""Integration Azure : secrets Key Vault et instantanes de collecte dans Azure SQL.

Tout passe par l'identite Entra ID (identite managee sur App Service,
`az login` en local) : aucun mot de passe ni cle n'est stocke dans l'app.
Seule la variable non secrete KEY_VAULT_URL active l'integration ; sans elle,
l'application fonctionne comme avant (st.secrets / variables locales).
"""
import logging
import os
import pickle
import struct
from functools import lru_cache
from threading import RLock

_LOG = logging.getLogger(__name__)
_SQL_SCOPE = "https://database.windows.net/.default"
_SQL_COPT_SS_ACCESS_TOKEN = 1256  # attribut pyodbc pour passer un jeton Entra ID
_SQL_LOCK = RLock()
_SQL_TABLE_READY = False


def key_vault_enabled() -> bool:
    return bool(os.getenv("KEY_VAULT_URL"))


@lru_cache(maxsize=1)
def _credential():
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@lru_cache(maxsize=1)
def _secret_client():
    from azure.keyvault.secrets import SecretClient
    return SecretClient(vault_url=os.environ["KEY_VAULT_URL"], credential=_credential())


_SECRET_CACHE = {}


def get_key_vault_secret(name: str):
    """Lit un secret ; les '_' sont convertis en '-' (noms Key Vault autorises).

    Les secrets trouves ou absents sont memorises jusqu'au redemarrage ; une
    erreur transitoire (reseau, jeton) n'est pas memorisee.
    """
    if not key_vault_enabled():
        return None
    if name in _SECRET_CACHE:
        return _SECRET_CACHE[name]
    from azure.core.exceptions import ResourceNotFoundError
    try:
        value = _secret_client().get_secret(name.replace("_", "-")).value or None
    except ResourceNotFoundError:
        value = None  # secret facultatif non cree (ex: GROQ_API_KEY_1)
    except Exception as exc:
        _LOG.warning("Secret Key Vault %s indisponible (%s)", name, type(exc).__name__)
        return None
    _SECRET_CACHE[name] = value
    return value


# ─── Azure SQL (authentification Entra ID uniquement) ─────────────────────────
def _sql_connect():
    import pyodbc

    server = get_key_vault_secret("SQL_SERVER")
    database = get_key_vault_secret("SQL_DATABASE")
    if not server or not database:
        return None
    token = _credential().get_token(_SQL_SCOPE).token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token)}s", len(token), token)
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{server},1433;Database={database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;"
    )
    return pyodbc.connect(conn_str, attrs_before={_SQL_COPT_SS_ACCESS_TOKEN: token_struct})


def _ensure_table(conn):
    global _SQL_TABLE_READY
    if _SQL_TABLE_READY:
        return
    conn.execute(
        """
        IF OBJECT_ID('dbo.ScoutSnapshots', 'U') IS NULL
        CREATE TABLE dbo.ScoutSnapshots (
            Slot NVARCHAR(64) NOT NULL PRIMARY KEY,
            CollectedAt DATETIME2 NULL,
            Payload VARBINARY(MAX) NOT NULL,
            CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
        )
        """
    )
    conn.commit()
    _SQL_TABLE_READY = True


def load_snapshot(slot: str):
    """Retourne le DataFrame collecte pour ce creneau, ou None."""
    if not key_vault_enabled():
        return None
    try:
        with _SQL_LOCK:
            conn = _sql_connect()
            if conn is None:
                return None
            try:
                _ensure_table(conn)
                row = conn.execute(
                    "SELECT Payload FROM dbo.ScoutSnapshots WHERE Slot = ?", slot,
                ).fetchone()
            finally:
                conn.close()
        # Payload ecrit uniquement par cette application (save_snapshot).
        return pickle.loads(row[0]) if row else None
    except Exception as exc:
        _LOG.warning("Lecture SQL impossible (%s)", type(exc).__name__)
        return None


def save_snapshot(slot: str, df, keep: int = 8):
    """Enregistre le DataFrame du creneau et ne conserve que les `keep` derniers."""
    if not key_vault_enabled():
        return
    try:
        payload = pickle.dumps(df, protocol=pickle.HIGHEST_PROTOCOL)
        collected_at = df.attrs.get("collected_at")
        if collected_at is not None:
            collected_at = collected_at.replace(tzinfo=None)  # heure Maroc
        with _SQL_LOCK:
            conn = _sql_connect()
            if conn is None:
                return
            try:
                _ensure_table(conn)
                conn.execute("DELETE FROM dbo.ScoutSnapshots WHERE Slot = ?", slot)
                conn.execute(
                    "INSERT INTO dbo.ScoutSnapshots (Slot, CollectedAt, Payload) VALUES (?, ?, ?)",
                    slot, collected_at, payload,
                )
                conn.execute(
                    "DELETE FROM dbo.ScoutSnapshots WHERE Slot NOT IN "
                    "(SELECT TOP (?) Slot FROM dbo.ScoutSnapshots ORDER BY CreatedAt DESC)",
                    keep,
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as exc:
        _LOG.warning("Ecriture SQL impossible (%s)", type(exc).__name__)
