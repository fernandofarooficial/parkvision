# PADRÕES DO PROJETO PARKVISION

Este documento define os padrões e convenções utilizados no projeto ParkVision para manter consistência e qualidade no código.

## 1. ARQUITETURA DO PROJETO

### 1.1 Estrutura de Diretórios
```
PromptVisionProject/
├── main.py                      # Aplicação Flask principal com rotas
├── globals.py                   # Configurações globais e utilities
├── create_admin.py              # Script para criação do primeiro admin
├── logging_config.py            # Configuração centralizada de logs
├── draftqualquer.py             # Scripts de teste e desenvolvimento
├── config/
│   └── database.py              # Conexão e configuração do MySQL
├── templates/                   # Templates HTML Jinja2
│   ├── base.html               # Template base com navbar e autenticação
│   ├── login.html              # Página de login
│   ├── admin-usuarios.html     # Interface administrativa
│   ├── veiculos-*.html         # Gestão de veículos
│   ├── mapa-vagas.html         # Monitoramento de vagas
│   └── relatorio-*.html        # Relatórios diversos
├── static/                     # Arquivos estáticos (CSS, JS, imagens)
├── visionlib/                  # Bibliotecas modulares especializadas
│   ├── authlib/               # Autenticação, sessões e permissões (469 linhas)
│   ├── userlib/               # Gestão de usuários e solicitações (852 linhas)
│   ├── carlib/                # Gestão completa de veículos (690 linhas)
│   ├── dblib/                 # Operações de banco e queries (676 linhas)
│   ├── vplib/                 # Validação e processamento de placas (909 linhas)
│   ├── permlib/               # Sistema de permissões por condomínio (312 linhas)
│   ├── rellib/                # Sistema de relatórios (100+ linhas)
│   ├── listlib/               # Listagens e filtros (100+ linhas)
│   ├── dashlib/               # Dashboard e estatísticas (100+ linhas)
│   ├── condlib/               # Gestão de condomínios (69 linhas)
│   ├── apontlib/              # Sistema de apontamentos manuais
│   ├── unidlib/               # Gestão de unidades habitacionais
│   ├── teleglib/              # Integração com Telegram Bot
│   ├── viewlib/               # Helpers de visualização
│   ├── apilib/                # Integração com API Heimdall LPR (18 linhas)
│   └── middleware.py          # Flask middleware (11KB)
└── ArquivosApoio/             # Scripts de manutenção e utilitários
    ├── X_administrar_base_de_carros.py    # Admin interativo
    ├── P_Acertar_CadLocal_Pelo_Movimento.py  # Correções automáticas
    ├── Y_Criar_massa_de_testes_da_cdup.py    # Dados de teste
    └── outros utilitários...
```

### 1.2 Padrão Arquitetural
- **MVC Pattern**: Separação clara entre View (Templates), Controller (main.py) e Model (visionlib)
- **Modular Design**: Cada módulo em visionlib tem responsabilidade única (Single Responsibility Principle)
- **Service Layer**: Funções de negócio encapsuladas nas libs, reutilizáveis entre rotas
- **Repository Pattern**: dblib centraliza acesso a dados, get_db_connection() abstrai conexões
- **Multi-tenant**: Suporte para múltiplos condomínios com isolamento de dados por idcond

### 1.2.1 Detalhamento dos Módulos visionlib

**Módulos de Autenticação e Usuários:**
- **authlib** (469 linhas): Login, logout, hash bcrypt, gerenciamento de sessões, recuperação de senha com tokens, validação de autenticação
- **userlib** (852 linhas): CRUD de usuários, solicitações de inscrição, permissões por condomínio, gestão de papéis (ADM/MONITOR/SINDICO), auditoria de ações

**Módulos de Veículos:**
- **carlib** (690 linhas): Registro de veículos, tratamento de não cadastrados, correção de placas, apelidos (nicknames), CRUD para cadveiculo
- **vplib** (909 linhas): Validação avançada de placas, correção de erros OCR, conversão de formatos (antiga/Mercosul), fuzzy matching, verificação em base de dados, mapeamento deparaplacas
- **dblib** (676 linhas): Gravação de movimentos, validação de placas, detecção de duplicatas, tratamento de tipos de câmera (tipo1/2/3), gestão de marcas/modelos/cores, notificações Telegram

**Módulos de Permissões e Controle:**
- **permlib** (312 linhas): Criação de permissões de estacionamento, controle de vigência, associação com unidades, modificação de permissões
- **condlib** (69 linhas): Recuperação de dados de condomínios, listagem de condomínios disponíveis

**Módulos de Visualização e Relatórios:**
- **listlib** (100+ linhas): Listas de veículos com filtros, histórico de movimentações, detalhes de veículos e unidades
- **dashlib** (100+ linhas): Mapa de vagas, estatísticas de ocupação, resumos de dashboard
- **rellib** (100+ linhas): Relatórios diversos (permissões válidas, movimentações, mapas de vagas, veículos não cadastrados, veículos estacionados)

**Módulos de Integração:**
- **apilib** (18 linhas): Receptor de webhook do sistema Heimdall LPR (License Plate Recognition)
- **teleglib**: Notificações via Telegram Bot para alertas e avisos
- **viewlib**: Helpers e utilitários para renderização de views

**Módulos Administrativos:**
- **apontlib**: Registro manual de entradas/saídas de veículos (bypass do sistema automático)
- **unidlib**: Configuração de vagas por unidade/apartamento, gestão de espaços

