# --------------------
# DBLIB
# --------------------

import json
import logging
from flask import jsonify
from datetime import datetime
from config.database import get_db_connection
from visionlib.vplib import process_heimdall_plate
from visionlib.operlib import adicionar_evento

logger = logging.getLogger(__name__)


def gravar_movimento(movdic):
    # Carregar variáveis importantes e criar dicionário de retorno
    inforec = carregar_leitura(movdic)
    # Gravar o log bruto
    gravar_log_bruto(inforec, movdic)
    # Carregar dados da câmera primeiro para obter idcond correto
    infocamera = carregar_dados_camera(inforec)
    if infocamera is None:
        logger.error(f"Câmera {inforec.get('camera_id')} não encontrada em cadcamera")
        return inforec
    inforec['idcond'] = infocamera['idcond']
    inforec['direcao'] = infocamera['direcao']
    # Validar a placa lida com o idcond correto
    verifica_placa = process_heimdall_plate(inforec['placalida'], inforec['idcond'], 0.8)
    placa = verifica_placa['corrected_plate']
    inforec['placa'] = placa
    linhalog = (
        f"Placa checada - Cam: {inforec['camera_id']} - "
        f"Placa lida: {inforec['placalida']} - "
        f"Placa de trabalho: {inforec['placa']} - "
        f"Post: {inforec['instante']}"
    )
    logger.info(linhalog)
    # Verifica se a placa é válida
    if not verifica_placa['found_match'] or placa == '*ERROR*':
        # placa inválida - grava log mas não considera o registro
        inforec['placa'] = '*ERROR*'
        inforec['contav'] = 0
        gravar_log(inforec)
        return inforec
    # Checar se tivemos eventos anteriores para esta placa
    inforec['contav'] = checar_anteriores(inforec)
    # Registrar se o evento é válido (não duplicata) antes de zerar o contav
    valido = (inforec['contav'] == 1)
    # Só processo se for válido; se for duplicata apenas grava o log
    if valido:
        # obter nome do condomínio
        inforec['nome_condominio'] = obter_nome_condominio(inforec)
        # Verifica se a placa está cadastrada, só abre se estiver cadastrada
        if placadastrada(inforec['idcond'], inforec['placa']):
            logger.info(f"[{placa}]: Placa cadastrada")
            # placa cadastrada - verifica se está na validade
            inforec['status_permissao'], inforec['unidade'] = placaautorizada(inforec)
            logger.info(f"[{placa}]: Status da permissão: {inforec['status_permissao']}")
            if inforec['status_permissao'] in ('INDEFINIDA', 'VIGENTE'):
                logger.info(f"[{placa}]: Placa com permissão válida")
                # placa autorizada - obter veículos estacionados
                inforec['qtde_estacionada'], inforec['placas_estacionadas'] = contar_vagas_ocupadas(inforec)
                inforec['vagas_permitidas'] = obter_vagas_permitidas(inforec)
                logger.info(f"[{placa}]: vagas_permitidas={inforec['vagas_permitidas']} estacionados={inforec['qtde_estacionada']}")
                # checar quantidade de vagas permitidas
                if inforec['qtde_estacionada'] >= inforec['vagas_permitidas']:
                    logger.info(f"[{placa}]: Todas as vagas ocupadas")
                else:
                    logger.info(f"[{placa}]: Todos critérios atendidos")
            else:
                logger.info(f"[{placa}]: Placa sem permissão válida")
        else:
            logger.info(f"[{placa}]: Placa sem cadastro")
            # placa não cadastrada - não abre portão (avisa para cadastrar ou barrar)
            inforec['status_permissao'] = 'NÃO CADASTRADO'
        # Zerar contav antes de gravar: o operador decide a ação (confirmar/rejeitar/ignorar)
        inforec['contav'] = 0
    # gravar o log
    gravar_log(inforec)
    # Atualizar tela Operador em tempo real apenas para eventos válidos (não duplicatas)
    if valido:
        adicionar_evento(inforec)
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


def gravar_log_bruto(inforec, movdic=None):
    # gravar o log bruto
    connection = get_db_connection()
    cursor = connection.cursor()
    #
    if movdic is not None:
        movdic_log = {k: ("Foto" if k == "imagebase64" else v) for k, v in movdic.items()}
        jsonbruto = json.dumps(movdic_log, ensure_ascii=False, default=str)
    else:
        jsonbruto = None
    consulta = '''
        INSERT INTO logbruto (idlog,placalida,nowpost,nomecam,idcam,jsonbruto)
        VALUES (%s, %s, %s, %s, %s, %s)
        '''
    valores = (inforec['log_id'], inforec['placalida'], inforec['momento'], inforec['nome_camera'], inforec['camera_id'], jsonbruto)
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
    # Ler os últimos movimentos (incluindo idgente para distinguir pendentes de rejeitados)
    query = "SELECT placa, contav, idgente, idcond, nowpost FROM movcar WHERE idcond = %s AND placa = %s ORDER BY nowpost DESC LIMIT 10"
    values = (inforec['idcond'],inforec['placa'])
    cursor.execute(query, values)
    movimentos = cursor.fetchall()
    # verificar se a placa já foi contabilizada anteriormente:
    # - contav=1 (confirmado pelo operador) → duplicata
    # - contav=0 e idgente IS NULL (pendente, aguardando operador) → duplicata
    # - contav=0 e idgente IS NOT NULL (rejeitado/ignorado) → NÃO é duplicata
    for movimento in movimentos:
        eh_pendente   = (movimento['contav'] == 0 and movimento['idgente'] is None)
        eh_confirmado = (movimento['contav'] == 1)
        if eh_pendente or eh_confirmado:
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
    inforec['idmov'] = cursor.lastrowid
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
    cursor.execute(query,values)
    retorno_query = cursor.fetchone()
    if retorno_query is None:
        retorno_query = {'estacionados': 0, 'placas': "N/A"}
    #
    cursor.close()
    connection.close()
    #
    return retorno_query['estacionados'], retorno_query['placas']


def obter_vagas_permitidas(inforec):
    # se for Prestador, Avulso ou Visitante colocar 10 vagas permitidas
    if inforec['unidade'] in ("Avulso", "Prestador", "Visitante"):
        return 10
    # obter quantidade de vagas permitidas
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    #
    query = 'SELECT vperm AS vagas_permitidas FROM vagasunidades WHERE idcond = %s AND unidade = %s LIMIT 1'
    values = (inforec['idcond'], inforec['unidade'])
    cursor.execute(query, values)
    retorno_query = cursor.fetchone()
    #
    cursor.close()
    connection.close()
    logger.debug(f"obter_vagas_permitidas: {retorno_query}")
    #
    return retorno_query['vagas_permitidas']


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
        resultado = {'status_permissao': 'INEXISTENTE', 'unidade': 'N/A', 'idcond': inforec['idcond'], 'placa': inforec['placa']}
    #
    cursor.close()
    connection.close()
    #
    return resultado['status_permissao'], resultado['unidade']
