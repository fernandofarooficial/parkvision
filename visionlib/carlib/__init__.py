# ------------------------
# CARLIB
# ------------------------

import mysql.connector
from config.database import get_db_connection
from flask import jsonify, request
from datetime import datetime


# ===== APIS BACKEND PARA MÓDULO CADASTRO DE VEÍCULOS (CADVEICULO) =====
# Adicionar estas APIs ao arquivo main.py


# API para buscar veículo por placa (para modificação)
# Referência no programa principal
# @app.route('/api/cadastrar-veiculo-nao-cadastrado', methods=['POST'])
# def api_cadastrar_veiculo_nao_cadastrado():
def cadastrar_veiculo_nao_cadastrado():

    data = request.get_json()

    # Autenticação agora é feita nas rotas principais do main.py

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor()
    try:
        # Extrair dados de permanência
        data_inicio = datetime.strptime(f"{data.get('data_inicio')} {data.get('hora_inicio')}", "%Y-%m-%d %H:%M")
        data_fim = datetime.strptime(f"{data.get('data_fim')} {data.get('hora_fim')}", "%Y-%m-%d %H:%M")
        tempo_indeterminado = data.get('tempo_indeterminado', False)

        # Validar dados obrigatórios
        if not data_inicio:
            return jsonify({'success': False, 'message': 'Data de início é obrigatória'})

        # Validar lógica de datas
        if not tempo_indeterminado and data_fim:
            try:
                if data_fim <= data_inicio:
                    return jsonify({'success': False, 'message': 'A data de fim deve ser posterior à data de início'})
            except ValueError:
                return jsonify({'success': False, 'message': 'Formato de data inválido'})

        # 1. Verificar se o veículo já existe em CADVEICULO
        cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (data['placa'],))
        veiculo_existente = cursor.fetchone()
        
        if veiculo_existente:
            return jsonify({'success': False, 'message': 'Veículo já cadastrado no sistema'})

        # 2. Inserir dados básicos do veículo em CADVEICULO
        sql_insert_veiculo = """
        INSERT INTO cadveiculo (placa, idmodelo, idcor)
        VALUES (%s, %s, %s)
        """

        # Buscar idmodelo baseado na marca e modelo
        cursor.execute("""
            SELECT mo.idmodelo FROM cadmodelo mo
            INNER JOIN cadmarca ma ON mo.idmarca = ma.idmarca
            WHERE ma.nmmarca = %s AND mo.nmmodelo = %s
            LIMIT 1
        """, [data['marca'], data['modelo']])

        modelo_result = cursor.fetchone()
        idmodelo = modelo_result[0] if modelo_result else 1  # Default para idmodelo = 1 (Agrale Marruá)

        cursor.execute(sql_insert_veiculo, [
            data['placa'],
            idmodelo,
            data['idcor']
        ])

        # 4. Inserir permissão em CADPERM com dados de permanência

        if tempo_indeterminado:
            sql_insert_perm = """
            INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim)
            VALUES (%s, %s, %s, %s, NULL)
            """
            cursor.execute(sql_insert_perm, [
                data['condominio_id'],
                data['placa'],
                data['unidade'],
                data_inicio
            ])
        else:
            sql_insert_perm = """
            INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql_insert_perm, [
                data['condominio_id'],
                data['placa'],
                data['unidade'],
                data_inicio,
                data_fim
            ])

        # Remover da tabela semcadastro após cadastrar
        sql_delete_semcadastro = """
        DELETE FROM semcadastro 
        WHERE idcond = %s AND placa = %s
        """

        cursor.execute(sql_delete_semcadastro, [
            data['condominio_id'],
            data['placa']
        ])

        # Remover também da tabela cadnick (apelidos) após cadastrar
        sql_delete_cadnick = """
        DELETE FROM cadnick 
        WHERE idcond = %s AND placa = %s
        """

        cursor.execute(sql_delete_cadnick, [
            data['condominio_id'],
            data['placa']
        ])

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Veículo cadastrado com sucesso!'
        })

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao cadastrar veículo (02): {err}'})
    finally:
        cursor.close()
        conn.close()


# API para criar novo veículo no cadveiculo
# Referência no programa principal
# @app.route('/api/cadveiculo', methods=['POST'])
# def api_criar_veiculo_cadveiculo():
def criar_veiculo_cadveiculo():
    """Cria novo veículo na tabela cadveiculo"""
    data = request.json

    placa = data.get('placa', '').strip().upper()
    marca = data.get('marca', '').strip()
    modelo = data.get('modelo', '').strip()
    idcor = data.get('idcor')

    # Validações
    if not placa or not marca or not modelo or not idcor:
        return jsonify({'success': False, 'message': 'Todos os campos são obrigatórios'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor()
    try:
        # Verificar se placa já existe
        cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (placa,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Placa já cadastrada no sistema'})

        # Buscar idmodelo baseado na marca e modelo
        cursor.execute("""
            SELECT mo.idmodelo FROM cadmodelo mo
            INNER JOIN cadmarca ma ON mo.idmarca = ma.idmarca
            WHERE ma.nmmarca = %s AND mo.nmmodelo = %s
            LIMIT 1
        """, (marca, modelo))

        resultado_modelo = cursor.fetchone()
        idmodelo = resultado_modelo[0] if resultado_modelo else 1  # Default para idmodelo = 1

        # Inserir novo veículo
        cursor.execute("""
            INSERT INTO cadveiculo (placa, idmodelo, idcor)
            VALUES (%s, %s, %s)
        """, (placa, idmodelo, idcor))

        conn.commit()

        return jsonify({'success': True, 'message': 'Veículo cadastrado com sucesso!'})

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao cadastrar veículo (01): {err}'})
    finally:
        cursor.close()
        conn.close()


# API para modificar veículo existente no cadveiculo
# Referência no programa principal
# @app.route('/api/cadveiculo/<placa>', methods=['PUT'])
# def api_modificar_veiculo_cadveiculo(placa):
def modificar_veiculo_cadveiculo(placa):
    """Modifica veículo existente na tabela cadveiculo"""
    data = request.json

    marca = data.get('marca', '').strip()
    modelo = data.get('modelo', '').strip()
    idcor = data.get('idcor')

    # Validações
    if not marca or not modelo or not idcor:
        return jsonify({'success': False, 'message': 'Todos os campos são obrigatórios'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor()
    try:
        # Verificar se veículo existe
        cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (placa,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Veículo não encontrado'})

        # Buscar idmodelo baseado na marca e modelo
        cursor.execute("""
            SELECT mo.idmodelo FROM cadmodelo mo
            INNER JOIN cadmarca ma ON mo.idmarca = ma.idmarca
            WHERE ma.nmmarca = %s AND mo.nmmodelo = %s
            LIMIT 1
        """, (marca, modelo))

        resultado_modelo = cursor.fetchone()
        idmodelo = resultado_modelo[0] if resultado_modelo else 1  # Default para idmodelo = 1

        # Atualizar veículo
        cursor.execute("""
            UPDATE cadveiculo 
            SET idmodelo = %s, idcor = %s
            WHERE placa = %s
        """, (idmodelo, idcor, placa))

        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'Nenhum registro foi atualizado'})

        conn.commit()

        return jsonify({'success': True, 'message': 'Veículo modificado com sucesso!'})

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao modificar veículo: {err}'})
    finally:
        cursor.close()
        conn.close()


# API para obter veículos não cadastrados
# Referência no programa principal
# @app.route('/api/veiculos-nao-cadastrados/<int:condominio_id>')
# def api_veiculos_nao_cadastrados(condominio_id)
def obter_veiculos_nao_cadastrados(condominio_id):
    # Autenticação agora é feita nas rotas principais do main.py
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar veículos da tabela semcadastro com última movimentação real (sem duplicados)
        sql = """
        SELECT DISTINCT 
            sc.placa,
            MAX(sc.lup) AS ultima_movimentacao,
            COUNT(m.placa) AS total_movimentacoes,
            cn.nickcar AS apelido
        FROM semcadastro sc
        LEFT JOIN cadnick cn ON cn.placa = sc.placa AND cn.idcond = sc.idcond
        LEFT JOIN movcar m ON m.placa = sc.placa AND m.idcond = sc.idcond AND m.contav = 1
        WHERE sc.idcond = %s
        GROUP BY sc.placa, cn.nickcar
        ORDER BY ultima_movimentacao DESC;
        """

        cursor.execute(sql, [condominio_id])
        veiculos = cursor.fetchall()

        # Formatar as datas para evitar "Invalid Date" no frontend
        for veiculo in veiculos:
            if veiculo['ultima_movimentacao']:
                try:
                    # Se for datetime, converter para string formatada
                    if hasattr(veiculo['ultima_movimentacao'], 'strftime'):
                        veiculo['ultima_movimentacao'] = veiculo['ultima_movimentacao'].strftime('%d/%m/%Y, %H:%M:%S')
                    else:
                        # Se já for string, manter como está
                        veiculo['ultima_movimentacao'] = str(veiculo['ultima_movimentacao'])
                except:
                    # Em caso de erro, usar timestamp atual
                    veiculo['ultima_movimentacao'] = datetime.now().strftime('%d/%m/%Y, %H:%M:%S')
            else:
                veiculo['ultima_movimentacao'] = 'Data não disponível'

        return jsonify({
            'success': True,
            'data': veiculos
        })

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao consultar veículos não cadastrados: {err}'})
    finally:
        cursor.close()
        conn.close()

# API para buscar veículo no cadastro de veículos (cadveiculo)
# Referência no programa principal
# @app.route('/api/cadveiculo/<placa>')
# def api_buscar_veiculo_cadveiculo(placa)
def buscar_veiculo_cadveiculo(placa):
    """Busca veículo na tabela cadveiculo por placa para modificação"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar veículo com marca, modelo e cor
        cursor.execute("""
            SELECT cv.placa, cv.idcor, co.nmcor as cor, cv.idmodelo,
                   ma.nmmarca as marca, mo.nmmodelo as modelo
            FROM cadveiculo cv
            LEFT JOIN cadmodelo mo ON cv.idmodelo = mo.idmodelo
            LEFT JOIN cadmarca ma ON mo.idmarca = ma.idmarca
            LEFT JOIN cadcores co ON cv.idcor = co.idcor
            WHERE cv.placa = %s
        """, (placa,))

        veiculo = cursor.fetchone()

        if not veiculo:
            return jsonify({'success': False, 'message': 'Veículo não encontrado'})

        return jsonify({'success': True, 'data': veiculo})

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao buscar veículo: {err}'})
    finally:
        cursor.close()
        conn.close()