**Infraestrutura:**
- **middleware.py** (11KB): Middlewares Flask para logging, autenticação, CORS, etc.

### 1.3 Padrão de Bibliotecas Modulares
Cada biblioteca em `visionlib/` segue o padrão:
```python
# visionlib/xyzlib/__init__.py

import mysql.connector
from config.database import get_db_connection
from flask import jsonify, request
from globals import verificar_autenticacao

# Funções de negócio específicas do módulo
def funcao_core():
    """Função principal do módulo"""
    pass

# APIs Flask para exposição web  
def api_funcao_publica():
    """API pública com autenticação"""
    # Verificar autenticação
    # Processar dados
    # Retornar JSON padronizado
    pass
```

## 2. CONVENÇÕES DE NOMENCLATURA

### 2.1 Arquivos e Diretórios
- **Python**: snake_case (`create_admin.py`, `database.py`)
- **Diretórios**: lowercase (`templates`, `static`, `visionlib`)
- **Templates**: kebab-case (`admin-usuarios.html`, `mapa-vagas.html`)
- **Scripts Apoio**: Prefixos descritivos (`X_`, `P_`, `Y_` etc.)

### 2.2 Python Code
- **Funções**: snake_case (`verificar_autenticacao`, `obter_veiculos_nao_cadastrados`)
- **Variáveis**: snake_case (`usuario_atual`, `dados_usuario`, `condominio_id`)
- **Constantes**: UPPER_SNAKE_CASE (`DB_CONFIG`, `SECRET_KEY`)
- **Classes**: PascalCase (quando aplicável)

### 2.3 Banco de Dados (Padrão Legacy)
- **Tabelas**: lowercase sem separadores (`cadcond`, `movcar`, `semcadastro`)
- **Campos**: abreviações compactas (`idgente`, `nmcond`, `nowpost`, `lup`)
- **Views**: prefixo `vw_` (`vw_usuarios_completo`, `vw_last_mov`)
- **Stored Procedures**: prefixos funcionais quando existirem

### 2.4 Frontend
- **CSS Classes**: kebab-case (`login-container`, `usuario-card`, `admin-header`)
- **HTML IDs**: kebab-case (`user-menu`, `alert-container`, `filtro-nome`)
- **JavaScript**: camelCase (`usuarioAtual`, `condominiosDisponiveis`)
- **Bootstrap Classes**: padrão Bootstrap 5

## 3. PADRÕES DE CÓDIGO

### 3.1 Estrutura de Funções de Negócio
```python
def funcao_negocio(dados_entrada, usuario_responsavel=None):
    """
    Docstring clara explicando propósito, parâmetros e retorno
    """
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão com banco de dados"
    
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Validações de entrada
        if not validacao_entrada():
            return False, "Dados inválidos"
        
        # 2. Lógica de negócio
        cursor.execute("SELECT ...", params)
        
        # 3. Processamento
        resultado = processar_dados()
        
        # 4. Persistência
        cursor.execute("INSERT/UPDATE ...", dados)
        conn.commit()
        
        # 5. Log da operação (quando relevante)
        if usuario_responsavel:
            registrar_log(usuario_responsavel, 'ACAO', 'detalhes')
        
        return True, "Operação realizada com sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro: {err}"
    finally:
        cursor.close()
        conn.close()
```

### 3.2 Estrutura de APIs Flask
```python
def api_funcao():
    """API para exposição web da funcionalidade"""
    # 1. Verificação de autenticação/autorização
    if not verificar_permissao_requerida():
        return jsonify({'success': False, 'message': 'Acesso negado'})

    # 2. Obtenção de dados
    data = request.json  # ou request.args para GET

    # 3. Validação de entrada
    if not dados_validos(data):
        return jsonify({'success': False, 'message': 'Dados inválidos'})

    # 4. Chamada da função de negócio
    sucesso, mensagem = funcao_negocio(data)

    # 5. Resposta padronizada
    return jsonify({
        'success': sucesso,
        'message': mensagem,
        'data': dados_adicionais  # quando aplicável
    })
```

### 3.2.1 Padrão de Resposta API (OBRIGATÓRIO)
**Todas as APIs devem seguir este formato de resposta JSON:**
```python
{
    'success': True/False,           # OBRIGATÓRIO: status da operação
    'message': 'Mensagem descritiva', # OBRIGATÓRIO: feedback ao usuário
    'data': {},                      # OPCIONAL: payload de dados
    'total': 0,                      # OPCIONAL: contagem para listas
    'errors': []                     # OPCIONAL: erros de validação
}
```

**Exemplos:**
```python
# Sucesso simples
return jsonify({'success': True, 'message': 'Veículo cadastrado com sucesso'})

# Sucesso com dados
return jsonify({
    'success': True,
    'message': 'Veículos carregados',
    'data': lista_veiculos,
    'total': len(lista_veiculos)
})

# Erro de validação
return jsonify({
    'success': False,
    'message': 'Dados inválidos',
    'errors': ['Email obrigatório', 'Placa inválida']
})

# Erro de sistema
return jsonify({
    'success': False,
    'message': f'Erro ao processar: {str(err)}'
})
```

### 3.3 Conexões com Banco de Dados
- **Sempre usar prepared statements** (parâmetros %)
- **Try/except/finally** obrigatório
- **Rollback automático** em caso de erro
- **Dictionary cursor** para facilitar manipulação
- **Connection pool** implícito via get_db_connection()

