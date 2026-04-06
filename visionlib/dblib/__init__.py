# --------------------
# DBLIB
# --------------------

from flask import jsonify
from datetime import datetime
from ArquivosApoio.draftqualquer import idcond
from config.database import get_db_connection
from visionlib.vplib import process_heimdall_plate
from visionlib.teleglib import enviar_mensagem_telegram


def gravar_movimento(movdic):
    # Carregar variaveis importantes e criar dicionário de retorno
    inforec = carregar_leitura(movdic)
    lpri = f"[AFP:{inforec['log_id']}]:"
    print(f"[{lpri}Primeira carga do inforec - Placa Lida = {inforec['placalida']}")
    # gravar o log bruto
    gravar_log_bruto(inforec)
    print(f"[{lpri}Log bruto gravado - Id Camera = {inforec['camera_id']}")
    # Validar a placa lida
    verifica_placa = process_heimdall_plate(inforec['placalida'], idcond, 0.8)
    placa = verifica_placa['corrected_plate']
    inforec['placa'] = placa
    print(f"{lpri}Placa analisada - Placa = {placa}")
    # Verifica se a placa é válida
    if not verifica_placa['found_match'] or placa == '*ERROR*':
        # placa invalida - grava log mas não considera o registro
        inforec['placa'] = '*ERROR*'
        inforec['contav'] = 0
        gravar_log(inforec)
        print(f"{lpri}placa inválida")
        return inforec
    # Carregar dados da camera
    infocamera = carregar_dados_camera(inforec)
    inforec['idcond'] = infocamera['idcond']
    inforec['direcao'] = infocamera['direcao']
    print(f"{lpri}Carreguei dados camera - Idcond: {inforec['idcond']}")
    # Checar se tivemos eventos anteriores para esta placa
    inforec['contav'] = checar_anteriores(inforec)
    print(f"{lpri}Chequei anteriores - ContaV: {inforec['contav']}")
    # Só processo se contav = 1, se for zero só grava o log
    if inforec['contav'] == 1:
        # Verifica se a placa está cadastrada, só abre se estiver cadastrada
        if placadastrada(inforec['idcond'], inforec['placa']):
            # placa cadastrada - verifica se está na validade e pega o nome do condominio
            inforec['nome_condominio'] = obter_nome_condominio(inforec)
            inforec['status_permissao'], inforec['unidade'] = placaautorizada(inforec)
            if inforec['status_permissao'] in ('INDEFINIDA', 'VIGENTE'):
                # placa autorizada
                # obter veiculos estacionados
                inforec['qtde_estacionada'], inforec['placas_estacionadas'] = contar_vagas_ocupadas(inforec)
                inforec['vagas_permitidas'] = obter_vagas_permitidas(inforec)
                print(f"{lpri}veículo autorizado - ",end=False)
                print(f"Vagas permitidas: {inforec['vagas_permitidas']} ",end=False)
                print(f"Estacionados: {inforec['qtde_estacionada']} - {inforec['placas_estacionadas']}")
            else:
                print(f"{lpri}: veículo não autorizado")
        else:
            # placa não cadastrada - não abre portão (avisa para cadastrar ou barrar)
            print(f"{lpri}placa não cadastrada - ")
    # gravar o log
    gravar_log(inforec)
    # Processar mensagens Telegram apenas para movimentos válidos (contav=1)
    if inforec['contav'] == 1:
        # Trata a mensagem para o Telegram
        mensagem_telegram(inforec)
    #
    return inforec