# API para gerenciar apelidos de veículos
# Referência no programa principal
# @app.route('/api/gerenciar-apelido', methods=['POST'])
# def api_gerenciar_apelido():
def gerenciar_apelido():
    """Gerencia apelidos de veículos na tabela cadnick"""
    data = request.get_json()
    
    placa = data.get('placa', '').strip().upper()
    idcond = data.get('idcond')
    apelido = data.get('apelido', '').strip()
    
    # Validações básicas
    if not placa or not idcond:
        return jsonify({'success': False, 'message': 'Placa e ID do condomínio são obrigatórios'})
    
    # Apelido pode ser vazio (para remover)
    if len(apelido) > 50:
        return jsonify({'success': False, 'message': 'Apelido deve ter no máximo 50 caracteres'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})
    
    cursor = conn.cursor()
    try:
        # Verificar se já existe um apelido para esta placa e condomínio
        cursor.execute("""
            SELECT nickcar FROM cadnick 
            WHERE placa = %s AND idcond = %s
        """, (placa, idcond))
        
        resultado = cursor.fetchone()
        
        if resultado:
            # Atualizar apelido existente
            if apelido:
                cursor.execute("""
                    UPDATE cadnick 
                    SET nickcar = %s 
                    WHERE placa = %s AND idcond = %s
                """, (apelido, placa, idcond))
                message = 'Apelido atualizado com sucesso!'
            else:
                # Remover apelido (deixar vazio)
                cursor.execute("""
                    UPDATE cadnick 
                    SET nickcar = '' 
                    WHERE placa = %s AND idcond = %s
                """, (placa, idcond))
                message = 'Apelido removido com sucesso!'
        else:
            # Criar novo apelido (apenas se não estiver vazio)
            if apelido:
                cursor.execute("""
                    INSERT INTO cadnick (placa, idcond, nickcar)
                    VALUES (%s, %s, %s)
                """, (placa, idcond, apelido))
                message = 'Apelido criado com sucesso!'
            else:
                # Não faz nada se não existe e apelido está vazio
                return jsonify({'success': True, 'message': 'Nenhuma alteração necessária'})
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao gerenciar apelido: {err}'})
    finally:
        cursor.close()
        conn.close()


