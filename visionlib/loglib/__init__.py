# ---------------------
# LOGLIB
# ---------------------
# Persiste os logs do sistema (app.logger / visionlib.*) em banco,
# com retenção de RETENCAO_DIAS dias, para a tela /logs.
#
# Gravação é assíncrona (fila em memória + thread consumidora) para não
# bloquear a requisição que gerou o log com uma escrita síncrona no MySQL.

import logging
import queue
import threading
import time

from config.database import get_db_connection

logger = logging.getLogger(__name__)

RETENCAO_DIAS         = 3
INTERVALO_LIMPEZA_SEG = 3600  # 1 hora

_started = False
_started_lock = threading.Lock()
_fila = queue.Queue(maxsize=10000)


# ── Migração de schema ────────────────────────────────────────────────────────

def _migrar_tabela() -> None:
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logsistema (
                idlog     INT AUTO_INCREMENT PRIMARY KEY,
                nivel     VARCHAR(10)  NOT NULL,
                mensagem  TEXT         NOT NULL,
                criado_em DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_criado_em (criado_em)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
    except Exception as e:
        print(f"loglib._migrar_tabela: erro — {e}")
    finally:
        cursor.close()
        conn.close()


# ── Handler de logging (produtor) ─────────────────────────────────────────────

class DBLogHandler(logging.Handler):
    """Enfileira registros formatados; a gravação no banco é feita por outra thread."""

    def emit(self, record):
        try:
            msg = self.format(record)
            _fila.put_nowait((record.levelname, msg))
        except queue.Full:
            pass
        except Exception:
            self.handleError(record)


# ── Consumidor da fila (grava em lote) ────────────────────────────────────────

def _inserir_lote(lote: list) -> None:
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.executemany(
            "INSERT INTO logsistema (nivel, mensagem) VALUES (%s, %s)",
            lote
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        # Não usar `logger` aqui — evitaria reentrância no próprio handler de log.
        print(f"loglib._inserir_lote: erro ao gravar {len(lote)} log(s) — {e}")
    finally:
        cursor.close()
        conn.close()


def _loop_gravacao() -> None:
    while True:
        item = _fila.get()
        lote = [item]
        while len(lote) < 200:
            try:
                lote.append(_fila.get_nowait())
            except queue.Empty:
                break
        _inserir_lote(lote)


# ── Limpeza periódica (retenção) ──────────────────────────────────────────────

def _limpar_antigos() -> None:
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM logsistema WHERE criado_em < NOW() - INTERVAL %s DAY",
            (RETENCAO_DIAS,)
        )
        conn.commit()
        if cursor.rowcount:
            print(f"loglib: {cursor.rowcount} log(s) com mais de {RETENCAO_DIAS} dias removido(s)")
    except Exception as e:
        conn.rollback()
        print(f"loglib._limpar_antigos: erro — {e}")
    finally:
        cursor.close()
        conn.close()


def _loop_limpeza() -> None:
    while True:
        try:
            _limpar_antigos()
        except Exception as e:
            print(f"loglib._loop_limpeza: erro inesperado — {e}")
        time.sleep(INTERVALO_LIMPEZA_SEG)


# ── Interface pública ─────────────────────────────────────────────────────────

def iniciar_persistencia_logs() -> None:
    """Cria a tabela e inicia as threads de gravação e limpeza. Idempotente por processo."""
    global _started
    with _started_lock:
        if _started:
            return
        _started = True

    _migrar_tabela()

    threading.Thread(target=_loop_gravacao, daemon=True, name='parkvision-log-writer').start()
    threading.Thread(target=_loop_limpeza, daemon=True, name='parkvision-log-cleanup').start()
    print(f"loglib: persistência de logs iniciada (retenção={RETENCAO_DIAS} dias)")


def obter_logs(desde_idlog: int = 0, limit: int = 300) -> list:
    """Retorna logs com idlog > desde_idlog, em ordem crescente (para polling incremental)."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT idlog, nivel, mensagem, criado_em
            FROM logsistema
            WHERE idlog > %s
            ORDER BY idlog ASC
            LIMIT %s
        """, (desde_idlog, limit))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def contar_logs() -> int:
    conn = get_db_connection()
    if not conn:
        return 0
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM logsistema")
        return cursor.fetchone()[0]
    finally:
        cursor.close()
        conn.close()


def limpar_todos() -> bool:
    """Apaga todos os logs (ação manual do administrador)."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("TRUNCATE TABLE logsistema")
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"loglib.limpar_todos: erro — {e}")
        return False
    finally:
        cursor.close()
        conn.close()
