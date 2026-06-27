import logging
from config.database import get_db_connection

logger = logging.getLogger(__name__)


def obter_ultimos_movimentos_mobile(idcond, limit=20):
    """Retorna os últimos movimentos válidos com unidade para a tela mobile."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT
                m.idmov,
                m.placa,
                m.direcao,
                m.nowpost,
                (SELECT p.unidade FROM cadperm p
                 WHERE p.placa = m.placa AND p.idcond = m.idcond
                 ORDER BY p.idperm DESC LIMIT 1) AS unidade,
                ma.nmmarca  AS marca,
                mo.nmmodelo AS modelo,
                co.nmcor    AS cor
            FROM movcar m
            LEFT JOIN cadveiculo  cv ON m.placa     = cv.placa
            LEFT JOIN cadmodelo   mo ON cv.idmodelo = mo.idmodelo
            LEFT JOIN cadmarca    ma ON mo.idmarca  = ma.idmarca
            LEFT JOIN cadcores    co ON cv.idcor    = co.idcor
            WHERE m.idcond = %s
              AND m.contav = 1
              AND m.placa != '*ERROR*'
            ORDER BY m.nowpost DESC
            LIMIT %s
        """, (idcond, limit))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            dt = row['nowpost']
            result.append({
                'idmov':   row['idmov'],
                'placa':   row['placa'],
                'direcao': row['direcao'],
                'unidade': row['unidade'] or '—',
                'marca':   row['marca']   or '—',
                'modelo':  row['modelo']  or '—',
                'cor':     row['cor']     or '—',
                'hora':    dt.strftime('%H:%M') if dt else '—',
                'data':    dt.strftime('%d/%m/%Y') if dt else '—',
            })
        return result
    except Exception as e:
        logger.error(f"obter_ultimos_movimentos_mobile: erro — {e}")
        return []
    finally:
        cursor.close()
        conn.close()
