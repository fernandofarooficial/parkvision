# --------------------
# DBLIB
# --------------------


from flask import jsonify, current_app
from datetime import datetime
import globals
from config.database import get_db_connection
from visionlib.vplib import process_heimdall_plate
from visionlib.teleglib import enviar_mensagem_telegram





def gravar_movimento(movdic):
    print(f'[GRAVAMOV] Entrei')
    # Carregar variaveis importantes e criar dicionário de retorno
    placalida = movdic.get('data', {}).get('plate_value', 'N/A')
    inforec = {'placalida': placalida}
    momentorecebido = movdic.get('data', {}).get('created_at', 'N/A')
    instante = inforec['instante'] = momentorecebido
    momento = inforec['momento'] = datetime.strptime(momentorecebido, '%d/%m/%Y %H:%M:%S')
    id_anl = inforec['id_analitico'] = movdic.get('data', {}).get('analytic_id', 'N/A')
    nome_cam = inforec['nome_camera'] = movdic.get('data', {}).get('camera_name', 'N/A')
    log_id = inforec['log_id'] = movdic.get('data', {}).get('log_id', 'N/A')
    cam_id = inforec['camera_id'] = movdic.get('data', {}).get('camera_id', 'N/A')
    adres = inforec['address'] = movdic.get('data', {}).get('address', 'N/A')
    cor = inforec['cor_do_carro'] = movdic.get('data', {}).get('car_color', 'N/A')
    corconf = inforec['cor_do_carro_conf'] = movdic.get('data', {}).get('car_color_confs', 'N/A')

    # gravar o log bruto
    connection = get_db_connection()
    cursor = connection.cursor()
    consulta = '''
        INSERT INTO logbruto (idlog,placalida,nowpost,nomecam,idcam)
        VALUES (%s, %s, %s, %s, %s)
        '''
    valores = (log_id, placalida, momento, nome_cam, cam_id)
    cursor.execute(consulta, valores)
    connection.commit()
    cursor.close()
    connection.close()
    # Log unificado do ciclo de gravação
    print(f'[GRAVAMOV({log_id})] 🚗 HEIMDALL - IdCam: {cam_id} PlacaLida:{placalida} LogID:{log_id}')

    # localizar o código do condomínio
    numerocondominio = int(nome_cam[:4])
    idcond = identificar_condominio(numerocondominio)
    if idcond == 0:
        print(f'[GRAVAMOV({log_id})] Condomínio não cadastrado: {nome_cam} (número: {numerocondominio})')
        return
    inforec['idcond'] = idcond

    # apontar a direção e o tipo de tratamento
    tipotratamento = 0
    direcao = 'I'
    configuracao_encontrada = False
    for dad_cond in globals.cvag:
        if dad_cond['idcond'] == idcond:
            configuracao_encontrada = True
            tipotratamento = dad_cond['tipo']
            if cam_id == dad_cond['cent'] or cam_id == dad_cond['vent']:
                direcao = 'E'
            elif cam_id == dad_cond['cetd'] or cam_id == dad_cond['vetd']:
                direcao = 'E'
            elif cam_id == dad_cond['csai'] or cam_id == dad_cond['vsai']:
                direcao = 'S'
            elif cam_id == dad_cond['cdup'] or cam_id == dad_cond['vdup']:
                direcao = 'I'
            else:
                print(f'[GRAVAMOV({log_id})] Câmera {cam_id} não configurada para condomínio {idcond}')
            if cam_id in (dad_cond['cent'], dad_cond['cetd'], dad_cond['csai'], dad_cond['cdup']):
                inforec['cent'] = dad_cond['cent']
                inforec['csai'] = dad_cond['csai']
                inforec['cdup'] = dad_cond['cdup']
                inforec['cetd'] = dad_cond['cetd']
            else:
                inforec['cent'] = dad_cond['vent']
                inforec['csai'] = dad_cond['vsai']
                inforec['cdup'] = dad_cond['vdup']
                inforec['cetd'] = dad_cond['vetd']
            break

    if not configuracao_encontrada:
        print(f'[GRAVAMOV({log_id})] Configuração não encontrada para condomínio {idcond}')

    inforec['direcao'] = direcao
    inforec['tipotratamento'] = tipotratamento

    # validação da placa
    pulacadastrocarros = False
    verifica_placa = process_heimdall_plate(placalida, idcond, 0.8, pulacadastrocarros)
    placa = verifica_placa['corrected_plate']
    print(f'[GRAVAMOV({log_id})] Resultado validação - Original: {placalida} -> Corrigida: {placa}')
    print(
        f'[GRAVAMOV({log_id})] Match encontrado: {verifica_placa["found_match"]}, Confiança: {verifica_placa["confidence"]}, Método: {verifica_placa["match_method"]}')
    inforec['placa'] = placa

    # 🔧 CORREÇÃO: Apenas rejeitar se a placa for realmente inválida (*ERROR*)
    # Placas válidas mas não cadastradas devem ser processadas normalmente
    if not verifica_placa['found_match'] or placa == '*ERROR*':
        placa = '*ERROR*'
        print(f'[GRAVAMOV({log_id})] ❌ PLACA REJEITADA - {placalida} inconsistente - Condomínio:{idcond}')
        contav = 0
        inforec['contav'] = 0

        gravar_log(log_id, idcond, placa, placalida, momento, cor, corconf, adres, nome_cam, cam_id, id_anl, contav,
                   instante, direcao)
        return inforec

    # ✅ Se chegou aqui, a placa é válida (cadastrada ou não)
    print(f'[GRAVAMOV({log_id})] ✅ PLACA VÁLIDA - {placa} - Método: {verifica_placa["match_method"]}')

    # Direcionar para o tipo de tratamento correto
    if tipotratamento == 1:
        contav_lista = [0, 1, 1, 1]
        direcao_lista = [inforec['direcao'], inforec['direcao'], 'E', 'S']
        cv = tratamentotipo01(inforec)
        contav = contav_lista[cv]
        direcao = direcao_lista[cv]
        inforec['direcao'] = direcao
    elif tipotratamento == 2:
        contav = tratamentotipo02(inforec)
    elif tipotratamento == 3:
        contav, direcao = tratamentotipo03(inforec)
        inforec['direcao'] = direcao
    elif tipotratamento == 0:
        contav = 1
    else:
        print(f'[GRAVAMOV({log_id})] ❌ TIPO INVÁLIDO - {tipotratamento} para {placa}')
        contav = 0
    #
    inforec['contav'] = contav

    # gravar o log
    gravar_log(log_id, idcond, placa, placalida, momento, cor, corconf, adres, nome_cam, cam_id, id_anl, contav,
               instante, direcao)
    print(
        f'[GRAVAMOV({log_id})] Movimento: placa:{placa}; cond:{idcond}; log:{log_id}; Cam:{cam_id}/{nome_cam}; cv:{contav}; dir:{direcao}')

    # 🔧 CORREÇÃO: Verificar cadastro SEMPRE para placas válidas, independentemente do contav
    # O contav controla contagem de vagas, mas o registro de placas novas deve ser independente
    print(f'[GRAVAMOV({log_id})] 🔍 VERIFICANDO CADASTRO DE VEICULOS: {placa}')
    if placadastrada(idcond, placa):
        print(f'[GRAVAMOV({log_id})] 🔍 Placa {placa} já cadastrada')
    else:
        print(f'[GRAVAMOV({log_id})] 🆕 Placa {placa} NOVA - inserida em semcadastro')

    # Processar mensagens Telegram apenas para movimentos válidos (contav=1)
    if contav == 1:
        # Trata a mensagem para o Telegram
        mensagem_telegram(idcond, direcao, placa)
    else:
        print(f'[GRAVAMOV({log_id})] Contav = 0, sem notificação Telegram')

    return inforec


