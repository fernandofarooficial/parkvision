# ---------------------
# CAMLIB
# ---------------------
# Status de câmeras — lido do CamWatch, app externo de monitoramento RTSP que
# já roda nesta mesma VPS/servidor MySQL (systemd: camwatch-checker + camwatch-web,
# banco `camwatch`). ParkVision não faz mais verificação própria de câmera
# (não há mais thread de background nem check RTSP aqui).
#
# Vínculo entre os dois cadastros é manual: cadcamera.camwatch_camera_id aponta
# para camwatch.camera.id. Câmeras sem esse vínculo preenchido (NULL) apenas não
# aparecem no resultado — não há chave de correspondência automática confiável
# entre os dois sistemas (ver ArquivosApoio/database_migration.sql, item 14).

import logging

from config.database import get_db_connection

logger = logging.getLogger(__name__)


def obter_status_cameras(idcond: int) -> list:
    """
    Lê o status das câmeras do condomínio a partir do CamWatch (banco `camwatch`,
    mesmo servidor MySQL, tabela `camera`), via cadcamera.camwatch_camera_id.
    Câmeras sem mapeamento (camwatch_camera_id NULL) não entram no resultado.
    """
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT cc.idcam,
                   COALESCE(cc.nomecamera, CONCAT('Câm. ', cc.idcam)) AS nome,
                   cw.ultimo_status                                    AS status,
                   cw.ultima_verificacao,
                   UNIX_TIMESTAMP(cw.ultima_verificacao)              AS checado_ts
            FROM cadcamera cc
            JOIN camwatch.camera cw ON cw.id = cc.camwatch_camera_id
            WHERE cc.idcond = %s
              AND cc.camwatch_camera_id IS NOT NULL
            ORDER BY cc.nomecamera
        """, (idcond,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            dt = row['ultima_verificacao']
            result.append({
                'idcam':      row['idcam'],
                'nome':       row['nome'],
                'ativo':      (row['status'] == 'online') if row['status'] is not None else None,
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
