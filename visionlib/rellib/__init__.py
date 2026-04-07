# ---------------
# RELIB
# ---------------

import mysql.connector
import logging
from config.database import get_db_connection
from flask import jsonify, request
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def obter_relatorio_permissoes_validas(condominio_id):
    """
    Relatório de veículos com permissões válidas (vigentes e indefinidas)
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            placa,
            unidade,
            CONCAT(nmmarca, ' ', nmmodelo) as marca_modelo,
            cor,
            status_permissao,
            data_fim as data_vencimento
            FROM vw_autorizacoes
            WHERE idcond = %s AND status_permissao <> 'VENCIDA'
            ORDER BY seqcond
        """
        
        cursor.execute(query, (condominio_id,))
        resultados = cursor.fetchall()
        
        # Formatar dados para o relatório
        dados_relatorio = []
        for row in resultados:
            # Formatar data de vencimento para dd/mm/aaaa
            data_vencimento = row['data_vencimento']
            if data_vencimento:
                if hasattr(data_vencimento, 'strftime'):
                    data_vencimento_formatada = data_vencimento.strftime('%d/%m/%Y %H:%M')
                else:
                    data_vencimento_formatada = str(data_vencimento)
            else:
                data_vencimento_formatada = 'Indefinida'
            # Verificar status Vencendo
            status_permissao = row['status_permissao']
            if status_permissao != 'INDEFINIDA':
                if abs(data_vencimento - datetime.now()) <= timedelta(seconds=72*3600):
                    status_permissao = "VENCENDO"

            dados_relatorio.append([
                row['placa'],
                row['unidade'],
                row['marca_modelo'],
                row['cor'],
                status_permissao,
                data_vencimento_formatada
            ])
        
        return jsonify({
            'success': True,
            'data': dados_relatorio,
            'total': len(dados_relatorio),
            'message': 'Relatório gerado com sucesso'
        })
        
    except mysql.connector.Error as e:
        return jsonify({
            'success': False,
            'data': [],
            'message': f'Erro na consulta: {str(e)}'
        })
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()


def obter_relatorio_movimento_veiculos(condominio_id, data_inicio=None, data_fim=None, limite=20, pagina=1):
    """
    Relatório de movimento de veículos (entradas e saídas) com filtros e paginação
    """
    try:
        # from flask import request
        
        # Se não foram passados parâmetros, pegar do request
        if data_inicio is None:
            data_inicio = request.args.get('data_inicio')
        if data_fim is None:
            data_fim = request.args.get('data_fim')
        if limite == 20:
            limite = int(request.args.get('limite', 20))
        if pagina == 1:
            pagina = int(request.args.get('pagina', 1))
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Construir WHERE clause com filtros de data
        where_conditions = ["idcond = %s"]
        query_params = [condominio_id]
        
        if data_inicio:
            where_conditions.append("ultima >= %s")
            query_params.append(data_inicio)
        
        if data_fim:
            # Tornar data_fim inclusiva - incluir todo o dia
            try:
                # Se a data_fim tem apenas data (formato YYYY-MM-DD), adicionar fim do dia
                if len(data_fim.strip()) == 10 and data_fim.count(':') == 0:
                    data_fim_inclusiva = data_fim + " 23:59:59"
                else:
                    data_fim_inclusiva = data_fim
            except (AttributeError, TypeError):
                data_fim_inclusiva = data_fim
            
            where_conditions.append("ultima <= %s")
            query_params.append(data_fim_inclusiva)
        
        where_clause = " AND ".join(where_conditions)

        # Query para contar total de registros
        count_query = """
                SELECT COUNT(*) as total
                FROM vw_movimentos
                WHERE {}
                """.format(where_clause)

        cursor.execute(count_query, query_params)
        total_registros = cursor.fetchone()['total']

        # Calcular offset para paginação
        offset = (pagina - 1) * limite

        # Query principal com paginação
        query = """
                SELECT 
                    idmov,
                    placa,
                    ultima as data_hora,
                    CASE 
                        WHEN direcao = "E" THEN "Entrada"
                        WHEN direcao = "S" THEN "Saída"
                        WHEN direcao = "I" THEN "Indeterminado"
                        ELSE "Movimento"
                    END as tipo,
                    unidade,
                    idcond,
                    CONCAT(marca, " ", modelo, " ", cor) as marca_modelo_cor
                FROM vw_movimentos
                WHERE {}
                ORDER BY idmov DESC
                LIMIT %s OFFSET %s
                """.format(where_clause)
        
        query_params.extend([limite, offset])
        cursor.execute(query, query_params)
        resultados = cursor.fetchall()
        
        # Formatear dados para o relatório
        dados_relatorio = []
        for row in resultados:
            # Formatar data_hora para dd/mm/aaaa hh:mm
            data_hora = row['data_hora']
            if data_hora:
                if hasattr(data_hora, 'strftime'):
                    data_hora_formatada = data_hora.strftime('%d/%m/%Y %H:%M')
                else:
                    data_hora_formatada = str(data_hora)
            else:
                data_hora_formatada = 'N/A'

            carro = 'Não cadastrado' if row['marca_modelo_cor'] is None else row['marca_modelo_cor']
            
            dados_relatorio.append([
                data_hora_formatada,
                row['placa'],
                row['unidade'],
                row['tipo'],
                carro
            ])
        
        # Calcular informações de paginação
        total_paginas = (total_registros + limite - 1) // limite
        
        return jsonify({
            'success': True,
            'data': dados_relatorio,
            'total': total_registros,
            'total_paginas': total_paginas,
            'pagina_atual': pagina,
            'limite': limite,
            'message': 'Relatório gerado com sucesso'
        })
        
    except mysql.connector.Error as e:
        return jsonify({
            'success': False,
            'data': [],
            'total': 0,
            'message': f'Erro na consulta: {str(e)}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'data': [],
            'total': 0,
            'message': f'Erro interno: {str(e)}'
        })
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()


