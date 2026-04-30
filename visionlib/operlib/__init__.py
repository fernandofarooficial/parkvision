# ---------------------
# OPERLIB
# ---------------------
# Módulo responsável pelo store de eventos em tempo real para a tela Operador.
# Os eventos são mantidos em memória (por idcond) e alimentados pelo dblib
# após cada leitura de placa válida.

import os
import time
import threading
import logging
import requests
from config.database import get_db_connection

logger = logging.getLogger(__name__)

_event_store = {}       # {idcond: [event_dict, ...]}  — mais recente primeiro
_event_lock = threading.Lock()
MAX_EVENTOS_POR_COND = 200

_acoes_store = {}       # {idcond: [acao_dict, ...]}  — ações recentes para broadcast
_acoes_lock  = threading.Lock()
MAX_ACOES_POR_COND     = 200
JANELA_ACOES_SEGUNDOS  = 180   # 3 minutos

_cam_dispositivo_cache: dict = {}  # {idcam: bool} — evita N+1 por evento


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

    status = inforec.get('status_permissao', 'NÃO CADASTRADO')
    if status == 'INEXISTENTE':
        status = 'SEM PERMISSÃO'

    vagas_disp = None
    if status in ('INDEFINIDA', 'VIGENTE'):
        vperm = inforec.get('vagas_permitidas') or 0
        vocup = inforec.get('qtde_estacionada') or 0
        vagas_disp = max(0, vperm - vocup)

    idcam = inforec.get('camera_id')
    evento = {
        'idmov':            inforec.get('idmov'),
        'idlog':            inforec.get('log_id'),
        'placa':            placa,
        'placalida':        inforec.get('placalida', 'N/A'),
        'momento':          inforec.get('instante', ''),
        'status_permissao': status,
        'vagas_disponiveis': vagas_disp,
        'unidade':          inforec.get('unidade', ''),
        'direcao':          inforec.get('direcao', ''),
        'ts':               time.time(),
        'idcam':            idcam,
        'tem_dispositivo':  _camera_tem_dispositivo(idcam),
    }

    with _event_lock:
        store = _event_store.setdefault(idcond, [])
        store.insert(0, evento)
        if len(store) > MAX_EVENTOS_POR_COND:
            _event_store[idcond] = store[:MAX_EVENTOS_POR_COND]


JANELA_MINUTOS = 10


def obter_eventos_recentes(idcond, desde_ts=None, limit=100):
    """
    Retorna eventos do store de memória para polling do front-end.
    Filtra apenas eventos dos últimos JANELA_MINUTOS minutos.

    Parâmetros:
        idcond (int):       ID do condomínio
        desde_ts (float):   Timestamp Unix — retorna apenas eventos posteriores
        limit (int):        Máximo de eventos retornados

    Retorna:
        list[dict]: lista de eventos (mais recente primeiro)
    """
    corte = time.time() - (JANELA_MINUTOS * 60)

    with _event_lock:
        eventos = list(_event_store.get(idcond, []))

    eventos = [e for e in eventos if e['ts'] >= corte]

    if desde_ts is not None:
        try:
            eventos = [e for e in eventos if e['ts'] > float(desde_ts)]
        except (ValueError, TypeError):
            pass

    return eventos[:limit]


def registrar_acao_store(idcond, idmov, acao, placa, momento, direcao):
    """Registra ação do operador no store em memória para broadcast a outros browsers."""
    entrada = {
        'idmov':   idmov,
        'acao':    acao,
        'placa':   placa,
        'momento': momento,
        'direcao': direcao,
        'ts':      time.time(),
    }
    with _acoes_lock:
        store = _acoes_store.setdefault(idcond, [])
        store.insert(0, entrada)
        if len(store) > MAX_ACOES_POR_COND:
            _acoes_store[idcond] = store[:MAX_ACOES_POR_COND]


