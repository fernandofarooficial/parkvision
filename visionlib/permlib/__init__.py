# --------------
# PERMLIB
# --------------

import mysql.connector
from config.database import get_db_connection
from flask import jsonify, request
from globals import verificar_autenticacao
from datetime import datetime

# Rota para criar nova permissão
# Referências no programa principal
# @app.route('/api/criar-permissao', methods=['POST'])
# def api_criar_permissao():
def criar_permissao():
    
    # Obter dados da requisição primeiro
    data = request.get_json()
    
    # Obter condominio_id dos dados da requisição (enviado pelo frontend)
    condominio_id = data.get('condominio_id')
    if not condominio_id:
        return jsonify({'success': False, 'message': 'ID do condomínio é obrigatório'})
    
    # Verificar acesso ao condomínio específico
    from globals import verificar_acesso_condominio
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado para este condomínio'})

    placa = data.get('placa', '').strip().upper()
    unidade = data.get('unidade', '').strip()
    # campos de tempo (vem do html em string)
    # Data/hora inicio
    inicio_str = f"{data.get('dataInicio')} {data.get('hora_inicio')}"
    formato = "%Y-%m-%d %H:%M"
    data_inicio = datetime.strptime(inicio_str, formato)
    # Data/hora fim
    if data.get('dataFim') is None:
        data_fim = None
    else:
        fim_str = f"{data.get('dataFim')} {data.get('hora_fim')}"
        data_fim = datetime.strptime(fim_str, formato)

    # Validações básicas
    if not placa or not unidade or not data_inicio:
        return jsonify({'success': False, 'message': 'Placa, unidade e data de início são obrigatórios'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor()

    try:
        # Verificar se o veículo está cadastrado
        cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (placa,))
        veiculo = cursor.fetchone()

        if not veiculo:
            return jsonify(
                {'success': False, 'message': 'Veículo não encontrado no sistema. Cadastre o veículo primeiro.'})

        # Verificar se já existe uma permissão vigente ou aberta para o veículo
        cursor.execute("""
            SELECT unidade, data_inicio, data_fim FROM cadperm
            WHERE placa = %s AND idcond = %s
            AND (data_fim IS NULL OR (data_inicio <= CURDATE() AND data_fim >= CURDATE()))
        """, (placa, condominio_id))

        perm_existente = cursor.fetchone()

        if perm_existente:
            return jsonify({
                'success': False,
                'message': 'Já existe uma permissão vigente ou aberta para este veículo. Finalize a permissão atual antes de criar uma nova.'
            })

        # Validação de datas
        try:
            if data_fim:
                if data_fim <= data_inicio:
                    return jsonify({'success': False, 'message': 'Data de fim deve ser posterior à data de início'})
        except ValueError:
            return jsonify({'success': False, 'message': 'Formato de data inválido'})

        # Se não houver permissão, criar nova
        cursor.execute("""
            INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim)
            VALUES (%s, %s, %s, %s, %s)
        """, (condominio_id, placa, unidade, data_inicio, data_fim))

        conn.commit()

        return jsonify({'success': True, 'message': 'Permissão criada com sucesso!'})

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar permissão: {err}'})
    finally:
        cursor.close()
        conn.close()


# Rota para modificar a data_fim de uma permissão
# Referências no programa principal
# @app.route('/api/modificar-permissao', methods=['PUT'])
# def api_modificar_permissao():
def modificar_permissao():

    # Obter dados da requisição primeiro
    data = request.get_json()
    
    # Obter condominio_id dos dados da requisição
    condominio_id = data.get('condominio_id')
    if not condominio_id:
        return jsonify({'success': False, 'message': 'ID do condomínio é obrigatório'})
    
    # Verificar acesso ao condomínio específico
    from globals import verificar_acesso_condominio
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado para este condomínio'})
    placa = data.get('placa', '').strip().upper()
    if data.get('dataFim') is None:
        nova_data_fim = None
    else:
        data_str = f"{data.get('dataFim')} {data.get('horaFim')}"
        formato = "%Y-%m-%d %H:%M"
        nova_data_fim = datetime.strptime(data_str, formato)
        hora_nova = int(data.get('horaInicio')[:2])
        minuto_novo = int(data.get('horaInicio')[-2:])

    # Validações básicas
    if not placa:
        return jsonify({'success': False, 'message': 'Placa é obrigatória'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)

    try:
        # Verificar se existe uma permissão válida para o veículo
        cursor.execute("""
            SELECT idperm, unidade, data_inicio, data_fim FROM vw_veiculos_autorizados 
            WHERE placa = %s AND idcond = %s 
            AND status_permissao <> 'VENCIDA'
            ORDER BY data_inicio DESC
            LIMIT 1
        """, (placa, condominio_id))

        # Obter id da permissão
        perm = cursor.fetchone()
        idperm = perm['idperm']

        # Nova hora de inicio
        nova_data_inicio = perm['data_inicio'].replace(hour=hora_nova, minute=minuto_novo, second=0)

        if not perm:
            return jsonify({'success': False,
                            'message': 'Permissão não encontrada ou está vencida. Apenas permissões vigentes ou indefinidas podem ser modificadas.'})

        # Validação de data
        if nova_data_fim:
            try:
                dt_inicio = perm['data_inicio']
                dt_fim = nova_data_fim
                if dt_fim <= dt_inicio:
                    return jsonify({'success': False, 'message': 'Data de fim deve ser posterior à data de início'})
            except ValueError:
                return jsonify({'success': False, 'message': 'Formato de data inválido'})


        # Modificar a data_fim da permissão
        cursor.execute("""
            UPDATE cadperm 
            SET data_fim = %s
            WHERE idperm = %s
        """, (nova_data_fim, idperm))

        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'Nenhuma permissão foi modificada'})

        conn.commit()

        return jsonify({'success': True, 'message': 'Data de permissão modificada com sucesso!'})

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao modificar permissão: {err}'})
    finally:
        cursor.close()
        conn.close()


