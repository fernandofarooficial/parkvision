import mysql.connector
from config.database import get_db_connection
from flask import jsonify, request
from visionlib.authlib import (verificar_autenticacao_usuario, verificar_permissao_tipo_usuario, 
                              hash_senha, validar_email, validar_senha_forte, registrar_log_usuario)


def criar_usuario(dados_usuario, criado_por):
    """
    Cria novo usuário no sistema
    Parâmetros:
    - dados_usuario: dict com dados do usuário
    - criado_por: idgente do usuário que está criando
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        # Validações
        email = dados_usuario.get('email', '').strip().lower()
        nome_completo = dados_usuario.get('nome_completo', '').strip()
        nome_curto = dados_usuario.get('nome_curto', '').strip()
        telefone = dados_usuario.get('telefone', '').strip()
        tipo_usuario = dados_usuario.get('tipo_usuario', '').upper()
        senha = dados_usuario.get('senha', '')
        
        if not all([email, nome_completo, nome_curto, tipo_usuario, senha]):
            return False, "Todos os campos obrigatórios devem ser preenchidos"
        
        if not validar_email(email):
            return False, "Formato de email inválido"
        
        if tipo_usuario not in ['ADM', 'MONITOR', 'SINDICO']:
            return False, "Tipo de usuário inválido"
        
        senha_valida, mensagem_senha = validar_senha_forte(senha)
        if not senha_valida:
            return False, mensagem_senha
        
        # Verificar se email já existe
        cursor.execute("SELECT idgente FROM usuarios WHERE email = %s", (email,))
        if cursor.fetchone():
            return False, "Email já cadastrado no sistema"
        
        # Criar usuário
        senha_hash = hash_senha(senha)
        cursor.execute("""
            INSERT INTO usuarios (nome_completo, nome_curto, email, telefone, senha_hash, tipo_usuario)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (nome_completo, nome_curto, email, telefone, senha_hash, tipo_usuario))
        
        novo_idgente = cursor.lastrowid
        conn.commit()
        
        registrar_log_usuario(criado_por, 'CRIAR_USUARIO', f'Usuário criado: {email} (ID: {novo_idgente})')
        
        return True, f"Usuário {nome_curto} criado com sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro ao criar usuário: {err}"
    finally:
        cursor.close()
        conn.close()