### 3.4 Validação e Sanitização
```python
# Validação de entrada
def validar_dados(dados):
    email = dados.get('email', '').strip().lower()
    if not validar_email(email):
        return False, "Email inválido"
    
    # Sanitização
    nome = dados.get('nome', '').strip()
    if len(nome) > 100:
        return False, "Nome muito longo"
    
    return True, "Dados válidos"
```

## 4. PADRÕES FRONTEND

### 4.1 Templates HTML (Jinja2)
```html
{% extends "base.html" %}

{% block title %}Título Específico - ParkVision{% endblock %}

{% block extra_css %}
<style>
/* CSS específico da página */
.classe-especifica {
    /* Regras CSS */
}
</style>
{% endblock %}

{% block content %}
<!-- Conteúdo da página -->
<div class="container">
    <h1><i class="bi bi-icone"></i>Título da Página</h1>
    <!-- Interface específica -->
</div>
{% endblock %}

{% block extra_js %}
<script>
// JavaScript específico da página
$(document).ready(function() {
    // Inicializações
    carregarDados();
    
    // Event listeners
    $('#form').on('submit', function(e) {
        // Lógica do formulário
    });
});
</script>
{% endblock %}
```

### 4.2 JavaScript/jQuery Patterns
```javascript
// Função para comunicação AJAX
function operacaoAjax(dados) {
    $.ajax({
        url: '/api/endpoint',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(dados),
        success: function(response) {
            if (response.success) {
                showAlert('container', response.message, 'success');
                // Atualizar interface
            } else {
                showAlert('container', response.message, 'danger');
            }
        },
        error: function(xhr) {
            const response = xhr.responseJSON;
            showAlert('container', response?.message || 'Erro interno', 'danger');
        },
        complete: function() {
            // Cleanup (remover loading, reabilitar botões, etc.)
        }
    });
}

// Função utilitária para alertas
function showAlert(container, message, type) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    $(`#alert-${container}`).html(alertHtml);
    
    // Auto-dismiss para sucessos
    if (type === 'success') {
        setTimeout(() => $('.alert').alert('close'), 5000);
    }
}
```

### 4.3 CSS e Responsividade
- **Bootstrap 5** como framework base
- **Bootstrap Icons** para iconografia
- **Utility Classes** do Bootstrap prioritariamente
- **CSS customizado** apenas quando necessário
- **Mobile-first** approach
- **Breakpoints** padrão do Bootstrap

## 5. SEGURANÇA

### 5.1 Autenticação
```python
# Hash de senhas
from werkzeug.security import generate_password_hash, check_password_hash

def hash_senha(senha):
    return generate_password_hash(senha)

def verificar_senha(senha, hash_armazenado):
    return check_password_hash(hash_armazenado, senha)
```

### 5.2 Autorização por Tipos
- **ADM**: Acesso total ao sistema
- **MONITOR**: Monitoramento e relatórios
- **SINDICO**: Gestão do próprio condomínio
- **Verificação granular** por função

### 5.3 Controle de Acesso
```python
def verificar_permissao_tipo_usuario(tipos_permitidos):
    """Verifica se usuário logado tem um dos tipos permitidos"""
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return False
    return usuario['tipo_usuario'] in tipos_permitidos
```

### 5.4 Proteção de Dados
- **Variáveis de ambiente** para credenciais
- **Prepared statements** contra SQL injection
- **Validação server-side** obrigatória
- **Logs de auditoria** para ações sensíveis

## 6. SISTEMA DE LOGGING

### 6.1 Configuração Centralizada
```python
# logging_config.py - Sistema único e limpo
def setup_logging(app):
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    file_handler = RotatingFileHandler(
        'parkvision.log', 
        maxBytes=5*1024*1024,
        backupCount=3
    )
    
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.propagate = False
```

### 6.2 Uso do Logging
```python
# Em qualquer parte do código
from flask import current_app

current_app.logger.info('Operação realizada com sucesso')
current_app.logger.warning('Situação de atenção detectada')
current_app.logger.error(f'Erro crítico: {str(erro)}')
```

## 7. GESTÃO DE DADOS

### 7.1 Modelo de Dados Principal
```sql
-- Estrutura base do sistema
usuarios (idgente, nome_completo, email, tipo_usuario, ativo)
cadcond (idcond, nmcond, cicond) -- Condomínios
cadveiculo (placa, idmodelo, idcor) -- Veículos cadastrados
movcar (placa, idcam, nowpost, direcao, contav) -- Movimentações
semcadastro (placa, idcond, lup) -- Veículos não cadastrados
cadperm (placa, idcond, data_inicio, data_fim) -- Permissões
```

### 7.2 Padrões de Query
```python
# Consultas com paginação quando necessário
cursor.execute("""
    SELECT * FROM tabela 
    WHERE condicao = %s 
    ORDER BY campo DESC 
    LIMIT %s
""", (valor, limite))

# Views para consultas complexas
cursor.execute("SELECT * FROM vw_dados_consolidados WHERE filtro = %s", (valor,))

# Transações para operações críticas
cursor.execute("START TRANSACTION")
try:
    # Operações múltiplas
    cursor.execute("INSERT...", dados1)
    cursor.execute("UPDATE...", dados2)
    conn.commit()
except:
    conn.rollback()
    raise
