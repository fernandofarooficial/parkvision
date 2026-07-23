# --------------------
# DBLIB
# --------------------

import json
import logging
from flask import jsonify
from datetime import datetime
from config.database import get_db_connection
from visionlib.vplib import process_heimdall_plate, consultar_tabela_deparaplacas
from visionlib.operlib import adicionar_evento, executar_acao_operador

logger = logging.getLogger(__name__)

# Quantidade máxima de registros de logbruto mantidos por condomínio.
# Ao inserir um novo, os mais antigos além desse limite são apagados —
# evita crescimento indefinido do jsonbruto (que carrega a foto em base64).
LOGBRUTO_RETENCAO_POR_COND = 20


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
    # Liberação automática (sem intervenção do operador) — decidida por direção da câmera
    auto_confirmar = False
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
            if inforec['direcao'] == 'S':
                # Saída: veículo cadastrado sai livremente, independente do status da permissão
                logger.info(f"[{placa}]: Saída de veículo cadastrado - liberação automática")
                auto_confirmar = True
            elif inforec['direcao'] == 'E' and inforec['status_permissao'] in ('INDEFINIDA', 'VIGENTE'):
                logger.info(f"[{placa}]: Placa com permissão válida")
                # placa autorizada - obter veículos estacionados
                inforec['qtde_estacionada'], inforec['placas_estacionadas'] = contar_vagas_ocupadas(inforec)
                inforec['vagas_permitidas'] = obter_vagas_permitidas(inforec)
                logger.info(f"[{placa}]: vagas_permitidas={inforec['vagas_permitidas']} estacionados={inforec['qtde_estacionada']}")
                # checar quantidade de vagas permitidas
                if inforec['qtde_estacionada'] >= inforec['vagas_permitidas']:
                    logger.info(f"[{placa}]: Todas as vagas ocupadas")
                    # Vaga cheia, mas se a própria placa já consta como estacionada
                    # (última entrada confirmada sem saída correspondente), a contagem
                    # de ocupação já a inclui — bloquear a entrada duplicaria a restrição
                    # sobre o próprio veículo. Libera e sinaliza para o operador conferir.
                    placas_estacionadas = [p.strip() for p in (inforec['placas_estacionadas'] or '').split(',')]
                    if placa in placas_estacionadas:
                        logger.info(f"[{placa}]: Veículo já constava como estacionado - liberando entrada")
                        inforec['motivo'] = 'Veículo já constava como estacionado, liberado'
                        inforec['statusmov_override'] = 'P'
                        auto_confirmar = True
                else:
                    logger.info(f"[{placa}]: Todos critérios atendidos")
                    auto_confirmar = True
            elif inforec['direcao'] == 'E':
                logger.info(f"[{placa}]: Placa sem permissão válida")
            else:
                # câmera interna (I): sempre depende de decisão manual do operador
                logger.info(f"[{placa}]: Câmera de direção '{inforec['direcao']}' - aguardando decisão do operador")
        else:
            logger.info(f"[{placa}]: Placa sem cadastro")
            # placa não cadastrada - não abre portão (avisa para cadastrar ou barrar)
            inforec['status_permissao'] = 'NÃO CADASTRADO'
        # Zerar contav antes de gravar: contav final é definido por gravar_log/executar_acao_operador
        inforec['contav'] = 0
    # gravar o log
    gravar_log(inforec)
    # Eventos válidos: liberar automaticamente quando elegível, senão aguardar o operador
    if valido:
        if auto_confirmar:
            resultado = executar_acao_operador(
                inforec['idmov'], 'confirmar', None, inforec.get('motivo'), origem='AUTO',
                statusmov_override=inforec.get('statusmov_override')
            )
            if resultado.get('success'):
                logger.info(f"[{placa}]: Liberação automática confirmada (idmov={inforec['idmov']})")
            else:
                logger.warning(
                    f"[{placa}]: falha na liberação automática ({resultado.get('message')}) "
                    f"- enviado para a tela Operador"
                )
                adicionar_evento(inforec)
        else:
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
    # gravar o log bruto (jsonbruto guarda o payload completo do Heimdall,
    # incluindo a foto em data.image_base64 — o volume é controlado pela
    # retenção de LOGBRUTO_RETENCAO_POR_COND registros por condomínio,
    # não por mascaramento de conteúdo)
    connection = get_db_connection()
    cursor = connection.cursor()
    #
    jsonbruto = json.dumps(movdic, ensure_ascii=False, default=str) if movdic is not None else None
    consulta = '''
        INSERT INTO logbruto (idlog,placalida,nowpost,nomecam,idcam,jsonbruto)
        VALUES (%s, %s, %s, %s, %s, %s)
        '''
    valores = (inforec['log_id'], inforec['placalida'], inforec['momento'], inforec['nome_camera'], inforec['camera_id'], jsonbruto)
    cursor.execute(consulta, valores)
    connection.commit()
    #
    limitar_logbruto_por_condominio(cursor, connection, inforec['camera_id'])
    #
    cursor.close()
    connection.close()
    return


