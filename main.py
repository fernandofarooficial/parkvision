# ------------------
# MAIN
# ------------------

from flask import Flask, render_template, jsonify, request, session, redirect, url_for, Response
import os
import pytz
import secrets
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
import datetime
from visionlib.apilib import receber_dados
from visionlib.dblib import obter_marcas, obter_modelos, inserir_carro, obter_cores
from visionlib.condlib import obter_dados_condminios, lista_condominios
from visionlib.permlib import criar_permissao, modificar_permissao, buscar_permissao, obter_unidades_condominio
from visionlib.carlib import cadastrar_veiculo_nao_cadastrado, criar_veiculo_cadveiculo, modificar_veiculo_cadveiculo
from visionlib.carlib import obter_veiculos_nao_cadastrados, buscar_veiculo_cadveiculo, gerenciar_apelido, excluir_veiculo_nao_cadastrado, corrigir_placa_veiculo
from visionlib.listlib import obter_lista_veiculos, veiculo_detalhes, detalhes_unidade
from visionlib.dashlib import obter_mapa_vagas, obter_resumo
from visionlib.rellib import (obter_relatorio_permissoes_validas, obter_relatorio_movimento_veiculos, 
                              obter_relatorio_mapa_vagas, obter_relatorio_veiculos_condominio, 
                              obter_relatorio_nao_cadastrados, obter_relatorio_veiculos_estacionados)
from globals import verificar_acesso_condominio

# Importar novas bibliotecas de autenticação e usuários
from visionlib.authlib import (api_login, api_logout, api_status_autenticacao, api_alterar_senha,
                              api_solicitar_recuperacao, api_recuperar_senha, verificar_autenticacao_usuario,
                              verificar_permissao_tipo_usuario)
from visionlib.userlib import (api_listar_usuarios, api_criar_usuario, api_atualizar_usuario,
                              api_desativar_usuario, api_criar_solicitacao, api_listar_solicitacoes,
                              api_responder_solicitacao, api_liberar_condominio, api_remover_condominio,
                              api_listar_condominios_disponiveis, api_listar_condominios_usuario,
                              api_gerenciar_condominios_usuario)
from visionlib.apontlib import obter_veiculos_cadastrados, obter_ultimo_movimento, processar_apontamento
from visionlib.operlib import (obter_eventos_recentes, obter_historico_db, executar_acao_operador,
                               obter_cameras_rtsp, obter_rtsp_camera, capturar_snapshot_rtsp,
                               corrigir_placa_operador, enviar_pulso_por_direcao,
                               obter_cameras_dispositivo_por_direcao,
                               obter_info_veiculo_operador, obter_ultimos_movimentos,
                               obter_resumo_vagas_cond, obter_acoes_recentes)
from visionlib.camlib import iniciar_monitor_cameras, obter_status_cameras

app = Flask(__name__)

# Configurações de sessão
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    raise RuntimeError("SECRET_KEY não definida. Configure a variável de ambiente SECRET_KEY no .env")
app.secret_key = _secret_key
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Previne acesso via JavaScript
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Proteção CSRF
app.config['SESSION_COOKIE_PATH'] = '/'  # Cookie válido para todo o site
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Duração da sessão
app.config['SESSION_COOKIE_NAME'] = 'parkvision_session'


# Definir fuso horário brasileiro
BRASIL_TZ = pytz.timezone('America/Sao_Paulo')

# Configurar timezone da aplicação
os.environ['TZ'] = 'America/Sao_Paulo'


# Rotas para páginas HTML
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/condominios')
def condominios():
    return render_template('condominios.html')


@app.route('/sobre')
def sobre():
    return render_template('sobre.html')