def obter_acoes_recentes(idcond, desde_ts=None):
    """Retorna ações recentes do store para polling do front-end."""
    corte = time.time() - JANELA_ACOES_SEGUNDOS
    with _acoes_lock:
        acoes = list(_acoes_store.get(idcond, []))
    acoes = [a for a in acoes if a['ts'] >= corte]
    if desde_ts is not None:
        try:
            acoes = [a for a in acoes if a['ts'] > float(desde_ts)]
        except (ValueError, TypeError):
            pass
    return acoes


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
                m.idmov,
                m.idlog,
                m.placa,
                m.placalida,
                m.instante AS momento,
                m.direcao,
                m.idcam,
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
                UNIX_TIMESTAMP(m.nowpost) AS ts,
                CASE WHEN cc.iddisp IS NOT NULL THEN 1 ELSE 0 END AS tem_dispositivo
            FROM movcar m
            LEFT JOIN cadveiculo cv ON cv.placa = m.placa
            LEFT JOIN cadcamera cc ON cc.idcam = m.idcam
            WHERE m.idcond = %s
              AND m.placa != '*ERROR*'
              AND m.contav = 0
              AND m.idgente IS NULL
              AND m.nowpost >= NOW() - INTERVAL 10 MINUTE
            ORDER BY m.nowpost DESC
            LIMIT %s
        """, (idcond, limit))

        rows = cursor.fetchall()
        for row in rows:
            row['vagas_disponiveis'] = None
            if row['ts'] is not None:
                row['ts'] = float(row['ts'])
            row['tem_dispositivo'] = bool(row.get('tem_dispositivo'))
        return rows

    except Exception as e:
        logger.error(f"operlib.obter_historico_db: erro ao carregar histórico — {e}")
        return []

    finally:
        cursor.close()
        conn.close()


TEMPO_PULSO_MS = 500   # duração do pulso em milissegundos


def _camera_tem_dispositivo(idcam):
    if not idcam:
        return False
    if idcam in _cam_dispositivo_cache:
        return _cam_dispositivo_cache[idcam]
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM cadcamera WHERE idcam = %s AND iddisp IS NOT NULL LIMIT 1",
            (idcam,)
        )
        result = cursor.fetchone() is not None
        _cam_dispositivo_cache[idcam] = result
        return result
    except Exception:
        return False
    finally:
        cursor.close()
        conn.close()


def _enviar_pulso_dispositivo(idcam, idcond):
    """
    Envia pulso ao relé do dispositivo associado à câmera que gerou o movimento.

    Busca a URL do dispositivo e o número do relé via:
        movcar.idcam → cadcamera(idcam, idcond) → caddisp(urldisp) + cadcamera.numrele

    A falha no envio é registrada em log mas NÃO interrompe o fluxo principal.
    """
    if not idcam or not idcond:
        return

    conn = get_db_connection()
    if not conn:
        logger.warning("_enviar_pulso_dispositivo: sem conexão com o banco")
        return

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT cd.urldisp, cc.numrele
            FROM cadcamera cc
            JOIN caddisp cd ON cd.iddisp = cc.iddisp
            WHERE cc.idcam = %s
              AND cc.idcond = %s
              AND cc.iddisp IS NOT NULL
            LIMIT 1
        """, (idcam, idcond))
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not row:
        logger.info(
            f"_enviar_pulso_dispositivo: nenhum dispositivo configurado "
            f"para idcam={idcam}, idcond={idcond}"
        )
        return

    url = f"http://{row['urldisp'].rstrip('/')}/set_output"
    rele = row['numrele'] or 1
    payload = {"address": rele, "state": 1, "time_1": TEMPO_PULSO_MS}

    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        resultado = resp.json().get("result", "?")
        logger.info(
            f"_enviar_pulso_dispositivo: pulso enviado → {url} "
            f"relé={rele} resultado={resultado}"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"_enviar_pulso_dispositivo: falha ao enviar pulso → {url} — {e}")


def obter_cameras_dispositivo_por_direcao(idcond):
    """
    Retorna quais direções ('E', 'S') têm ao menos uma câmera com dispositivo configurado.

    Retorna:
        dict: {'E': bool, 'S': bool}
    """
    conn = get_db_connection()
    if not conn:
        return {'E': False, 'S': False}
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT DISTINCT cc.direcao
            FROM cadcamera cc
            JOIN caddisp cd ON cd.iddisp = cc.iddisp
            WHERE cc.idcond = %s AND cc.iddisp IS NOT NULL
        """, (idcond,))
        direcoes = {row['direcao'] for row in cursor.fetchall()}
        return {'E': 'E' in direcoes, 'S': 'S' in direcoes}
    except Exception:
        return {'E': False, 'S': False}
    finally:
        cursor.close()
        conn.close()


def enviar_pulso_por_direcao(idcond, direcao):
    """
    Envia pulso manual a todas as câmeras com dispositivo da direção indicada.

    Parâmetros:
        idcond   (int): ID do condomínio
        direcao  (str): 'E' (entrada) ou 'S' (saída)
    """
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'message': 'Sem conexão com o banco'}
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT cc.idcam
            FROM cadcamera cc
            JOIN caddisp cd ON cd.iddisp = cc.iddisp
            WHERE cc.idcond = %s AND cc.direcao = %s AND cc.iddisp IS NOT NULL
        """, (idcond, direcao))
        cameras = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    if not cameras:
        return {'success': False, 'message': 'Nenhuma câmera com dispositivo para esta direção'}

    for cam in cameras:
        _enviar_pulso_dispositivo(cam['idcam'], idcond)

    return {'success': True, 'message': f'Pulso enviado ({len(cameras)} câmera(s))'}


