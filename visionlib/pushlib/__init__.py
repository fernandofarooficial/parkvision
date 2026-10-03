# ---------------------
# PUSHLIB
# ---------------------
# Notificações Web Push (VAPID) para a versão mobile — mesmo gatilho que o
# WhatsApp (visionlib/statuslib): câmera/NioBox mudou de status. Cada
# dispositivo/navegador que autorizou notificações fica em push_subscriptions,
# vinculado ao usuário (idgente) que autorizou.
#
# "Quem recebe" é decidido por acesso ao condomínio no momento do envio —
# consulta usuario_condominios (+ ADM, acesso total), não a sessão (quem
# dispara o envio é uma thread de background, sem sessão de ninguém).

import os
import json
import logging

from pywebpush import webpush, WebPushException

from config.database import get_db_connection

logger = logging.getLogger(__name__)


def salvar_inscricao(idgente, endpoint, p256dh, auth):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO push_subscriptions (idgente, endpoint, p256dh, auth)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE idgente = VALUES(idgente),
                                    p256dh  = VALUES(p256dh),
                                    auth    = VALUES(auth)
        """, (idgente, endpoint, p256dh, auth))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"pushlib.salvar_inscricao: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def remover_inscricao(endpoint):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"pushlib.remover_inscricao: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def _obter_inscricoes_condominio(idcond):
    """Inscrições de todos os usuários ativos com acesso ao condomínio (ADM + usuario_condominios)."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT ps.endpoint, ps.p256dh, ps.auth
            FROM push_subscriptions ps
            JOIN usuarios u ON u.idgente = ps.idgente
            WHERE u.ativo = 1
              AND (
                  u.tipo_usuario = 'ADM'
                  OR EXISTS (
                      SELECT 1 FROM usuario_condominios uc
                      WHERE uc.idgente = ps.idgente AND uc.idcond = %s
                  )
              )
        """, (idcond,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"pushlib._obter_inscricoes_condominio: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def enviar_push(idcond, titulo, corpo):
    """
    Envia notificação push para todos os inscritos com acesso ao condomínio.
    Retorna True se pelo menos uma notificação foi entregue com sucesso.
    """
    public_key   = os.getenv('VAPID_PUBLIC_KEY')
    private_file = os.getenv('VAPID_PRIVATE_KEY_FILE')
    claims_email = os.getenv('VAPID_CLAIMS_EMAIL')
    if not public_key or not private_file or not claims_email:
        logger.warning("pushlib.enviar_push: VAPID_PUBLIC_KEY/PRIVATE_KEY_FILE/CLAIMS_EMAIL não configurados")
        return False

    inscricoes = _obter_inscricoes_condominio(idcond)
    if not inscricoes:
        return False

    payload = json.dumps({'title': titulo, 'body': corpo})
    algum_sucesso = False

    for insc in inscricoes:
        subscription_info = {
            'endpoint': insc['endpoint'],
            'keys': {'p256dh': insc['p256dh'], 'auth': insc['auth']},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_file,
                vapid_claims={'sub': claims_email},
            )
            algum_sucesso = True
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in (404, 410):
                remover_inscricao(insc['endpoint'])
                logger.info(f"pushlib.enviar_push: inscrição expirada removida")
            else:
                logger.error(f"pushlib.enviar_push: falha ao enviar — {e}")

    return algum_sucesso