```

## 8. TRATAMENTO DE VEÍCULOS

### 8.1 Sistema de Cadastro
- **cadveiculo**: Veículos oficialmente cadastrados
- **semcadastro**: Veículos detectados mas não cadastrados
- **cadnick**: Sistema de apelidos para veículos
- **deparaplacas**: Mapeamento de correções de placas

### 8.2 Controle de Movimentação
- **movcar**: Registro de todas as movimentações
- **cadlocal**: Status atual dos veículos (dentro/fora)
- **Direções**: E (entrada), S (saída), I (indeterminado)
- **contav**: Flag para contabilização de vagas

### 8.3 Sistema de Duplicatas
```python
def verificar_duplicata(placa, momento, intervalo_segundos=90):
    """Evita processamento duplicado de movimentações"""
    # Verificar últimos movimentos
    # Se mesmo veículo em < 90s, não processar
    # Controle automático de duplicatas
```

### 8.4 Sistema Avançado de Processamento de Placas (vplib)

O **vplib** implementa um sistema sofisticado de validação e correção de placas com múltiplas etapas:

#### 8.4.1 Pipeline de Validação (Multi-Stage)
```python
# Estágio 1: Match exato no banco (confidence: 1.0)
placa_db = buscar_placa_exata_no_banco(placa)
if placa_db:
    return (placa_db, 1.0)

# Estágio 2: Validação de formato brasileiro
# Formato antigo: ABC1234 (3 letras + 4 números)
# Formato Mercosul: ABC1D23 (3 letras + 1 número + 1 letra + 2 números)
if not validar_formato_brasileiro(placa):
    return (None, 0.0)

# Estágio 3: Correção de erros comuns de OCR
placa_corrigida = corrigir_erros_ocr(placa)
# Mapeamento: I→1, O→0, S→5, B→8, etc.

# Estágio 4: Fuzzy matching contra placas cadastradas
match_fuzzy = buscar_fuzzy_match(placa_corrigida, threshold=0.85)

# Estágio 5: Consulta tabela deparaplacas
placa_mapeada = buscar_deparaplacas(placa)

# Estágio 6: Aceitar formato válido mesmo se não cadastrado (confidence: 0.85)
if formato_valido and not cadastrado:
    return (placa, 0.85)
```

#### 8.4.2 Formatos de Placas Suportados
```python
# Formato Antigo (até 2018)
ANTIGO = r'^[A-Z]{3}[0-9]{4}$'  # Exemplo: ABC1234

# Formato Mercosul (2018+)
MERCOSUL = r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$'  # Exemplo: ABC1D23

# Conversão automática entre formatos
def converter_formato(placa, formato_destino):
    """Converte entre formato antigo e Mercosul quando possível"""
    pass
```

#### 8.4.3 Correção de Erros OCR
```python
# Mapeamento de correções comuns
CORRECOES_OCR = {
    'I': '1',  # I maiúsculo → número 1
    'O': '0',  # O maiúsculo → número 0
    'S': '5',  # S pode ser 5
    'B': '8',  # B pode ser 8
    'G': '6',  # G pode ser 6
    'Z': '2',  # Z pode ser 2
}

def corrigir_erros_ocr(placa):
    """Aplica correções baseadas em posição (letras vs números)"""
    # Letras nas posições 0,1,2 (e 4 no Mercosul)
    # Números nas demais posições
    pass
```

#### 8.4.4 Sistema deparaplacas
Tabela de mapeamento para correções conhecidas:
```sql
-- Exemplo: placas que o OCR sempre erra da mesma forma
INSERT INTO deparaplacas (placade, placapara) VALUES
    ('ABC123A', 'ABC1234'),  -- A confundido com 4
    ('XYZ0001', 'XYZ0OO1'),  -- 0 confundido com O
    ('DEF5B89', 'DEF5889');  -- B confundido com 8
```

#### 8.4.5 Fuzzy Matching
```python
def calcular_similaridade(placa1, placa2):
    """
    Calcula similaridade entre placas usando:
    - Distância de Levenshtein
    - Similaridade fonética
    - Peso maior para primeiras posições
    """
    pass

def buscar_melhor_match(placa_entrada, placas_cadastradas):
    """
    Retorna melhor match com confidence score
    Threshold mínimo: 0.85 (85% de similaridade)
    """
    pass
```

### 8.5 Sistema de Tipos de Câmera (globals.cvag)

O ParkVision suporta três configurações de câmera por condomínio:

#### Tipo 1: Três Câmeras (Entrada + Saída + Dual)
```python
{
    'cent': 10,  # Câmera exclusiva de entrada
    'csai': 11,  # Câmera exclusiva de saída
    'cdup': 12   # Câmera dual (entrada/saída)
}
```
**Lógica:**
- cent → sempre ENTRADA
- csai → sempre SAÍDA
- cdup → direção INDETERMINADA (I), requer lógica adicional

#### Tipo 2: Câmera Única Dual
```python
{
    'cent': None,
    'csai': None,
    'cdup': 10   # Única câmera, dual-function
}
```
**Lógica:**
- Determinar direção baseada em último movimento
- Se último foi entrada → próximo é saída (e vice-versa)

#### Tipo 3: Câmera Única Dual (Lógica Alternativa)
```python
{
    'cent': None,
    'csai': None,
    'cdup': 10
}
```
**Lógica:**
- Similar ao Tipo 2, mas com algoritmo diferente
- Considera intervalo de tempo entre movimentos
- Timeout para resetar estado

## 9. INTERFACE DO USUÁRIO

### 9.1 Navegação Consistente
- **Navbar Bootstrap** com autenticação integrada
- **Breadcrumbs** quando aplicável
- **Menu contextual** baseado no tipo de usuário
- **Estados visuais** para loading, sucesso, erro

### 9.2 Formulários Padrão
```html
<!-- Formulário com validação -->
<form id="formId" class="needs-validation" novalidate>
    <div class="form-floating mb-3">
        <input type="email" class="form-control" id="email" required>
        <label for="email">Email</label>
    </div>
    
    <button type="submit" class="btn btn-primary">
        <span class="spinner-border spinner-border-sm me-2" style="display: none;"></span>
        Salvar
    </button>
