# ---------------------
# OPERLIB
# ---------------------
# Módulo responsável pelo store de eventos em tempo real para a tela Operador.
# Os eventos são mantidos em memória (por idcond) e alimentados pelo dblib
# após cada leitura de placa válida.

import time
import threading
import logging
import requests
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

    status = inforec.get('status_permissao', 'NÃO CADASTRADO')
    if status == 'INEXISTENTE':
        status = 'SEM PERMISSÃO'

    vagas_disp = None
    if status in ('INDEFINIDA', 'VIGENTE'):
        vperm = inforec.get('vagas_permitidas') or 0
        vocup = inforec.get('qtde_estacionada') or 0
        vagas_disp = max(0, vperm - vocup)

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
              AND m.contav = 0
              AND m.idgente IS NULL
              AND m.nowpost >= NOW() - INTERVAL 10 MINUTE
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


TEMPO_PULSO_MS = 500   # duração do pulso em milissegundos


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


def _calcular_statusmov(cursor, rec, acao):
    """
    Calcula o statusmov conforme tabela de decisão da tela operador.

    Retorna:
        tuple: (statusmov: str, tem_cadastro: bool)
            statusmov — Z, A, B, C, D, E, F ou G
            tem_cadastro — True se placa existe em cadveiculo
    """
    if acao == 'ignorar':
        return 'Z', True  # tem_cadastro irrelevante para ignorar

    # Verificar cadastro
    cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (rec['placa'],))
    tem_cadastro = cursor.fetchone() is not None

    if not tem_cadastro:
        return ('C' if acao == 'confirmar' else 'D'), False

    # Verificar permissão vigente ou indefinida
    cursor.execute("""
        SELECT status_permissao FROM vw_autorizacoes
        WHERE idcond = %s AND placa = %s
          AND status_permissao IN ('VIGENTE', 'INDEFINIDA')
        LIMIT 1
    """, (rec['idcond'], rec['placa']))
    tem_permissao = cursor.fetchone() is not None

    if not tem_permissao:
        return ('E' if acao == 'confirmar' else 'F'), True

    # Verificar vagas disponíveis
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
        return ('G' if acao == 'confirmar' else 'F'), True


def executar_acao_operador(idmov, acao, idgente, motivo=None):
    """
    Executa a ação do operador sobre um registro de movimento (movcar).

    Parâmetros:
        idmov (int):    PK do registro em movcar
        acao (str):     'confirmar' | 'rejeitar' | 'ignorar'
        idgente (int):  ID do usuário que realizou a ação (movcar.idgente)
        motivo (str):   Texto opcional para registrar na tabela motivo

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
            "SELECT idmov, idlog, idcond, placa, idcam FROM movcar WHERE idmov = %s",
            (idmov,)
        )
        rec = cursor.fetchone()
        if not rec:
            return {'success': False, 'message': 'Registro não encontrado'}

        novo_contav = contav_map[acao]
        statusmov, tem_cadastro = _calcular_statusmov(cursor, rec, acao)

        cursor.execute(
            "UPDATE movcar SET contav = %s, idgente = %s, statusmov = %s WHERE idmov = %s",
            (novo_contav, idgente, statusmov, idmov)
        )

        if motivo and motivo.strip():
            cursor.execute(
                "INSERT INTO motivo (idlog, motivo) VALUES (%s, %s)",
                (rec['idlog'], motivo.strip())
            )

        # Status C: confirmar veículo não cadastrado → gravar em semcadastro
        if acao == 'confirmar' and not tem_cadastro:
            cursor.execute(
                """INSERT INTO semcadastro (idcond, placa)
                   VALUES (%s, %s)
                   ON DUPLICATE KEY UPDATE lup = NOW()""",
                (rec['idcond'], rec['placa'])
            )

        conn.commit()

        # Enviar pulso ao dispositivo nos status que exigem abertura do portão
        # (A, C, E, G) — todos os casos de confirmação
        if statusmov in ('A', 'C', 'E', 'G'):
            _enviar_pulso_dispositivo(rec.get('idcam'), rec.get('idcond'))

        return {'success': True, 'message': 'Ação registrada com sucesso'}

    except Exception as e:
        logger.error(f"operlib.executar_acao_operador: erro — {e}")
        conn.rollback()
        return {'success': False, 'message': 'Erro interno ao registrar ação'}

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
            SELECT idcam, rtsp
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
        bytes | None: imagem JPEG ou None em caso de falha
    """
    try:
        import cv2
        import os
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