def limitar_logbruto_por_condominio(cursor, connection, idcam):
    # Mantém apenas os últimos LOGBRUTO_RETENCAO_POR_COND registros de logbruto
    # por condomínio (via cadcamera.idcond), apagando os mais antigos
    cursor.execute("SELECT idcond FROM cadcamera WHERE idcam = %s LIMIT 1", (idcam,))
    resultado = cursor.fetchone()
    if resultado is None:
        # Câmera desconhecida - não é possível associar a um condomínio, nada a limitar
        return
    idcond = resultado[0]
    consulta = f'''
        DELETE FROM logbruto
        WHERE idcam IN (SELECT idcam FROM cadcamera WHERE idcond = %s)
          AND id NOT IN (
              SELECT id FROM (
                  SELECT lb.id
                  FROM logbruto lb
                  INNER JOIN cadcamera cc ON cc.idcam = lb.idcam
                  WHERE cc.idcond = %s
                  ORDER BY lb.id DESC
                  LIMIT {LOGBRUTO_RETENCAO_POR_COND}
              ) AS manter
          )
        '''
    cursor.execute(consulta, (idcond, idcond))
    connection.commit()
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


def obter_ultimas_fotos(idcond, limite=10):
    # Lista as últimas fotos de veículos disponíveis em logbruto.jsonbruto
    # (campo data.image_base64) para o condomínio informado.
    # Restrita aos eventos ainda pendentes de confirmação (movcar.contav = 0)
    # e com placa reconhecida (diferente do sentinel '*ERROR*'), via join
    # pelo idlog compartilhado entre logbruto e movcar (ver gravar_log/registrar_log_bruto).
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        query = '''
            SELECT lb.id, lb.idlog, lb.placalida, lb.nowpost, lb.nomecam, mc.idmov,
                   JSON_UNQUOTE(JSON_EXTRACT(lb.jsonbruto, '$.data.image_base64')) AS foto,
                   (SELECT MAX(m2.idmov) FROM movcar m2
                     WHERE m2.idcond = mc.idcond AND m2.contav = 1 AND m2.idmov < mc.idmov) AS idmov_anterior,
                   (SELECT MIN(m3.idmov) FROM movcar m3
                     WHERE m3.idcond = mc.idcond AND m3.contav = 1 AND m3.idmov > mc.idmov) AS idmov_posterior
            FROM logbruto lb
            INNER JOIN cadcamera cc ON cc.idcam = lb.idcam
            INNER JOIN movcar mc ON mc.idlog = lb.idlog
            WHERE cc.idcond = %s
              AND JSON_EXTRACT(lb.jsonbruto, '$.data.image_base64') IS NOT NULL
              AND mc.contav = 0
              AND mc.placa != '*ERROR*'
            ORDER BY lb.id DESC
            LIMIT %s
        '''
        cursor.execute(query, (idcond, limite))
        fotos = cursor.fetchall()

        # Para cada foto pendente, buscar placa/marca/modelo/cor do movimento confirmado
        # (contav=1) imediatamente anterior e posterior no mesmo condomínio, reaproveitando
        # vw_movimentos (já encapsula os JOINs cadveiculo->cadmodelo->cadmarca->cadcores)
        idmovs_vizinhos = {f['idmov_anterior'] for f in fotos if f['idmov_anterior']} | \
                          {f['idmov_posterior'] for f in fotos if f['idmov_posterior']}
        vizinhos_por_idmov = {}
        if idmovs_vizinhos:
            placeholders = ','.join(['%s'] * len(idmovs_vizinhos))
            cursor.execute(
                f'''SELECT idmov, placa, marca, modelo, cor, ultima AS nowpost
                    FROM vw_movimentos WHERE idmov IN ({placeholders})''',
                tuple(idmovs_vizinhos)
            )
            vizinhos_por_idmov = {row['idmov']: row for row in cursor.fetchall()}

        for f in fotos:
            id_anterior = f.pop('idmov_anterior', None)
            id_posterior = f.pop('idmov_posterior', None)
            f.pop('idmov', None)
            f['movimento_anterior'] = vizinhos_por_idmov.get(id_anterior)
            f['movimento_posterior'] = vizinhos_por_idmov.get(id_posterior)
            # Indica se a placa lida na foto já está mapeada em deparaplacas.placade
            # (mesma consulta usada por vplib no fluxo de correção automática de placa)
            f['existe_em_deparaplacas'] = consultar_tabela_deparaplacas(f.get('placalida'))['found']

        return jsonify({'success': True, 'data': fotos})
    except Exception as err:
        logger.error(f"obter_ultimas_fotos: erro ao consultar logbruto - {err}")
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        conn.close()











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
