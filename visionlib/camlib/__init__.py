# ---------------------
# CAMLIB
# ---------------------
# Monitoramento de câmeras RTSP em background.
# Verifica periodicamente se as câmeras estão respondendo via protocolo RTSP
# e notifica via Telegram quando o status muda.

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

_camera_status: dict = {}          # {idcam: dict} — store em memória
_status_lock  = threading.Lock()
_started      = False
_started_lock = threading.Lock()


# ── Verificação de câmera ─────────────────────────────────────────────────────

def _check_rtsp_alive(rtsp_url: str, timeout: int = 3) -> bool:
    """
    Verifica se câmera responde via protocolo RTSP.
    Usa conexão TCP + OPTIONS request — muito mais leve que OpenCV.
    """
    try:
        parsed = urlparse(rtsp_url)
        host   = parsed.hostname
        port   = parsed.port or 554
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b'OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n')
            data = sock.recv(256)
            return b'RTSP' in data
    except Exception:
        return False


# ── Consultas ao banco ────────────────────────────────────────────────────────

def _listar_cameras_rtsp() -> list:
    """Retorna todas as câmeras com RTSP configurado em todos os condomínios."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT idcam, idcond,
                   COALESCE(nomecamera, CONCAT('Câm. ', idcam)) AS nomecamera,
                   rtsp
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
    """Envia alerta Telegram quando o status de uma câmera muda."""
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
    """Verifica todas as câmeras RTSP e atualiza o store em memória."""
    cameras = _listar_cameras_rtsp()
    if not cameras:
        return

    agora      = datetime.now(BRASIL_TZ)
    checado_em = agora.strftime('%d/%m/%Y %H:%M:%S')
    checado_ts = agora.timestamp()

    for cam in cameras:
        idcam  = cam['idcam']
        idcond = cam['idcond']
        nome   = cam['nomecamera']
        rtsp   = cam['rtsp']

        # Captura status anterior antes de checar
        with _status_lock:
            anterior       = _camera_status.get(idcam)
            anterior_ativo = anterior['ativo'] if anterior is not None else None

        novo_ativo = _check_rtsp_alive(rtsp)

        with _status_lock:
            _camera_status[idcam] = {
                'idcam':      idcam,
                'idcond':     idcond,
                'nome':       nome,
                'ativo':      novo_ativo,
                'checado_em': checado_em,
                'checado_ts': checado_ts,
            }

        # Notifica apenas na mudança de estado (não na primeira verificação)
        if anterior_ativo is not None and anterior_ativo != novo_ativo:
            try:
                _notificar_mudanca_status(idcond, nome, novo_ativo)
            except Exception as e:
                logger.warning(f"camlib: erro ao notificar mudança — {e}")

        # Pausa mínima entre câmeras para não saturar a rede
        time.sleep(0.3)

    n_ativas   = sum(1 for v in _camera_status.values() if v['ativo'])
    n_total    = len(cameras)
    logger.info(f"camlib: verificação concluída — {n_ativas}/{n_total} câmera(s) ativa(s)")


def _monitor_loop(interval_seconds: int) -> None:
    """Loop principal: verifica câmeras e dorme pelo intervalo configurado."""
    while True:
        try:
            _executar_verificacao()
        except Exception as e:
            logger.error(f"camlib._monitor_loop: erro inesperado — {e}")
        time.sleep(interval_seconds)


# ── Interface pública ─────────────────────────────────────────────────────────

def iniciar_monitor_cameras() -> None:
    """
    Inicia a thread de monitoramento de câmeras em background (daemon, baixa prioridade).
    Idempotente: chamadas subsequentes no mesmo processo são ignoradas.
    O intervalo é configurado pela variável de ambiente CAM_MONITOR_INTERVAL_MIN (padrão: 10).
    """
    global _started
    with _started_lock:
        if _started:
            return
        _started = True

    interval_min = max(1, int(os.getenv('CAM_MONITOR_INTERVAL_MIN', '10')))
    interval_sec = interval_min * 60

    t = threading.Thread(
        target=_monitor_loop,
        args=(interval_sec,),
        daemon=True,
        name='parkvision-cam-monitor',
    )
    t.start()
    logger.info(f"camlib: monitor de câmeras iniciado (intervalo={interval_min} min)")


def obter_status_cameras(idcond: int) -> list:
    """Retorna o último status conhecido das câmeras de um condomínio específico."""
    with _status_lock:
        cameras = [v.copy() for v in _camera_status.values() if v['idcond'] == idcond]
    cameras.sort(key=lambda c: c['nome'])
    return cameras
