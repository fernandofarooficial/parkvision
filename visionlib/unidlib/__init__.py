# ------------------------
# UNIDLIB - GESTÃO DE UNIDADES E VAGAS
# ------------------------

import mysql.connector
from config.database import get_db_connection
from flask import jsonify, request
from datetime import datetime


def listar_unidades_vagas(condominio_id):
    """
    Lista todas as unidades do condomínio com suas configurações de vagas
    """
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})
        
        cursor = connection.cursor(dictionary=True)
        
        # Query para listar todas as unidades com suas configurações
        query = """
        SELECT 
            vu.unidade, 
            vu.vperm, 
            vu.seqcond,
            COALESCE(ve.estacionados, 0) as veiculos_estacionados, 
            placas as placas_estacionadas
        FROM vagasunidades vu
        LEFT JOIN vw_estacionados ve ON ve.idcond = vu.idcond AND ve.seqcond = vu.seqcond
        WHERE vu.idcond = %s
        ORDER BY vu.seqcond;
        """
        
        cursor.execute(query, (condominio_id,))
        resultados = cursor.fetchall()
        
        # Formatar dados para o frontend
        unidades = []
        for row in resultados:
            unidades.append({
                'unidade': row['unidade'],
                'vagas_permitidas': row['vperm'],
                'vagas_ocupadas': row['veiculos_estacionados'],
                'placas_estacionadas': row['placas_estacionadas'] or '',
                'status': 'Disponível' if row['veiculos_estacionados'] < row['vperm'] 
                         else 'Completo' if row['veiculos_estacionados'] == row['vperm']
                         else 'Excesso'
            })
        
        return jsonify({
            'success': True,
            'data': unidades,
            'total': len(unidades),
            'message': 'Unidades carregadas com sucesso'
        })
        
    except mysql.connector.Error as e:
        return jsonify({
            'success': False,
            'data': [],
            'message': f'Erro na consulta: {str(e)}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'data': [],
            'message': f'Erro interno: {str(e)}'
        })
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()


def atualizar_vagas_unidade(condominio_id, unidade):
    """
    Atualiza a quantidade de vagas permitidas para uma unidade
    """
    try:
        data = request.get_json()
        
        if not data or 'vagas_permitidas' not in data:
            return jsonify({
                'success': False,
                'message': 'Dados inválidos. Campo vagas_permitidas é obrigatório.'
            })
        
        vagas_permitidas = data['vagas_permitidas']
        
        # Validar se o valor é um número positivo
        try:
            vagas_permitidas = int(vagas_permitidas)
            if vagas_permitidas < 0:
                raise ValueError("Número negativo")
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Quantidade de vagas deve ser um número inteiro positivo.'
            })
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})
        
        cursor = connection.cursor()
        
        # Verificar se a unidade existe
        cursor.execute("""
            SELECT vperm FROM vagasunidades 
            WHERE idcond = %s AND unidade = %s
        """, (condominio_id, unidade))
        
        unidade_existe = cursor.fetchone()
        if not unidade_existe:
            return jsonify({
                'success': False,
                'message': f'Unidade {unidade} não encontrada no condomínio.'
            })
        
        # Atualizar a quantidade de vagas
        cursor.execute("""
            UPDATE vagasunidades 
            SET vperm = %s
            WHERE idcond = %s AND unidade = %s
        """, (vagas_permitidas, condominio_id, unidade))
        
        connection.commit()
        
        # Registrar log da alteração (se necessário)
        # Aqui poderia ser adicionado um log de auditoria
        
        return jsonify({
            'success': True,
            'message': f'Quantidade de vagas da unidade {unidade} atualizada para {vagas_permitidas}.',
            'data': {
                'unidade': unidade,
                'vagas_permitidas_anterior': unidade_existe[0],
                'vagas_permitidas_nova': vagas_permitidas
            }
        })
        
    except mysql.connector.Error as e:
        if connection:
            connection.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro na atualização: {str(e)}'
        })
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        })
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()