def obter_relatorio_mapa_vagas(condominio_id):
    """
    Relatório do mapa de vagas atual
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            vu.unidade, 
            vu.vperm as vagas_permitidas, 
            COALESCE(ve.estacionados, 0) as vagas_ocupadas, 
            CASE 
                WHEN ve.estacionados = 0 THEN 'Vazio'
                WHEN ve.estacionados > COALESCE(vu.vperm, 0) THEN 'Excesso'
                WHEN ve.estacionados = COALESCE(vu.vperm, 0) THEN 'Completo'
                WHEN ve.estacionados > 0 AND ve.estacionados < COALESCE(vu.vperm, 0) THEN 'Parcial'
                ELSE 'Disponível'
            END as status,
            placas as veiculos_estacionados
        FROM vagasunidades vu
        LEFT JOIN vw_estacionados ve ON ve.idcond = vu.idcond AND ve.seqcond = vu.seqcond
        WHERE vu.idcond = %s
        ORDER BY vu.seqcond;
        """
        
        cursor.execute(query, (condominio_id,))
        resultados = cursor.fetchall()
        
        # Formatear dados para o relatório
        dados_relatorio = []
        for row in resultados:
            dados_relatorio.append([
                row['unidade'],
                str(row['vagas_permitidas']),
                str(row['vagas_ocupadas']),
                row['status'],
                row['veiculos_estacionados'] or 'Nenhum'
            ])
        
        return jsonify({
            'success': True,
            'data': dados_relatorio,
            'total': len(dados_relatorio),
            'message': 'Relatório gerado com sucesso'
        })
        
    except mysql.connector.Error as e:
        return jsonify({
            'success': False,
            'data': [],
            'message': f'Erro na consulta: {str(e)}'
        })
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()


