# ------------------
# LISTLIB
# ------------------

import mysql.connector
from config.database import get_db_connection
from flask import jsonify, request
from globals import verificar_autenticacao
from datetime import datetime
import pytz

# Definir fuso horário brasileiro
BRASIL_TZ = pytz.timezone('America/Sao_Paulo')

# API para obter lista de veículos
# Referências no programa principal
# @app.route('/api/veiculos/<int:condominio_id>')
# def api_veiculos(condominio_id):
def obter_lista_veiculos(condominio_id):
    # Autenticação agora é feita nas rotas principais do main.py
    placa = request.args.get('placa', '')
    unidade = request.args.get('unidade', '')

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        sql_cadastrados = """
        SELECT * FROM vw_movimentos WHERE idcond = %s
        ORDER BY idmov DESC 
        LIMIT 100;
        """

        params_cadastrados = [condominio_id]

        if placa:
            sql_cadastrados += " AND mc.placa LIKE %s"  # Corrigido para mc.placa
            params_cadastrados.append(f"%{placa}%")

        if unidade:
            sql_cadastrados += " AND cp.unidade LIKE %s"  # Corrigido para cp.unidade
            params_cadastrados.append(f"%{unidade}%")

        cursor.execute(sql_cadastrados, params_cadastrados)
        veiculos_cadastrados = cursor.fetchall()

        todos_veiculos = list(veiculos_cadastrados)

        # Localizar as datas lidas - CORREÇÃO: Tratar valores NULL
        for y in todos_veiculos:
            if y['ultima'] is not None:
                y['ultima'] = BRASIL_TZ.localize(y['ultima'])
            # Se for None, manter como None

        # Ordenar por data (mais recente primeiro)
        todos_veiculos.sort(key=lambda x: x['ultima'] if x['ultima'] else datetime.min, reverse=True)

        for i, veiculo in enumerate(todos_veiculos):
            if veiculo['ultima'] is None:
                veiculo['ultima'] = None
                veiculo['status'] = 'Sem registro'
            else:
                # Verificar se a data é válida (não é anterior a 2000)
                if veiculo['ultima'].year < 2000:
                    veiculo['ultima'] = None
                    veiculo['status'] = 'Sem registro'
                else:
                    # Definir status baseado na última câmera usando a função
                    if veiculo.get('ultima_camera'):
                        statuscamera = 'Movimento'
                        if veiculo['direcao'] == 'E':
                            statuscamera = 'Entrada'
                        elif veiculo['direcao'] == 'S':
                            statuscamera = 'Saída'
                        veiculo['status'] = statuscamera
                    else:
                        veiculo['status'] = 'Sem movimento'

            # Como estamos usando apenas lastupdate, penultima sempre será None
            veiculo['penultima'] = None

            # Tratar unidade N/I
            if not veiculo['unidade'] or veiculo['unidade'] == '':
                veiculo['unidade'] = 'N/I'

            # Marcar o primeiro veículo (mais recente) como último cadastrado
            if i == 0 and veiculo['ultima'] is not None:
                veiculo['ultimo_cadastrado'] = False  # Mantém a lógica existente para o badge
            else:
                veiculo['ultimo_cadastrado'] = False

            # Carro com dados completo
            if veiculo['origem'] == 'Detectado':
                cursor.execute("SELECT nickcar FROM cadnick WHERE placa = %s AND idcond = %s",(veiculo['placa'],veiculo['idcond']))
                apelidolido = cursor.fetchone()
                apelido = "Sem cadastro" if apelidolido is None else apelidolido['nickcar']
                veiculo['carrocompleto'] = f"{veiculo['placa']} ({apelido})"
            else:
                # Validação para marca e modelo nulos ou 'N/I'
                marca_exibicao = veiculo['marca'] if veiculo['marca'] and veiculo['marca'] != 'N/I' else 'Desconhecida'
                modelo_exibicao = veiculo['modelo'] if veiculo['modelo'] and veiculo[
                    'modelo'] != 'N/I' else 'Desconhecido'
                cor_exibicao = veiculo['cor'].strip() if veiculo['cor'] else 'Cor N/I'

                infocarro = f"({marca_exibicao}-{modelo_exibicao}-{cor_exibicao})"
                veiculo['carrocompleto'] = f"{veiculo['placa']}{infocarro}"

                # Certificar que status_vaga é preenchido e não nulo
                if veiculo['status_vaga'] == 'Não aplicável':
                    veiculo['status_vaga'] = 'N/A'
                else:
                    veiculo['status_vaga'] += f" ({veiculo['ocupadas']}/{veiculo['permitidas']})"

        return jsonify({'success': True, 'data': todos_veiculos})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao consultar veículos: {err}'})
    finally:
        cursor.close()
        conn.close()


