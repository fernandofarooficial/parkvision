"""
Middleware para controle de acesso e autorização
Implementa decorators para verificar permissões de usuários
"""

from functools import wraps
from flask import redirect, url_for, jsonify, request
from visionlib.authlib import verificar_autenticacao_usuario, verificar_permissao_condominio, verificar_permissao_tipo_usuario


def requer_autenticacao(redirect_to='login'):
    """
    Decorator que requer usuário autenticado
    Se não autenticado, redireciona para página de login ou retorna JSON error
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            autenticado, usuario = verificar_autenticacao_usuario()
            
            if not autenticado:
                # Se for requisição AJAX/API, retorna JSON
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'success': False, 
                        'message': 'Usuário não autenticado',
                        'error_code': 'UNAUTHORIZED'
                    }), 401
                
                # Se for requisição normal, redireciona para login
                return redirect(url_for(redirect_to))
            
            # Adicionar usuário ao contexto da função
            return f(usuario=usuario, *args, **kwargs)
        
        return decorated_function
    return decorator


def requer_tipo_usuario(tipos_permitidos, redirect_to='login'):
    """
    Decorator que requer tipos específicos de usuário
    Parâmetros: tipos_permitidos (lista): ['ADM', 'MONITOR', 'SINDICO']
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            autenticado, usuario = verificar_autenticacao_usuario()
            
            if not autenticado:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'success': False, 
                        'message': 'Usuário não autenticado',
                        'error_code': 'UNAUTHORIZED'
                    }), 401
                return redirect(url_for(redirect_to))
            
            if not verificar_permissao_tipo_usuario(tipos_permitidos):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'success': False, 
                        'message': 'Acesso negado. Privilégios insuficientes.',
                        'error_code': 'FORBIDDEN'
                    }), 403
                return redirect(url_for('condominios'))  # Redirecionar para área permitida
            
            return f(usuario=usuario, *args, **kwargs)
        
        return decorated_function
    return decorator


def requer_acesso_condominio(obter_id_do_parametro=True, nome_parametro='condominio_id'):
    """
    Decorator que verifica se o usuário tem acesso ao condomínio específico
    Parâmetros:
    - obter_id_do_parametro: Se True, obtém o ID do parâmetro da URL
    - nome_parametro: Nome do parâmetro que contém o ID do condomínio
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            autenticado, usuario = verificar_autenticacao_usuario()
            
            if not autenticado:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'success': False, 
                        'message': 'Usuário não autenticado',
                        'error_code': 'UNAUTHORIZED'
                    }), 401
                return redirect(url_for('login'))
            
            # Obter ID do condomínio
            if obter_id_do_parametro:
                condominio_id = kwargs.get(nome_parametro)
                if not condominio_id:
                    if request.is_json or request.path.startswith('/api/'):
                        return jsonify({
                            'success': False, 
                            'message': 'ID do condomínio não fornecido',
                            'error_code': 'BAD_REQUEST'
                        }), 400
                    return redirect(url_for('condominios'))
            else:
                # Buscar ID do condomínio em outro local (body, query params, etc.)
                condominio_id = request.json.get('condominio_id') if request.is_json else request.args.get('condominio_id')
                if not condominio_id:
                    if request.is_json or request.path.startswith('/api/'):
                        return jsonify({
                            'success': False, 
                            'message': 'ID do condomínio não fornecido',
                            'error_code': 'BAD_REQUEST'
                        }), 400
                    return redirect(url_for('condominios'))
            
            # Verificar permissão
            if not verificar_permissao_condominio(condominio_id):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'success': False, 
                        'message': 'Acesso negado a este condomínio',
                        'error_code': 'FORBIDDEN'
                    }), 403
                return redirect(url_for('condominios'))
            
            return f(usuario=usuario, *args, **kwargs)
        
        return decorated_function
    return decorator


def requer_admin(redirect_to='login'):
    """
    Decorator específico para funcionalidades administrativas
    Atalho para requer_tipo_usuario(['ADM'])
    """
    return requer_tipo_usuario(['ADM'], redirect_to)


def requer_monitor_ou_admin(redirect_to='login'):
    """
    Decorator para funcionalidades que requerem MONITOR ou ADM
    """
    return requer_tipo_usuario(['ADM', 'MONITOR'], redirect_to)


def api_requer_autenticacao(f):
    """
    Decorator específico para APIs que sempre retorna JSON
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        autenticado, usuario = verificar_autenticacao_usuario()
        
        if not autenticado:
            return jsonify({
                'success': False, 
                'message': 'Token de autenticação inválido ou expirado',
                'error_code': 'UNAUTHORIZED'
            }), 401
        
        return f(usuario=usuario, *args, **kwargs)
    
    return decorated_function


