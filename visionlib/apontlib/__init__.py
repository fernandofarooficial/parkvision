# --------------
# APONTLIB - Biblioteca para Apontamento Manual
# --------------

import logging
from config.database import get_db_connection
from flask import jsonify, request
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

BRASIL_TZ = pytz.timezone('America/Sao_Paulo')


def obter_veiculos_cadastrados(condominio_id):
    """
    Retorna todos os veículos em cadveiculo.
    Inclui a unidade do condomínio quando houver permissão cadastrada.
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT cv.placa,
                   COALESCE(ma.nmmarca,  'N/I') AS marca,
                   COALESCE(mo.nmmodelo, 'N/I') AS modelo,
                   COALESCE(co.nmcor,    'N/I') AS cor,
                   COALESCE(
                       (SELECT a.unidade FROM vw_autorizacoes a
                        WHERE a.idcond = %s AND a.placa = cv.placa
                        ORDER BY a.rank_permissao LIMIT 1),
                       ''
                   ) AS unidade
            FROM cadveiculo cv
            LEFT JOIN cadmodelo mo ON cv.idmodelo = mo.idmodelo
            LEFT JOIN cadmarca  ma ON mo.idmarca  = ma.idmarca
            LEFT JOIN cadcores  co ON cv.idcor    = co.idcor
            ORDER BY cv.placa
        """, (condominio_id,))
        return jsonify({'success': True, 'data': cursor.fetchall()})
    except Exception as e:
        logger.error(f"Erro ao buscar veículos cadastrados: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


def obter_ultimo_movimento(placa, condominio_id):
    """Retorna a última direção de movimento confirmado de um veículo no condomínio."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT direcao
            FROM movcar
            WHERE placa  = %s
              AND idcond = %s
              AND contav = 1
            ORDER BY idmov DESC
            LIMIT 1
        """, (placa, condominio_id))
        resultado = cursor.fetchone()
        # Sem histórico → assume saída (para que o próximo apontamento seja entrada)
        ultima_direcao = resultado['direcao'] if resultado else 'S'
        return jsonify({'success': True, 'ultima_direcao': ultima_direcao})
    except Exception as e:
        logger.error(f"Erro ao buscar último movimento: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


def processar_apontamento():
    """
    Registra um apontamento manual em movcar.
    statusmov = 'M' (apontamento manual).
    Motivo é obrigatório.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dados JSON não fornecidos'})

        placa         = str(data.get('placa',  '')).strip().upper()
        direcao       = str(data.get('direcao', '')).strip().upper()
        motivo        = str(data.get('motivo',  '')).strip()
        unidade       = str(data.get('unidade', '')).strip()
        condominio_id = data.get('condominio_id')

        if condominio_id:
            try:
                condominio_id = int(condominio_id)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'ID do condomínio inválido'})

        if not placa or not direcao or not condominio_id:
            return jsonify({'success': False, 'message': 'Dados obrigatórios não informados'})

        if direcao not in ('E', 'S'):
            return jsonify({'success': False, 'message': 'Direção inválida'})

        if not motivo:
            return jsonify({'success': False, 'message': 'O motivo do apontamento é obrigatório'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

        cursor = conn.cursor()
        try:
            agora    = datetime.now(BRASIL_TZ)
            nowpost  = agora.strftime('%Y-%m-%d %H:%M:%S')
            instante = agora.strftime('%d/%m/%Y %H:%M:%S')

            cursor.execute("""
                INSERT INTO movcar (
                    idlog, idcond, placa, nowpost, instante, cor, ender,
                    corconf, idcam, idaia, contav, nomecam, direcao, statusmov, motivo
                ) VALUES (
                    0, %s, %s, %s, %s, 'N/A', 'N/A',
                    0, 0, 0, 1, 'Apontamento', %s, 'M', %s
                )
            """, (condominio_id, placa, nowpost, instante, direcao, motivo))

            conn.commit()

            return jsonify({
                'success':  True,
                'message':  'Apontamento registrado com sucesso',
                'movimento': {
                    'placa':    placa,
                    'unidade':  unidade,
                    'direcao':  direcao,
                    'instante': instante,
                    'motivo':   motivo,
                }
            })

        except Exception as db_error:
            conn.rollback()
            logger.error(f"Erro na operação do banco de dados: {db_error}")
            return jsonify({'success': False, 'message': f'Erro no banco de dados: {str(db_error)}'})
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.error(f"Erro geral ao processar apontamento: {e}")
        return jsonify({'success': False, 'message': f'Erro ao processar apontamento: {str(e)}'})