# NOVA API: Buscar permissão por placa para modificação
# Referências no programa principal
# @app.route('/api/permissao/<placa>')
# def api_buscar_permissao(placa):
def buscar_permissao(placa):
    """Busca permissão vigente ou indefinida por placa para modificação"""
    # Validar placa
    if not placa or not placa.strip():
        return jsonify({'success': False, 'message': 'Placa é obrigatória'})

    placa = placa.strip().upper()

    # Esta função é chamada via URL parameter, precisamos obter o condominio_id de outro lugar
    # Verificar se há dados JSON no body (pode ser chamada via POST/PUT)
    # silent=True evita exceção se não houver JSON válido
    data = request.get_json(silent=True) or {}
    condominio_id = data.get('condominio_id')

    # Se não veio no JSON, tentar obter dos query parameters
    if not condominio_id:
        condominio_id = request.args.get('condominio_id')

    if not condominio_id:
        return jsonify({'success': False, 'message': 'ID do condomínio é obrigatório'})

    # Verificar acesso ao condomínio específico
    from globals import verificar_acesso_condominio
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado para este condomínio'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar permissão vigente ou indefinida
        # Usa a view vw_veiculos_autorizados para obter dados completos
        cursor.execute("""
            SELECT placa, unidade, data_inicio, data_fim
            FROM vw_veiculos_autorizados
            WHERE placa = %s AND idcond = %s
            AND status_permissao <> 'VENCIDA'
            ORDER BY data_inicio DESC
            LIMIT 1
        """, (placa, condominio_id))

        permissao = cursor.fetchone()

        if not permissao:
            return jsonify(
                {'success': False, 'message': 'Nenhuma permissão vigente ou indefinida encontrada para esta placa'})

        # Converter datas para string para JSON serialization
        # Inicializar campos de hora
        permissao['hora_inicio'] = None
        permissao['hora_fim'] = None

        # Processar data_inicio se existir
        if permissao.get('data_inicio'):
            permissao['hora_inicio'] = permissao['data_inicio'].strftime('%H:%M')
            permissao['data_inicio'] = permissao['data_inicio'].strftime('%Y-%m-%d')

        # Processar data_fim se existir
        if permissao.get('data_fim'):
            permissao['hora_fim'] = permissao['data_fim'].strftime('%H:%M')
            permissao['data_fim'] = permissao['data_fim'].strftime('%Y-%m-%d')

        return jsonify({'success': True, 'data': permissao})

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao buscar permissão: {err}'})
    except Exception as err:
        return jsonify({'success': False, 'message': f'Erro inesperado ao buscar permissão'})
    finally:
        cursor.close()
        conn.close()


def obter_unidades_condominio(condominio_id):
    """Obtém lista de unidades do condomínio ordenadas por seqcond"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar unidades ordenadas por seqcond
        cursor.execute("""
            SELECT unidade 
            FROM vagasunidades 
            WHERE idcond = %s 
            ORDER BY seqcond ASC
        """, (condominio_id,))

        unidades = cursor.fetchall()
        
        # Extrair apenas os valores das unidades
        lista_unidades = [u['unidade'] for u in unidades]

        # Adicionar as opções especiais no final
        lista_unidades.extend(['Avulso', 'Prestador', 'Visitante'])

        return jsonify({
            'success': True, 
            'data': lista_unidades
        })

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao buscar unidades: {err}'})
    finally:
        cursor.close()
        conn.close()