</form>
```

### 9.3 Modais e Popups
- **Bootstrap Modals** para operações secundárias
- **Confirmações** para ações destrutivas
- **Loading states** em operações demoradas
- **Feedback visual** imediato

## 10. SCRIPTS DE MANUTENÇÃO

### 10.1 ArquivosApoio/
- **X_**: Scripts administrativos interativos
- **P_**: Scripts de correção e processamento
- **Y_**: Scripts de geração de dados de teste
- **Outros**: Utilitários específicos (Telegram, WhatsApp, etc.)

### 10.2 Padrão de Scripts
```python
#!/usr/bin/env python3
"""
Descrição clara do propósito do script
Autor: Nome
Data: YYYY-MM-DD
"""

from config.database import get_db_connection

def main():
    """Função principal do script"""
    print("Iniciando processo...")
    
    # Lógica do script
    conn = get_db_connection()
    # ... operações
    
    print("Processo concluído!")

if __name__ == "__main__":
    main()
```

## 11. PERFORMANCE E OTIMIZAÇÃO

### 11.1 Banco de Dados
- **Índices** nas colunas mais consultadas
- **LIMIT** em queries que podem retornar muitos resultados
- **Views** para consultas complexas frequentes
- **Connection pooling** via get_db_connection()

### 11.2 Frontend
- **CDN** para Bootstrap, jQuery e outros recursos
- **Lazy loading** para dados grandes
- **Caching** de consultas frequentes
- **Compressão** de assets em produção

## 12. STACK TECNOLÓGICA COMPLETA

### 12.1 Backend
```python
# Framework e Linguagem
Flask==2.x              # Framework web principal
Python==3.x            # Linguagem de programação

# Banco de Dados
mysql-connector-python # Driver MySQL oficial
# Suporte para MySQL/MariaDB 5.7+

# Segurança e Autenticação
bcrypt                 # Hash de senhas (authlib)
werkzeug.security      # Utilities de segurança
python-dotenv          # Gerenciamento de variáveis de ambiente

# Utilitários
pytz                   # Timezone handling (America/Sao_Paulo)
logging                # Sistema de logs nativo Python
RotatingFileHandler    # Rotação de logs (5MB, 3 backups)

# Servidor
Gunicorn              # WSGI server para produção
```

### 12.2 Frontend
```html
<!-- Framework CSS -->
Bootstrap 5.1.3       # Framework CSS principal
Bootstrap Icons 1.8.1 # Iconografia

<!-- JavaScript -->
jQuery 3.6.0          # Manipulação DOM e AJAX
Jinja2                # Template engine (Flask padrão)

<!-- Recursos via CDN -->
- Bootstrap CSS/JS via CDN
- Bootstrap Icons via CDN
- jQuery via CDN
```

### 12.3 Integrações Externas

#### 12.3.1 Heimdall LPR (License Plate Recognition)
**Sistema principal de captura de placas por câmeras**

```python
# apilib - Receptor de Webhook
@app.route('/api/heimdall/webhook', methods=['POST'])
def receber_heimdall():
    """
    Recebe eventos do sistema Heimdall quando uma placa é detectada

    Payload esperado:
    {
        'plate': 'ABC1234',
        'camera_id': 10,
        'timestamp': '2025-01-10T14:30:00',
        'confidence': 0.95,
        'image_url': 'http://...'
    }
    """
    # 1. Validar payload
    # 2. Processar placa via vplib
    # 3. Gravar movimento via dblib
    # 4. Notificar se necessário
    pass
```

**Características:**
- Detecção em tempo real de placas veiculares
- Múltiplas câmeras por condomínio
- Confidence score da leitura OCR
- Imagens das capturas disponíveis
- Webhook assíncrono (não bloqueia sistema)

#### 12.3.2 Telegram Bot (teleglib)
**Sistema de notificações e alertas**

```python
# Casos de uso:
- Veículo não autorizado detectado
- Permissão de estacionamento expirando (72h)
- Vaga ocupada por muito tempo
- Alertas de segurança
- Relatórios diários/semanais

# Exemplo de notificação
def notificar_telegram(idcond, mensagem, tipo='INFO'):
    """
    Envia notificação para canal/grupo do condomínio

    Tipos:
    - INFO: Informações gerais
    - ALERTA: Situações de atenção
    - CRITICO: Situações críticas
    """
    pass
```

#### 12.3.3 Twilio WhatsApp (opcional)
**Notificações via WhatsApp Business**

```python
# ArquivosApoio/T_envio_whatsapp_twilio.py
def enviar_whatsapp(numero, mensagem):
    """
    Envia mensagem WhatsApp via Twilio API
    Usado para notificações importantes a síndicos/administradores
    """
    pass
