import requests
from config.database import get_db_connection

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
            print("✅ Mensagem enviada com sucesso!")
            return True
        else:
            print(f"❌ Erro: {response.status_code} - {response.text}")
            return False

    except requests.RequestException as e:
        print(f"❌ Erro de conexão: {e}")
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

