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


def obter_estacionados_mobile(idcond):
    """Veículos atualmente estacionados (último movimento = entrada)."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        # Reutiliza vw_autorizacoes (já tem marca/modelo/cor) + vw_last_mov
        cursor.execute("""
            SELECT au.placa,
                   au.unidade,
                   au.nmmarca  AS marca,
                   au.nmmodelo AS modelo,
                   au.cor,
                   lm.nowpost  AS ultima_entrada
            FROM vw_autorizacoes au
            LEFT JOIN vw_last_mov lm
                ON lm.idcond = au.idcond AND lm.placa = au.placa AND lm.direcao = 'E'
            WHERE au.idperm = (
                SELECT ax.idperm FROM vw_autorizacoes ax
                WHERE ax.placa = au.placa LIMIT 1
            )
            AND lm.direcao = 'E'
            AND au.idcond = %s
            ORDER BY au.seqcond ASC, lm.nowpost DESC
        """, (idcond,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            dt = row['ultima_entrada']
            result.append({
                'placa':   row['placa'],
                'unidade': row['unidade'] or '—',
                'marca':   row['marca']   or '—',
                'modelo':  row['modelo']  or '—',
                'cor':     row['cor']     or '—',
                'hora':    dt.strftime('%H:%M')    if dt else '—',
                'data':    dt.strftime('%d/%m/%Y') if dt else '—',
            })
        return result
    except Exception as e:
        logger.error(f"obter_estacionados_mobile: erro — {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def obter_veiculos_unidade_mobile(idcond, unidade):
    """Veículos estacionados em uma unidade específica (para detalhe do mapa)."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT au.placa,
                   au.nmmarca  AS marca,
                   au.nmmodelo AS modelo,
                   au.cor,
                   lm.nowpost  AS ultima_entrada
            FROM vw_autorizacoes au
            LEFT JOIN vw_last_mov lm
                ON lm.idcond = au.idcond AND lm.placa = au.placa AND lm.direcao = 'E'
            WHERE au.idperm = (
                SELECT ax.idperm FROM vw_autorizacoes ax
                WHERE ax.placa = au.placa LIMIT 1
            )
            AND lm.direcao = 'E'
            AND au.idcond = %s
            AND au.unidade = %s
            ORDER BY lm.nowpost DESC
        """, (idcond, unidade))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            dt = row['ultima_entrada']
            result.append({
                'placa':  row['placa'],
                'marca':  row['marca']  or '—',
                'modelo': row['modelo'] or '—',
                'cor':    row['cor']    or '—',
                'hora':   dt.strftime('%H:%M')    if dt else '—',
                'data':   dt.strftime('%d/%m/%Y') if dt else '—',
            })
        return result
    except Exception as e:
        logger.error(f"obter_veiculos_unidade_mobile: erro — {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def buscar_permissao_mobile(idcond, placa):
    """Busca permissão vigente/indefinida por placa — para uso mobile (idcond vem da sessão)."""
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão", None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT placa, unidade, data_inicio, data_fim
            FROM vw_veiculos_autorizados
            WHERE placa = %s AND idcond = %s
              AND status_permissao <> 'VENCIDA'
            ORDER BY data_inicio DESC
            LIMIT 1
        """, (placa, idcond))
        perm = cursor.fetchone()
        if not perm:
            return False, 'Nenhuma permissão vigente ou indefinida encontrada para esta placa', None
        di = perm['data_inicio']
        df = perm['data_fim']
        result = {
            'placa':        perm['placa'],
            'unidade':      perm['unidade'],
            'hora_inicio':  di.strftime('%H:%M') if di else None,
            'data_inicio':  di.strftime('%Y-%m-%d') if di else None,
            'hora_fim':     df.strftime('%H:%M') if df else None,
            'data_fim':     df.strftime('%Y-%m-%d') if df else None,
        }
        return True, 'OK', result
    except Exception as e:
        logger.error(f"buscar_permissao_mobile: erro — {e}")
        return False, str(e), None
    finally:
        cursor.close()
        conn.close()


def novo_veiculo_mobile(idcond, placa, marca, modelo, idcor, unidade, data_inicio, data_fim):
    """Cria veículo em cadveiculo (se não existir) e permissão em cadperm."""
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão"
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (placa,))
        existe = cursor.fetchone()

        if not existe:
            cursor.execute("""
                SELECT mo.idmodelo FROM cadmodelo mo
                INNER JOIN cadmarca ma ON mo.idmarca = ma.idmarca
                WHERE ma.nmmarca = %s AND mo.nmmodelo = %s
                LIMIT 1
            """, (marca, modelo))
            res = cursor.fetchone()
            idmodelo = res['idmodelo'] if res else 1
            cursor.execute(
                "INSERT INTO cadveiculo (placa, idmodelo, idcor) VALUES (%s, %s, %s)",
                (placa, idmodelo, idcor)
            )

        cursor.execute("""
            SELECT unidade FROM cadperm
            WHERE placa = %s AND idcond = %s
              AND (data_fim IS NULL OR data_fim >= NOW())
        """, (placa, idcond))
        perm_ativa = cursor.fetchone()
        if perm_ativa:
            conn.rollback()
            return False, f'Já existe permissão ativa para este veículo na unidade "{perm_ativa["unidade"]}"'

        cursor.execute("""
            INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim)
            VALUES (%s, %s, %s, %s, %s)
        """, (idcond, placa, unidade, data_inicio, data_fim))

        conn.commit()
        msg = 'Veículo e permissão cadastrados com sucesso!' if not existe else 'Permissão criada com sucesso!'
        return True, msg
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()
