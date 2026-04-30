import logging
from flask import jsonify, request
from visionlib.dblib import gravar_movimento

logger = logging.getLogger(__name__)

def receber_dados():
    try:
        # Receber o JSON enviado pelo sistema
        dados = request.get_json()

        # Processar os dados e gravar no banco de dados
        dadosdic = gravar_movimento(dados)
        logger.info(f"Fim do Ciclo de Gravação - Placa: {dadosdic.get('placa','NA')}/{dadosdic.get('placalida','NA')} - IdCamera: {dadosdic.get('camera_id','NA')}")

        # Retornar confirmação
        return jsonify({'status': 'sucesso', 'mensagem': 'Dados recebidos'}), 200

    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 400
