import bcrypt
import secrets
import mysql.connector
import logging
from datetime import datetime, timedelta
from config.database import get_db_connection
from flask import jsonify, request, session
import re

logger = logging.getLogger(__name__)


def hash_senha(senha):
    """Gera hash bcrypt da senha"""
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verificar_senha(senha, hash_armazenado):
    """Verifica se a senha corresponde ao hash"""
    return bcrypt.checkpw(senha.encode('utf-8'), hash_armazenado.encode('utf-8'))


def validar_email(email):
    """Valida formato do email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validar_senha_forte(senha):
    """
    Valida se a senha atende aos critérios de segurança:
    - Mínimo 8 caracteres
    - Pelo menos uma letra maiúscula
    - Pelo menos uma letra minúscula
    - Pelo menos um número
    - Pelo menos um caractere especial
    """
    if len(senha) < 8:
        return False, "Senha deve ter no mínimo 8 caracteres"
    
    if not re.search(r'[A-Z]', senha):
        return False, "Senha deve conter pelo menos uma letra maiúscula"
    
    if not re.search(r'[a-z]', senha):
        return False, "Senha deve conter pelo menos uma letra minúscula"
    
    if not re.search(r'\d', senha):
        return False, "Senha deve conter pelo menos um número"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', senha):
        return False, "Senha deve conter pelo menos um caractere especial"
    
    return True, "Senha válida"


def login_usuario(email, senha):
    """
    Realiza login do usuário
    Retorna: dict com informações do usuário ou None se falhou
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar usuário por email
        cursor.execute("""
            SELECT idgente, nome_completo, nome_curto, email, tipo_usuario, 
                   senha_hash, ativo
            FROM usuarios 
            WHERE email = %s AND ativo = TRUE
        """, (email,))
        
        usuario = cursor.fetchone()
        
        if not usuario:
            return None
        
        # Verificar senha
        if not verificar_senha(senha, usuario['senha_hash']):
            return None
        
        # Buscar condomínios permitidos
        cursor.execute("""
            SELECT uc.idcond, c.nmcond 
            FROM usuario_condominios uc
            INNER JOIN cadcond c ON uc.idcond = c.idcond
            WHERE uc.idgente = %s
        """, (usuario['idgente'],))
        
        condominios = cursor.fetchall()
        
        # Registrar login no log
        registrar_log_usuario(usuario['idgente'], 'LOGIN', 'Login realizado com sucesso')
        
        # Preparar dados do usuário para sessão
        usuario_sessao = {
            'idgente': usuario['idgente'],
            'nome_completo': usuario['nome_completo'],
            'nome_curto': usuario['nome_curto'],
            'email': usuario['email'],
            'tipo_usuario': usuario['tipo_usuario'],
            'condominios': condominios
        }
        
        return usuario_sessao
        
    except mysql.connector.Error as err:
        logger.error(f"Erro no login: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def obter_usuario_atual():
    """
    Obtém dados do usuário da sessão atual
    Retorna: dict com dados do usuário ou None
    """
    if 'usuario' not in session:
        return None
    
    return session['usuario']


def verificar_autenticacao_usuario():
    """
    Verifica se usuário está autenticado
    Retorna: (bool autenticado, dict usuario_dados)
    """
    usuario = obter_usuario_atual()
    if usuario:
        return True, usuario
    return False, None


def verificar_permissao_condominio(idcond):
    """
    Verifica se o usuário atual tem permissão para acessar o condomínio
    Retorna: bool
    """
    autenticado, usuario = verificar_autenticacao_usuario()
    
    if not autenticado:
        return False
    
    # ADM tem acesso a todos os condomínios
    if usuario['tipo_usuario'] == 'ADM':
        return True
    
    # Verificar se o condomínio está na lista de permissões do usuário
    condominios_permitidos = [c['idcond'] for c in usuario['condominios']]
    return int(idcond) in condominios_permitidos


def verificar_permissao_tipo_usuario(tipos_permitidos):
    """
    Verifica se o tipo do usuário atual está na lista de tipos permitidos
    Parâmetros: tipos_permitidos (lista de strings: ['ADM', 'MONITOR', 'SINDICO'])
    Retorna: bool
    """
    autenticado, usuario = verificar_autenticacao_usuario()
    
    if not autenticado:
        return False
    
    return usuario['tipo_usuario'] in tipos_permitidos


def gerar_token_recuperacao(email):
    """
    Gera token para recuperação de senha
    Retorna: token string ou None se email não encontrado
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    try:
        # Verificar se email existe
        cursor.execute("SELECT idgente FROM usuarios WHERE email = %s AND ativo = TRUE", (email,))
        usuario = cursor.fetchone()
        
        if not usuario:
            return None
        
        idgente = usuario[0]
        token = secrets.token_urlsafe(32)
        expira_em = datetime.now() + timedelta(hours=24)  # Token válido por 24 horas
        
        # Inserir token
        cursor.execute("""
            INSERT INTO tokens_recuperacao (idgente, token, expira_em)
            VALUES (%s, %s, %s)
        """, (idgente, token, expira_em))
        
        conn.commit()
        
        registrar_log_usuario(idgente, 'TOKEN_RECUPERACAO', 'Token de recuperação gerado')
        
        return token
        
    except mysql.connector.Error as err:
        logger.error(f"Erro ao gerar token: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def recuperar_senha_com_token(token, nova_senha):
    """
    Recupera senha usando token
    Retorna: bool success
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        # Validar nova senha
        senha_valida, mensagem = validar_senha_forte(nova_senha)
        if not senha_valida:
            return False
        
        # Verificar token
        cursor.execute("""
            SELECT t.idgente FROM tokens_recuperacao t
            WHERE t.token = %s AND t.expira_em > NOW() AND t.usado = FALSE
        """, (token,))
        
        resultado = cursor.fetchone()
        if not resultado:
            return False
        
        idgente = resultado[0]
        
        # Atualizar senha
        nova_senha_hash = hash_senha(nova_senha)
        cursor.execute("""
            UPDATE usuarios SET senha_hash = %s, lup = NOW()
            WHERE idgente = %s
        """, (nova_senha_hash, idgente))
        
        # Marcar token como usado
        cursor.execute("""
            UPDATE tokens_recuperacao SET usado = TRUE
            WHERE token = %s
        """, (token,))
        
        conn.commit()
        
        registrar_log_usuario(idgente, 'RECUPERACAO_SENHA', 'Senha alterada via token')
        
        return True
        
    except mysql.connector.Error as err:
        logger.error(f"Erro na recuperação: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def alterar_senha(idgente, senha_atual, nova_senha):
    """
    Altera senha do usuário (requer senha atual)
    Retorna: (bool success, string mensagem)
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        # Validar nova senha
        senha_valida, mensagem = validar_senha_forte(nova_senha)
        if not senha_valida:
            return False, mensagem
        
        # Verificar senha atual
        cursor.execute("SELECT senha_hash FROM usuarios WHERE idgente = %s", (idgente,))
        resultado = cursor.fetchone()
        
        if not resultado or not verificar_senha(senha_atual, resultado[0]):
            return False, "Senha atual incorreta"
        
        # Atualizar senha
        nova_senha_hash = hash_senha(nova_senha)
        cursor.execute("""
            UPDATE usuarios SET senha_hash = %s, lup = NOW()
            WHERE idgente = %s
        """, (nova_senha_hash, idgente))
        
        conn.commit()
        
        registrar_log_usuario(idgente, 'ALTERACAO_SENHA', 'Senha alterada pelo usuário')
        
        return True, "Senha alterada com sucesso"
        
    except mysql.connector.Error as err:
        logger.error(f"Erro ao alterar senha: {err}")
        conn.rollback()
        return False, "Erro interno do sistema"
    finally:
        cursor.close()
        conn.close()


def registrar_log_usuario(idgente, acao, detalhes=None):
    """
    Registra ação do usuário no log de auditoria
    """
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    try:
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
        user_agent = request.environ.get('HTTP_USER_AGENT', '')
        
        cursor.execute("""
            INSERT INTO log_usuarios (idgente, acao, detalhes, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s)
        """, (idgente, acao, detalhes, ip_address, user_agent))
        
        conn.commit()
        
    except mysql.connector.Error as err:
        logger.error(f"Erro ao registrar log: {err}")
    finally:
        cursor.close()
        conn.close()


def logout_usuario():
    """
    Realiza logout do usuário
    """
    usuario = obter_usuario_atual()
    if usuario:
        registrar_log_usuario(usuario['idgente'], 'LOGOUT', 'Logout realizado')
    
    session.clear()
    return True


# APIs Flask para autenticação

def api_login():
    """API para login de usuário"""
    data = request.json
    email = data.get('email', '').strip().lower()
    senha = data.get('senha', '')
    
    if not email or not senha:
        return jsonify({'success': False, 'message': 'Email e senha são obrigatórios'})
    
    if not validar_email(email):
        return jsonify({'success': False, 'message': 'Formato de email inválido'})
    
    usuario = login_usuario(email, senha)
    
    if usuario:
        session.permanent = True  # Tornar sessão permanente
        session['usuario'] = usuario
        session['autenticado'] = True  # Compatibilidade com sistema antigo
        return jsonify({
            'success': True, 
            'message': 'Login realizado com sucesso',
            'usuario': {
                'nome_curto': usuario['nome_curto'],
                'tipo_usuario': usuario['tipo_usuario']
            }
        })
    else:
        return jsonify({'success': False, 'message': 'Email ou senha incorretos'})


def api_logout():
    """API para logout de usuário"""
    logout_usuario()
    return jsonify({'success': True, 'message': 'Logout realizado com sucesso'})


def api_status_autenticacao():
    """API para verificar status de autenticação"""
    autenticado, usuario = verificar_autenticacao_usuario()
    
    if autenticado:
        return jsonify({
            'authenticated': True,
            'usuario': {
                'nome_curto': usuario['nome_curto'],
                'tipo_usuario': usuario['tipo_usuario'],
                'condominios': usuario['condominios']
            }
        })
    else:
        return jsonify({'authenticated': False})


def api_alterar_senha():
    """API para alteração de senha"""
    autenticado, usuario = verificar_autenticacao_usuario()
    
    if not autenticado:
        return jsonify({'success': False, 'message': 'Usuário não autenticado'})
    
    data = request.json
    senha_atual = data.get('senha_atual', '')
    nova_senha = data.get('nova_senha', '')
    
    if not senha_atual or not nova_senha:
        return jsonify({'success': False, 'message': 'Senha atual e nova senha são obrigatórias'})
    
    success, mensagem = alterar_senha(usuario['idgente'], senha_atual, nova_senha)
    
    return jsonify({'success': success, 'message': mensagem})


def api_solicitar_recuperacao():
    """API para solicitar recuperação de senha"""
    data = request.json
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'success': False, 'message': 'Email é obrigatório'})
    
    if not validar_email(email):
        return jsonify({'success': False, 'message': 'Formato de email inválido'})
    
    token = gerar_token_recuperacao(email)
    
    if token:
        # Aqui você implementaria o envio de email com o token
        # Por enquanto, apenas retorna sucesso
        return jsonify({
            'success': True,
            'message': 'Se o email estiver cadastrado, você receberá instruções para recuperação'
        })
    else:
        # Mesmo se o email não existir, retorna sucesso por segurança
        return jsonify({
            'success': True, 
            'message': 'Se o email estiver cadastrado, você receberá instruções para recuperação'
        })


def api_recuperar_senha():
    """API para recuperar senha com token"""
    data = request.json
    token = data.get('token', '')
    nova_senha = data.get('nova_senha', '')
    
    if not token or not nova_senha:
        return jsonify({'success': False, 'message': 'Token e nova senha são obrigatórios'})
    
    success = recuperar_senha_com_token(token, nova_senha)
    
    if success:
        return jsonify({'success': True, 'message': 'Senha alterada com sucesso'})
    else:
        return jsonify({'success': False, 'message': 'Token inválido ou expirado'})