def carregar_leitura(movdic):
    # Carregar variaveis importantes e criar dicionário de retorno
    placalida = movdic.get('data', {}).get('plate_value', 'N/A')
    inforec = {'placalida': placalida}
    momentorecebido = movdic.get('data', {}).get('created_at', 'N/A')
    inforec['instante'] = momentorecebido
    inforec['momento'] = datetime.strptime(momentorecebido, '%d/%m/%Y %H:%M:%S')
    inforec['id_analitico'] = movdic.get('data', {}).get('analytic_id', 'N/A')
    inforec['nome_camera'] = movdic.get('data', {}).get('camera_name', 'N/A')
    inforec['log_id'] = movdic.get('data', {}).get('log_id', 'N/A')
    inforec['camera_id'] = movdic.get('data', {}).get('camera_id', 'N/A')
    inforec['address'] = movdic.get('data', {}).get('address', 'N/A')
    inforec['cor_do_carro'] = movdic.get('data', {}).get('car_color', 'N/A')
    inforec['cor_do_carro_conf'] = movdic.get('data', {}).get('car_color_confs', 'N/A')
    return inforec


def gravar_log_bruto(inforec):
    # gravar o log bruto
    connection = get_db_connection()
    cursor = connection.cursor()
    #
    consulta = '''
        INSERT INTO logbruto (idlog,placalida,nowpost,nomecam,idcam)
        VALUES (%s, %s, %s, %s, %s)
        '''
    valores = (inforec['log_id'], inforec['placalida'], inforec['momento'], inforec['nome_camera'], inforec['camera_id'])
    cursor.execute(consulta, valores)
    connection.commit()
    #
    cursor.close()
    connection.close()
    return


def carregar_dados_camera(inforec):
    # gerar lista com as informações da câmera que recebemos o alerta
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    #
    query = "SELECT * FROM cadcamera WHERE idcam = %s LIMIT 1"
    values = (inforec['camera_id'],)
    cursor.execute(query, values)
    infocamera = cursor.fetchone()
    #
    cursor.close()
    connection.close()
    #
    return infocamera


def checar_anteriores(inforec):
    # verificar se a placa foi computada no ultimo minuto para evitar duplo movimento
    # Por padrão, conta a vaga
    contav = 1
    # abrir conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    # Ler os últimos movimentos
    query = "SELECT placa, contav, idcond, nowpost FROM movcar WHERE idcond = %s AND placa = %s ORDER BY nowpost DESC LIMIT 10"
    values = (inforec['idcond'],inforec['placa'])
    cursor.execute(query, values)
    movimentos = cursor.fetchall()
    # verificar se a placa já foi contabilizada anteriormente
    for movimento in movimentos:
        if movimento['contav'] == 1:
            tempo_diferenca = abs(inforec["momento"] - movimento['nowpost']).total_seconds()
            if tempo_diferenca < 90:  # Movimento duplicado em 90s
                contav = 0  # Não contar esta vaga
    # fechar base de dados
    cursor.close()
    connection.close()
    # fecha a função com o resultado de contav
    return contav