def tratamentotipo01(inforec):
    #
    # Devolutiva agora ficou mais complexa
    #
    # contav = 0 : Não conta vaga e não muda direção
    # contav = 1 : Conta vaga e não muda direção
    # contav = 2 : Conta vaga e direção é igual a E (entrada)
    # contav = 3 : Conta vaga e direção é igual a S (saída)
    #

    # Extrair dados do registro
    log_heimdall = inforec['log_id']
    placa = inforec['placa']
    cam_id = inforec['camera_id']
    momento = inforec['momento']
    cam_entrada = inforec['cent']
    cam_saida = inforec['csai']
    cam_dup = inforec['cdup']

    # Por padrão, conta a vaga
    contav = 1

    # abrir conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    print(f'[TIPO1({log_heimdall})] Cam:{cam_id} Placa:{placa}')

    # Ler os últimos movimentos
    cursor.execute(
        'SELECT placa, idcam, nowpost, contav, direcao, idcond, idlog FROM movcar ORDER BY nowpost DESC LIMIT 10')
    movimentos = cursor.fetchall()

    # verificar se a placa já foi contabilizada anteriormente
    for movimento in movimentos:
        if movimento['contav'] == 1 and movimento['placa'] == placa:
            tempo_diferenca = abs(momento - movimento['nowpost']).total_seconds()
            if tempo_diferenca < 90:  # Movimento duplicado em 90s
                print(
                    f'[TIPO1({log_heimdall})] ⚠️ DUPLICATA - {placa} já processada há {tempo_diferenca:.1f}s')
                contav = 0  # Não contar esta vaga
                return contav

    # Checar se é camera dupla
    if cam_id == cam_dup:
        cursor.execute('SELECT direcao from movcar where placa = %s AND contav = 1 ORDER BY nowpost DESC LIMIT 1',
                       (placa,))
        retorno = cursor.fetchone()
        if retorno is None:
            contav = 0  # direção = I
            inforec['direcao'] = 'I'
        else:
            ultdir = retorno['direcao']
            if ultdir == 'S':
                contav = 2  # direcao = E
                inforec['direcao'] = 'E'
            elif ultdir == 'E':
                contav = 3  # direcao = S
                inforec['direcao'] = 'S'
            elif ultdir == 'I':
                contav = 0  # direcao = I
                inforec['direcao'] = 'I'
            else:
                contav = 0
        print(f'[TIPO1({log_heimdall})] Cam:{cam_id} Placa:{placa} final (CDUP) contav = {contav}')
    else:
        if cam_id == cam_entrada:
            inforec['direcao'] = 'E'
        elif cam_id == cam_saida:
            inforec['direcao'] = 'S'
        print(
            f'[TIPO1({log_heimdall})] Cam:{cam_id} Placa:{placa} final (E/S) contav = {contav} e direção: {inforec['direcao']}')

    # fechar a conexão com a base de dados
    cursor.close()
    connection.close()

    return contav


