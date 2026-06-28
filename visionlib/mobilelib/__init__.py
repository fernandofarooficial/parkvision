import logging
from config.database import get_db_connection

logger = logging.getLogger(__name__)


def obter_ultimos_movimentos_mobile(idcond, limit=20):
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT idmov, placa, direcao, unidade, marca, modelo, cor, ultima
            FROM vw_movimentos
            WHERE idcond = %s AND placa != '*ERROR*'
            ORDER BY idmov DESC
            LIMIT %s
        """, (idcond, limit))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            dt = row['ultima']
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
