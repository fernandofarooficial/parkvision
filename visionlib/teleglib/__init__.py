import requests
import logging
from config.database import get_db_connection

logger = logging.getLogger(__name__)

def enviar_mensagem_telegram(token, chat_id, mensagem):
    """
    Envia uma mensagem para um grupo do Telegram usando requests

    Args:
        token (str): Token do bot do Telegram
        chat_id (str/int): ID do chat/grupo
        mensagem (str): Mensagem a ser enviada

    Returns:
        bool: True se enviou com sucesso, False caso contrário
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    dados = {
        'chat_id': chat_id,
        'text': mensagem
    }

    try:
        response = requests.post(url, data=dados)

        if response.status_code == 200:
            logger.info("Telegram: mensagem enviada com sucesso")
            return True
        else:
            logger.error(f"Telegram: erro {response.status_code} - {response.text}")
            return False

    except requests.RequestException as e:
        logger.error(f"Telegram: erro de conexão: {e}")
        return False


def teleg_info(cond, tipo = 1):
    # abrindo a conexão com a base de dados
    connection = get_db_connection()
    cursor = connection.cursor()
    # pega informações de envio de mensagem
    cursor.execute("SELECT * FROM cadmensagem WHERE idcond = %s AND tipomensagem = %s", (cond, tipo))
    vmsg = cursor.fetchone()
    #
    cursor.close()
    connection.close()
    #
    return vmsg[3], vmsg[4]


def teleg_sem_vaga(irec):
    token, chat_id = teleg_info(irec['idcond'])
    motivo = f"Sem vagas disponíveis: Permitidas: {irec['vagas_permitidas']} - "
    motivo += f"Ocupadas: {irec['qtde_estacionada']} ({irec['placas_estacionadas']})."
    msg = f"ParkVision informa: {irec['nome_condominio']} - Placa: {irec['placa']}: não autorizada. {motivo}"
    enviar_mensagem_telegram(token, chat_id, msg)
    return


def teleg_veiculo_nao_autorizado(irec):
    token, chat_id = teleg_info(irec['idcond'])
    motivo = "Sem permissão" if irec['status_permissao'] == "INEXISTENTE" else 'Permissão vencida.'
    msg = f"ParkVision informa: {irec['nome_condominio']} - Placa: {irec['placa']}: não autorizada. {motivo}"
    enviar_mensagem_telegram(token, chat_id, msg)
    return


def teleg_veiculo_ok(irec):
    token, chat_id = teleg_info(irec['idcond'])
    direcao = 'Saída' if irec['direcao'] == 'S' else 'Entrada'
    msg = f"ParkVision informa: {irec['nome_condominio']} - Placa: {irec['placa']}: {direcao}"
    enviar_mensagem_telegram(token, chat_id, msg)
    return


def teleg_placa_nao_cadastrada(irec):
    token, chat_id = teleg_info(irec['idcond'])
    msg = f"ParkVision informa: {irec['nome_condominio']} - Placa: {irec['placa']} não cadastrada!"
    enviar_mensagem_telegram(token, chat_id, msg)
    return


def teleg_acao_operador(irec):
    """
    Envia notificação Telegram para exceções tratadas pelo operador.

    statusmov esperados:
        B — entrada recusada (veículo com permissão válida)
        C — entrada confirmada, veículo sem cadastro
        E — entrada confirmada, sem permissão válida
        J — saída de veículo não cadastrado
    """
    try:
        token, chat_id = teleg_info(irec['idcond'])
    except Exception:
        return
    if not token or not chat_id:
        return

    statusmov = irec.get('statusmov', '')
    placa     = irec.get('placa', 'N/I')
    marca     = irec.get('marca', 'Não cadastrado')
    modelo    = irec.get('modelo', 'Não cadastrado')
    cor       = irec.get('cor', 'Não cadastrado')
    unidade   = irec.get('unidade')
    nmcond    = irec.get('nmcond', '')
    motivo    = irec.get('motivo') or 'Não informado'

    titulos = {
        'B': '🚫 Entrada Recusada pelo Operador',
        'C': '⚠️ Entrada Autorizada — Veículo Não Cadastrado',
        'E': '⚠️ Entrada Autorizada — Sem Permissão',
        'J': '⚠️ Saída de Veículo Não Cadastrado',
    }
    situacoes = {
        'B': 'Veículo com permissão válida teve entrada recusada pelo operador',
        'C': 'Operador autorizou entrada de veículo não cadastrado no sistema',
        'E': 'Operador autorizou entrada de veículo sem permissão válida',
        'J': 'Veículo não cadastrado no sistema registrou saída',
    }

    titulo   = titulos.get(statusmov, f'Ação do Operador ({statusmov})')
    situacao = situacoes.get(statusmov, '')

    linhas = [
        f'ParkVision — {titulo}',
        f'Condomínio: {nmcond}',
        f'Situação: {situacao}',
        '',
        '🚗 Veículo',
        f'Placa: {placa}',
    ]

    if marca != 'Não cadastrado' or modelo != 'Não cadastrado':
        linhas.append(f'Marca / Modelo: {marca} {modelo}'.strip())
    if cor != 'Não cadastrado':
        linhas.append(f'Cor: {cor}')

    if unidade:
        linhas += ['', f'🏠 Unidade: {unidade}']

    linhas += ['', f'📝 Motivo: {motivo}']

    enviar_mensagem_telegram(token, chat_id, '\n'.join(linhas))