def listar_usuarios(incluir_inativos=False):
    """
    Lista todos os usuários do sistema
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    try:
        if incluir_inativos:
            query = "SELECT * FROM vw_usuarios_completo"
            cursor.execute(query)
        else:
            query = "SELECT * FROM vw_usuarios_completo WHERE ativo = TRUE"
            cursor.execute(query)
        
        usuarios = cursor.fetchall()
        
        # Formatar datas para exibição
        for usuario in usuarios:
            if usuario['data_criacao']:
                usuario['data_criacao'] = usuario['data_criacao'].strftime('%d/%m/%Y %H:%M')
        
        return usuarios
        
    except mysql.connector.Error as err:
        print(f"Erro ao listar usuários: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def obter_usuario_por_id(idgente):
    """
    Obtém dados completos de um usuário por ID
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT u.idgente, u.nome_completo, u.nome_curto, u.email, u.telefone,
                   u.tipo_usuario, u.ativo, u.data_criacao
            FROM usuarios u
            WHERE u.idgente = %s
        """, (idgente,))
        
        usuario = cursor.fetchone()
        
        if usuario:
            # Buscar condomínios do usuário
            cursor.execute("""
                SELECT uc.idcond, c.nmcond, uc.data_liberacao,
                       liberador.nome_curto as liberado_por_nome
                FROM usuario_condominios uc
                INNER JOIN cadcond c ON uc.idcond = c.idcond
                INNER JOIN usuarios liberador ON uc.liberado_por = liberador.idgente
                WHERE uc.idgente = %s
                ORDER BY c.nmcond
            """, (idgente,))
            
            usuario['condominios'] = cursor.fetchall()
        
        return usuario
        
    except mysql.connector.Error as err:
        print(f"Erro ao obter usuário: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def atualizar_usuario(idgente, dados_usuario, atualizado_por):
    """
    Atualiza dados do usuário
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        # Validações
        email = dados_usuario.get('email', '').strip().lower()
        nome_completo = dados_usuario.get('nome_completo', '').strip()
        nome_curto = dados_usuario.get('nome_curto', '').strip()
        telefone = dados_usuario.get('telefone', '').strip()
        tipo_usuario = dados_usuario.get('tipo_usuario', '').upper()
        
        if not all([email, nome_completo, nome_curto, tipo_usuario]):
            return False, "Todos os campos obrigatórios devem ser preenchidos"
        
        if not validar_email(email):
            return False, "Formato de email inválido"
        
        if tipo_usuario not in ['ADM', 'MONITOR', 'SINDICO']:
            return False, "Tipo de usuário inválido"
        
        # Verificar se email já existe em outro usuário
        cursor.execute("SELECT idgente FROM usuarios WHERE email = %s AND idgente != %s", (email, idgente))
        if cursor.fetchone():
            return False, "Email já cadastrado para outro usuário"
        
        # Verificar se deve alterar senha
        nova_senha = dados_usuario.get('nova_senha', '').strip()
        if nova_senha:
            if len(nova_senha) < 8:
                return False, "Nova senha deve ter pelo menos 8 caracteres"
            
            # Gerar hash da nova senha
            senha_hash = hash_senha(nova_senha)
            
            # Atualizar usuário com nova senha
            cursor.execute("""
                UPDATE usuarios 
                SET nome_completo = %s, nome_curto = %s, email = %s, telefone = %s, 
                    tipo_usuario = %s, senha_hash = %s, lup = NOW()
                WHERE idgente = %s
            """, (nome_completo, nome_curto, email, telefone, tipo_usuario, senha_hash, idgente))
        else:
            # Atualizar usuário sem alterar senha
            cursor.execute("""
                UPDATE usuarios 
                SET nome_completo = %s, nome_curto = %s, email = %s, telefone = %s, 
                    tipo_usuario = %s, lup = NOW()
                WHERE idgente = %s
            """, (nome_completo, nome_curto, email, telefone, tipo_usuario, idgente))
        
        if cursor.rowcount == 0:
            return False, "Usuário não encontrado"
        
        conn.commit()
        
        registrar_log_usuario(atualizado_por, 'ATUALIZAR_USUARIO', f'Usuário atualizado: {email} (ID: {idgente})')
        
        return True, "Usuário atualizado com sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro ao atualizar usuário: {err}"
    finally:
        cursor.close()
        conn.close()


def desativar_usuario(idgente, desativado_por, motivo=None):
    """
    Desativa usuário (não exclui, apenas marca como inativo)
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE usuarios SET ativo = FALSE, lup = NOW()
            WHERE idgente = %s AND ativo = TRUE
        """, (idgente,))
        
        if cursor.rowcount == 0:
            return False, "Usuário não encontrado ou já desativado"
        
        conn.commit()
        
        detalhes = f'Usuário desativado (ID: {idgente})'
        if motivo:
            detalhes += f' - Motivo: {motivo}'
        
        registrar_log_usuario(desativado_por, 'DESATIVAR_USUARIO', detalhes)
        
        return True, "Usuário desativado com sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro ao desativar usuário: {err}"
    finally:
        cursor.close()
        conn.close()


def reativar_usuario(idgente, reativado_por):
    """
    Reativa usuário desativado
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE usuarios SET ativo = TRUE, lup = NOW()
            WHERE idgente = %s AND ativo = FALSE
        """, (idgente,))
        
        if cursor.rowcount == 0:
            return False, "Usuário não encontrado ou já ativo"
        
        conn.commit()
        
        registrar_log_usuario(reativado_por, 'REATIVAR_USUARIO', f'Usuário reativado (ID: {idgente})')
        
        return True, "Usuário reativado com sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro ao reativar usuário: {err}"
    finally:
        cursor.close()
        conn.close()


