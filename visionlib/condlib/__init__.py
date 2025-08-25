import mysql.connector
import globals
from config.database import get_db_connection
from flask import jsonify, session, request
from globals import verificar_autenticacao


# API para autenticação
# @app.route('/api/auth/login', methods=['POST'])
def condominio_login():
    data = request.json
    condominio_id = data.get('condominio_id')
    senha = data.get('senha')

    print(f'Cond_id: {condominio_id} -- Senha: {senha}')

    if condominio_id in globals.CONDOMINIO_SENHAS and globals.CONDOMINIO_SENHAS[condominio_id] == senha:
        session['autenticado'] = True
        session['condominio_id'] = condominio_id
        return jsonify({'success': True, 'message': 'Login realizado com sucesso'})
    else:
        return jsonify({'success': False, 'message': 'Credenciais inválidas'})

# API para obter lista de condomínios
# Referências no programa principal
# @app.route('/api/condominios')
# def api_condominios():
def lista_condominios():

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT idcond, nmcond, nrcond FROM cadcond")
        condominios = cursor.fetchall()
        return jsonify({'success': True, 'data': condominios})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao consultar condomínios: {err}'})
    finally:
        cursor.close()
        conn.close()

# API para obter dados do condomínio
# Referências no programa principal
# @app.route('/api/condominio/<int:condominio_id>')
# def api_condominio(condominio_id):
def obter_dados_condminios(condominio_id):
    # Autenticação agora é feita nas rotas principais do main.py
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Erro ao conectar ao banco de dados'})

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT idcond, nmcond FROM cadcond WHERE idcond = %s", (condominio_id,))
        condominio = cursor.fetchone()

        if not condominio:
            return jsonify({'success': False, 'message': 'Condomínio não encontrado'})

        return jsonify({'success': True, 'data': condominio})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erro ao consultar condomínio: {err}'})
    finally:
        cursor.close()
        conn.close()