def obter_relatorio_veiculos_condominio(condominio_id):
    """
    Relatório completo de veículos do condomínio
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT idcond, placa, unidade, status_permissao, data_inicio, data_fim,
        CONCAT(nmmarca, ' ', nmmodelo, ' ', cor) as veiculo  
        FROM vw_autorizacoes a1
        WHERE a1.idperm = 
        (
        SELECT a2.idperm 
        FROM vw_autorizacoes a2
        WHERE a1.idcond = a2.idcond AND a1.placa = a2.placa AND a1.unidade = a2.unidade
        LIMIT 1
        ) AND idcond = %s;
        """
        
        cursor.execute(query, (condominio_id,))
        resultados = cursor.fetchall()
        logger.debug(f'relatorio_mapa_vagas linha extra: {cursor.fetchone()}')
        
        # Formatear dados para o relatório
        dados_relatorio = []
        for row in resultados:
            dataInicioExib = row['data_inicio'].strftime('%d/%m/%Y %H:%M')
            dataFinal = row['data_fim']
            dataFinalExib = 'n/a' if dataFinal is None else dataFinal.strftime('%d/%m/%Y %H:%M')
            dados_relatorio.append([
                row['unidade'],
                row['placa'],
                row['veiculo'],
                row['status_permissao'],
                dataInicioExib,
                dataFinalExib
            ])
        
        return jsonify({
            'success': True,
            'data': dados_relatorio,
            'total': len(dados_relatorio),
            'message': 'Relatório gerado com sucesso'
        })
        
    except mysql.connector.Error as e:
        return jsonify({
            'success': False,
            'data': [],
            'message': f'Erro na consulta: {str(e)}'
        })
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()


def obter_relatorio_nao_cadastrados(condominio_id):
    """
    Relatório de veículos não cadastrados (detectados mas não no sistema)
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            idcond, 
            placa, 
            MAX(lup) as ultima_ocorrencia,
            COUNT(*) as total_ocorrencias
        FROM semcadastro 
        WHERE idcond = %s
        GROUP BY idcond, placa
        ORDER BY MAX(idseq) DESC;
        """
        
        cursor.execute(query, (condominio_id,))
        resultados = cursor.fetchall()
        
        # Formatear dados para o relatório
        dados_relatorio = []
        for row in resultados:
            UltimaOcorrenciaExib = row['ultima_ocorrencia'].strftime('%d/%m/%Y %H:%M')
            dados_relatorio.append([
                row['placa'],
                UltimaOcorrenciaExib,
                str(row['total_ocorrencias'])
            ])
        
        return jsonify({
            'success': True,
            'data': dados_relatorio,
            'total': len(dados_relatorio),
            'message': 'Relatório gerado com sucesso'
        })
        
    except mysql.connector.Error as e:
        return jsonify({
            'success': False,
            'data': [],
            'message': f'Erro na consulta: {str(e)}'
        })
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()


def obter_relatorio_veiculos_estacionados(condominio_id):
    """
    Relatório de veículos que estão estacionados no condomínio (Ultimo movcar com direcao = E)
    Colunas: Placa, Unidade, Veículo (marca-modelo-cor), Última Entrada
    Ordenação: Por unidade e depois por última entrada
    """
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT au.placa, au.unidade, 
        CONCAT(nmmarca, " ", nmmodelo, " ", cor) as veiculo, 
        lm.nowpost as ultima_entrada, au.seqcond  
        FROM vw_autorizacoes au 
        LEFT JOIN vw_last_mov lm on lm.idcond = au.idcond AND au.placa = lm.placa and lm.direcao = 'E'
        WHERE au.idperm = (SELECT idperm FROM vw_autorizacoes ax WHERE ax.placa = au.placa LIMIT 1)
        AND lm.direcao = 'E' AND au.idcond = %s
        ORDER BY au.seqcond ASC, lm.nowpost DESC;
        """
        
        cursor.execute(query, (condominio_id,))
        resultados = cursor.fetchall()
        
        # Formatar dados para o relatório
        dados_relatorio = []
        for row in resultados:
            # Formatar data da última entrada
            ultima_entrada = row['ultima_entrada']
            if ultima_entrada:
                if hasattr(ultima_entrada, 'strftime'):
                    ultima_entrada_formatada = ultima_entrada.strftime('%d/%m/%Y %H:%M')
                else:
                    ultima_entrada_formatada = str(ultima_entrada)
            else:
                ultima_entrada_formatada = 'N/A'
            
            dados_relatorio.append([
                row['placa'],
                row['unidade'],
                row['veiculo'],
                ultima_entrada_formatada
            ])
        
        return jsonify({
            'success': True,
            'data': dados_relatorio,
            'total': len(dados_relatorio),
            'message': 'Relatório gerado com sucesso'
        })
        
    except mysql.connector.Error as e:
        return jsonify({
            'success': False,
            'data': [],
            'message': f'Erro na consulta: {str(e)}'
        })
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()