# API para obter detalhes de um veículo específico
# Referências no programa principal
# @app.route('/api/veiculo/<int:condominio_id>/<placa>')
# def api_veiculo_detalhes(condominio_id, placa):
def veiculo_detalhes(condominio_id, placa):
    autenticado, cond_id = verificar_autenticacao()
    if not autenticado or str(cond_id) != str(condominio_id):
        return jsonify({'success': False, 'message': 'Não autorizado'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        # NOVA ESTRUTURA: Obter dados do veículo usando vw_veiculos_autorizados
        cursor.execute("""
            SELECT vva.placa, vva.unidade, vva.cor, 
                   COALESCE(ma.nmmarca, 'N/I') as marca, 
                   COALESCE(mo.nmmodelo, 'N/I') as modelo,
                   vva.data_inicio, vva.data_fim, vva.status_permissao
            FROM vw_veiculos_autorizados vva
            LEFT JOIN cadmodelo mo ON vva.idmodelo = mo.idmodelo
            LEFT JOIN cadmarca ma ON mo.idmarca = ma.idmarca
            WHERE vva.idcond = %s AND vva.placa = %s
        """, (condominio_id, placa))

        veiculo = cursor.fetchone()

        if not veiculo:
            # Retornar estrutura consistente mesmo quando veículo não encontrado
            return jsonify({
                'success': False,
                'message': 'Veículo não encontrado',
                'data': {
                    'veiculo': None,
                    'movimentacoes': []
                }
            })

        # Obter movimentações do veículo (apenas contav = 1)
        cursor.execute("""
            SELECT nowpost as data, idcam, direcao
            FROM movcar
            WHERE idcond = %s AND placa = %s AND contav = 1
            ORDER BY nowpost DESC
            LIMIT 10
        """, (condominio_id, placa))

        movimentacoes_raw = cursor.fetchall()

        # Processar movimentações com validação de sequência lógica
        movimentacoes = []
        ultimo_tipo = None  # Para controlar a alternância

        for mov in movimentacoes_raw:
            tipo_movimento = 'Movimento'
            if mov['direcao'] == 'E':
                tipo_movimento = 'Entrada'
            elif mov['direcao'] == 'S':
                tipo_movimento = 'Saída'

            # Validar sequência lógica: Entrada -> Saída -> Entrada -> Saída
            if ultimo_tipo is None:
                # Primeiro movimento sempre é válido
                movimentacoes.append({
                    'data': BRASIL_TZ.localize(mov['data']),
                    'tipo': tipo_movimento
                })
                ultimo_tipo = tipo_movimento
            else:
                # Verificar se o movimento atual é diferente do anterior
                if tipo_movimento != ultimo_tipo:
                    movimentacoes.append({
                        'data': BRASIL_TZ.localize(mov['data']),
                        'tipo': tipo_movimento
                    })
                    ultimo_tipo = tipo_movimento
                # Se for igual ao anterior, ignorar (movimento duplicado/inconsistente)

        # Tratar valores nulos e dados não verídicos para marca e modelo
        if veiculo:
            marca = veiculo['marca'] if veiculo['marca'] else 'N/I'
            modelo = veiculo['modelo'] if veiculo['modelo'] else 'N/I'

            # Verificar se são dados genéricos/não verídicos EXCETO quando idmodelo = 1
            # Para idmodelo = 1, manter "Agrale" como marca válida
            cursor.execute("""
                SELECT cv.idmodelo FROM cadveiculo cv WHERE cv.placa = %s
            """, (placa,))
            resultado_modelo_veiculo = cursor.fetchone()

            if marca == 'Agrale' and modelo == 'Marruá' and (
                    not resultado_modelo_veiculo or resultado_modelo_veiculo['idmodelo'] != 1):
                # Para outros casos que não idmodelo=1 (Agrale), considerar como dados não verídicos
                veiculo['marca'] = 'N/I'
                veiculo['modelo'] = 'N/I'
            else:
                # Manter dados que parecem verídicos
                veiculo['marca'] = marca
                veiculo['modelo'] = modelo

        return jsonify({
            'success': True,
            'data': {
                'veiculo': veiculo,
                'movimentacoes': movimentacoes
            }
        })
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao consultar detalhes do veículo: {err}'})
    finally:
        cursor.close()
        conn.close()


# API para obter detalhes de uma unidade específica
# Referências no programa principal
# @app.route('/api/unidade/<int:condominio_id>/<unidade>')
# def api_detalhes_unidade(condominio_id, unidade):
def detalhes_unidade(condominio_id, unidade):
    autenticado, cond_id = verificar_autenticacao()
    if not autenticado or str(cond_id) != str(condominio_id):
        return jsonify({'success': False, 'message': 'Não autorizado'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        # NOVA ESTRUTURA: Buscar veículos estacionados usando vw_veiculos_autorizados
        sql_veiculos = """
        SELECT vva.placa, vva.cor, 
               vva.nmmarca as marca, vva.nmmodelo as modelo,
               vva.data_inicio, vva.data_fim, vva.status_permissao, clo.sit
		FROM vw_veiculos_autorizados vva
		LEFT JOIN cadlocal clo ON clo.idcond = vva.idcond AND clo.unidade = vva.unidade 
			AND clo.placa = vva.placa
        WHERE vva.idcond = %s AND vva.unidade = %s AND clo.sit = 1;
        """

        cursor.execute(sql_veiculos, [condominio_id, str(unidade)])
        veiculos = cursor.fetchall()

        # Buscar informações da unidade - usar tabela vagasunidades como fallback
        info_unidade = None
        try:
            sql_unidade = """
            SELECT vperm, vocup 
            FROM vagasunidades 
            WHERE idcond = %s AND unidade = %s
            """

            cursor.execute(sql_unidade, [condominio_id, str(unidade)])
            info_unidade = cursor.fetchone()
        except mysql.connector.Error:
            # Se vagasunidades não existir, usar valores padrão baseados nos veículos encontrados
            info_unidade = {'vperm': 2, 'vocup': len(veiculos)}

        # Se não encontrou na tabela, usar valores padrão
        if not info_unidade:
            info_unidade = {'vperm': 2, 'vocup': len(veiculos)}

        # Contar total de veículos não cadastrados do condomínio
        total_nao_cadastrados = 0
        try:
            sql_nao_cadastrados = """
            SELECT COUNT(DISTINCT m.placa) as total
            FROM movcar m
            WHERE m.idcond = %s AND m.contav = 1
            AND m.placa IS NOT NULL AND m.placa != ''
            AND LENGTH(m.placa) >= 7
            AND m.placa REGEXP '^[A-Z]{3}[0-9]{4}$|^[A-Z]{3}[0-9][A-Z][0-9]{2}'
            AND m.placa NOT IN (
                SELECT cv.placa FROM cadveiculo cv
                INNER JOIN cadlocal cl ON cv.placa = cl.placa AND cl.idcond = %s
                WHERE cv.placa IS NOT NULL AND cv.placa != ''
            )
            """

            cursor.execute(sql_nao_cadastrados, [condominio_id, condominio_id])
            result = cursor.fetchone()
            total_nao_cadastrados = result['total'] if result else 0
        except mysql.connector.Error:
            total_nao_cadastrados = 0

        return jsonify({
            'success': True,
            'data': {
                'veiculos': veiculos,
                'vagas_permitidas': info_unidade['vperm'],
                'vagas_ocupadas': len(veiculos)  # Usar contagem real dos veículos encontrados
            }
        })

    except mysql.connector.Error as err:
        print(f"ERRO API UNIDADE: {err}")
        return jsonify({'success': False, 'message': f'Erro ao consultar unidade: {err}'})
    finally:
        cursor.close()
        conn.close()