@app.route('/veiculos/<int:condominio_id>')
def veiculos(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('veiculos.html')


@app.route('/unidades/<int:condominio_id>')
def unidades(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('unidades.html')


@app.route('/mapa-vagas/<int:condominio_id>')
def mapa_vagas(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('mapa-vagas.html')


@app.route('/operador/<int:condominio_id>')
def operador(condominio_id):
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('operador.html')


# API: carga inicial do histórico de eventos (banco de dados)
@app.route('/api/operador/historico/<int:condominio_id>')
def api_operador_historico(condominio_id):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    eventos = obter_historico_db(condominio_id, limit=10)
    return jsonify({'success': True, 'eventos': eventos})


# API: ação do operador sobre um evento (confirmar / rejeitar / ignorar)
@app.route('/api/operador/acao', methods=['POST'])
def api_operador_acao():
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 403

    data = request.get_json() or {}
    idmov  = data.get('idmov')
    acao   = data.get('acao')
    motivo = data.get('motivo')

    if not idmov or not acao:
        return jsonify({'success': False, 'message': 'Parâmetros obrigatórios ausentes'}), 400

    idgente = usuario.get('idgente')
    resultado = executar_acao_operador(int(idmov), acao, idgente, motivo)
    status_http = 200 if resultado['success'] else 500
    return jsonify(resultado), status_http


# API: polling de novos eventos (memória — tempo real)
@app.route('/api/operador/eventos/<int:condominio_id>')
def api_operador_eventos(condominio_id):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    desde_ts = request.args.get('desde_ts', None)
    eventos = obter_eventos_recentes(condominio_id, desde_ts)
    return jsonify({'success': True, 'eventos': eventos})


# API: correção de placa pelo operador
@app.route('/api/operador/corrigir-placa', methods=['POST'])
def api_operador_corrigir_placa():
    autenticado, _ = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 403
    data = request.get_json() or {}
    idmov          = data.get('idmov')
    placa_corrigida = data.get('placa_corrigida', '').strip().upper()
    idcond         = data.get('idcond')
    if not idmov or not placa_corrigida or not idcond:
        return jsonify({'success': False, 'message': 'Parâmetros obrigatórios ausentes'}), 400
    resultado = corrigir_placa_operador(int(idmov), placa_corrigida, int(idcond))
    status_http = 200 if resultado['success'] else 422
    return jsonify(resultado), status_http


# API: câmeras com RTSP para a tela operador
@app.route('/api/operador/cameras/<int:condominio_id>')
def api_operador_cameras(condominio_id):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    if os.getenv('CAMERAS_ENABLED', 'true').lower() == 'false':
        return jsonify({'success': True, 'cameras': []})
    cameras = obter_cameras_rtsp(condominio_id)
    # Não expor a URL RTSP ao cliente — apenas o ID
    cameras_safe = [{'idcam': c['idcam'], 'nomecamera': c.get('nomecamera') or f'Câm. {c["idcam"]}'} for c in cameras]
    return jsonify({'success': True, 'cameras': cameras_safe})


# API: disponibilidade de dispositivos por direção
@app.route('/api/operador/dispositivos/<int:condominio_id>')
def api_operador_dispositivos(condominio_id):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    direcoes = obter_cameras_dispositivo_por_direcao(condominio_id)
    return jsonify({'success': True, 'direcoes': direcoes})


# API: últimos 10 movimentos confirmados (entrada ou saída) para o painel da tela operador
@app.route('/api/operador/ultimos-movimentos/<int:condominio_id>')
def api_operador_ultimos_movimentos(condominio_id):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    movimentos = obter_ultimos_movimentos(condominio_id)
    return jsonify({'success': True, 'movimentos': movimentos})


# API: ações recentes do operador para sincronização entre browsers
@app.route('/api/operador/acoes/<int:condominio_id>')
def api_operador_acoes(condominio_id):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    desde_ts = request.args.get('desde_ts', None)
    acoes = obter_acoes_recentes(condominio_id, desde_ts)
    return jsonify({'success': True, 'acoes': acoes})


# API: informações do veículo para painel da tela operador
@app.route('/api/operador/info-veiculo/<int:condominio_id>/<placa>')
def api_operador_info_veiculo(condominio_id, placa):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    resultado = obter_info_veiculo_operador(condominio_id, placa.upper())
    return jsonify(resultado)


# API: resumo de vagas do condomínio para a tela operador
@app.route('/api/operador/vagas-cond/<int:condominio_id>')
def api_operador_vagas_cond(condominio_id):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    return jsonify(obter_resumo_vagas_cond(condominio_id))


# API: pulso manual de porta pelo operador
@app.route('/api/operador/abrir-porta', methods=['POST'])
def api_operador_abrir_porta():
    autenticado, _ = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 403
    data = request.get_json() or {}
    idcond  = data.get('idcond')
    direcao = data.get('direcao')  # 'E' ou 'S'
    if not idcond or direcao not in ('E', 'S'):
        return jsonify({'success': False, 'message': 'Parâmetros obrigatórios ausentes'}), 400
    resultado = enviar_pulso_por_direcao(int(idcond), direcao)
    status_http = 200 if resultado['success'] else 422
    return jsonify(resultado), status_http


# API: status das câmeras (monitoramento background — resultado da última verificação)
@app.route('/api/operador/monitor-cameras/<int:condominio_id>')
def api_operador_monitor_cameras(condominio_id):
    tem_acesso, _ = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    cameras = obter_status_cameras(condominio_id)
    cameras_enabled = os.getenv('CAMERAS_ENABLED', 'true').lower() != 'false'
    return jsonify({'success': True, 'cameras': cameras, 'cameras_enabled': cameras_enabled})


# API: snapshot JPEG de câmera via RTSP
@app.route('/api/camera/snapshot/<int:idcam>')
def api_camera_snapshot(idcam):
    if os.getenv('CAMERAS_ENABLED', 'true').lower() == 'false':
        return jsonify({'success': False, 'message': 'Câmeras desabilitadas'}), 503
    autenticado, _ = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 403
    rtsp_url = obter_rtsp_camera(idcam)
    if not rtsp_url:
        return jsonify({'success': False, 'message': 'Câmera sem RTSP configurado'}), 404
    img_bytes = capturar_snapshot_rtsp(rtsp_url)
    if img_bytes is None:
        return jsonify({'success': False, 'message': 'Falha ao capturar imagem da câmera'}), 503
    return Response(
        img_bytes,
        mimetype='image/jpeg',
        headers={'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache'}
    )


# ===== NOVAS ROTAS DE AUTENTICAÇÃO E GESTÃO DE USUÁRIOS =====

# Páginas de autenticação
@app.route('/login')
def login():
    # Se já estiver autenticado, redirecionar
    autenticado, usuario = verificar_autenticacao_usuario()
    if autenticado:
        if usuario['tipo_usuario'] == 'ADM':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('condominios'))
    return render_template('login.html')


@app.route('/solicitar-inscricao')
def solicitar_inscricao():
    return render_template('solicitar-inscricao.html')


@app.route('/alterar-senha')
def alterar_senha():
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return redirect(url_for('login'))
    return render_template('alterar-senha.html')


@app.route('/recuperar-senha')
def recuperar_senha():
    return render_template('recuperar-senha.html')


# Área administrativa
@app.route('/admin/dashboard')
def admin_dashboard():
    if not verificar_permissao_tipo_usuario(['ADM']):
        return redirect(url_for('login'))
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/usuarios')
def admin_usuarios():
    if not verificar_permissao_tipo_usuario(['ADM']):
        return redirect(url_for('login'))
    return render_template('admin-usuarios.html')


# ===== APIS DE AUTENTICAÇÃO =====

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    return api_login()


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    return api_logout()


@app.route('/api/auth/status')
def api_auth_status():
    return api_status_autenticacao()



@app.route('/api/auth/alterar-senha', methods=['POST'])
def api_auth_alterar_senha():
    return api_alterar_senha()


@app.route('/api/auth/solicitar-recuperacao', methods=['POST'])
def api_auth_solicitar_recuperacao():
    return api_solicitar_recuperacao()


@app.route('/api/auth/recuperar-senha', methods=['POST'])
def api_auth_recuperar_senha():
    return api_recuperar_senha()


# ===== APIS DE GESTÃO DE USUÁRIOS (ADMIN) =====

@app.route('/api/admin/usuarios', methods=['GET'])
def api_admin_listar_usuarios():
    return api_listar_usuarios()


@app.route('/api/admin/usuarios', methods=['POST'])
def api_admin_criar_usuario():
    return api_criar_usuario()


@app.route('/api/admin/usuarios/<int:idgente>', methods=['PUT'])
def api_admin_atualizar_usuario(idgente):
    return api_atualizar_usuario(idgente)


@app.route('/api/admin/usuarios/<int:idgente>/desativar', methods=['POST'])
def api_admin_desativar_usuario(idgente):
    return api_desativar_usuario(idgente)


@app.route('/api/admin/usuarios/<int:idgente>/condominios', methods=['POST'])
def api_admin_liberar_condominio(idgente):
    return api_liberar_condominio(idgente)


@app.route('/api/admin/usuarios/<int:idgente>/condominios', methods=['DELETE'])
def api_admin_remover_condominio(idgente):
    return api_remover_condominio(idgente)


# ===== APIS DE SOLICITAÇÕES DE CADASTRO =====

@app.route('/api/solicitar-inscricao', methods=['POST'])
def api_public_solicitar_inscricao():
    return api_criar_solicitacao()


@app.route('/api/admin/solicitacoes', methods=['GET'])
def api_admin_listar_solicitacoes():
    return api_listar_solicitacoes()


@app.route('/api/admin/solicitacoes/<int:solicitacao_id>/responder', methods=['POST'])
def api_admin_responder_solicitacao(solicitacao_id):
    return api_responder_solicitacao(solicitacao_id)


# ===== APIS PARA GERENCIAMENTO DE CONDOMÍNIOS DE USUÁRIOS =====

@app.route('/api/admin/condominios', methods=['GET'])
def api_admin_listar_condominios():
    return api_listar_condominios_disponiveis()


@app.route('/api/admin/usuarios/<int:idgente>/condominios', methods=['GET'])
def api_admin_listar_condominios_usuario(idgente):
    return api_listar_condominios_usuario(idgente)


@app.route('/api/admin/usuarios/<int:idgente>/condominios/gerenciar', methods=['POST'])
def api_admin_gerenciar_condominios_usuario(idgente):
    return api_gerenciar_condominios_usuario(idgente)


# ===== COMPATIBILIDADE COM SISTEMA ANTIGO =====
# Rotas legadas removidas - sistema agora usa apenas autenticação por usuário


# API para obter lista de condomínios
# Biblioteca: condlib
@app.route('/api/condominios')
def api_condominios():
    return lista_condominios()


# API para obter dados do condomínio
# Biblioteca: condlib
@app.route('/api/condominio/<int:condominio_id>')
def api_condominio(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_dados_condminios(condominio_id)


# Rota para criar nova permissão
# Biblioteca: permlib
@app.route('/api/criar-permissao', methods=['POST'])
def api_criar_permissao():
    return criar_permissao()


# Rota para modificar a data_fim de uma permissão
# Biblioteca: permlib
@app.route('/api/modificar-permissao', methods=['PUT'])
def api_modificar_permissao():
    return modificar_permissao()


# NOVA API: Buscar permissão por placa para modificação
# Biblioteca: permlib
@app.route('/api/permissao/<placa>')
def api_buscar_permissao(placa):
    return buscar_permissao(placa)


# API para obter unidades do condomínio para permissões
# Biblioteca: permlib
@app.route('/api/unidades-condominio/<int:condominio_id>')
def api_unidades_condominio(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_unidades_condominio(condominio_id)


def determinar_tipo_movimento(idcam, condominio_id):
    """
    Determina se o movimento é entrada ou saída baseado na câmera e condomínio
    """
    # Configuração das câmeras por condomínio
    cameras_config = {
        1: {  # Condomínio Blaia
            89: 'Entrada',
            90: 'Saída'
            # Câmera 8 é ignorada (contav = 0)
        }
        # Adicionar outros condomínios conforme necessário
    }

    if condominio_id in cameras_config:
        return cameras_config[condominio_id].get(idcam, 'Movimento')

    # Fallback para condomínios não configurados
    return 'Movimento'


# API para obter lista de veículos
# Biblioteca listlib
@app.route('/api/veiculos/<int:condominio_id>')
def api_veiculos(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_lista_veiculos(condominio_id)


# API para obter detalhes de um veículo específico
# Biblioteca listlib
@app.route('/api/veiculo/<int:condominio_id>/<placa>')
def api_veiculo_detalhes(condominio_id, placa):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return veiculo_detalhes(condominio_id, placa)


# API para obter detalhes de uma unidade específica
# Biblioteca listlib
@app.route('/api/unidade/<int:condominio_id>/<unidade>')
def api_detalhes_unidade(condominio_id, unidade):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return detalhes_unidade(condominio_id, unidade)


# API para obter marcas de veículos
@app.route('/api/marcas')
def api_marcas():
    marcas = obter_marcas()
    if marcas is None:
        return jsonify({'success': False, 'message': 'Erro ao consultar marcas!'})
    return jsonify({'success': True, 'data': marcas})


# API para obter modelos de uma marca específica
@app.route('/api/modelos/<marca>')
def api_modelos(marca):
    modelos = obter_modelos(marca)
    if modelos is None:
        return jsonify({'success': False, 'message': 'Erro ao consultar modelos!'})
    return jsonify({'success': True, 'data': modelos})


# API para obter cores de veículos
@app.route('/api/cores')
def api_cores():
    cores = obter_cores()
    if cores is None:
        return jsonify({'success': False, 'message': 'Erro ao consultar cores!'})
    return jsonify({'success': True, 'data': cores})


# API para cadastrar novo veículo
@app.route('/api/veiculo/<int:condominio_id>', methods=['POST'])
def api_cadastrar_veiculo(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    data = request.json
    # A função inserir_carro deve estar em visionlib.dblib
    return inserir_carro(condominio_id, data)


# Função para gerar vagas fictícias
def gerar_vagas_ficticias():
    vagas = []
    for i in range(1, 16):  # Gerar 15 unidades fictícias
        for j in range(1, 8):  # 7 unidades por andar
            unidade = f"{i:02d}{j:02d}"
            vperm = 1 if j <= 5 else 2  # Primeiras 5 unidades têm 1 vaga, outras têm 2
            vocup = min(vperm, (i + j) % 3)  # Ocupação variável
            vagas.append({
                'unidade': unidade,
                'vperm': vperm,
                'vocup': vocup
            })
    return vagas


# API para obter mapa de vagas
# Biblioteca dashlib
@app.route('/api/mapa-vagas/<int:condominio_id>')
def api_mapa_vagas(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_mapa_vagas(condominio_id)


# API para obter resumo
# Biblioteca dashlib
@app.route('/api/resumo')
def api_resumo():
    return obter_resumo()


# API para consumir dados do Heimdall
# Biblioteca: apilib
@app.route('/api/heimdall/webservice/lpr', methods=['POST'])
def consumir_dados_heimdall():
    try:
        return receber_dados()
    except Exception as e:
        return receber_dados()


# Rota para página de veículos não cadastrados
@app.route('/veiculos-nao-cadastrados/<int:condominio_id>')
def veiculos_nao_cadastrados(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('veiculos-nao-cadastrados.html', condominio_id=condominio_id)


# ===== APIS BACKEND PARA MÓDULO CADASTRO DE VEÍCULOS (CADVEICULO) =====

# API para obter veículos não cadastrados
# Biblioteca carlib
@app.route('/api/veiculos-nao-cadastrados/<int:condominio_id>')
def api_veiculos_nao_cadastrados(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_veiculos_nao_cadastrados(condominio_id)

# API para buscar veículo no cadastro de veículos (cadveiculo)
# Biblioteca carlib
@app.route('/api/cadveiculo/<placa>')
def api_buscar_veiculo_cadveiculo(placa):
    return buscar_veiculo_cadveiculo(placa)

# API para buscar veículo por placa (para modificação)
# Biblioteca: carlib
@app.route('/api/cadastrar-veiculo-nao-cadastrado', methods=['POST'])
def api_cadastrar_veiculo_nao_cadastrado():
    # Verificar se usuário está autenticado (validação básica)
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return cadastrar_veiculo_nao_cadastrado()


# API para criar novo veículo no cadveiculo
# Biblioteca: carlib
@app.route('/api/cadveiculo', methods=['POST'])
def api_criar_veiculo_cadveiculo():
    return criar_veiculo_cadveiculo()


# API para modificar veículo existente no cadveiculo
# Biblioteca: carlib
@app.route('/api/cadveiculo/<placa>', methods=['PUT'])
def api_modificar_veiculo_cadveiculo(placa):
    return modificar_veiculo_cadveiculo(placa)


# API para gerenciar apelidos de veículos
# Biblioteca: carlib
@app.route('/api/gerenciar-apelido', methods=['POST'])
def api_gerenciar_apelido():
    # Verificar se usuário está autenticado (validação básica)
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return gerenciar_apelido()


# API para excluir veículo não cadastrado
# Biblioteca: carlib
@app.route('/api/excluir-veiculo-nao-cadastrado', methods=['POST'])
def api_excluir_veiculo_nao_cadastrado():
    # Verificar se usuário está autenticado (validação básica)
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return excluir_veiculo_nao_cadastrado()


# API para corrigir placa de veículo não cadastrado
# Biblioteca: carlib
@app.route('/api/corrigir-placa-veiculo', methods=['POST'])
def api_corrigir_placa_veiculo():
    # Verificar se usuário está autenticado (validação básica)
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return corrigir_placa_veiculo()


# ===== APIS PARA APONTAMENTO MANUAL =====
# Biblioteca: apontlib

# Rota para página de apontamento
@app.route('/apontamento/<int:condominio_id>')
def apontamento(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('apontamento.html')

# API para obter veículos com permissão vigente
@app.route('/api/veiculos-vigentes/<int:condominio_id>')
def api_veiculos_vigentes(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_veiculos_cadastrados(condominio_id)

# API para obter último movimento de um veículo
@app.route('/api/ultimo-movimento', methods=['POST'])
def api_ultimo_movimento():
    # Verificar se usuário está autenticado
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    data = request.get_json()
    placa = data.get('placa')
    condominio_id = data.get('condominio_id')
    
    # Verificar acesso ao condomínio
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    return obter_ultimo_movimento(placa, condominio_id)

# API para processar apontamento manual
@app.route('/api/processar-apontamento', methods=['POST'])
def api_processar_apontamento():
    # Verificar se usuário está autenticado
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    # A verificação de acesso ao condomínio será feita dentro da função processar_apontamento
    return processar_apontamento()


# ===== APIS PARA RELATÓRIOS =====
# Biblioteca: rellib

# API para tela de relatórios
@app.route('/relatorios/<int:condominio_id>')
def relatorios(condominio_id):
  # Verificar acesso usando novo sistema de autenticação
  tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
  if not tem_acesso:
      return redirect(url_for('login'))
  return render_template('relatorios.html')

# Rota para visualizar relatório de permissões válidas
@app.route('/relatorio-permissoes-validas/<int:condominio_id>')
def relatorio_permissoes_validas_view(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('relatorio-permissoes-validas.html')

# Rota para visualizar relatório de movimento de veículos
@app.route('/relatorio-movimento-veiculos/<int:condominio_id>')
def relatorio_movimento_veiculos_view(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('relatorio-movimento-veiculos.html')

# Rota para visualizar relatório de mapa de vagas
@app.route('/relatorio-mapa-vagas/<int:condominio_id>')
def relatorio_mapa_vagas_view(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('relatorio-mapa-vagas.html')

# Rota para visualizar relatório de veículos do condomínio
@app.route('/relatorio-veiculos-condominio/<int:condominio_id>')
def relatorio_veiculos_condominio_view(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('relatorio-veiculos-condominio.html')

# Rota para visualizar relatório de veículos não cadastrados
@app.route('/relatorio-nao-cadastrados/<int:condominio_id>')
def relatorio_nao_cadastrados_view(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('relatorio-nao-cadastrados.html')

# Rota para visualizar relatório de veículos estacionados
@app.route('/relatorio-veiculos-estacionados/<int:condominio_id>')
def relatorio_veiculos_estacionados_view(condominio_id):
    # Verificar acesso usando novo sistema de autenticação
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return redirect(url_for('login'))
    return render_template('relatorio-veiculos-estacionados.html')

@app.route('/relatorio/permissoes-validas/<int:condominio_id>')
def api_relatorio_permissoes_validas(condominio_id):
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_relatorio_permissoes_validas(condominio_id)

@app.route('/relatorio/movimento-veiculos/<int:condominio_id>')
def api_relatorio_movimento_veiculos(condominio_id):
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_relatorio_movimento_veiculos(condominio_id)

@app.route('/relatorio/mapa-vagas/<int:condominio_id>')
def api_relatorio_mapa_vagas(condominio_id):
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_relatorio_mapa_vagas(condominio_id)

@app.route('/api/relatorio/veiculos-condominio/<int:condominio_id>')
def api_relatorio_veiculos_condominio(condominio_id):
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_relatorio_veiculos_condominio(condominio_id)

@app.route('/api/relatorio/nao-cadastrados/<int:condominio_id>')
def api_relatorio_nao_cadastrados(condominio_id):
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_relatorio_nao_cadastrados(condominio_id)

@app.route('/api/relatorio/veiculos-estacionados/<int:condominio_id>')
def api_relatorio_veiculos_estacionados(condominio_id):
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    return obter_relatorio_veiculos_estacionados(condominio_id)


# ===== APIS PARA GERENCIAMENTO DE UNIDADES E VAGAS =====

@app.route('/api/unidades-vagas/<int:condominio_id>')
def api_listar_unidades_vagas(condominio_id):
    """API para listar todas as unidades com suas configurações de vagas"""
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    from visionlib.unidlib import listar_unidades_vagas
    return listar_unidades_vagas(condominio_id)


@app.route('/api/unidades-vagas/<int:condominio_id>/<unidade>', methods=['PUT'])
def api_atualizar_vagas_unidade(condominio_id, unidade):
    """API para atualizar a quantidade de vagas permitidas de uma unidade"""
    tem_acesso, usuario = verificar_acesso_condominio(condominio_id)
    if not tem_acesso:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    from visionlib.unidlib import atualizar_vagas_unidade
    return atualizar_vagas_unidade(condominio_id, unidade)


# ===== ROTAS PARA MONITORAMENTO DE LOGS =====

@app.route('/logs')
def logs_viewer():
    """Página para visualizar logs em tempo real"""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return redirect(url_for('login'))
    return render_template('logs.html')


@app.route('/api/logs/tail')
def api_logs_tail():
    """Retorna novas linhas do arquivo de log a partir de um offset.
    Auto-trunca o arquivo quando atinge MAX_LINHAS.
    """
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Não autorizado'}), 403

    MAX_LINHAS = 300
    log_file = 'parkvision.log'
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0

    try:
        if not os.path.exists(log_file):
            return jsonify({'success': True, 'lines': [], 'next_offset': 0,
                            'total_lines': 0, 'truncated': False})

        # Contar linhas totais para decidir se auto-trunca
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            total_lines = sum(1 for linha in f if linha.strip())

        # Auto-limpar ao atingir o limite
        if total_lines >= MAX_LINHAS:
            agora = datetime.datetime.now(BRASIL_TZ).strftime('%H:%M:%S')
            msg = f'{agora} [INFO] === Log limpo automaticamente após {total_lines} linhas ==='
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(msg + '\n')
            return jsonify({'success': True, 'lines': [msg],
                            'next_offset': len(msg.encode('utf-8')) + 1,
                            'total_lines': 1, 'truncated': True})

        # Leitura incremental por offset de bytes
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(0, 2)
            file_size = f.tell()
            if offset > file_size:
                offset = 0
            if offset == 0 and file_size > 50000:
                f.seek(-50000, 2)
                f.readline()
            else:
                f.seek(offset)
            lines = [line.rstrip('\n') for line in f.readlines() if line.strip()]
            next_offset = f.tell()

        return jsonify({'success': True, 'lines': lines, 'next_offset': next_offset,
                        'total_lines': total_lines, 'truncated': False})

    except OSError as e:
        return jsonify({'success': False, 'message': f'Erro ao ler log: {e}'})


@app.route('/api/logs/limpar', methods=['POST'])
def api_logs_limpar():
    """Trunca o arquivo de log manualmente (somente ADM)."""
    if not verificar_permissao_tipo_usuario(['ADM']):
        return jsonify({'success': False, 'message': 'Não autorizado'}), 403

    log_file = 'parkvision.log'
    try:
        agora = datetime.datetime.now(BRASIL_TZ).strftime('%H:%M:%S')
        msg = f'{agora} [INFO] === Log limpo pelo administrador ==='
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(msg + '\n')
        return jsonify({'success': True, 'message': 'Log limpo com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao limpar log: {e}'})

# ── Monitor de câmeras em background ──────────────────────────────────────────
# WERKZEUG_RUN_MAIN='true' indica o processo filho do reloader (desenvolvimento).
# Em produção ou sem reloader, a variável não está definida — inicia normalmente.
if os.environ.get('WERKZEUG_RUN_MAIN', 'false') == 'true' or not os.environ.get('WERKZEUG_RUN_MAIN'):
    iniciar_monitor_cameras()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