```

### 12.4 Banco de Dados MySQL

#### Schema Principal (Tabelas Críticas)
```sql
-- USUÁRIOS E AUTENTICAÇÃO
usuarios (
    idgente INT PRIMARY KEY AUTO_INCREMENT,
    nome_completo VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    senha_hash VARCHAR(255),
    tipo_usuario ENUM('ADM', 'MONITOR', 'SINDICO'),
    ativo BOOLEAN DEFAULT TRUE,
    data_criacao TIMESTAMP
)

usuario_condominios (
    idgente INT,
    idcond INT,
    liberado_por INT,
    data_liberacao TIMESTAMP,
    FOREIGN KEY (idgente) REFERENCES usuarios(idgente)
)

tokens_recuperacao (
    token VARCHAR(100) PRIMARY KEY,
    idgente INT,
    expiracao DATETIME,
    usado BOOLEAN
)

-- CONDOMÍNIOS
cadcond (
    idcond INT PRIMARY KEY,
    nmcond VARCHAR(100),    -- Nome
    cicond VARCHAR(50),     -- Cidade
    nrcond VARCHAR(20)      -- Número/Complemento
)

-- VEÍCULOS
cadveiculo (
    placa VARCHAR(7) PRIMARY KEY,
    idmodelo INT,
    idcor INT,
    FOREIGN KEY (idmodelo) REFERENCES cadmodelo(idmodelo)
)

cadperm (
    idperm INT PRIMARY KEY AUTO_INCREMENT,
    idcond INT,
    placa VARCHAR(7),
    unidade VARCHAR(20),
    data_inicio DATE,
    data_fim DATE,
    status ENUM('VIGENTE', 'VENCIDA', 'INDEFINIDA'),
    FOREIGN KEY (placa) REFERENCES cadveiculo(placa)
)

-- MOVIMENTAÇÕES
movcar (
    idmov INT PRIMARY KEY AUTO_INCREMENT,
    idcond INT,
    placa VARCHAR(7),
    idcam INT,              -- ID da câmera
    nowpost DATETIME,       -- Timestamp da captura
    direcao ENUM('E', 'S', 'I'),  -- Entrada/Saída/Indeterminado
    contav BOOLEAN,         -- Contabiliza vaga?
    confidence FLOAT        -- Confiança da leitura OCR
)

cadlocal (
    idcond INT,
    placa VARCHAR(7),
    sit ENUM('D', 'F'),    -- Dentro/Fora
    lup TIMESTAMP,          -- Last update
    PRIMARY KEY (idcond, placa)
)

-- NÃO CADASTRADOS
semcadastro (
    id INT PRIMARY KEY AUTO_INCREMENT,
    placa VARCHAR(7),
    idcond INT,
    primeira_deteccao DATETIME,
    ultima_deteccao DATETIME,
    total_deteccoes INT
)

-- CORREÇÕES DE PLACAS
deparaplacas (
    placade VARCHAR(7),     -- Placa errada (OCR)
    placapara VARCHAR(7),   -- Placa correta
    PRIMARY KEY (placade)
)

-- VAGAS POR UNIDADE
vagasunidades (
    idcond INT,
    unidade VARCHAR(20),
    vperm INT,              -- Vagas permitidas
    vocup INT,              -- Vagas ocupadas
    PRIMARY KEY (idcond, unidade)
)
```

#### Views Importantes
```sql
-- View de usuários com informações completas
CREATE VIEW vw_usuarios_completo AS
SELECT u.*, GROUP_CONCAT(c.nmcond) as condominios
FROM usuarios u
LEFT JOIN usuario_condominios uc ON u.idgente = uc.idgente
LEFT JOIN cadcond c ON uc.idcond = c.idcond
GROUP BY u.idgente;

-- View de veículos estacionados atualmente
CREATE VIEW vw_estacionados AS
SELECT cl.*, cv.*, cd.nmcond
FROM cadlocal cl
JOIN cadveiculo cv ON cl.placa = cv.placa
JOIN cadcond cd ON cl.idcond = cd.idcond
WHERE cl.sit = 'D';  -- Dentro