# API para excluir veículo não cadastrado
# Referência no programa principal
# @app.route('/api/excluir-veiculo-nao-cadastrado', methods=['POST'])
# def api_excluir_veiculo_nao_cadastrado():
def excluir_veiculo_nao_cadastrado():
    """Exclui veículo da tabela semcadastro e opcionalmente da movcar"""
    data = request.get_json()
    
    placa = data.get('placa', '').strip().upper()
    idcond = data.get('idcond')
    excluir_movimentos = data.get('excluir_movimentos', False)
    
    # Validações básicas
    if not placa or not idcond:
        return jsonify({'success': False, 'message': 'Placa e ID do condomínio são obrigatórios'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})
    
    cursor = conn.cursor()
    try:
        # Verificar se o veículo existe na tabela semcadastro
        cursor.execute("""
            SELECT placa FROM semcadastro 
            WHERE placa = %s AND idcond = %s
            LIMIT 1
        """, (placa, idcond))
        
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Veículo não encontrado na lista de não cadastrados'})
        
        # Iniciar transação
        cursor.execute("START TRANSACTION")
        
        # 1. Excluir da tabela semcadastro
        cursor.execute("""
            DELETE FROM semcadastro 
            WHERE placa = %s AND idcond = %s
        """, (placa, idcond))
        
        registros_semcadastro = cursor.rowcount
        
        # 2. Se solicitado, excluir também da tabela movcar
        registros_movimentos = 0
        if excluir_movimentos:
            cursor.execute("""
                DELETE FROM movcar 
                WHERE placa = %s AND idcond = %s
            """, (placa, idcond))
            registros_movimentos = cursor.rowcount
        
        # Verificar se algum registro foi afetado
        if registros_semcadastro == 0:
            conn.rollback()
            return jsonify({'success': False, 'message': 'Nenhum registro foi excluído da lista de não cadastrados'})
        
        conn.commit()
        
        # Criar mensagem de sucesso
        if excluir_movimentos and registros_movimentos > 0:
            message = f'Veículo {placa} excluído com sucesso! Removidos {registros_semcadastro} registro(s) da lista de não cadastrados e {registros_movimentos} movimento(s).'
        elif excluir_movimentos and registros_movimentos == 0:
            message = f'Veículo {placa} excluído da lista de não cadastrados. Nenhum movimento foi encontrado para exclusão.'
        else:
            message = f'Veículo {placa} excluído da lista de não cadastrados com sucesso!'
        
        return jsonify({
            'success': True,
            'message': message,
            'registros_semcadastro': registros_semcadastro,
            'registros_movimentos': registros_movimentos
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao excluir veículo: {err}'})
    finally:
        cursor.close()
        conn.close()


# API para corrigir placa de veículo não cadastrado
# Referência no programa principal
# @app.route('/api/corrigir-placa-veiculo', methods=['POST'])
# def api_corrigir_placa_veiculo():
def corrigir_placa_veiculo():
    """Corrige a placa de um veículo não cadastrado para uma placa existente no cadveiculo"""
    data = request.get_json()
    
    placa_atual = data.get('placa_atual', '').strip().upper()
    placa_corrigida = data.get('placa_corrigida', '').strip().upper()
    idcond = data.get('idcond')
    
    # Validações básicas
    if not placa_atual or not placa_corrigida or not idcond:
        return jsonify({'success': False, 'message': 'Placa atual, placa corrigida e ID do condomínio são obrigatórios'})
    
    if placa_atual == placa_corrigida:
        return jsonify({'success': False, 'message': 'A placa corrigida deve ser diferente da placa atual'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})
    
    cursor = conn.cursor()
    try:
        # 1. Verificar se a placa atual existe na tabela semcadastro
        cursor.execute("""
            SELECT placa FROM semcadastro 
            WHERE placa = %s AND idcond = %s
            LIMIT 1
        """, (placa_atual, idcond))
        
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Placa atual não encontrada na lista de não cadastrados'})
        
        # 2. Verificar se a placa corrigida existe no cadastro de veículos (cadveiculo)
        cursor.execute("""
            SELECT cv.placa, co.nmcor as cor, ma.nmmarca as marca, mo.nmmodelo as modelo
            FROM cadveiculo cv
            LEFT JOIN cadmodelo mo ON cv.idmodelo = mo.idmodelo
            LEFT JOIN cadmarca ma ON mo.idmarca = ma.idmarca
            LEFT JOIN cadcores co ON cv.idcor = co.idcor
            WHERE cv.placa = %s
            LIMIT 1
        """, (placa_corrigida,))
        
        veiculo_corrigido = cursor.fetchone()
        if not veiculo_corrigido:
            return jsonify({'success': False, 'message': 'Placa corrigida não encontrada no cadastro de veículos'})

        # Iniciar transação
        cursor.execute("START TRANSACTION")
        
        # Inicializar contador para deparaplacas
        registros_deparaplacas = 0
        
        # 3. Atualizar a placa na tabela movcar (todos os movimentos)
        cursor.execute("""
            UPDATE movcar 
            SET placa = %s
            WHERE placa = %s AND idcond = %s
        """, (placa_corrigida, placa_atual, idcond))

        registros_movimentos = cursor.rowcount

        # 4. Excluir a placa da tabela semcadastro
        cursor.execute("""
            DELETE FROM semcadastro 
            WHERE placa = %s AND idcond = %s
        """, (placa_atual, idcond))

        registros_semcadastro = cursor.rowcount

        # 5. Excluir a placa da tabela cadnick (apelidos) se existir
        cursor.execute("""
            DELETE FROM cadnick 
            WHERE placa = %s AND idcond = %s
        """, (placa_atual, idcond))

        registros_apelidos = cursor.rowcount

        # 6. Inserir o mapeamento na tabela deparaplacas
        # placade = placa atual (incorreta), placapara = placa corrigida (correta)
        try:
            cursor.execute("""
                INSERT INTO deparaplacas (placade, placapara)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE placapara = VALUES(placapara)
            """, (placa_atual, placa_corrigida))

            registros_deparaplacas = cursor.rowcount

        except mysql.connector.Error as err:
            registros_deparaplacas = 0  # Não falhar a operação por causa disso
        
        # Verificar se pelo menos o registro principal foi afetado
        if registros_semcadastro == 0:
            conn.rollback()
            return jsonify({'success': False, 'message': 'Nenhum registro foi excluído da lista de não cadastrados'})
        
        conn.commit()
        cursor.close()
        conn.close()

        # Criar mensagem de sucesso detalhada
        veiculo_info = f"{veiculo_corrigido[2]} {veiculo_corrigido[3]}" if veiculo_corrigido[2] and veiculo_corrigido[3] else "veículo"
        message = f'Placa corrigida com sucesso! {placa_atual} → {placa_corrigida} ({veiculo_info}). '
        
        detalhes = []
        if registros_movimentos > 0:
            detalhes.append(f'{registros_movimentos} movimento(s) atualizados')
        if registros_semcadastro > 0:
            detalhes.append(f'{registros_semcadastro} registro(s) excluído(s) da lista de não cadastrados')
        if registros_apelidos > 0:
            detalhes.append(f'{registros_apelidos} apelido(s) excluído(s)')
        if registros_deparaplacas > 0:
            detalhes.append('mapeamento salvo para futuras correções automáticas')
        
        if detalhes:
            message += f'{", ".join(detalhes)}.'

        # Corrigir movimentações em duplicatas
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT idmov, nowpost, placa, contav from movcar where placa = %s AND contav = %s', (placa_corrigida, 1))
        movimentos = cursor.fetchall()
        primeiro = datetime.now()
        if movimentos:
            for mov in movimentos:
                idmov = mov['idmov']
                deltat = abs(primeiro - mov['nowpost']).total_seconds()
                if deltat < 180:
                    cursor.execute('UPDATE movcar SET contav = %s WHERE idmov = %s', (0, idmov))
                    conn.commit()
                else:
                    primeiro = mov['nowpost']
        
        return jsonify({
            'success': True,
            'message': message,
            'placa_anterior': placa_atual,
            'placa_nova': placa_corrigida,
            'veiculo_info': {
                'marca': veiculo_corrigido[2] or 'N/A',
                'modelo': veiculo_corrigido[3] or 'N/A',
                'cor': veiculo_corrigido[1] or 'N/A'
            },
            'registros_processados': {
                'movimentos_atualizados': registros_movimentos,
                'semcadastro_excluidos': registros_semcadastro,
                'apelidos_excluidos': registros_apelidos,
                'mapeamento_deparaplacas': registros_deparaplacas
            }
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao corrigir placa: {err}'})
    finally:
        cursor.close()
        conn.close()
        
