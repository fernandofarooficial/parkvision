from datetime import datetime
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


lastmov = ['XXX1X11', 1, datetime.now()]


# Senhas temporárias para os condomínios (em produção, isso estaria no banco de dados)
CONDOMINIO_SENHAS = {
    '1': 'senha1',  # CONDOMÍNIO 1
    '2': 'senha2',  # Outros condomínios
    '3': 'senha3',
    '4': 'senha4',
    '5': 'senha5',
    '6': 'senha6',
    '7': 'senha7',
    '8': 'senha8'
}

# Variáveis para controle de vagas
# idcond = Código do condomínio no aplicativo
# nrcond = Número do condomínio no cliente
# Tipo   = Tipo de controle
#          Tipo 1: Uma câmera de entrada, uma de saída e uma de entrada e saída - portão único
#          Tipo 2: Uma cãmera para entrada e saída - portão único
#          Tipo 3: Uma câmera de entrada, uma de saída
# cent   = Número da câmera de entrada
# csai   = Número da câmera de saída
# cdup   = Número de câmera de dupla função (entrada e saída)
# cetd   = Número de câmera auxiliar de entrada
# vent   = Número da câmera de entrada - máquina extra
# vsai   = Número da câmera de saída - máquina extra
# vdup   = Número de câmera de dupla função (entrada e saída) - máquina extra
# vetd   = Número de câmera auxiliar de entrada - máquina extra

def carregar_cvag():
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT idcond, nrcond, tipo, cent, csai, cdup, cetd, '
            'vent, vsai, vdup, vetd, limite, colunas FROM cadcond'
        )
        resultado = cursor.fetchall()
        return [
            {
                'idcond':  int(r['idcond']  or 0),
                'nrcond':  int(r['nrcond']  or 0),
                'tipo':    int(r['tipo']    or 0),
                'cent':    int(r['cent']    or 0),
                'csai':    int(r['csai']    or 0),
                'cdup':    int(r['cdup']    or 0),
                'cetd':    int(r['cetd']    or 0),
                'vent':    int(r['vent']    or 0),
                'vsai':    int(r['vsai']    or 0),
                'vdup':    int(r['vdup']    or 0),
                'vetd':    int(r['vetd']    or 0),
                'limite':  int(r['limite']  or 0),
                'colunas': int(r['colunas'] or 0),
            }
            for r in resultado
        ]
    except Exception as e:
        print(f'Erro ao carregar cvag: {e}')
        return []
    finally:
        cursor.close()
        conn.close()


cvag = carregar_cvag()
