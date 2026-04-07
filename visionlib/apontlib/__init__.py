# --------------
# APONTLIB - Biblioteca para Apontamento Manual
# --------------

import mysql.connector
import logging
from config.database import get_db_connection
from flask import jsonify, request
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# Definir fuso horário brasileiro
BRASIL_TZ = pytz.timezone('America/Sao_Paulo')

def obter_veiculos_vigentes(condominio_id):
    """
    Obtém veículos com permissão vigente ou indefinida para o condomínio
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Query para buscar veículos com permissões vigentes ou indefinidas
        query = """
        select placa, nmmarca as marca, nmmodelo as modelo, cor as nmcor, unidade 
        from vw_veiculos_autorizados
        where idcond = %s
        order by placa;
        """
        
        cursor.execute(query, (condominio_id,))
        veiculos = cursor.fetchall()
        
        return jsonify({'success': True, 'data': veiculos})
        
    except Exception as e:
        logger.error(f"Erro ao buscar veículos vigentes: {e}")
        return jsonify({'success': False, 'message': f'Erro ao consultar veículos: {str(e)}'})
    finally:
        cursor.close()
        conn.close()


def obter_ultimo_movimento(placa, condominio_id):
    """
    Obtém a última direção de movimento de um veículo
    """

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    logger.debug(f'obter_ultimo_movimento: placa={placa} condominio={condominio_id}')
    try:
        # Buscar último movimento do veículo com contav = 1
        query = """
        SELECT direcao
        FROM movcar 
        WHERE placa = %s 
        AND idcond = %s 
        AND contav = 1
        ORDER BY idmov DESC 
        LIMIT 1
        """

        cursor.execute(query, (placa, condominio_id))
        resultado = cursor.fetchone()
        
        # Se não houver movimento anterior, assume saída (para primeira entrada ser E)
        ultima_direcao = resultado['direcao'] if resultado else 'S'
        
        return jsonify({'success': True, 'ultima_direcao': ultima_direcao})
        
    except Exception as e:
        logger.error(f"Erro ao buscar último movimento: {e}")
        return jsonify({'success': False, 'message': f'Erro ao consultar último movimento: {str(e)}'})
    finally:
        cursor.close()
        conn.close()


def processar_apontamento():
    """
    Processa um apontamento manual registrando nas tabelas movcar
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dados JSON não fornecidos'})
        
        placa = str(data.get('placa', '')).strip().upper()
        unidade = str(data.get('unidade', '')).strip()
        direcao = str(data.get('direcao', '')).strip().upper()
        condominio_id = data.get('condominio_id')
        
        # Converter condominio_id para inteiro se necessário
        if condominio_id:
            try:
                condominio_id = int(condominio_id)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'ID do condomínio inválido'})
        
        logger.debug(f"processar_apontamento: placa={placa}, unidade={unidade}, direcao={direcao}, condominio_id={condominio_id}")
        
        # Validações básicas
        if not placa or not unidade or not direcao or not condominio_id:
            return jsonify({'success': False, 'message': 'Dados obrigatórios não informados'})
        
        if direcao not in ['E', 'S']:
            return jsonify({'success': False, 'message': 'Direção inválida'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})
        
        cursor = conn.cursor()
        
        try:
            # Obter data/hora atual
            agora = datetime.now(BRASIL_TZ)
            nowpost = agora.strftime('%Y-%m-%d %H:%M:%S')
            instante = agora.strftime('%d/%m/%Y %H:%M:%S')
            
            # Inserir registro na tabela movcar
            query_movcar = """
            INSERT INTO movcar (
                idlog, idcond, placa, nowpost, instante, cor, ender, 
                corconf, idcam, idaia, contav, nomecam, direcao
            ) VALUES (
                0, %s, %s, %s, %s, 'N/A', 'N/A', 
                0, 0, 0, 1, 'Apontamento', %s
            )
            """
            
            cursor.execute(query_movcar, (
                condominio_id, placa, nowpost, instante, direcao
            ))

            # Confirmar transação
            conn.commit()
            
            # Retornar dados do movimento registrado
            movimento = {
                'placa': placa,
                'unidade': unidade,
                'direcao': direcao,
                'instante': instante
            }
            
            return jsonify({
                'success': True, 
                'message': 'Apontamento registrado com sucesso',
                'movimento': movimento
            })
            
        except Exception as db_error:
            # Rollback em caso de erro
            conn.rollback()
            logger.error(f"Erro na operação do banco de dados: {db_error}")
            return jsonify({'success': False, 'message': f'Erro na operação do banco de dados: {str(db_error)}'})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        # Erro geral na função
        logger.error(f"Erro geral ao processar apontamento: {e}")
        return jsonify({'success': False, 'message': f'Erro ao processar apontamento: {str(e)}'})