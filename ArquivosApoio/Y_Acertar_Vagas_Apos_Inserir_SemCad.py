# API para cadastrar veículo não cadastrado
@app.route('/api/cadastrar-veiculo-nao-cadastrado', methods=['POST'])
def api_cadastrar_veiculo_nao_cadastrado():
    data = request.get_json()

    autenticado, cond_id = verificar_autenticacao()
    if not autenticado or str(cond_id) != str(data.get('condominio_id')):
        return jsonify({'success': False, 'message': 'Não autorizado'})

    conn = get_db_connection_local()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor()
    try:
        # Extrair dados de permanência
        data_inicio = data.get('data_inicio')
        data_fim = data.get('data_fim')
        tempo_indeterminado = data.get('tempo_indeterminado', False)

        # Validar dados obrigatórios
        if not data_inicio:
            return jsonify({'success': False, 'message': 'Data de início é obrigatória'})

        # Validar lógica de datas
        if not tempo_indeterminado and data_fim:
            from datetime import datetime
            try:
                inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
                fim = datetime.strptime(data_fim, '%Y-%m-%d')
                if fim <= inicio:
                    return jsonify({'success': False, 'message': 'A data de fim deve ser posterior à data de início'})
            except ValueError:
                return jsonify({'success': False, 'message': 'Formato de data inválido'})

        # 1. Inserir dados básicos do veículo em CADVEICULO
        sql_insert_veiculo = """
        INSERT INTO cadveiculo (placa, idmodelo, cor, lup)
        VALUES (%s, %s, %s, NOW())
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
            data['cor']
        ])

        # Pegar o ultimo movimento, para determinar o sit
        q = 'SELECT direcao FROM movcar WHERE contav = %s AND placa = %s ORDER BY idmov DESC LIMIT 1;'
        v = (1, data['placa'])
        cursor.execute(q, v)
        direcao = cursor.fetchone()
        sit = 1 if direcao[0] == 'E' else 0

        # 2. Inserir localização em CADLOCAL
        sql_insert_local = """
        INSERT INTO cadlocal (idcond, placa, unidade, sit)
        VALUES (%s, %s, %s, %s)
        """

        cursor.execute(sql_insert_local, [
            data['condominio_id'],
            data['placa'],
            data['unidade'],
            sit
        ])

        # 3. Inserir permissão em CADPERM com dados de permanência
        if tempo_indeterminado:
            sql_insert_perm = """
            INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim, lup)
            VALUES (%s, %s, %s, %s, NULL, NOW())
            """
            cursor.execute(sql_insert_perm, [
                data['condominio_id'],
                data['placa'],
                data['unidade'],
                data_inicio
            ])
        else:
            sql_insert_perm = """
            INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim, lup)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(sql_insert_perm, [
                data['condominio_id'],
                data['placa'],
                data['unidade'],
                data_inicio,
                data_fim
            ])

        # Remover da tabela semcadastro após cadastrar
        sql_delete = """
        DELETE FROM semcadastro 
        WHERE idcond = %s AND placa = %s
        """

        cursor.execute(sql_delete, [
            data['condominio_id'],
            data['placa']
        ])

        conn.commit()

        # Recebendo a quantidade de vagas do cadlocal
        cursor.execute('SELECT SUM(sit) FROM cadlocal WHERE idcond = %s AND unidade = %s', (idcond, unidade))
        qtdfinal = int(cursor.fetchone()[0])
        query = 'UPDATE vagasunidades SET vocup = %s WHERE idcond = %s AND unidade = %s'
        cursor.execute(query, (qtdfinal, data['condominio_id'], data['unidade']))
        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Veículo cadastrado com sucesso!'
        })

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao cadastrar veículo: {err}'})
    finally:
        cursor.close()
        conn.close()
