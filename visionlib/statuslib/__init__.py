# ---------------------
# STATUSLIB
# ---------------------
# Monitoramento em background de mudança de status (online/offline) de câmeras
# (lidas do CamWatch, ver camlib) e dispositivos NioBox (ver operlib) — envia
# WhatsApp (Evolution API) e push mobile (pushlib, Web Push/VAPID) quando muda,
# nunca a cada checagem. Mesmo conteúdo nos dois canais.
#
# Câmeras e dispositivos usam critérios diferentes de notificação:
#   - Câmera: só notifica offline depois de CAM_LIMIAR_OFFLINE_SEGUNDOS (10 min)
#     contínuos, pra não alarmar por quedas curtas que a própria câmera já
#     resolve sozinha (câmeras "piscando" foram observadas na prática). Enquanto
#     alguma câmera monitorada estiver offline, a checagem de câmeras roda a
#     cada CAM_INTERVALO_OFFLINE_SEGUNDOS (1 min) em vez do intervalo normal.
#   - Dispositivo (NioBox): notifica na primeira mudança confirmada — a
#     confirmação de offline já é feita em operlib._checar_dispositivo_online
#     (3 leituras, 10s de intervalo), então aqui não precisa de limiar extra.
#     Continua no intervalo normal (STATUS_MONITOR_INTERVAL_MIN).
#
# Último status conhecido fica em memória (dicts + lock), não no banco — o
# processo roda com um único worker Gunicorn (--workers 1), então não há
# inconsistência entre processos. Efeito colateral aceito: o estado se perde
# a cada restart/deploy — a checagem seguinte a um restart nunca notifica
# (não há "status anterior" pra comparar), só atrasa em até um ciclo a
# detecção de uma mudança que coincidiu com o restart.

import os
import time
import threading
import logging

import requests

from config.database import get_db_connection
from visionlib.camlib import obter_status_cameras, formatar_duracao
from visionlib.operlib import obter_status_dispositivos
from visionlib import pushlib

logger = logging.getLogger(__name__)

_started = False
_started_lock = threading.Lock()

CAM_LIMIAR_OFFLINE_SEGUNDOS = 600  # 10 min contínuos antes de notificar câmera offline
CAM_INTERVALO_OFFLINE_SEGUNDOS = 60  # checagem de câmeras a cada 1 min enquanto alguma estiver offline

_cam_notificado = {}   # {chave: bool} — já mandou o alerta de OFFLINE para este episódio
_disp_status = {}      # {chave: bool} — último status conhecido de dispositivo
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
    if not numero:
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


def _notificar(idcond, nome_cond, numero_whatsapp, corpo):
    """
    Manda o mesmo alerta pelos dois canais — WhatsApp (número por condomínio,
    cadmensagem_whatsapp) e push mobile (todo usuário com acesso ao
    condomínio, ver pushlib). Retorna True se pelo menos um canal entregou.
    """
    titulo = f"ParkVision — {nome_cond}"
    ok_whatsapp = _enviar_whatsapp(numero_whatsapp, f"{titulo}\n{corpo}")
    try:
        ok_push = pushlib.enviar_push(idcond, titulo, corpo)
    except Exception as e:
        logger.error(f"statuslib._notificar: push falhou — {e}")
        ok_push = False
    return ok_whatsapp or ok_push


def _verificar_cameras_condominio(idcond, nome_cond, numero_whatsapp):
    """
    Checa as câmeras do condomínio. Notifica OFFLINE só após
    CAM_LIMIAR_OFFLINE_SEGUNDOS contínuos, e ONLINE só se o offline anterior
    já tinha sido notificado (evita mensagem de recuperação de algo que nunca
    chegou a alarmar).

    Retorna True se alguma câmera do condomínio está offline agora (usado para
    decidir o intervalo do próximo ciclo).
    """
    algum_offline = False
    for cam in obter_status_cameras(idcond):
        chave = f"cam:{cam['idcam']}"
        ativo = cam['ativo']
        if ativo is None:
            continue

        if ativo:
            with _status_lock:
                estava_notificado = _cam_notificado.pop(chave, False)
            if estava_notificado:
                logger.info(f"statuslib: câmera recuperada — {nome_cond} / {cam['nome']}")
                _notificar(idcond, nome_cond, numero_whatsapp, f"Câmera {cam['nome']}: ONLINE ✅ (voltou)")
            continue

        algum_offline = True
        segundos = cam.get('offline_segundos') or 0
        with _status_lock:
            ja_notificado = _cam_notificado.get(chave, False)
        if not ja_notificado and segundos >= CAM_LIMIAR_OFFLINE_SEGUNDOS:
            duracao = formatar_duracao(segundos)
            logger.info(f"statuslib: câmera offline confirmada — {nome_cond} / {cam['nome']} ({duracao})")
            if _notificar(idcond, nome_cond, numero_whatsapp, f"Câmera {cam['nome']}: OFFLINE ⚠️ há {duracao}"):
                with _status_lock:
                    _cam_notificado[chave] = True

    return algum_offline


def _verificar_dispositivos_condominio(idcond, nome_cond, numero_whatsapp):
    """Checa os dispositivos NioBox — notifica na primeira mudança confirmada."""
    for disp in obter_status_dispositivos(idcond):
        chave = f"disp:{disp['idcam']}"
        ativo = disp['ativo']
        if ativo is None:
            continue

        with _status_lock:
            anterior = _disp_status.get(chave)
            _disp_status[chave] = ativo
        if anterior is None or anterior == ativo:
            continue

        status_txt = 'ONLINE ✅' if ativo else 'OFFLINE ⚠️'
        logger.info(f"statuslib: mudança de status — {nome_cond} / Dispositivo {disp['label']} -> {status_txt}")
        _notificar(idcond, nome_cond, numero_whatsapp, f"Dispositivo {disp['label']}: {status_txt}")


def _monitor_loop(interval_normal_seconds):
    proxima_checagem_dispositivos = 0.0

    while True:
        algum_cam_offline = False
        try:
            agora = time.time()
            checar_dispositivos_agora = agora >= proxima_checagem_dispositivos

            for idcond in _listar_condominios_monitorados():
                nome_cond       = _obter_nome_condominio(idcond)
                numero_whatsapp = _obter_numero_whatsapp(idcond)

                if _verificar_cameras_condominio(idcond, nome_cond, numero_whatsapp):
                    algum_cam_offline = True

                if checar_dispositivos_agora:
                    _verificar_dispositivos_condominio(idcond, nome_cond, numero_whatsapp)

            if checar_dispositivos_agora:
                proxima_checagem_dispositivos = agora + interval_normal_seconds
        except Exception as e:
            logger.error(f"statuslib._monitor_loop: erro inesperado — {e}")

        time.sleep(CAM_INTERVALO_OFFLINE_SEGUNDOS if algum_cam_offline else interval_normal_seconds)


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
    logger.info(f"statuslib: monitor iniciado (intervalo={interval_min} min; "
                f"{CAM_INTERVALO_OFFLINE_SEGUNDOS}s enquanto alguma câmera estiver offline)")