def liberar_condominio_usuario(idgente, idcond, liberado_por):
    """
    Libera acesso do usuário a um condomínio
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        # Verificar se já existe liberação
        cursor.execute("""
            SELECT id FROM usuario_condominios 
            WHERE idgente = %s AND idcond = %s
        """, (idgente, idcond))
        
        if cursor.fetchone():
            return False, "Usuário já tem acesso a este condomínio"
        
        # Criar liberação
        cursor.execute("""
            INSERT INTO usuario_condominios (idgente, idcond, liberado_por)
            VALUES (%s, %s, %s)
        """, (idgente, idcond, liberado_por))
        
        conn.commit()
        
        registrar_log_usuario(liberado_por, 'LIBERAR_CONDOMINIO', 
                             f'Liberado condomínio {idcond} para usuário {idgente}')
        
        return True, "Condomínio liberado para o usuário"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro ao liberar condomínio: {err}"
    finally:
        cursor.close()
        conn.close()


def remover_condominio_usuario(idgente, idcond, removido_por):
    """
    Remove acesso do usuário a um condomínio
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM usuario_condominios 
            WHERE idgente = %s AND idcond = %s
        """, (idgente, idcond))
        
        if cursor.rowcount == 0:
            return False, "Liberação não encontrada"
        
        conn.commit()
        
        registrar_log_usuario(removido_por, 'REMOVER_CONDOMINIO', 
                             f'Removido condomínio {idcond} do usuário {idgente}')
        
        return True, "Acesso ao condomínio removido"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro ao remover condomínio: {err}"
    finally:
        cursor.close()
        conn.close()


def criar_solicitacao_inscricao(dados_solicitacao):
    """
    Cria solicitação de inscrição no sistema
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        # Validações
        email = dados_solicitacao.get('email', '').strip().lower()
        nome_completo = dados_solicitacao.get('nome_completo', '').strip()
        nome_curto = dados_solicitacao.get('nome_curto', '').strip()
        telefone = dados_solicitacao.get('telefone', '').strip()
        tipo_usuario = dados_solicitacao.get('tipo_usuario_solicitado', '').upper()
        justificativa = dados_solicitacao.get('justificativa', '').strip()
        
        if not all([email, nome_completo, nome_curto, tipo_usuario]):
            return False, "Todos os campos obrigatórios devem ser preenchidos"
        
        if not validar_email(email):
            return False, "Formato de email inválido"
        
        if tipo_usuario not in ['MONITOR', 'SINDICO']:
            return False, "Tipo de usuário deve ser MONITOR ou SÍNDICO"
        
        # Verificar se email já existe
        cursor.execute("SELECT idgente FROM usuarios WHERE email = %s", (email,))
        if cursor.fetchone():
            return False, "Email já cadastrado no sistema"
        
        # Verificar se já existe solicitação pendente
        cursor.execute("""
            SELECT id FROM solicitacoes_inscricao 
            WHERE email = %s AND status = 'PENDENTE'
        """, (email,))
        if cursor.fetchone():
            return False, "Já existe uma solicitação pendente para este email"
        
        # Criar solicitação
        cursor.execute("""
            INSERT INTO solicitacoes_inscricao 
            (nome_completo, nome_curto, email, telefone, tipo_usuario_solicitado, justificativa)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (nome_completo, nome_curto, email, telefone, tipo_usuario, justificativa))
        
        conn.commit()
        
        return True, "Solicitação de inscrição enviada com sucesso. Aguarde aprovação do administrador."
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro ao criar solicitação: {err}"
    finally:
        cursor.close()
        conn.close()


def listar_solicitacoes_pendentes():
    """
    Lista todas as solicitações de inscrição pendentes
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM vw_solicitacoes_pendentes")
        solicitacoes = cursor.fetchall()
        
        # Formatar datas
        for solicitacao in solicitacoes:
            if solicitacao['data_solicitacao']:
                solicitacao['data_solicitacao'] = solicitacao['data_solicitacao'].strftime('%d/%m/%Y %H:%M')
        
        return solicitacoes
        
    except mysql.connector.Error as err:
        print(f"Erro ao listar solicitações: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def responder_solicitacao(solicitacao_id, aprovado, senha_inicial, respondido_por, observacoes=None):
    """
    Responde a uma solicitação de inscrição
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        # Buscar solicitação
        cursor.execute("""
            SELECT * FROM solicitacoes_inscricao 
            WHERE id = %s AND status = 'PENDENTE'
        """, (solicitacao_id,))
        
        solicitacao = cursor.fetchone()
        if not solicitacao:
            return False, "Solicitação não encontrada ou já processada"
        
        status = 'APROVADO' if aprovado else 'REJEITADO'
        
        # Atualizar solicitação
        cursor.execute("""
            UPDATE solicitacoes_inscricao 
            SET status = %s, data_resposta = NOW(), respondido_por = %s, observacoes_resposta = %s
            WHERE id = %s
        """, (status, respondido_por, observacoes, solicitacao_id))
        
        # Se aprovado, criar usuário
        if aprovado:
            if not senha_inicial:
                return False, "Senha inicial é obrigatória para aprovação"
            
            dados_usuario = {
                'nome_completo': solicitacao[1],  # nome_completo
                'nome_curto': solicitacao[2],     # nome_curto  
                'email': solicitacao[3],          # email
                'telefone': solicitacao[4],       # telefone
                'tipo_usuario': solicitacao[5],   # tipo_usuario_solicitado
                'senha': senha_inicial
            }
            
            success, message = criar_usuario(dados_usuario, respondido_por)
            if not success:
                conn.rollback()
                return False, f"Erro ao criar usuário: {message}"
        
        conn.commit()
        
        acao = 'APROVAR_SOLICITACAO' if aprovado else 'REJEITAR_SOLICITACAO'
        registrar_log_usuario(respondido_por, acao, f'Solicitação {solicitacao_id} - Email: {solicitacao[3]}')
        
        resultado = "aprovada" if aprovado else "rejeitada"
        return True, f"Solicitação {resultado} com sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro ao processar solicitação: {err}"
    finally:
        cursor.close()
        conn.close()


# APIs Flask para gestão de usuários

def api_listar_usuarios():
    """API para listar usuários - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    usuarios = listar_usuarios()
    if usuarios is not None:
        return jsonify({'success': True, 'data': usuarios})
    else:
        return jsonify({'success': False, 'message': 'Erro ao consultar usuários'})


def api_criar_usuario():
    """API para criar usuário - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    data = request.json
    autenticado, usuario_atual = verificar_autenticacao_usuario()
    
    success, message = criar_usuario(data, usuario_atual['idgente'])
    return jsonify({'success': success, 'message': message})


def api_atualizar_usuario(idgente):
    """API para atualizar usuário - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    data = request.json
    autenticado, usuario_atual = verificar_autenticacao_usuario()
    
    success, message = atualizar_usuario(idgente, data, usuario_atual['idgente'])
    return jsonify({'success': success, 'message': message})


def api_desativar_usuario(idgente):
    """API para desativar usuário - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    data = request.json
    motivo = data.get('motivo', '')
    autenticado, usuario_atual = verificar_autenticacao_usuario()
    
    success, message = desativar_usuario(idgente, usuario_atual['idgente'], motivo)
    return jsonify({'success': success, 'message': message})


def api_criar_solicitacao():
    """API para criar solicitação de inscrição - público"""
    data = request.json
    success, message = criar_solicitacao_inscricao(data)
    return jsonify({'success': success, 'message': message})


def api_listar_solicitacoes():
    """API para listar solicitações - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    solicitacoes = listar_solicitacoes_pendentes()
    if solicitacoes is not None:
        return jsonify({'success': True, 'data': solicitacoes})
    else:
        return jsonify({'success': False, 'message': 'Erro ao consultar solicitações'})


def api_responder_solicitacao(solicitacao_id):
    """API para responder solicitação - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    data = request.json
    aprovado = data.get('aprovado', False)
    senha_inicial = data.get('senha_inicial', '')
    observacoes = data.get('observacoes', '')
    
    autenticado, usuario_atual = verificar_autenticacao_usuario()
    
    success, message = responder_solicitacao(
        solicitacao_id, aprovado, senha_inicial, usuario_atual['idgente'], observacoes
    )
    
    return jsonify({'success': success, 'message': message})


def api_liberar_condominio(idgente):
    """API para liberar condomínio para usuário - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    data = request.json
    idcond = data.get('idcond')
    
    if not idcond:
        return jsonify({'success': False, 'message': 'ID do condomínio é obrigatório'})
    
    autenticado, usuario_atual = verificar_autenticacao_usuario()
    
    success, message = liberar_condominio_usuario(idgente, idcond, usuario_atual['idgente'])
    return jsonify({'success': success, 'message': message})


def api_remover_condominio(idgente):
    """API para remover condomínio do usuário - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    data = request.json
    idcond = data.get('idcond')
    
    if not idcond:
        return jsonify({'success': False, 'message': 'ID do condomínio é obrigatório'})
    
    autenticado, usuario_atual = verificar_autenticacao_usuario()
    
    success, message = remover_condominio_usuario(idgente, idcond, usuario_atual['idgente'])
    return jsonify({'success': success, 'message': message})


# ===== FUNÇÕES PARA GERENCIAMENTO DE CONDOMÍNIOS DE USUÁRIOS =====

def listar_condominios_disponiveis():
    """Lista todos os condomínios cadastrados"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT idcond, nmcond, nrcond, idemp, cicond
            FROM cadcond 
            ORDER BY nmcond
        """)
        condominios = cursor.fetchall()
        return condominios
        
    except mysql.connector.Error as err:
        print(f"Erro ao listar condomínios: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def listar_condominios_usuario(idgente):
    """Lista condomínios associados a um usuário"""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT c.idcond, c.nmcond, c.nrcond, c.idemp, c.cicond,
                   uc.data_liberacao, uc.liberado_por
            FROM usuario_condominios uc
            INNER JOIN cadcond c ON uc.idcond = c.idcond
            WHERE uc.idgente = %s
            ORDER BY c.nmcond
        """, (idgente,))
        condominios = cursor.fetchall()
        
        # Formatar datas
        for condominio in condominios:
            if condominio['data_liberacao']:
                condominio['data_liberacao'] = condominio['data_liberacao'].strftime('%d/%m/%Y %H:%M')
        
        return condominios
        
    except mysql.connector.Error as err:
        print(f"Erro ao listar condomínios do usuário: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def liberar_condominio_usuario(idgente, idcond, liberado_por):
    """Associa um condomínio a um usuário"""
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        # Verificar se usuário existe e não é ADM (ADM tem acesso a todos)
        cursor.execute("SELECT tipo_usuario FROM usuarios WHERE idgente = %s", (idgente,))
        usuario = cursor.fetchone()
        if not usuario:
            return False, "Usuário não encontrado"
        
        if usuario[0] == 'ADM':
            return False, "Usuários ADM têm acesso a todos os condomínios automaticamente"
        
        # Verificar se condomínio existe
        cursor.execute("SELECT nmcond FROM cadcond WHERE idcond = %s", (idcond,))
        condominio = cursor.fetchone()
        if not condominio:
            return False, "Condomínio não encontrado"
        
        # Verificar se já existe associação
        cursor.execute("""
            SELECT id FROM usuario_condominios 
            WHERE idgente = %s AND idcond = %s
        """, (idgente, idcond))
        
        if cursor.fetchone():
            return False, f"Usuário já possui acesso ao condomínio {condominio[0]}"
        
        # Criar associação
        cursor.execute("""
            INSERT INTO usuario_condominios (idgente, idcond, liberado_por, data_liberacao)
            VALUES (%s, %s, %s, NOW())
        """, (idgente, idcond, liberado_por))
        
        # Log da operação
        cursor.execute("""
            INSERT INTO log_usuarios (idgente, acao, detalhes, data_acao)
            VALUES (%s, 'CONDOMINIO_LIBERADO', %s, NOW())
        """, (liberado_por, f"Liberou acesso ao condomínio {condominio[0]} para usuário ID {idgente}"))
        
        conn.commit()
        return True, f"Acesso ao condomínio {condominio[0]} liberado com sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Erro ao liberar condomínio: {err}")
        return False, f"Erro ao liberar condomínio: {err}"
    finally:
        cursor.close()
        conn.close()


def remover_condominio_usuario(idgente, idcond, removido_por):
    """Remove associação entre usuário e condomínio"""
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor()
    try:
        # Verificar se usuário existe e não é ADM
        cursor.execute("SELECT tipo_usuario FROM usuarios WHERE idgente = %s", (idgente,))
        usuario = cursor.fetchone()
        if not usuario:
            return False, "Usuário não encontrado"
        
        if usuario[0] == 'ADM':
            return False, "Não é possível remover acesso de usuários ADM"
        
        # Buscar nome do condomínio para log
        cursor.execute("SELECT nmcond FROM cadcond WHERE idcond = %s", (idcond,))
        condominio = cursor.fetchone()
        if not condominio:
            return False, "Condomínio não encontrado"
        
        # Verificar se existe associação
        cursor.execute("""
            SELECT id FROM usuario_condominios 
            WHERE idgente = %s AND idcond = %s
        """, (idgente, idcond))
        
        if not cursor.fetchone():
            return False, f"Usuário não possui acesso ao condomínio {condominio[0]}"
        
        # Remover associação
        cursor.execute("""
            DELETE FROM usuario_condominios 
            WHERE idgente = %s AND idcond = %s
        """, (idgente, idcond))
        
        # Log da operação
        cursor.execute("""
            INSERT INTO log_usuarios (idgente, acao, detalhes, data_acao)
            VALUES (%s, 'CONDOMINIO_REMOVIDO', %s, NOW())
        """, (removido_por, f"Removeu acesso ao condomínio {condominio[0]} do usuário ID {idgente}"))
        
        conn.commit()
        return True, f"Acesso ao condomínio {condominio[0]} removido com sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Erro ao remover condomínio: {err}")
        return False, f"Erro ao remover condomínio: {err}"
    finally:
        cursor.close()
        conn.close()