def gravar_log(inforec):
    # gravar o log em movcar
    connection = get_db_connection()
    cursor = connection.cursor()
    # montar query para gravar na tabela de movimento de carro - log
    query = f"""
            INSERT INTO movcar 
            (idlog, idcond, placa, placalida, nowpost, cor, corconf, ender, nomecam, 
            idcam, idaia, contav, instante, direcao) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
    valor = (inforec['log_id'],      inforec['idcond'],       inforec['placa'],             inforec['placalida'],
             inforec['momento'],     inforec['cor_do_carro'], inforec['cor_do_carro_conf'], inforec['address'],
             inforec['nome_camera'], inforec['camera_id'],    inforec['id_analitico'],      inforec['contav'],
             inforec['instante'],    inforec['direcao'])
    cursor.execute(query, valor)
    connection.commit()
    #
    cursor.close()
    connection.close()
    #
    return


def contar_vagas_ocupadas(inforec):
    # obter situação das vagas da unidade
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    #
    query = 'SELECT estacionados, placas FROM vw_estacionados WHERE idcond = %s AND unidade = %s LIMIT 1'
    values = (inforec['idcond'], inforec['unidade'])
    cursor.execute((query,values))
    retorno_query = cursor.fetchone()
    #
    cursor.close()
    connection.close()
    #
    return retorno_query


def obter_vagas_permitidas(inforec):
    # obter quantidade de vagas permitidas
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    #
    query = 'SELECT vperm ASs vagas_permitidas vagasunidades WHERE idcond = %s AND unidade = %s LIMIT 1'
    values = (inforec['idcond'], inforec['unidade'])
    cursor.execute(query, values)
    retorno_query = cursor.fetchone()
    #
    cursor.close()
    connection.close()
    #
    return retorno_query


def obter_nome_condominio(inforec):
    # obter o nome do condomínio
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    #
    query = 'SELECT nmcond FROM cadcond WHERE idcond = %s LIMIT 1'
    values = (inforec['idcond'],)
    cursor.execute(query, values)
    retorno_query = cursor.fetchone()
    #
    cursor.close()
    connection.close()
    #
    return retorno_query['nmcond']



def mensagem_telegram(inforec):
    # Trata mensagens no telegram
    print(f"mensagem telegram {inforec}")
    return







# --------------------------------------------------------------------------------------------
#
# funcões de banco de dados de cadastro
#
def obter_marcas():
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)

    # Tentar buscar marcas da view vw_marca, se não existir, usar lista padrão
    try:
        cursor.execute("SELECT DISTINCT nmmarca as marca FROM vw_marca ORDER BY nmmarca")
        marcas = cursor.fetchall()
        if not marcas:
            raise Exception("Tabela vazia")
        return marcas
    except:
        return None

    finally:
        cursor.close()
        conn.close()


def obter_idmarca(nomemarca):

    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor()

    qry1 = 'SELECT idmarca FROM cadmarca WHERE nmmarca = %s'

    cursor.execute(qry1, (nomemarca,))
    rst = cursor.fetchall()

    linhas_id_marca = cursor.rowcount
    if linhas_id_marca == 0:
        return None

    cursor.close()
    return rst[0][0]


def obter_modelos(marca):
    idmarca = obter_idmarca(marca)
    if idmarca is None:
        return None

    conn = get_db_connection()
    if not conn:
        return None

    """Versão mais simples da função."""
    try:
        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT DISTINCT nmmodelo as modelo FROM cadmodelo WHERE idmarca = %s ORDER BY modelo"
            cursor.execute(query, (idmarca,))
            modelos_lista = cursor.fetchall()
            modelos_formatados = []
            for modelo in modelos_lista:
                modelos_formatados.append(modelo)
            return modelos_formatados
            # return {marca.upper(): modelos_formatados}

    except Exception as e:
        return []


def inserir_carro(idcond, data):

    placa = data.get('placa')
    marca = data.get('marca')
    modelo = data.get('modelo')
    unidade = data.get('unidade')
    idcor = data.get('idcor')
    # campos de tempo (vem do html em string)
    # Data/hora inicio
    inicio_str = f"{data.get('data_inicio')} {data.get('hora_inicio')}"
    formato = "%Y-%m-%d %H:%M"
    data_inicio = datetime.strptime(inicio_str, formato)
    # Data/hora fim
    if data.get('data_fim') is None:
        data_fim = None
    else:
        fim_str = f"{data.get('data_fim')} {data.get('hora_fim')}"
        data_fim = datetime.strptime(fim_str, formato)
    # tempo indeterminado
    tempo_indeterminado = data.get('tempo_indeterminado', False)

    # Validar dados obrigatórios
    if not placa or not marca or not modelo or not unidade or not idcor or not data_inicio:
        return jsonify({'success': False, 'message': 'Todos os campos obrigatórios devem ser preenchidos'})

    # Validar lógica de datas
    if not tempo_indeterminado and data_fim:
        try:
            if data_fim <= data_inicio:
                return jsonify({'success': False, 'message': 'A data de fim deve ser posterior à data de início'})
        except ValueError:
            return jsonify({'success': False, 'message': 'Formato de data inválido'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor()

    # NOVA ESTRUTURA: Verificar se o veículo já existe usando CADVEICULO
    cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (placa,))

    if cursor.fetchone():
        return jsonify({'success': False, 'message': 'Veículo já cadastrado'})

    # obter o id do modelo
    cursor.execute("""
            SELECT idmodelo from cadmodelo where nmmodelo = %s""", (modelo,))
    resultado = cursor.fetchall()
    linhas = cursor.rowcount
    if linhas == 0:
        return jsonify({'success': False, 'message': 'Código do modelo não foi encontrado'})
    idmodelo = resultado[0][0]
    # dados = {'idcond': idcond, 'placa': placa, 'unidade': unidade, 'idmodelo': idmodelo, 'cor': cor,
    #          'data_inicio': data_inicio, 'data_fim': data_fim}

    # NOVA ESTRUTURA: Inserir nas 3 tabelas com dados de permanência
    try:
        # 1. Inserir em CADVEICULO
        query_veiculo = 'INSERT INTO cadveiculo (placa, idmodelo, idcor) VALUES (%s, %s, %s)'
        cursor.execute(query_veiculo, (placa, idmodelo, idcor))

        # 2. Inserir em CADPERM com dados de permanência
        if tempo_indeterminado:
            query_perm = 'INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim) VALUES (%s, %s, %s, %s, NULL)'
            cursor.execute(query_perm, (idcond, placa, unidade, data_inicio))
        else:
            query_perm = 'INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim) VALUES (%s, %s, %s, %s, %s)'
            cursor.execute(query_perm, (idcond, placa, unidade, data_inicio, data_fim))

        conn.commit()
        rows_affected = cursor.rowcount

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': f'Erro ao cadastrar veículo (03): {str(e)}'})

    cursor.close()
    conn.close()
    if rows_affected > 0:
        return jsonify({'success': True, 'message': 'Veículo cadastrado com sucesso'})
    else:
        return jsonify({'success': False, 'message': 'Veículo NÃO cadastrado!'})


def obter_cores():
    """
    Obtém lista de cores disponíveis da tabela vw_cores
    Retorna: lista de dicts com idcor e nmcor
    """
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT idcor, nmcor FROM vw_cor ORDER BY nmcor")
        cores = cursor.fetchall()
        return cores
    except Exception as e:
        return None
    finally:
        cursor.close()
        conn.close()


def placadastrada(cond, pplaca):
    # verifica se a placa está cadastrada
    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()
    # ler cadastro
    resultadoconsulta = False
    cursor.execute('SELECT placa FROM cadveiculo WHERE placa = %s', (pplaca,))
    placaretornada = cursor.fetchall()
    if placaretornada:
        resultadoconsulta = True
    else:
        query = 'INSERT INTO semcadastro (idcond, placa) VALUES (%s, %s)'
        cursor.execute(query, (cond, pplaca))
        connection.commit()
    #
    cursor.close()
    connection.close()
    #
    return resultadoconsulta


def placaautorizada(inforec):
    # verifica se a placa está dentro do tempo de validade
    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    # fazer a consulta
    query = """
        SELECT placa, idcond, status_permissao, unidade
        FROM vw_autorizacoes
        WHERE idcond = %s AND placa = %s
        ORDER BY rank_permissao
        LIMIT 1
    """
    values = (inforec['idcond'],inforec['placa'])
    cursor.execute(query, values)
    resultado = cursor.fetchone()
    #
    if resultado is None:
        # Não achou placa no condomínio
        resultado = {'status_permissao': 'Inexistente', 'unidade': 'N/A', 'idcond': inforec['idcond'], 'placa': inforec['placa']}
    #
    cursor.close()
    connection.close()
    #
    print(f'PlacaAut - resultado: {resultado}')
    return resultado['status_permissao'], resultado['unidade']