def _calcular_statusmov(cursor, rec, acao, direcao_cam='E'):
    """
    Calcula o statusmov conforme tabela de decisão da tela operador.

    Retorna:
        tuple: (statusmov: str, tem_cadastro: bool)
            statusmov — Z, A, B, C, D, E, F, G, H (entrada) ou I, J (saída)
            tem_cadastro — True se placa existe em cadveiculo
    """
    if acao == 'ignorar':
        return 'Z', True

    # ── Câmera de saída: apenas verifica cadastro ──
    if direcao_cam == 'S':
        cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (rec['placa'],))
        tem_cadastro = cursor.fetchone() is not None
        return ('I' if tem_cadastro else 'J'), tem_cadastro

    # ── Câmera de entrada: lógica completa ────────
    cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (rec['placa'],))
    tem_cadastro = cursor.fetchone() is not None

    if not tem_cadastro:
        return ('C' if acao == 'confirmar' else 'D'), False

    cursor.execute("""
        SELECT status_permissao FROM vw_autorizacoes
        WHERE idcond = %s AND placa = %s
          AND status_permissao IN ('VIGENTE', 'INDEFINIDA')
        LIMIT 1
    """, (rec['idcond'], rec['placa']))
    tem_permissao = cursor.fetchone() is not None

    if not tem_permissao:
        return ('E' if acao == 'confirmar' else 'F'), True

    cursor.execute("""
        SELECT vu.vperm, COALESCE(ve.estacionados, 0) AS estacionados
        FROM vw_autorizacoes a
        JOIN vagasunidades vu ON vu.idcond = a.idcond AND vu.unidade = a.unidade
        LEFT JOIN vw_estacionados ve ON ve.idcond = a.idcond AND ve.unidade = a.unidade
        WHERE a.idcond = %s AND a.placa = %s
          AND a.status_permissao IN ('VIGENTE', 'INDEFINIDA')
        ORDER BY a.rank_permissao
        LIMIT 1
    """, (rec['idcond'], rec['placa']))
    vagas_row = cursor.fetchone()

    tem_vagas = (vagas_row is None) or (vagas_row['estacionados'] < vagas_row['vperm'])

    if tem_vagas:
        return ('A' if acao == 'confirmar' else 'B'), True
    else:
        return ('G' if acao == 'confirmar' else 'H'), True


def _notificar_acao_telegram(cursor, rec, statusmov, motivo):
    """Coleta dados complementares e envia notificação Telegram para ações excepcionais."""
    from visionlib.teleglib import teleg_acao_operador

    idcond = rec['idcond']
    placa  = rec['placa']

    cursor.execute("SELECT nmcond FROM cadcond WHERE idcond = %s LIMIT 1", (idcond,))
    row = cursor.fetchone()
    nmcond = row['nmcond'] if row else f'Cond. {idcond}'

    cursor.execute("""
        SELECT COALESCE(ma.nmmarca,  'Não cadastrado') AS marca,
               COALESCE(mo.nmmodelo, 'Não cadastrado') AS modelo,
               COALESCE(co.nmcor,    'Não cadastrado') AS cor
        FROM cadveiculo cv
        LEFT JOIN cadmodelo mo ON mo.idmodelo = cv.idmodelo
        LEFT JOIN cadmarca  ma ON ma.idmarca  = mo.idmarca
        LEFT JOIN cadcores  co ON co.idcor    = cv.idcor
        WHERE cv.placa = %s
    """, (placa,))
    row_vei = cursor.fetchone()
    marca   = row_vei['marca']  if row_vei else 'Não cadastrado'
    modelo  = row_vei['modelo'] if row_vei else 'Não cadastrado'
    cor     = row_vei['cor']    if row_vei else 'Não cadastrado'

    cursor.execute("""
        SELECT unidade FROM vw_autorizacoes
        WHERE idcond = %s AND placa = %s
        ORDER BY rank_permissao
        LIMIT 1
    """, (idcond, placa))
    row_uni = cursor.fetchone()
    unidade = row_uni['unidade'] if row_uni else None

    teleg_acao_operador({
        'idcond':    idcond,
        'statusmov': statusmov,
        'placa':     placa,
        'marca':     marca,
        'modelo':    modelo,
        'cor':       cor,
        'unidade':   unidade,
        'nmcond':    nmcond,
        'motivo':    motivo.strip() if motivo and motivo.strip() else None,
    })


