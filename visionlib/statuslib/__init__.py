# ---------------------
# STATUSLIB
# ---------------------
# Monitoramento em background de mudança de status (online/offline) de câmeras
# (lidas do CamWatch, ver camlib) e dispositivos NioBox (ver operlib) — envia
# WhatsApp via Evolution API só quando o status muda, nunca a cada checagem.
#
# Último status conhecido fica em memória (dict + lock), não no banco — o
# processo roda com um único worker Gunicorn (--workers 1), então não há
# inconsistência entre processos. Efeito colateral aceito: o estado se perde
# a cada restart/deploy, então a checagem seguinte a um restart nunca notifica
# (não há "status anterior" pra comparar) — só atrasa em até um ciclo a
# detecção de uma mudança que coincidiu com o restart.

import os
import time
import threading
import logging

import requests

from config.database import get_db_connection
from visionlib.camlib import obter_status_cameras
from visionlib.operlib import obter_status_dispositivos

logger = logging.getLogger(__name__)

_started = False
_started_lock = threading.Lock()

_ultimo_status = {}  # {chave: bool} — último status conhecido de cada câmera/dispositivo
_status_lock = threading.Lock()


def _listar_condominios_monitorados():
    """Condomínios com pelo menos uma câmera (CamWatch) ou dispositivo (NioBox) configurado."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DISTINCT idcond FROM cadcamera
            WHERE camwatch_camera_id IS NOT NULL OR iddisp IS NOT NULL
        """)
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"statuslib._listar_condominios_monitorados: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def _obter_nome_condominio(idcond):
    conn = get_db_connection()
    if not conn:
        return f'Cond. {idcond}'
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nmcond FROM cadcond WHERE idcond = %s LIMIT 1", (idcond,))
        row = cursor.fetchone()
        return row[0] if row else f'Cond. {idcond}'
    except Exception:
        return f'Cond. {idcond}'
    finally:
        cursor.close()
        conn.close()


def _obter_numero_whatsapp(idcond):
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT numero FROM cadmensagem_whatsapp WHERE idcond = %s LIMIT 1", (idcond,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"statuslib._obter_numero_whatsapp: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def _enviar_whatsapp(numero, mensagem):
    api_url  = os.getenv('EVOLUTION_API_URL')
    api_key  = os.getenv('EVOLUTION_API_KEY')
    instance = os.getenv('EVOLUTION_INSTANCE')
    if not api_url or not api_key or not instance:
        logger.warning("statuslib._enviar_whatsapp: EVOLUTION_API_URL/API_KEY/INSTANCE não configurados")
        return False

    url = f"{api_url.rstrip('/')}/message/sendText/{instance}"
    try:
        resp = requests.post(
            url,
            json={'number': numero, 'text': mensagem},
            headers={'apikey': api_key},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"statuslib._enviar_whatsapp: mensagem enviada para {numero}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"statuslib._enviar_whatsapp: falha ao enviar para {numero} — {e}")
        return False


def _checar_mudanca(chave, ativo, descricao, idcond, nome_cond, numero_whatsapp):
    """
    Compara `ativo` com o último status conhecido de `chave`. Se mudou (e já
    havia um status anterior conhecido), envia WhatsApp. Sempre atualiza o
    último status guardado, inclusive na primeira vez (sem notificar).
    """
    if ativo is None:
        return
    with _status_lock:
        anterior = _ultimo_status.get(chave)
        _ultimo_status[chave] = ativo
    if anterior is None or anterior == ativo:
        return

    status_txt = 'ONLINE ✅' if ativo else 'OFFLINE ⚠️'
    mensagem = f"ParkVision — {nome_cond}\n{descricao}: {status_txt}"
    logger.info(f"statuslib: mudança de status — {nome_cond} / {descricao} -> {status_txt}")
    if numero_whatsapp:
        _enviar_whatsapp(numero_whatsapp, mensagem)


def _verificar_condominio(idcond):
    nome_cond       = _obter_nome_condominio(idcond)
    numero_whatsapp = _obter_numero_whatsapp(idcond)

    for cam in obter_status_cameras(idcond):
        _checar_mudanca(
            f"cam:{cam['idcam']}", cam['ativo'],
            f"Câmera {cam['nome']}", idcond, nome_cond, numero_whatsapp,
        )

    for disp in obter_status_dispositivos(idcond):
        _checar_mudanca(
            f"disp:{disp['idcam']}", disp['ativo'],
            f"Dispositivo {disp['label']}", idcond, nome_cond, numero_whatsapp,
        )


def _executar_verificacao():
    for idcond in _listar_condominios_monitorados():
        try:
            _verificar_condominio(idcond)
        except Exception as e:
            logger.error(f"statuslib._executar_verificacao: idcond={idcond} — {e}")


def _monitor_loop(interval_seconds):
    while True:
        try:
            _executar_verificacao()
        except Exception as e:
            logger.error(f"statuslib._monitor_loop: erro inesperado — {e}")
        time.sleep(interval_seconds)


def iniciar_monitor_status():
    """Inicia a thread daemon de monitoramento. Idempotente por processo."""
    global _started
    with _started_lock:
        if _started:
            return
        _started = True

    interval_min = max(1, int(os.getenv('STATUS_MONITOR_INTERVAL_MIN', '5')))
    interval_sec = interval_min * 60

    t = threading.Thread(
        target=_monitor_loop,
        args=(interval_sec,),
        daemon=True,
        name='parkvision-status-monitor',
    )
    t.start()
    logger.info(f"statuslib: monitor iniciado (intervalo={interval_min} min)")
