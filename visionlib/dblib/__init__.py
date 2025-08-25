# --------------------
# DBLIB
# --------------------

from flask import jsonify
from datetime import datetime
import globals
from config.database import get_db_connection
from visionlib.vplib import process_heimdall_plate
from visionlib.teleglib import enviar_mensagem_telegram


def get_last_ten_records():
    """Busca as 10 últimas linhas da tabela"""

    # Query para pegar as 10 últimas linhas
    query = f"""
    SELECT 
        t1.placa as Veiculo, 
        cc.nmcond as Condominio,
        ce.nmemp as Empresa,
        MAX(t1.nowpost) as Ultima,
        (SELECT nowpost 
         FROM movcar t2 
         WHERE t2.placa = t1.placa 
           AND t2.nowpost < MAX(t1.nowpost)
           AND t2.idcond = 1
         ORDER BY nowpost DESC 
         LIMIT 1) as Penultima
    FROM movcar t1
    INNER JOIN cadcond cc ON t1.idcond = cc.idcond
    INNER JOIN cademp ce ON cc.idemp = ce.idemp
    WHERE t1.idcond = 1
    GROUP BY t1.placa, t1.idcond, cc.nmcond, ce.nmemp
    ORDER BY Ultima DESC
    LIMIT 10;
    """

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query)
    records = cursor.fetchall()
    connection.close()

    # Converter datetime para string se necessário
    for record in records:
        for key, value in record.items():
            if isinstance(value, datetime):
                record[key] = value.strftime('%Y-%m-%d %H:%M:%S')

    return records


def gravar_movimento(movdic):
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

    # Exibir inicio do ciclo de gravação
    print(f'Início do ciclo de gravação - IdCam:{cam_id} - PlacaLida:{placalida} - Instante:{instante}')

    # localizar o código do condomínio
    numerocondominio = int(nome_cam[:4])
    idcond = identificar_condominio(numerocondominio)
    if idcond == 0:
        print(f'Condomínio não cadastrado: {nome_cam}')
        return
    inforec['idcond'] = idcond

    # apontar a direção e o tipo de tratamento
    tipotratamento = 0
    direcao = 'I'
    pulacadastrocarros = True
    for dad_cond in globals.cvag:
        if dad_cond['idcond'] == idcond:
            pulacadastrocarros = False
            tipotratamento = dad_cond['tipo']
            if cam_id == dad_cond['cent']:
                direcao = 'E'
            elif cam_id == dad_cond['csai']:
                direcao = 'S'
            elif cam_id == dad_cond['cdup']:
                direcao = 'I'
            inforec['cent'] = dad_cond['cent']
            inforec['csai'] = dad_cond['csai']
            inforec['cdup'] = dad_cond['cdup']
            break
    inforec['direcao'] = direcao
    inforec['tipotratamento'] = tipotratamento

    # validação da placa
    verifica_placa = process_heimdall_plate(placalida, idcond, 0.8, pulacadastrocarros)
    placa = verifica_placa['corrected_plate']
    inforec['placa'] = placa
    if not verifica_placa['found_match']:
        placa = '*ERROR*'
        print(f'Placa {placalida} inconsistente e não será contabilizada!')
        contav = 0
        inforec['contav'] = 0
        gravar_log(log_id, idcond, placa, placalida, momento, cor, corconf, adres, nome_cam, cam_id, id_anl, contav,
                   instante, direcao)
        return inforec

    # Direcionar para o tipo de tratamento corrto
    if tipotratamento == 1:
        contav = tratamentotipo01(inforec)
    elif tipotratamento == 2:
        contav = tratamentotipo02(inforec)
    elif tipotratamento == 3:
        contav = tratamentotipo03(inforec)
    elif tipotratamento == 0:
        contav = 1
    inforec['contav'] = contav

    # gravar o log
    gravar_log(log_id, idcond, placa, placalida, momento, cor, corconf, adres, nome_cam, cam_id, id_anl, contav,
               instante, direcao)

    return inforec