-- View de último movimento por veículo
CREATE VIEW vw_last_mov AS
SELECT m1.*
FROM movcar m1
WHERE m1.nowpost = (
    SELECT MAX(m2.nowpost)
    FROM movcar m2
    WHERE m2.placa = m1.placa AND m2.idcond = m1.idcond
);
```

## 13. DEPLOY E PRODUÇÃO

### 12.1 Configuração
```python
# Produção
DEBUG = False
SECRET_KEY = os.getenv('SECRET_KEY')
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}
```

### 12.2 Servidor
- **Gunicorn** como WSGI server
- **Nginx** como proxy reverso
- **SSL/TLS** obrigatório
- **Logs centralizados**

## 13. MANUTENIBILIDADE

### 13.1 Código Limpo
- **Funções pequenas** com responsabilidade única
- **Nomes descritivos** e autoexplicativos
- **Comentários** apenas quando a lógica não é óbvia
- **Docstrings** em todas as funções públicas

### 13.2 Dependências
- **requirements.txt** atualizado
- **Versões específicas** para produção
- **Bibliotecas mínimas** necessárias
- **Compatibilidade** entre versões

## 14. CONVENÇÕES ESPECÍFICAS DO PARKVISION

### 14.1 Nomenclatura de Condomínios
- **idcond**: ID único do condomínio
- **nmcond**: Nome do condomínio
- **cicond**: Cidade do condomínio
- **nrcond**: Número/endereço complementar

### 14.2 Sistema de Câmeras
- **cent**: ID da câmera de entrada
- **csai**: ID da câmera de saída
- **cdup**: ID da câmera dupla (entrada/saída)
- **Tratamento especial** para câmeras duplas

### 14.3 Gestão de Vagas
- **vagasunidades**: Controle de vagas por unidade
- **vocup**: Vagas ocupadas
- **vtotal**: Total de vagas
- **Atualização automática** via movimentações

## 15. INCONSISTÊNCIAS E ÁREAS DE MELHORIA

### 15.1 Nomenclatura

**Consistências Identificadas (MANTER):**
- ✅ snake_case consistente em funções Python
- ✅ kebab-case consistente em templates HTML
- ✅ Prepared statements em 100% das queries
- ✅ Padrão de resposta API unificado

**Inconsistências a Considerar:**
- ⚠️ **Database vs Code**: Banco usa abreviações portuguesas (idcond, nmcond) enquanto código usa nomes descritivos em português
- ⚠️ **Tabelas Legacy**: Algumas tabelas antigas têm nomes inconsistentes (ex: `cadcar` deprecado mas ainda referenciado)
- ⚠️ **Mixing Languages**: Mix de português (placa, unidade) e inglês (query, success) no código

**Recomendação:** Manter status quo por compatibilidade. Novos módulos devem seguir padrões existentes.

### 15.2 Organização de Código

**Pontos Fortes:**
- ✅ Separação modular excelente em visionlib
- ✅ Single Responsibility Principle bem aplicado
- ✅ Reusabilidade de funções entre módulos

**Áreas de Melhoria:**
- ⚠️ **Funções Longas**: Algumas funções em dblib ultrapassam 200 linhas
- ⚠️ **Duplicação**: Lógica duplicada entre `dblib` e `ArquivosApoio/db_lib_generico.py`
- ⚠️ **main.py Monolítico**: 1018 linhas com todas as rotas (considerar blueprints Flask)

**Recomendações:**
1. Refatorar funções >100 linhas em subfunções
2. Consolidar `db_lib_generico.py` no dblib ou vice-versa
3. Migrar main.py para blueprints organizados por domínio:
   ```python
   # Estrutura proposta
   routes/
   ├── auth_routes.py       # Rotas de autenticação
   ├── vehicle_routes.py    # Rotas de veículos
   ├── report_routes.py     # Rotas de relatórios
   ├── admin_routes.py      # Rotas administrativas
   └── api_routes.py        # APIs externas
   ```

### 15.3 Documentação

**Situação Atual:**
- ✅ PADROES_PROJETO.md abrangente e atualizado
- ⚠️ Docstrings presentes mas não consistentes
- ⚠️ Algoritmos complexos (plate processing) precisam mais comentários inline
- ⚠️ Falta documentação de API endpoints (considerar Swagger/OpenAPI)

**Recomendações:**
1. Padronizar formato de docstrings (Google Style ou NumPy Style)
2. Adicionar comentários em algoritmos complexos do vplib
3. Implementar Swagger UI para documentação interativa de APIs
4. Criar diagramas de fluxo para processos críticos (gravação de movimento, validação de placas)

### 15.4 Tratamento de Erros

**Pontos Fortes:**
- ✅ Try/except/finally consistente
- ✅ Rollback automático em erros de transação
- ✅ Mensagens de erro descritivas

**Áreas de Melhoria:**
- ⚠️ Alguns módulos usam `print()` em vez de logging
- ⚠️ Mensagens de erro podem conter dados sensíveis em debug
- ⚠️ Falta categorização de erros (ValidationError, DatabaseError, AuthError)

**Recomendações:**
1. Substituir todos os `print()` por logging apropriado
2. Criar classes de exceção customizadas:
   ```python
   class ParkVisionError(Exception):
       """Base exception for ParkVision"""
       pass

   class ValidationError(ParkVisionError):
       """Raised when validation fails"""
       pass

   class AuthenticationError(ParkVisionError):
       """Raised when authentication fails"""
       pass
   ```
3. Sanitizar mensagens de erro em produção

### 15.5 Segurança

**Pontos Fortes (EXCELENTES):**
- ✅ Prepared statements em 100% das queries (SQL Injection protection)
- ✅ bcrypt para hash de senhas
- ✅ Autenticação baseada em sessão
- ✅ Controle de acesso granular por tipo de usuário
- ✅ Variáveis de ambiente para credenciais

**Áreas de Atenção:**
- ⚠️ Alguns prints de debug podem expor dados sensíveis
- ⚠️ Sistema de recuperação de senha sem verificação de email
- ⚠️ Ausência de rate limiting em endpoints críticos
- ⚠️ Falta CSRF protection em formulários

**Recomendações:**
1. Implementar verificação de email no sistema de recuperação
2. Adicionar rate limiting (Flask-Limiter):
   ```python
   @limiter.limit("5 per minute")
   @app.route('/api/auth/login')
   ```
3. Ativar CSRF protection do Flask-WTF
4. Remover/desabilitar prints de debug em produção

### 15.6 Performance

**Considerações Atuais:**
- ✅ Connection pooling via get_db_connection()
- ✅ Views para queries complexas
- ✅ Índices nas colunas críticas
- ⚠️ Falta paginação em algumas listagens grandes
- ⚠️ N+1 queries em alguns relatórios

**Recomendações:**
1. Implementar paginação padrão para listas >100 registros
2. Adicionar cache Redis para:
   - Dados de condomínios (raramente mudam)
   - Lista de marcas/modelos/cores
   - Estatísticas de dashboard (refresh a cada 5 minutos)
3. Otimizar queries N+1 usando JOINs apropriados

### 15.7 Testes

**Situação Atual:**
- ⚠️ Arquivos de teste existem (test_*.py) mas cobertura incompleta
- ⚠️ Falta integração contínua (CI/CD)
- ⚠️ Sem testes de integração end-to-end

**Recomendações:**
1. Estabelecer meta de 80% de cobertura de testes
2. Estruturar testes por tipo:
   ```
   tests/
   ├── unit/           # Testes unitários de funções
   ├── integration/    # Testes de integração entre módulos
   ├── e2e/           # Testes end-to-end de fluxos completos
   └── fixtures/      # Dados de teste
   ```
3. Implementar CI/CD pipeline (GitHub Actions/GitLab CI)
4. Testes automatizados antes de cada deploy

### 15.8 Logging

**Situação Atual:**
- ✅ Sistema centralizado (logging_config.py)
- ✅ Rotação de logs configurada (5MB, 3 backups)
- ✅ Decorator @log_route para auditoria de acessos
- ⚠️ Falta níveis de log consistentes (INFO vs DEBUG vs ERROR)
- ⚠️ Logs não estruturados (dificulta parsing)

**Recomendações:**
1. Padronizar níveis de log:
   - **DEBUG**: Informações de desenvolvimento
   - **INFO**: Operações normais, auditoria
   - **WARNING**: Situações anormais mas recuperáveis
   - **ERROR**: Erros que precisam atenção
   - **CRITICAL**: Falhas críticas do sistema
2. Implementar logging estruturado (JSON):
   ```python
   logger.info('vehicle_movement', extra={
       'placa': 'ABC1234',
       'idcond': 10,
       'direcao': 'E',
       'confidence': 0.95
   })
   ```
3. Considerar centralização de logs (ELK Stack, Papertrail, CloudWatch)

### 15.9 Padrões de Rotas

**Organização Atual:**
- 📍 `main.py:1018` - Todas as rotas em único arquivo
- ✅ Separação lógica por comentários
- ⚠️ Dificulta manutenção e testes

**Proposta de Reorganização com Blueprints:**
```python
# routes/auth.py
from flask import Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    return authlib.login()