def tratamentotipo02(inforec):
    # Colocar valor nas variáveis
    log_heimdall = inforec['log_id']
    placa = inforec['placa']
    cam_id = inforec['camera_id']
    momento = inforec['momento']
    cam_e = inforec['cent']
    cam_s = inforec['csai']
    cam_x = inforec['cetd']
    print(f'[TIPO2({log_heimdall})] = Entrei - placa: {placa}')
    # Inicia com a ideia que o movimento será válido
    contav = 1
    if cam_id in (cam_e, cam_s, cam_x):
        # A câmera é de trabalho
        # ler os últimos movimentos
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            'SELECT nowpost FROM movcar WHERE placa = %s AND contav = 1 ORDER BY nowpost DESC LIMIT 1', (placa,))
        movimento = cursor.fetchone()
        cursor.close()
        connection.close()
        # verifica se teve algum retorno
        print(f'[TIPO2({log_heimdall})] = movimento: {movimento}')
        if movimento:
            tempo_diferenca = abs(momento - movimento['nowpost']).total_seconds()
            if tempo_diferenca < 90:  # Movimento duplicado em 90s
                print(
                    f'[TIPO2({log_heimdall})] ⚠️ DUPLICATA - {placa} já processada há {tempo_diferenca:.1f}s')
                contav = 0  # Não contar esta vaga
                return contav
    else:
        return 0
    return contav


def tratamentotipo03(inforec):
    # Extrair dados do registro
    log_heimdall = inforec['log_id']
    placa = inforec['placa']
    cam_id = inforec['camera_id']
    momento = inforec['momento']
    cam_dup = inforec['cdup']
    # Valida se é a câmera correta
    if cam_id != cam_dup:
        return 0, 'I'  # não é a camera para o tratamento indicado
    # abrir conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    # Ler os últimos 10 movimentos
    cursor.execute('SELECT placa, idcam, nowpost, contav, direcao, idcond, idlog FROM movcar ORDER BY nowpost DESC LIMIT 10')
    movimentos = cursor.fetchall()
    # verificar se a placa já foi contabilizada anteriormente
    for movimento in movimentos:
        if movimento['contav'] == 1 and movimento['placa'] == placa:
            tempo_diferenca = abs(momento - movimento['nowpost']).total_seconds()
            if tempo_diferenca < 90:  # Movimento duplicado em 90s
                return 0, 'I'   # Não contar esta vaga
    # Computar a vaga - verificar a ultima direção
    cursor.execute('SELECT direcao from movcar where placa = %s AND contav = 1 ORDER BY nowpost DESC LIMIT 1',(placa,))
    dir = cursor.fetchone()
    if dir is None:
        return 1, 'I'
    print(f'[TIPO3] A direção do ultimo movimento é {dir}')
    direcao = dir['direcao']
    if direcao == 'E':
        return 1, 'S'
    elif direcao == 'S':
        return 1, 'E'
    # fim da função
    return 1, 'I'