def tratamentotipo01(inforec):
    # Colocar valor nas variáveis
    placa = inforec['placa']
    cam_id = inforec['camera_id']
    momento = inforec['momento']
    cam_e = inforec['cent']
    cam_s = inforec['csai']
    # ainda não foi desenvolvido o tratamebto da cdup no tipo 1
    cam_d = inforec['cdup']
    # Administrar o movimento anterior
    contav = 0
    if cam_id in (cam_e, cam_s):
        diftime = abs(momento - globals.lastmov[2]).total_seconds()
        contarvaga = False
        if placa != globals.lastmov[0]:
            contarvaga = True
        else:
            if diftime > 59:
                contarvaga = True
        if contarvaga:
            controle_vagas_piloto(inforec)
            globals.lastmov = [placa, cam_id, momento]
            contav = 1
    return contav

def tratamentotipo02(inforec):
    controle_vagas_piloto(inforec)
    return 1

def tratamentotipo03(inforec):
    # Colocar valor nas variáveis
    placa = inforec['placa']
    cam_id = inforec['camera_id']
    momento = inforec['momento']
    cam_e = inforec['cent']
    cam_s = inforec['csai']
    # Administrar o movimento anterior
    contav = 0
    if cam_id in (cam_e, cam_s):
        diftime = abs(momento - globals.lastmov[2]).total_seconds()
        contarvaga = False
        if placa != globals.lastmov[0]:
            contarvaga = True
        else:
            if diftime > 59:
                contarvaga = True
        if contarvaga:
            controle_vagas_piloto(inforec)
            globals.lastmov = [placa, cam_id, momento]
            contav = 1
    return contav

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
    log_id, idcond, placa, placalida, momento, cor, corconf, adres, nome_cam, cam_id, id_anl, contav, instante, direcao)
    cursor.execute(query, valor)
    connection.commit()
    right_now = momento.strftime("%d/%m/%Y %H:%M:%S")

    # fechar conexão com a base de dados
    cursor.close()
    connection.close()

    # atualizar movimentos globais
    globals.m2 = globals.m1
    globals.m1 = globals.m0
    globals.m0 = {'idcond': idcond, 'placa': placa, 'momento:': momento, 'contav': contav,
                  'direcao': direcao, 'camera_id': cam_id, 'log_id': log_id}

    return