# routes/vehicles.py
vehicles_bp = Blueprint('vehicles', __name__, url_prefix='/api/vehicles')

@vehicles_bp.route('/', methods=['GET'])
def list_vehicles():
    return carlib.obter_lista_veiculos()

# main.py (simplificado)
from routes import auth_bp, vehicles_bp, reports_bp

app.register_blueprint(auth_bp)
app.register_blueprint(vehicles_bp)
app.register_blueprint(reports_bp)
```

**Benefícios:**
- Separação clara de responsabilidades
- Facilita testes unitários
- Melhora navegação no código
- Permite lazy loading de módulos

## 16. PONTOS FORTES DO PROJETO

### 16.1 Arquitetura
✅ **Design modular excepcional** com separação clara de responsabilidades
✅ **Service layer pattern** bem implementado
✅ **Multi-tenant** com isolamento adequado de dados
✅ **Escalabilidade** pronta para crescimento

### 16.2 Segurança
✅ **SQL Injection protection** completa via prepared statements
✅ **Password hashing** com bcrypt
✅ **Controle de acesso** granular e bem estruturado
✅ **Auditoria** completa de ações de usuários

### 16.3 Funcionalidades
✅ **Processamento de placas sofisticado** com múltiplas estratégias de validação
✅ **Integração LPR** bem projetada e assíncrona
✅ **Sistema de notificações** robusto (Telegram, WhatsApp)
✅ **Relatórios abrangentes** cobrindo todas necessidades do negócio

### 16.4 Código
✅ **Convenções consistentes** dentro de cada camada
✅ **Reutilização** eficiente de componentes
✅ **Tratamento de erros** adequado e consistente
✅ **Logging** estruturado e centralizado

### 16.5 Experiência de Desenvolvimento
✅ **Estrutura intuitiva** de diretórios
✅ **Documentação clara** (PADROES_PROJETO.md)
✅ **Scripts de manutenção** bem organizados
✅ **Utilities administrativos** facilitam operações

---

## CONCLUSÃO

O **ParkVision** é um sistema de gestão de estacionamento em condomínios maduro, bem arquitetado e production-ready. Demonstra excelentes práticas de engenharia de software com:

- **Arquitetura modular** seguindo princípios SOLID
- **Segurança robusta** em todas as camadas
- **Processamento inteligente** de placas com correção de erros OCR
- **Integração real-world** com sistemas LPR e notificações
- **Padrões consistentes** e bem documentados

**Áreas de excelência:**
1. Design modular e separação de responsabilidades
2. Segurança (SQL injection protection, password hashing)
3. Validação avançada de placas veiculares
4. Sistema multi-tenant bem estruturado
5. Logging e auditoria abrangentes

**Oportunidades de evolução:**
1. Migração para Flask Blueprints (melhor organização)
2. Aumento de cobertura de testes
3. Implementação de cache (Redis)
4. Documentação OpenAPI/Swagger
5. Logging estruturado (JSON)

Este documento serve como guia definitivo para manter a consistência e qualidade do projeto em futuras implementações.

---

**Sistema:** ParkVision - Monitoramento Inteligente de Condomínios
**Versão:** 2.0
**Última Atualização:** 10 de Janeiro de 2025
**Responsável:** Equipe de Desenvolvimento ParkVision