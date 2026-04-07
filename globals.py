from flask import session
from config.database import get_db_connection

# COMPATIBILIDADE: Função legada para verificar autenticação por condomínio
# DEPRECATED: Usar visionlib.authlib.verificar_autenticacao_usuario() para novas implementações
def verificar_autenticacao():
    """
    Função mantida para compatibilidade com código existente.
    Verifica se há sessão de usuário e retorna o primeiro condomínio permitido como condominio_id.
    Para novo sistema de autenticação, use visionlib.authlib.
    """
    # Verificar se há autenticação do novo sistema
    if 'usuario' in session and session.get('autenticado', False):
        usuario = session['usuario']

        # Para compatibilidade, retorna o primeiro condomínio da lista
        if usuario.get('condominios') and len(usuario['condominios']) > 0:
            primeiro_condominio = usuario['condominios'][0]['idcond']
            return True, primeiro_condominio
        # Se for ADM, retorna True mas sem condomínio específico (acesso total)
        elif usuario.get('tipo_usuario') == 'ADM':
            return True, None
    
    # Verificar sistema antigo para compatibilidade
    if 'autenticado' in session and 'condominio_id' in session:
        return True, session['condominio_id']
    
    return False, None


# Função auxiliar para verificar acesso a condomínio específico
def verificar_acesso_condominio(idcond_requisitado):
    """
    Verifica se o usuário atual tem acesso ao condomínio específico.
    Retorna: (bool tem_acesso, dict dados_usuario ou None)
    """
    if 'usuario' not in session:
        return False, None
    
    usuario = session['usuario']
    
    # ADM tem acesso a todos os condomínios
    if usuario.get('tipo_usuario') == 'ADM':
        return True, usuario
    
    # Verificar se o condomínio está na lista de permissões
    condominios_permitidos = [c['idcond'] for c in usuario.get('condominios', [])]
    tem_acesso = int(idcond_requisitado) in condominios_permitidos
    
    return tem_acesso, usuario if tem_acesso else None