def controle_vagas_piloto(ir):
    # Tratamento tipo 1 - Três câmeras diferentes
    # cent: Câmera de entrada
    # csai: Câmera de saída
    # cdup: Cãmera de entrada e saída
    #
    # Tratamento tipo 2 - Uma câmera de entrada e saída
    # cdup: Cãmera de entrada e saída
    #
    # Tratamento tipo 3 - Duas câmeras diferentes
    # cent: Câmera de entrada
    # csai: Câmera de saída
    #
    # carregar variaveis
    placa = ir.get('placa', )
    idcond = ir.get('idcond', )
    idcam = ir.get('camera_id', )
    momento = ir.get('momento')
    instante = ir.get('instante')
    cent = ir.get('cent')
    csai = ir.get('csai')
    cdup = ir.get('cdup')
    tipotratamento = ir.get('tipotratamento')

    # obter a unidade do veículo e validar se o mesmo existe no cadastro
    unidade = obter_unidade(placa, idcond, instante)
    if unidade is None:
        # placa não existe no cadastro de veículos ou permissão está vencida
        print(f'Placa {placa} não existe no cadastro de veículos ou permissão está vencida!')
        return False

    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()

    if tipotratamento == 1:
        # Tipo de tratamento 1
        if idcam == cent:
            # camera de entrada - aloca 1 no campo sit
            intsit = 1  # veiculo entrou - sit = 1
        elif idcam == csai:
            # camera de saída - aloca 0 no campo sit
            intsit = 0  # veículo saiu - sit = 0
    elif tipotratamento == 2:
        # Tipo de tratamento 2
        if idcam != cdup:
            # Verifica se a câmera está consistente com o condomínio
            print(f'Camera {idcam} inconsistente com o condomínio {idcond}!')
            return False
        intsit = 0
    elif tipotratamento == 3:
        # Tipo de tratamento 3
        if idcam == cent:
            # camera de entrada - aloca 1 no campo sit
            intsit = 1  # veiculo entrou - sit = 1
        elif idcam == csai:
            # camera de saída - aloca 0 no campo sit
            intsit = 0  # veículo saiu - sit = 0

    # Atualização do cadastro de localização (cadlocal)
    q = 'SELECT * FROM cadlocal WHERE idcond = %s AND placa = %s AND unidade = %s'
    v = (idcond, placa, unidade)
    cursor.execute(q, v)
    resultados = cursor.fetchall()
    if len(resultados) == 0:
        # se não achou então criar
        q = 'INSERT INTO cadlocal (idcond, placa, unidade, sit) VALUES (%s,%s,%s,%s)'
        v = (idcond, placa, unidade, intsit)
        cursor.execute(q, v)
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected == 0:
            print('Veículo não foi inserido no cadastro de localização!')
    else:
        # Para tratamento tipo 2 = calcular o intsit depois da leitura
        if tipotratamento == 2:
            intsit = 1 if resultados[0][3] == 0 else 0
        # localizou então atualiza
        q = 'UPDATE cadlocal SET sit = %s WHERE idcond = %s AND placa = %s AND unidade = %s'
        v = (intsit, idcond, placa, unidade)
        cursor.execute(q, v)
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected == 0:
            print(f'Falha na atualização do veículo no cadastro de localização!')
            # deletar o registro
            q = 'DELETE FROM cadlocal WHERE idcond = %s AND placa = %s AND unidade = %s'
            v = (idcond, placa, unidade)
            cursor.execute(q, v)
            rows_affected = cursor.rowcount
            connection.commit()
            if rows_affected > 0:
                q = 'INSERT INTO cadlocal (idcond, placa, unidade, sit) VALUES (%s,%s,%s,%s)'
                v = (idcond, placa, unidade, intsit)
                cursor.execute(q, v)
                rows_affected = cursor.rowcount
                connection.commit()
                if rows_affected == 0:
                    print('Falha na reinserção do veiculo no cadastro de localização!')
            else:
                print('Falha na exclusão do veiculo no cadastro de localização!')

    # fechar conexão
    cursor.close()
    connection.close()

    # obter quantas vagas estão ocupadas pela unidade
    # vagasocupadas = obter_vagas_ocupadas(idcond, unidade)
    # if vagasocupadas is None:
    #    print(f'Unidade {unidade} não localizada no cadastro de vagas por unidade')
    #    return

    # atualizar a quantidade de vagas da unidade
    atualizar_quadro_vagas(idcond, unidade, intsit, momento, placa, idcam, instante)

    return True


def atualizar_quadro_vagas(idcond, unidade, intsit, momento, placa, idcam, instante):
    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()

    # Recebendo a quantidade de vagas do cadlocal
    cursor.execute('SELECT SUM(sit) FROM cadlocal WHERE idcond = %s AND unidade = %s', (idcond, unidade))
    qtdfinal = int(cursor.fetchone()[0])
    query = 'UPDATE vagasunidades SET vocup = %s, instante = %s WHERE idcond = %s AND unidade = %s'

    # executando a query e repetindo se der erro de gravação
    naogravou = True
    while naogravou:
        cursor.execute(query, (qtdfinal, instante, idcond, unidade))
        rows_affected = cursor.rowcount
        connection.commit()
        if rows_affected > 0:
            naogravou = False
            # Pegar nome do condomínio
            cursor.execute("SELECT nmcond FROM cadcond WHERE idcond = %s",(idcond,))
            nomecond = cursor.fetchone()[0]
            # Pegar numero de vagas
            cursor.execute('SELECT vperm FROM vagasunidades WHERE idcond = %s AND unidade = %s', (idcond, unidade))
            qtdpermitida = int(cursor.fetchone()[0])
            textopadrao1 = "ParkVision informa: "
            textopadrao3 = f"Condomínio: {nomecond} - Unidade: {unidade} - Permitidas: {qtdpermitida} - Ocupadas: {qtdfinal} - Placa: {placa} ("
            textopadrao4 = "Entrada)" if intsit == 1 else "Saída)"
            if qtdfinal > qtdpermitida:
                textopadrao2 = "Vagas excedidas: "
            elif qtdfinal == qtdpermitida:
                textopadrao2 = "Vagas completas: "
            else:
                textopadrao2 = "Vagas disponíveis: "
            msgtxt = f"{textopadrao1}{textopadrao2}{textopadrao3}{textopadrao4}"
            cursor.execute("SELECT * FROM cadmensagem WHERE idcond = %s AND tipomensagem = %s",(1,1))
            vmsg = cursor.fetchone()
            status_mensagem = enviar_mensagem_telegram(vmsg[3],vmsg[4],msgtxt)
            print(status_mensagem)
        else:
            print(f'Falha na atualização da contagem de vagas, tentamos de novo - {(qtdfinal, idcond, unidade, momento, instante)}')

    # fechar conexão com a base de dados
    connection.close()

    return