def api_requer_admin(f):
    """
    Decorator específico para APIs administrativas
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        autenticado, usuario = verificar_autenticacao_usuario()
        
        if not autenticado:
            return jsonify({
                'success': False, 
                'message': 'Token de autenticação inválido ou expirado',
                'error_code': 'UNAUTHORIZED'
            }), 401
        
        if not verificar_permissao_tipo_usuario(['ADM']):
            return jsonify({
                'success': False, 
                'message': 'Acesso restrito a administradores',
                'error_code': 'FORBIDDEN'
            }), 403
        
        return f(usuario=usuario, *args, **kwargs)
    
    return decorated_function


def rate_limit_por_usuario(max_requests=60, window_minutes=1):
    """
    Decorator para implementar rate limiting por usuário
    NOTA: Implementação básica usando sessão. Para produção, usar Redis ou similar.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from datetime import datetime, timedelta
            from flask import session
            
            # Obter identificador do usuário
            autenticado, usuario = verificar_autenticacao_usuario()
            if not autenticado:
                user_id = request.environ.get('REMOTE_ADDR', 'anonymous')
            else:
                user_id = f"user_{usuario['idgente']}"
            
            # Verificar rate limit (implementação simples)
            now = datetime.now()
            rate_limit_key = f"rate_limit_{user_id}"
            
            if rate_limit_key in session:
                requests_data = session[rate_limit_key]
                window_start = datetime.fromisoformat(requests_data['window_start'])
                
                # Se passou da janela de tempo, resetar contador
                if now > window_start + timedelta(minutes=window_minutes):
                    session[rate_limit_key] = {
                        'count': 1,
                        'window_start': now.isoformat()
                    }
                else:
                    # Incrementar contador
                    requests_data['count'] += 1
                    if requests_data['count'] > max_requests:
                        return jsonify({
                            'success': False, 
                            'message': f'Muitas requisições. Limite: {max_requests} por {window_minutes} minuto(s)',
                            'error_code': 'RATE_LIMIT_EXCEEDED'
                        }), 429
                    session[rate_limit_key] = requests_data
            else:
                # Primeira requisição na janela
                session[rate_limit_key] = {
                    'count': 1,
                    'window_start': now.isoformat()
                }
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# Decorators de conveniência para casos comuns

def pagina_admin(f):
    """Decorator para páginas administrativas"""
    return requer_admin()(f)


def pagina_autenticada(f):
    """Decorator para páginas que requerem login"""
    return requer_autenticacao()(f)


def api_admin(f):
    """Decorator para APIs administrativas"""
    return api_requer_admin(f)


def api_autenticada(f):
    """Decorator para APIs que requerem autenticação"""
    return api_requer_autenticacao(f)


# Exemplo de uso dos decorators:
"""
from visionlib.middleware import pagina_admin, api_admin, requer_acesso_condominio

# Página administrativa
@app.route('/admin/usuarios')
@pagina_admin
def admin_usuarios(usuario):
    # usuario já está disponível como parâmetro
    return render_template('admin-usuarios.html')

# API administrativa  
@app.route('/api/admin/usuarios', methods=['GET'])
@api_admin
def api_admin_usuarios(usuario):
    # usuario já está disponível como parâmetro
    return listar_usuarios()

# Página que requer acesso a condomínio específico
@app.route('/veiculos/<int:condominio_id>')
@requer_acesso_condominio()
def veiculos(usuario, condominio_id):
    return render_template('veiculos.html')

# API com rate limiting
@app.route('/api/data')
@rate_limit_por_usuario(max_requests=100, window_minutes=5)
@api_autenticada
def api_data(usuario):
    return jsonify({'data': 'sensitive_data'})
"""