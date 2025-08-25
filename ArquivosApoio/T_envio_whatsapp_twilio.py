from twilio.rest import Client


def enviar_whatsapp(numero_destino, mensagem):
    """
  Envia mensagem WhatsApp via Twilio

  Args:
      numero_destino (str): Número no formato +5511999999999
      mensagem (str): Texto da mensagem

  Returns:
      dict: {'sucesso': True/False, 'sid': 'message_id' ou 'erro': 'descrição_erro'}

    # Suas credenciais Twilio
    ACCOUNT_SID = 'AC444a17c13f4dc86afe7dd00bedafcd00'
    AUTH_TOKEN = 'ee02ebc156f456ad8ce6e46ba3a24bbd'
    WHATSAPP_NUMBER = 'whatsapp:+14155238886'  # Número do sandbox

    try:
        # Criar cliente Twilio
        client = Client(ACCOUNT_SID, AUTH_TOKEN)

        # Enviar mensagem
        message = client.messages.create(
            body=mensagem,
            from_=WHATSAPP_NUMBER,
            to=f'whatsapp:{numero_destino}'
        )

        return {
            'sucesso': True,
            'sid': message.sid,
            'status': message.status
        }

    except Exception as e:
        return {
            'sucesso': False,
            'erro': str(e)
        }