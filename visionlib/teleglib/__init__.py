import requests


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