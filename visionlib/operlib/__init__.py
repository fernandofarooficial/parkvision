# ---------------------
# OPERLIB
# ---------------------
# Módulo responsável pelo store de eventos em tempo real para a tela Operador.
# Os eventos são mantidos em memória (por idcond) e alimentados pelo dblib
# após cada leitura de placa válida.

import time
import threading
import logging
from config.database import get_db_connection

logger = logging.getLogger(__name__)

_event_store = {}       # {idcond: [event_dict, ...]}  — mais recente primeiro
_event_lock = threading.Lock()
MAX_EVENTOS_POR_COND = 200


def adicionar_evento(inforec):
    """
    Adiciona evento ao store de memória para exibição na tela Operador.
    Chamado pelo dblib após gravar_log().

    Parâmetros:
        inforec (dict): dicionário de informações do movimento processado
    """
    idcond = inforec.get('idcond')
    if idcond is None:
        return

    placa = inforec.get('placa', '')
    if placa == '*ERROR*':
        return

    # Ignorar leituras duplicadas (contav=0) — evita poluição visual
    if inforec.get('contav', 0) == 0:
        return

    status = inforec.get('status_permissao', 'NÃO CADASTRADO')
    if status == 'INEXISTENTE':
        status = 'SEM PERMISSÃO'

    vagas_disp = None
    if status in ('INDEFINIDA', 'VIGENTE'):
        vperm = inforec.get('vagas_permitidas') or 0
        vocup = inforec.get('qtde_estacionada') or 0
        vagas_disp = max(0, vperm - vocup)

    evento = {
        'placa':            placa,
        'placalida':        inforec.get('placalida', 'N/A'),
        'momento':          inforec.get('instante', ''),
        'status_permissao': status,
        'vagas_disponiveis': vagas_disp,
        'unidade':          inforec.get('unidade', ''),
        'direcao':          inforec.get('direcao', ''),
        'ts':               time.time(),
    }

    with _event_lock:
        store = _event_store.setdefault(idcond, [])
        store.insert(0, evento)
        if len(store) > MAX_EVENTOS_POR_COND:
            _event_store[idcond] = store[:MAX_EVENTOS_POR_COND]


def obter_eventos_recentes(idcond, desde_ts=None, limit=100):
    """
    Retorna eventos do store de memória para polling do front-end.

    Parâmetros:
        idcond (int):       ID do condomínio
        desde_ts (float):   Timestamp Unix — retorna apenas eventos posteriores
        limit (int):        Máximo de eventos retornados

    Retorna:
        list[dict]: lista de eventos (mais recente primeiro)
    """
    with _event_lock:
        eventos = list(_event_store.get(idcond, []))

    if desde_ts is not None:
        try:
            eventos = [e for e in eventos if e['ts'] > float(desde_ts)]
        except (ValueError, TypeError):
            pass

    return eventos[:limit]


def obter_historico_db(idcond, limit=50):
    """
    Carrega movimentos recentes do banco para carga inicial da tela Operador.
    O status de permissão reflete o estado ATUAL (não o estado no momento do evento).

    Parâmetros:
        idcond (int): ID do condomínio
        limit (int):  Máximo de registros retornados

    Retorna:
        list[dict]: lista de eventos
    """
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT
                m.placa,
                m.placalida,
                m.instante AS momento,
                m.direcao,
                CASE
                    WHEN cv.placa IS NULL THEN 'NÃO CADASTRADO'
                    ELSE COALESCE(
                        (SELECT
                            CASE WHEN a.status_permissao = 'INEXISTENTE' THEN 'SEM PERMISSÃO'
                                 ELSE a.status_permissao
                            END
                         FROM vw_autorizacoes a
                         WHERE a.idcond = m.idcond AND a.placa = m.placa
                         ORDER BY a.rank_permissao
                         LIMIT 1),
                        'SEM PERMISSÃO'
                    )
                END AS status_permissao,
                COALESCE(
                    (SELECT a.unidade FROM vw_autorizacoes a
                     WHERE a.idcond = m.idcond AND a.placa = m.placa
                     ORDER BY a.rank_permissao
                     LIMIT 1),
                    ''
                ) AS unidade,
                UNIX_TIMESTAMP(m.nowpost) AS ts
            FROM movcar m
            LEFT JOIN cadveiculo cv ON cv.placa = m.placa
            WHERE m.idcond = %s
              AND m.placa != '*ERROR*'
              AND m.contav = 1
            ORDER BY m.nowpost DESC
            LIMIT %s
        """, (idcond, limit))

        rows = cursor.fetchall()
        for row in rows:
            row['vagas_disponiveis'] = None          # Histórico não tem vagas snapshot
            if row['ts'] is not None:
                row['ts'] = float(row['ts'])
        return rows

    except Exception as e:
        logger.error(f"operlib.obter_historico_db: erro ao carregar histórico — {e}")
        return []

    finally:
        cursor.close()
        conn.close()