def obter_unidade(placa, idcond, instante):
    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()

    # elaborando  e executando a query de consulta
    query = "SELECT unidade FROM vw_veiculos_autorizados WHERE placa = %s AND idcond = %s AND status_permissao <> 'VENCIDA'"
    cursor.execute(query, (placa, idcond))
    resultado = cursor.fetchall()
    ql = cursor.rowcount

    # se a quantidade de linhas for zero, a unidade não existe no cadastro
    if ql == 1:
        connection.close()
        return resultado[0][0]  # Retorna a unidade
    else:
        # Placa não encontrada (com permissão válida)
        # Verificar se existe no cadastro de veículos
        cursor.execute("SELECT placa FROM cadveiculo WHERE placa = %s", (placa,))
        if cursor.rowcount == 0:
            # não achou a placa no cadastro de veiculos então inclui no sem cadastro
            # Incluir nos carros sem cadastro
            query = 'INSERT INTO semcadastro (idcond, placa, instante) VALUES (%s, %s, %s)'
            cursor.execute(query, (idcond, placa, instante))
            connection.commit()
            connection.close()
        return None  # Placa não encontrada


def obter_vagas_ocupadas(idcond, unidade):
    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()

    # elaborando e executando a consulta para ter a quantidade de vagas ocupadas
    query = 'SELECT vocup FROM vagasunidades WHERE unidade = %s AND idcond = %s'
    cursor.execute(query, (unidade, idcond))
    resultado = cursor.fetchone()

    # fechando a conexão com a base de dados
    connection.close()

    # tratando o resultado da query
    if resultado:
        return resultado[0]  # Retorna quantidade de vagas ocupadas
    else:
        return None  # Unidade não encontrada


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


####################################################################

def api_last_ten():
    """Retorna JSON com as últimas 10 linhas"""
    records = get_last_ten_records()

    if not records:
        return jsonify({
            'success': False,
            'message': 'Nenhum registro encontrado ou erro na conexão',
            'data': []
        }), 404

    return jsonify({
        'success': True,
        'message': f'{len(records)} registros encontrados',
        'data': records
    })


def last_ten_page():
    """Página HTML com as últimas 10 linhas"""
    records = get_last_ten_records()

    if not records:
        return '<h1>Erro</h1><p>Nenhum registro encontrado ou erro na conexão</p>'

    # Gerar HTML simples
    html = '<h1>Últimos 10 veículos</h1>'
    html += f'<p>Total de veículos: {len(records)}</p>'
    html += '<table border="1" style="border-collapse: collapse; width: 100%;">'

    # Cabeçalho da tabela
    if records:
        html += '<tr style="background-color: #f2f2f2;">'
        for key in records[0].keys():
            html += f'<th style="padding: 8px;">{key}</th>'
        html += '</tr>'

        # Dados da tabela
        for record in records:
            html += '<tr>'
            for value in record.values():
                html += f'<td style="padding: 8px;">{value}</td>'
            html += '</tr>'

    html += '</table>'
    html += '<br><a href="/">Voltar ao início</a>'

    return html


