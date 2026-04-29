# ---------------------
# CAMLIB
# ---------------------
# Monitoramento de câmeras RTSP em background.
# Persiste os resultados no banco (cadcamera.cam_ativo / cam_checado_em)
# para que qualquer worker/processo sirva dados consistentes.

import os
import time
import socket
import logging
import threading
from datetime import datetime
from urllib.parse import urlparse

import pytz

from config.database import get_db_connection

logger    = logging.getLogger(__name__)
BRASIL_TZ = pytz.timezone('America/Sao_Paulo')

_started      = False
_started_lock = threading.Lock()


# ── Migração de schema ────────────────────────────────────────────────────────

def _migrar_tabela() -> None:
    """Adiciona cam_ativo e cam_checado_em em cadcamera se ainda não existirem."""
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME   = 'cadcamera'
              AND COLUMN_NAME  = 'cam_ativo'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "ALTER TABLE cadcamera "
                "ADD COLUMN cam_ativo      TINYINT(1) NULL DEFAULT NULL, "
                "ADD COLUMN cam_checado_em DATETIME   NULL DEFAULT NULL"
            )
            conn.commit()
            logger.info("camlib: colunas cam_ativo / cam_checado_em adicionadas em cadcamera")
    except Exception as e:
        logger.error(f"camlib._migrar_tabela: {e}")
    finally:
        cursor.close()
        conn.close()


# ── Verificação de câmera ─────────────────────────────────────────────────────

def _check_rtsp_alive(rtsp_url: str, timeout: int = 4) -> bool:
    """
    Verifica se câmera responde via TCP na porta RTSP.
    Apenas testa a abertura de conexão TCP — não exige resposta RTSP,
    evitando falsos negativos em câmeras que aceitam a porta mas
    ignoram ou demoram para responder ao handshake RTSP/OPTIONS.
    """
    try:
        parsed = urlparse(rtsp_url)
        host   = parsed.hostname
        port   = parsed.port or 554
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


# ── Consultas ao banco ────────────────────────────────────────────────────────