def executar_acao_operador(idmov, acao, idgente, motivo=None):
    """
    Executa a ação do operador sobre um registro de movimento (movcar).

    Parâmetros:
        idmov (int):    PK do registro em movcar
        acao (str):     'confirmar' | 'rejeitar' | 'ignorar'
        idgente (int):  ID do usuário que realizou a ação (movcar.idgente)
        motivo (str):   Texto opcional para registrar em movcar.motivo

    Retorna:
        dict: {'success': bool, 'message': str}
    """
    contav_map = {'confirmar': 1, 'rejeitar': 0, 'ignorar': 0}
    if acao not in contav_map:
        return {'success': False, 'message': f'Ação inválida: {acao}'}

    conn = get_db_connection()
    if not conn:
        return {'success': False, 'message': 'Sem conexão com o banco de dados'}

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT idmov, idlog, idcond, placa, idcam, direcao FROM movcar WHERE idmov = %s",
            (idmov,)
        )
        rec = cursor.fetchone()
        if not rec:
            return {'success': False, 'message': 'Registro não encontrado'}

        novo_contav = contav_map[acao]
        direcao_cam = rec.get('direcao') or 'E'
        statusmov, tem_cadastro = _calcular_statusmov(cursor, rec, acao, direcao_cam)

        # Atualizar o movimento principal — AND idgente IS NULL garante que apenas
        # o primeiro request vence quando múltiplas abas enviam a ação simultaneamente.
        cursor.execute(
            "UPDATE movcar SET contav = %s, idgente = %s, statusmov = %s WHERE idmov = %s AND idgente IS NULL",
            (novo_contav, idgente, statusmov, idmov)
        )
        if cursor.rowcount == 0:
            return {'success': True, 'message': 'Já processado'}

        if motivo and motivo.strip():
            cursor.execute(
                "UPDATE movcar SET motivo = %s WHERE idmov = %s",
                (motivo.strip(), idmov)
            )

        # Status C: confirmar veículo não cadastrado → gravar em semcadastro
        if acao == 'confirmar' and not tem_cadastro:
            cursor.execute(
                """INSERT INTO semcadastro (idcond, placa)
                   VALUES (%s, %s)
                   ON DUPLICATE KEY UPDATE lup = NOW()""",
                (rec['idcond'], rec['placa'])
            )

        # Fechar automaticamente duplicatas pendentes da mesma placa no mesmo condomínio:
        # outros eventos com contav=0 e idgente=NULL para a mesma placa são ignorados,
        # evitando que o operador precise tratá-los individualmente.
        cursor.execute("""
            UPDATE movcar
               SET idgente   = %s,
                   statusmov = 'Z'
             WHERE placa     = %s
               AND idcond    = %s
               AND idmov    != %s
               AND contav    = 0
               AND idgente   IS NULL
               AND nowpost  >= NOW() - INTERVAL 10 MINUTE
        """, (idgente, rec['placa'], rec['idcond'], idmov))

        conn.commit()

        # Broadcast da ação para outros browsers via acoes_store
        momento_str = time.strftime('%d/%m/%Y %H:%M:%S')
        registrar_acao_store(rec['idcond'], idmov, acao, rec['placa'], momento_str, rec.get('direcao', 'E'))

        # Remover evento do _event_store para novos browsers não verem evento já tratado
        with _event_lock:
            ev_list = _event_store.get(rec['idcond'], [])
            _event_store[rec['idcond']] = [e for e in ev_list if e.get('idmov') != idmov]

        # Notificação Telegram para situações excepcionais
        if statusmov in ('B', 'C', 'E', 'J'):
            try:
                _notificar_acao_telegram(cursor, rec, statusmov, motivo)
            except Exception as e_tg:
                logger.warning(f"operlib._notificar_acao_telegram: {e_tg}")

        # Enviar pulso: entrada (A, C, E, G) e saída (I, J)
        if statusmov in ('A', 'C', 'E', 'G', 'I', 'J'):
            _enviar_pulso_dispositivo(rec.get('idcam'), rec.get('idcond'))

        return {'success': True, 'message': 'Ação registrada com sucesso'}

    except Exception as e:
        logger.error(f"operlib.executar_acao_operador: erro — {e}")
        conn.rollback()
        return {'success': False, 'message': 'Erro interno ao registrar ação'}

    finally:
        cursor.close()
        conn.close()