# --------------------------------------------------------------------------------------------
#
# funcões de banco de dados de cadastro
#
def obter_marcas():
    conn = get_db_connection()
    if not conn:
        print('Banco de dados não conectou!')
        return None

    cursor = conn.cursor(dictionary=True)

    # Tentar buscar marcas da tabela cadmarca, se não existir, usar lista padrão
    try:
        cursor.execute("SELECT DISTINCT nmmarca as marca FROM cadmarca ORDER BY nmmarca")
        marcas = cursor.fetchall()
        if not marcas:
            raise Exception("Tabela vazia")
        return marcas
    except:
        print("Problemas para localizar nome da marca no cadastro de marcas")
        return None

    finally:
        cursor.close()
        conn.close()


def obter_idmarca(nomemarca):

    conn = get_db_connection()
    if not conn:
        print('Banco de dados não conectou!')
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
        print('Banco de dados não conectou!')
        return None

    cursor = conn.cursor(dictionary=True)

    """Versão mais simples da função."""
    try:
        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT DISTINCT nmmodelo as modelo FROM cadmodelo WHERE idmarca = %s ORDER BY modelo"
            cursor.execute(query, (idmarca))
            modelos_lista = cursor.fetchall()
            modelos_formatados = []
            for modelo in modelos_lista:
                modelos_formatados.append(modelo)
            return modelos_formatados
            # return {marca.upper(): modelos_formatados}

    except Exception as e:
        print(f"Erro ao buscar modelos: {e}")
        return []


def inserir_carro(idcond, data):

    placa = data.get('placa')
    marca = data.get('marca')
    modelo = data.get('modelo')
    unidade = data.get('unidade')
    cor = data.get('cor')
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
    if not placa or not marca or not modelo or not unidade or not cor or not data_inicio:
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
        # DETERMINAR SIT CORRETO baseado na última movimentação
        q = 'SELECT direcao FROM movcar WHERE contav = %s AND placa = %s ORDER BY idmov DESC LIMIT 1;'
        v = (1, data['placa'])
        cursor.execute(q, v)
        direcao = cursor.fetchone()
        sit_correto = 1 if direcao[0] == 'E' else 0

        # 1. Inserir em CADVEICULO
        query_veiculo = 'INSERT INTO cadveiculo (placa, idmodelo, cor) VALUES (%s, %s, %s)'
        cursor.execute(query_veiculo, (placa, idmodelo, cor))

        # 2. Inserir em CADLOCAL com sit correto
        query_local = 'INSERT INTO cadlocal (idcond, placa, unidade, sit) VALUES (%s, %s, %s, %s)'
        cursor.execute(query_local, (idcond, placa, unidade, sit_correto))

        # 3. Inserir em CADPERM com dados de permanência
        if tempo_indeterminado:
            query_perm = 'INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim) VALUES (%s, %s, %s, %s, NULL)'
            cursor.execute(query_perm, (idcond, placa, unidade, data_inicio))
        else:
            query_perm = 'INSERT INTO cadperm (idcond, placa, unidade, data_inicio, data_fim) VALUES (%s, %s, %s, %s, %s)'
            cursor.execute(query_perm, (idcond, placa, unidade, data_inicio, data_fim))

        conn.commit()
        rows_affected = cursor.rowcount
        contar_vagas_ocupadas_uma_unidade(idcond,unidade)

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': f'Erro ao cadastrar veículo: {str(e)}'})

    cursor.close()
    conn.close()
    if rows_affected > 0:
        return jsonify({'success': True, 'message': 'Veículo cadastrado com sucesso'})
    else:
        return jsonify({'success': False, 'message': 'Veículo NÃO cadastrado!'})

def contar_vagas_ocupadas_uma_unidade(idcond, unidade):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(sit) FROM cadlocal WHERE idcond = %s AND unidade = %s', (idcond, unidade))
    contagem = cursor.fetchone()[0]
    qtdfinal = contagem if contagem else 0
    query = 'UPDATE vagasunidades SET vocup = %s WHERE idcond = %s AND unidade = %s'
    cursor.execute(query, (qtdfinal, idcond, unidade))
    cursor.close()
    conn.close()
    return