def _listar_cameras_rtsp() -> list:
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT idcam, idcond,
                   COALESCE(nomecamera, CONCAT('Câm. ', idcam)) AS nomecamera,
                   rtsp, cam_ativo
            FROM cadcamera
            WHERE rtsp IS NOT NULL AND TRIM(rtsp) <> ''
        """)
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"camlib._listar_cameras_rtsp: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def _obter_nome_cond(idcond: int) -> str:
    conn = get_db_connection()
    if not conn:
        return f'Cond. {idcond}'
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT nmcond FROM cadcond WHERE idcond = %s LIMIT 1", (idcond,))
        row = cursor.fetchone()
        return row['nmcond'] if row else f'Cond. {idcond}'
    except Exception:
        return f'Cond. {idcond}'
    finally:
        cursor.close()
        conn.close()


# ── Notificação Telegram ──────────────────────────────────────────────────────

def _notificar_mudanca_status(idcond: int, nome_camera: str, ativo: bool) -> None:
    from visionlib.teleglib import teleg_info, enviar_mensagem_telegram
    try:
        token, chat_id = teleg_info(idcond)
        if not token or not chat_id:
            return
    except Exception:
        return

    nmcond = _obter_nome_cond(idcond)
    status = '✅ ATIVA' if ativo else '❌ INATIVA'
    agora  = datetime.now(BRASIL_TZ).strftime('%d/%m/%Y %H:%M:%S')

    msg = (
        '⚠️ IMPORTANTE — ParkVision\n'
        'Monitoramento de Câmeras\n'
        '\n'
        f'Condomínio: {nmcond}\n'
        f'Câmera: {nome_camera}\n'
        f'Novo status: {status}\n'
        '\n'
        f'Data/Hora: {agora}'
    )
    try:
        enviar_mensagem_telegram(token, chat_id, msg)
        logger.info(f"camlib: Telegram enviado — {nome_camera} ({nmcond}) → {status}")
    except Exception as e:
        logger.warning(f"camlib._notificar_mudanca_status: falha no Telegram — {e}")


# ── Ciclo de verificação ──────────────────────────────────────────────────────

def _executar_verificacao() -> None:
    """
    Verifica todas as câmeras RTSP e persiste o resultado no banco.
    Lê e escreve em cadcamera para que qualquer worker sirva dados atualizados.
    """
    cameras = _listar_cameras_rtsp()
    if not cameras:
        return

    conn = get_db_connection()
    if not conn:
        logger.error("camlib._executar_verificacao: sem conexão com o banco")
        return

    cursor = conn.cursor()
    n_ativas = 0

    try:
        for cam in cameras:
            idcam          = cam['idcam']
            idcond         = cam['idcond']
            nome           = cam['nomecamera']
            rtsp           = cam['rtsp']
            anterior_ativo = cam['cam_ativo']   # valor lido junto com a lista

            novo_ativo     = _check_rtsp_alive(rtsp)
            novo_ativo_int = 1 if novo_ativo else 0
            if novo_ativo:
                n_ativas += 1

            cursor.execute("""
                UPDATE cadcamera
                   SET cam_ativo = %s, cam_checado_em = NOW()
                 WHERE idcam = %s
            """, (novo_ativo_int, idcam))

            # Notifica apenas quando o status muda (não na primeira verificação)
            if anterior_ativo is not None and anterior_ativo != novo_ativo_int:
                try:
                    _notificar_mudanca_status(idcond, nome, novo_ativo)
                except Exception as e:
                    logger.warning(f"camlib: erro ao notificar — {e}")

            time.sleep(0.3)   # pausa mínima entre câmeras

        conn.commit()

    except Exception as e:
        logger.error(f"camlib._executar_verificacao: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    logger.info(
        f"camlib: verificação concluída — {n_ativas}/{len(cameras)} câmera(s) ativa(s)"
    )


def _monitor_loop(interval_seconds: int) -> None:
    while True:
        try:
            _executar_verificacao()
        except Exception as e:
            logger.error(f"camlib._monitor_loop: erro inesperado — {e}")
        time.sleep(interval_seconds)


# ── Interface pública ─────────────────────────────────────────────────────────

def iniciar_monitor_cameras() -> None:
    """
    Inicia a thread daemon de monitoramento. Idempotente por processo.
    Executa a migração de schema antes de subir a thread.
    """
    global _started
    with _started_lock:
        if _started:
            return
        _started = True

    _migrar_tabela()

    interval_min = max(1, int(os.getenv('CAM_MONITOR_INTERVAL_MIN', '3')))
    interval_sec = interval_min * 60

    t = threading.Thread(
        target=_monitor_loop,
        args=(interval_sec,),
        daemon=True,
        name='parkvision-cam-monitor',
    )
    t.start()
    logger.info(f"camlib: monitor iniciado (intervalo={interval_min} min)")


def obter_status_cameras(idcond: int) -> list:
    """
    Lê o último status das câmeras diretamente do banco.
    Funciona em qualquer worker/processo — sem dependência de estado em memória.
    """
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT idcam,
                   COALESCE(nomecamera, CONCAT('Câm. ', idcam)) AS nome,
                   cam_ativo                                     AS ativo,
                   cam_checado_em,
                   UNIX_TIMESTAMP(cam_checado_em)               AS checado_ts
            FROM cadcamera
            WHERE idcond = %s
              AND rtsp IS NOT NULL AND TRIM(rtsp) <> ''
              AND cam_checado_em IS NOT NULL
            ORDER BY nomecamera
        """, (idcond,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            dt = row['cam_checado_em']
            result.append({
                'idcam':      row['idcam'],
                'nome':       row['nome'],
                'ativo':      bool(row['ativo']) if row['ativo'] is not None else None,
                'checado_em': dt.strftime('%d/%m/%Y %H:%M:%S') if dt else None,
                'checado_ts': float(row['checado_ts']) if row['checado_ts'] else None,
            })
        return result
    except Exception as e:
        logger.error(f"camlib.obter_status_cameras: {e}")
        return []
    finally:
        cursor.close()
        conn.close()