# ===== APIS PARA GERENCIAMENTO DE CONDOMÍNIOS =====

def api_listar_condominios_disponiveis():
    """API para listar todos os condomínios - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    condominios = listar_condominios_disponiveis()
    if condominios is not None:
        return jsonify({'success': True, 'data': condominios})
    else:
        return jsonify({'success': False, 'message': 'Erro ao consultar condomínios'})


def api_listar_condominios_usuario(idgente):
    """API para listar condomínios de um usuário - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    condominios = listar_condominios_usuario(idgente)
    if condominios is not None:
        return jsonify({'success': True, 'data': condominios})
    else:
        return jsonify({'success': False, 'message': 'Erro ao consultar condomínios do usuário'})


def api_gerenciar_condominios_usuario(idgente):
    """API para gerenciar condomínios de um usuário - apenas ADM"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    data = request.json
    acao = data.get('acao')  # 'adicionar' ou 'remover'
    idcond = data.get('idcond')
    
    if not acao or not idcond:
        return jsonify({'success': False, 'message': 'Ação e ID do condomínio são obrigatórios'})
    
    autenticado, usuario_atual = verificar_autenticacao_usuario()
    
    if acao == 'adicionar':
        success, message = liberar_condominio_usuario(idgente, idcond, usuario_atual['idgente'])
    elif acao == 'remover':
        success, message = remover_condominio_usuario(idgente, idcond, usuario_atual['idgente'])
    else:
        return jsonify({'success': False, 'message': 'Ação inválida'})
    
    return jsonify({'success': success, 'message': message})