# ── Correção de placa pelo Operador ──────────────────────────────────────────

def corrigir_placa_operador(idmov, placa_corrigida, idcond):
    """
    Corrige a placa de um movimento diretamente pela tela Operador.

    Diferente da correção da tela de não-cadastrados, esta função não exige
    que a placa esteja em semcadastro — opera apenas sobre movcar e registra
    o mapeamento em deparaplacas para futuras correções automáticas.

    Parâmetros:
        idmov (int):          PK do registro em movcar
        placa_corrigida (str): Placa correta já cadastrada em cadveiculo
        idcond (int):          ID do condomínio (segurança)

    Retorna:
        dict: {'success': bool, 'message': str}
    """
    placa_corrigida = placa_corrigida.strip().upper()

    conn = get_db_connection()
    if not conn:
        return {'success': False, 'message': 'Sem conexão com o banco de dados'}

    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Buscar o movimento e a placa atual
        cursor.execute(
            "SELECT idmov, placa, idcond FROM movcar WHERE idmov = %s AND idcond = %s LIMIT 1",
            (idmov, idcond)
        )
        mov = cursor.fetchone()
        if not mov:
            return {'success': False, 'message': 'Movimento não encontrado'}

        placa_atual = mov['placa']

        if placa_atual == placa_corrigida:
            return {'success': False, 'message': 'A placa corrigida deve ser diferente da atual'}

        # 2. Verificar se a placa corrigida existe em cadveiculo
        cursor.execute(
            "SELECT placa FROM cadveiculo WHERE placa = %s LIMIT 1",
            (placa_corrigida,)
        )
        if not cursor.fetchone():
            return {'success': False, 'message': 'Placa corrigida não encontrada no cadastro de veículos'}

        # 3. Atualizar movcar: todos os movimentos pendentes com a placa errada neste condomínio
        cursor.execute("""
            UPDATE movcar
            SET placa = %s
            WHERE placa = %s AND idcond = %s AND contav = 0 AND idgente IS NULL
        """, (placa_corrigida, placa_atual, idcond))
        movimentos_atualizados = cursor.rowcount

        # Garantir que o movimento específico também seja atualizado (ex: já processado)
        if movimentos_atualizados == 0:
            cursor.execute(
                "UPDATE movcar SET placa = %s WHERE idmov = %s",
                (placa_corrigida, idmov)
            )
            movimentos_atualizados = cursor.rowcount

        # 4. Registrar mapeamento em deparaplacas para futura correção automática
        try:
            cursor.execute("""
                INSERT INTO deparaplacas (placade, placapara)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE placapara = VALUES(placapara)
            """, (placa_atual, placa_corrigida))
        except Exception:
            pass  # tabela pode não existir; não bloqueia a operação

        conn.commit()
        return {
            'success': True,
            'message': f'Placa corrigida: {placa_atual} → {placa_corrigida} '
                       f'({movimentos_atualizados} movimento(s) atualizado(s))'
        }

    except Exception as e:
        logger.error(f"corrigir_placa_operador: erro — {e}")
        conn.rollback()
        return {'success': False, 'message': 'Erro interno ao corrigir placa'}

    finally:
        cursor.close()
        conn.close()


# ── Câmeras RTSP ──────────────────────────────────────────────────────────────