def gravar_log(log_id, idcond, placa, placalida, momento, cor, corconf, adres, nome_cam, cam_id, id_anl, contav,
               instante, direcao):
    # abrir conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()

    # montar query para gravar na tabela de movimento de carro - log
    query = f"""
            INSERT INTO movcar 
            (idlog, idcond, placa, placalida, nowpost, cor, corconf, ender, nomecam, idcam, idaia, contav, instante, direcao) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
    valor = (
        log_id, idcond, placa, placalida, momento, cor, corconf, adres, nome_cam, cam_id, id_anl, contav, instante,
        direcao)
    cursor.execute(query, valor)
    connection.commit()

    print(f'[GRAVALOG({log_id})] 💾 GRAVADO - {placa} LogID:{log_id} Contav:{contav}')

    # fechar conexão com a base de dados
    cursor.close()
    connection.close()

    return


def identificar_condominio(numerocondominio):
    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()

    # localizar o código do condomínio na base de dados
    idcond = 0
    vlr = numerocondominio
    qry = f"SELECT idcond FROM cadcond WHERE nrcond = {vlr}"
    cursor.execute(qry)
    resultadoquery = cursor.fetchall()
    qtdlin = cursor.rowcount

    # fechar a conexão com a base de dados
    connection.close()

    # tratando o resultado da query
    if qtdlin == 1:
        idcond = resultadoquery[0][0]
    return idcond


# --------------------------------------------------------------------------------------------
#
# funcões de banco de dados de cadastro
#
def obter_marcas():
    conn = get_db_connection()
    if not conn:
        print('[OBTERMARCAS] Banco de dados não conectou!')
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
        print('[OBTERMARCAS] Problemas para localizar nome da marca no cadastro de marcas')
        return None

    finally:
        cursor.close()
        conn.close()


def obter_idmarca(nomemarca):
    conn = get_db_connection()
    if not conn:
        print('[OBTERIDMARCAS] Banco de dados não conectou!')
        return None

    cursor = conn.cursor()

    qry1 = 'SELECT idmarca FROM cadmarca WHERE nmmarca = %s'

    cursor.execute(qry1, (nomemarca,))
    rst = cursor.fetchall()

    linhas_id_marca = cursor.rowcount
    if linhas_id_marca == 0:
        return None

    cursor.close()
    return rst[0]


def obter_modelos(marca):
    idmarca = obter_idmarca(marca)
    if idmarca is None:
        return None

    conn = get_db_connection()
    if not conn:
        print('[OBTERMODELO] Banco de dados não conectou!')
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
        print(f'[OBTERMODELO] Erro ao buscar modelos: {e}')
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
        print('[OBTERCORES] Banco de dados não conectou!')
        return None

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT idcor, nmcor FROM vw_cor ORDER BY nmcor")
        cores = cursor.fetchall()
        return cores
    except Exception as e:
        print(f'[OBTERCORES] Erro ao buscar cores: {e}')
        return None
    finally:
        cursor.close()
        conn.close()


def mensagem_telegram(idcond, direcao, placa):
    """
    Atualiza contagem de vagas e verifica se deve enviar notificações
    """

    print(f'[TELEGRAM({placa})] Check de envio de mensagem:Direção: {direcao}')

    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()

    # pegar a unidade do véiculo e a situação da permissão
    cursor.execute('''
        SELECT unidade, status_permissao 
        FROM vw_autorizacoes 
        WHERE idcond = %s AND placa = %s
        ORDER BY placa ASC, rank_permissao ASC, idperm DESC 
        LIMIT 1;
        ''', (idcond, placa))
    retorno_vigencia = cursor.fetchone()
    if retorno_vigencia is not None:
        vigencia = retorno_vigencia[1]
        unidade = retorno_vigencia[0]
    else:
        vigencia = 'S/I'
        unidade = 'N/A'

    print(f'[TELEGRAM({placa})] Placa:{placa};Direção:{direcao};Unid:{unidade};Vig:{vigencia}')

    # Pegar quantidade de vagas realmente ocupadas
    cursor.execute('SELECT estacionados, placas FROM vw_estacionados WHERE idcond = %s AND unidade = %s',
                   (idcond, unidade))
    linhalida = cursor.fetchone()
    if linhalida:
        qtdfinal = linhalida[0]
        carrosdentro = linhalida[1]
    else:
        qtdfinal = 0
        carrosdentro = "."

    print(f'[TELEGRAM({placa})] Vagas ocupadas: {qtdfinal} e Carros Estacionados: {carrosdentro}')

    # Pegar quantidade permitida
    cursor.execute('SELECT vperm FROM vagasunidades WHERE idcond = %s AND unidade = %s', (idcond, unidade))
    resultado_permitidas = cursor.fetchone()
    qtdpermitida = int(resultado_permitidas[0]) if resultado_permitidas else 1

    print(f'[TELEGRAM({placa})] Vagas Permitidas: {qtdpermitida}')

    # checa o status - só envia mensagem em caso de excesso
    enviarmensagemvagas = False
    if qtdfinal > qtdpermitida:
        enviarmensagemvagas = True
        textopadrao2 = "Vagas excedidas: "
        textopadrao5 = f' - Veículos estacionados: {carrosdentro}'
    elif qtdfinal == qtdpermitida:
        textopadrao2 = "Vagas completas: "
        textopadrao5 = ''
    else:
        textopadrao2 = "Vagas disponíveis: "
        textopadrao5 = ''

    # checa a vigência - só envia se vencida
    enviarmensagemvigencia = True if direcao == 'E' and vigencia in ('VENCIDA', 'S/I') else False

    enviarmensagem = True if enviarmensagemvagas or enviarmensagemvigencia else False

    if enviarmensagem:
        # Pegar nome do condomínio
        cursor.execute("SELECT nmcond FROM cadcond WHERE idcond = %s", (idcond,))
        resultado_nome = cursor.fetchone()
        nomecond = resultado_nome[0] if resultado_nome else f"Condomínio {idcond}"

        # pega informações de envio de mensagem
        cursor.execute("SELECT * FROM cadmensagem WHERE idcond = %s AND tipomensagem = %s", (idcond, 1))
        vmsg = cursor.fetchone()

        if enviarmensagemvagas:
            print('[TELEGRAM({placa})] Envia mensagem de excesso de vagas')
            # montar texto da mensagem
            textopadrao1 = "ParkVision informa: "
            textopadrao3 = f"Condomínio: {nomecond} - Unidade: {unidade} - Permitidas: {qtdpermitida} - Ocupadas: {qtdfinal} - Placa: {placa} ("
            textopadrao4 = "Entrada)" if direcao == 'E' else "Saída)"

            msgtxt = f"{textopadrao1}{textopadrao2}{textopadrao3}{textopadrao4}{textopadrao5}"
            try:
                status_mensagem = enviar_mensagem_telegram(vmsg[3], vmsg[4], msgtxt)
                print(f'[TELEGRAM({placa})] Status envio Telegram (Excesso): {status_mensagem}')
            except Exception as e:
                print(f'[TELEGRAM({placa})] Erro ao enviar mensagem Telegram (Excesso): {e}')

        if enviarmensagemvigencia:
            print(f'[TELEGRAM({placa})] Envia mensagem de permissão vencida')
            # Formatar texto da mensagem
            if vigencia == 'VENCIDA':
                msgvigencia = f"ParkVision informa: Condomínio: {nomecond} - Veículo {placa} entrou com permissão vencida, referente a unidade {unidade}"
            else:
                msgvigencia = f"ParkVision informa:  Condomínio: {nomecond} - Veículo {placa} entrou sem permissão cadastrada, referente a unidade {unidade}"
            try:
                status_mensagem = enviar_mensagem_telegram(vmsg[3], vmsg[4], msgvigencia)
                print(f'[TELEGRAM({placa})] Status envio Telegram (Vigência): {status_mensagem}')
            except Exception as e:
                print(f'[TELEGRAM({placa})] Erro ao enviar mensagem Telegram (Vigência): {e}')

    # fechar conexão com a base de dados
    connection.close()

    return


def placadastrada(cond, pplaca):
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
    cursor.close()
    connection.close()
    return resultadoconsulta