def obter_cameras_rtsp(idcond):
    """
    Retorna as câmeras do condomínio que possuem o campo rtsp preenchido.

    Parâmetros:
        idcond (int): ID do condomínio

    Retorna:
        list[dict]: [{'idcam': ..., 'rtsp': ...}, ...]
    """
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT idcam, nomecamera, rtsp
            FROM cadcamera
            WHERE idcond = %s
              AND rtsp IS NOT NULL
              AND TRIM(rtsp) <> ''
            ORDER BY idcam
        """, (idcond,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"obter_cameras_rtsp: erro — {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def obter_rtsp_camera(idcam):
    """
    Retorna a URL RTSP de uma câmera pelo ID.

    Retorna:
        str | None
    """
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT rtsp FROM cadcamera WHERE idcam = %s LIMIT 1",
            (idcam,)
        )
        row = cursor.fetchone()
        return row['rtsp'] if row and row.get('rtsp') else None
    except Exception as e:
        logger.error(f"obter_rtsp_camera: erro — {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def capturar_snapshot_rtsp(rtsp_url):
    """
    Captura um frame JPEG de uma URL RTSP usando OpenCV.

    Parâmetros:
        rtsp_url (str): URL RTSP da câmera (ex: rtsp://user:pass@ip:port/stream)

    Retorna:
        bytes | None: imagem JPEG ou None em caso de falha / câmeras desabilitadas
    """
    if os.getenv('CAMERAS_ENABLED', 'true').lower() == 'false':
        logger.info("capturar_snapshot_rtsp: câmeras desabilitadas (CAMERAS_ENABLED=false)")
        return None

    try:
        import cv2
        # Forçar transporte TCP para maior compatibilidade
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        try:
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        except Exception:
            pass  # versões antigas não suportam esses flags
        if not cap.isOpened():
            logger.warning(f"capturar_snapshot_rtsp: não foi possível abrir {rtsp_url}")
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            logger.warning(f"capturar_snapshot_rtsp: frame vazio de {rtsp_url}")
            return None
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            return None
        return buffer.tobytes()
    except Exception as e:
        logger.error(f"capturar_snapshot_rtsp: erro ({rtsp_url}) — {e}")
        return None


def obter_resumo_vagas_cond(idcond):
    """
    Retorna o resumo de vagas do condomínio: limite total (cadcond.limite),
    vagas ocupadas (vw_estacionados) e disponíveis.

    Retorna:
        dict: {'success': bool, 'limite': int, 'ocupadas': int, 'disponiveis': int|None}
              disponiveis é None quando limite não está configurado em cadcond.
    """
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'message': 'Sem conexão com o banco de dados'}
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT COALESCE(limite, 0) AS limite FROM cadcond WHERE idcond = %s LIMIT 1",
            (idcond,)
        )
        row = cursor.fetchone()
        limite = int(row['limite']) if row else 0

        cursor.execute(
            "SELECT COALESCE(SUM(estacionados), 0) AS ocupadas FROM vw_estacionados WHERE idcond = %s",
            (idcond,)
        )
        row2 = cursor.fetchone()
        ocupadas = int(row2['ocupadas']) if row2 else 0

        disponiveis = max(0, limite - ocupadas) if limite > 0 else None
        return {
            'success':     True,
            'limite':      limite,
            'ocupadas':    ocupadas,
            'disponiveis': disponiveis,
        }
    except Exception as e:
        logger.error(f"obter_resumo_vagas_cond: erro — {e}")
        return {'success': False, 'message': 'Erro interno'}
    finally:
        cursor.close()
        conn.close()


def obter_ultimos_movimentos(idcond, limit=10):
    """
    Retorna os últimos movimentos válidos (contav=1, entrada ou saída) do condomínio.
    """
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT placa, direcao, nowpost
            FROM movcar
            WHERE idcond   = %s
              AND contav   = 1
              AND placa   != '*ERROR*'
            ORDER BY nowpost DESC
            LIMIT %s
        """, (idcond, limit))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            dt = row['nowpost']
            result.append({
                'placa':   row['placa'],
                'direcao': row['direcao'],
                'hora':    dt.strftime('%H:%M:%S') if dt else '—',
                'data':    dt.strftime('%d/%m/%Y')  if dt else '—',
            })
        return result
    except Exception as e:
        logger.error(f"obter_ultimos_movimentos: erro — {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def obter_info_veiculo_operador(idcond, placa):
    """
    Retorna dados completos de um veículo para o painel de informações da tela Operador:
    dados cadastrais, melhor permissão vigente e ocupação atual da unidade.
    """
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'message': 'Sem conexão com o banco de dados'}

    cursor = conn.cursor(dictionary=True)
    try:
        # Dados cadastrais do veículo
        cursor.execute("""
            SELECT cv.placa,
                   COALESCE(ma.nmmarca, 'N/I')  AS marca,
                   COALESCE(mo.nmmodelo, 'N/I') AS modelo,
                   COALESCE(co.nmcor, 'N/I')    AS cor
            FROM cadveiculo cv
            LEFT JOIN cadmodelo mo ON cv.idmodelo = mo.idmodelo
            LEFT JOIN cadmarca  ma ON mo.idmarca  = ma.idmarca
            LEFT JOIN cadcores  co ON cv.idcor    = co.idcor
            WHERE cv.placa = %s
        """, (placa,))
        veiculo = cursor.fetchone()

        # Melhor permissão (rank mais alto)
        cursor.execute("""
            SELECT a.unidade,
                   a.status_permissao,
                   a.data_inicio,
                   a.data_fim
            FROM vw_autorizacoes a
            WHERE a.idcond = %s AND a.placa = %s
            ORDER BY a.rank_permissao
            LIMIT 1
        """, (idcond, placa))
        row_perm = cursor.fetchone()
        permissao = None
        if row_perm:
            def fmt_data(dt): return dt.strftime('%d/%m/%Y') if dt else None
            def fmt_hora(dt): return dt.strftime('%H:%M')    if dt else None
            permissao = {
                'unidade':          row_perm['unidade'],
                'status_permissao': row_perm['status_permissao'],
                'data_inicio':      fmt_data(row_perm['data_inicio']),
                'hora_inicio':      fmt_hora(row_perm['data_inicio']),
                'data_fim':         fmt_data(row_perm['data_fim']),
                'hora_fim':         fmt_hora(row_perm['data_fim']),
            }

        # Vagas da unidade (total permitido e atualmente ocupadas)
        vagas = None
        estacionados = []
        if permissao and permissao.get('unidade'):
            unidade = permissao['unidade']

            cursor.execute("""
                SELECT vu.vperm                     AS total_permitidas,
                       COALESCE(ve.estacionados, 0) AS ocupadas
                FROM vagasunidades vu
                LEFT JOIN vw_estacionados ve
                       ON ve.idcond = vu.idcond AND ve.unidade = vu.unidade
                WHERE vu.idcond = %s AND vu.unidade = %s
            """, (idcond, unidade))
            vagas = cursor.fetchone()

            # Veículos atualmente estacionados na unidade:
            # último movimento confirmado de cada placa é uma entrada (direcao='E')
            # e a placa tem permissão para esta unidade neste condomínio.
            cursor.execute("""
                SELECT m.placa,
                       COALESCE(ma.nmmarca,  'N/I') AS marca,
                       COALESCE(mo.nmmodelo, 'N/I') AS modelo,
                       COALESCE(co.nmcor,    'N/I') AS cor,
                       m.nowpost                     AS entrada
                FROM (
                    SELECT placa, MAX(idmov) AS ultimo_idmov
                    FROM movcar
                    WHERE idcond = %s AND contav = 1
                    GROUP BY placa
                ) t
                JOIN movcar m ON m.idmov = t.ultimo_idmov AND m.direcao = 'E'
                LEFT JOIN cadveiculo cv  ON cv.placa     = m.placa
                LEFT JOIN cadmodelo  mo  ON mo.idmodelo  = cv.idmodelo
                LEFT JOIN cadmarca   ma  ON ma.idmarca   = mo.idmarca
                LEFT JOIN cadcores   co  ON co.idcor     = cv.idcor
                WHERE EXISTS (
                    SELECT 1 FROM vw_autorizacoes a
                    WHERE a.idcond  = %s
                      AND a.placa   = m.placa
                      AND a.unidade = %s
                )
                ORDER BY m.nowpost
            """, (idcond, idcond, unidade))
            for row in cursor.fetchall():
                dt = row['entrada']
                estacionados.append({
                    'placa':   row['placa'],
                    'marca':   row['marca'],
                    'modelo':  row['modelo'],
                    'cor':     row['cor'],
                    'entrada': dt.strftime('%d/%m/%Y %H:%M') if dt else '—',
                })

        return {
            'success':      True,
            'veiculo':      veiculo,
            'permissao':    permissao,
            'vagas':        vagas,
            'estacionados': estacionados,
        }

    except Exception as e:
        logger.error(f"obter_info_veiculo_operador: erro — {e}")
        return {'success': False, 'message': 'Erro interno ao consultar informações'}

    finally:
        cursor.close()
        conn.close()
