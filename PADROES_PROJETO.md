1# Padrões e Convenções do Projeto PromptVision

## 📋 Resumo Executivo

Este documento analisa a arquitetura, padrões de código, convenções de nomenclatura e estrutura organizacional do projeto PromptVision, um sistema de gestão de vagas de estacionamento em condomínios com integração LPR (License Plate Recognition).

---

## 🏗️ Arquitetura do Sistema

### **Padrão Arquitetural: Modular Monolítico**
- **Estrutura Principal**: Flask Web Application
- **Organização**: Bibliotecas modulares organizadas por domínio
- **Backend**: MySQL com conectores Python nativos
- **Frontend**: Templates HTML com JavaScript vanilla

### **Estrutura de Diretórios**
```
PromptVisionPoject/
├── main.py                    # Ponto de entrada da aplicação
├── globals.py                 # Variáveis globais e compatibilidade
├── config/
│   └── database.py           # Configurações de banco de dados
├── visionlib/                # Biblioteca principal modular
│   ├── apilib/               # Recepção de dados externos (Heimdall)
│   ├── authlib/              # Autenticação e autorização
│   ├── userlib/              # Gestão de usuários
│   ├── carlib/               # Gestão de veículos
│   ├── condlib/              # Gestão de condomínios
│   ├── dblib/                # Operações de banco de dados
│   ├── dashlib/              # Dashboard e métricas
│   ├── listlib/              # Listagens e consultas
│   ├── permlib/              # Gestão de permissões
│   ├── rellib/               # Relatórios
│   ├── teleglib/             # Integração Telegram
│   ├── vplib/                # Processamento de placas
│   └── middleware.py         # Decorators e middleware
├── templates/                # Templates HTML Jinja2
├── static/                   # Recursos estáticos (CSS/JS)
└── ArquivosApoio/           # Scripts auxiliares
```

---

## 🎯 Padrões de Nomenclatura

### **Variáveis e Funções**
- **Formato**: `snake_case` (Python PEP 8)
- **Exemplos**: 
  - `verificar_autenticacao_usuario()`
  - `data_inicio`, `condominio_id`
  - `nome_completo`, `tipo_usuario`

### **Classes** 
- **Formato**: `PascalCase` (limitado - projeto usa principalmente funções)
- **Não há classes explícitas** - arquitetura funcional

### **Constantes**
- **Formato**: `UPPER_SNAKE_CASE`
- **Exemplos**: 
  - `DB_CONFIG`, `BRASIL_TZ`
  - `CONDOMINIO_SENHAS`

### **Arquivos e Módulos**
- **Bibliotecas**: Sufixo `lib` (authlib, userlib, carlib)
- **Arquivos**: `snake_case.py`
- **Templates**: `kebab-case.html`

### **Banco de Dados**
- **Tabelas**: `camel_case_minusculo` (`cadcond`, `cadveiculo`, `movcar`)
- **Campos**: `snake_case` (`nome_completo`, `data_inicio`)
- **IDs**: Prefixo `id` (`idcond`, `idgente`, `idmodelo`)

### **URLs e Rotas**
- **Formato**: `kebab-case`
- **Exemplos**: 
  - `/veiculos-nao-cadastrados/`
  - `/relatorio-movimento-veiculos/`
  - `/api/auth/alterar-senha`

---

## 🔧 Convenções de Código

### **Imports e Dependências**
```python
# Ordem padrão dos imports:
# 1. Bibliotecas padrão Python
from datetime import datetime, timedelta
import secrets, re

# 2. Bibliotecas externas
from flask import Flask, jsonify, request, session
import mysql.connector
import bcrypt

# 3. Módulos locais  
from config.database import get_db_connection
from visionlib.authlib import verificar_autenticacao_usuario
```

### **Estrutura de Funções**
```python
def nome_funcao(parametros):
    """
    Docstring descrevendo a função
    Parâmetros: descrição dos parâmetros
    Retorna: descrição do retorno
    """
    # Validações primeiro
    if not parametros:
        return False, "Mensagem de erro"
    
    # Conexão com banco
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão"
    
    cursor = conn.cursor()
    try:
        # Lógica principal
        # ...
        conn.commit()
        return True, "Sucesso"
        
    except mysql.connector.Error as err:
        conn.rollback()
        return False, f"Erro: {err}"
    finally:
        cursor.close()
        conn.close()
```

### **APIs Flask**
```python
@app.route('/api/endpoint', methods=['POST'])
def api_nome_funcao():
    # Verificação de autenticação quando necessário
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    # Processamento
    data = request.json
    result = processar_dados(data)
    
    # Resposta padronizada
    return jsonify({
        'success': True/False,
        'message': 'Mensagem',
        'data': resultado_opcional
    })
```

### **Tratamento de Erros**
- **Padrão de retorno**: `(bool success, str message)`
- **Logs**: `print()` statements para debug
- **Rollback**: Sempre em transações de banco
- **Finally**: Cleanup de conexões

---

## 🏛️ Padrões Arquiteturais

### **1. Arquitetura Modular por Domínio**
- Cada biblioteca (`*lib`) representa um domínio específico
- Separação clara de responsabilidades
- Reutilização através de imports específicos

### **2. Service Layer Pattern**
- Funções de negócio separadas das rotas Flask
- APIs delegam para funções de serviço
- Validações centralizadas

### **3. Repository Pattern (Implícito)**
- Funções de banco agrupadas por domínio
- Abstração de queries SQL
- Reutilização de conexões

### **4. Middleware Pattern**
- Decorators para autenticação e autorização
- Middleware centralizado em `middleware.py`
- Rate limiting e logging

### **5. Template Method Pattern**
- Estruturas consistentes para operações CRUD
- Padrões de validação e tratamento de erro
- Templates de resposta JSON

---

## 🔐 Sistema de Autenticação

### **Modelo de Segurança**
- **Hash de senhas**: bcrypt
- **Sessões**: Flask sessions com chave secreta
- **Tokens**: Para recuperação de senha (24h validade)
- **Auditoria**: Log completo de ações de usuários

### **Níveis de Acesso**
- **ADM**: Acesso total ao sistema
- **MONITOR**: Acesso a relatórios e monitoramento
- **SINDICO**: Acesso limitado ao condomínio

### **Middleware de Autenticação**
```python
# Decorators disponíveis:
@requer_autenticacao()
@requer_tipo_usuario(['ADM'])
@requer_acesso_condominio()
@api_requer_admin
@rate_limit_por_usuario()
```

---

## 🗄️ Padrões de Banco de Dados

### **Convenções de Nomenclatura**
- **Prefixos por tipo**: 
  - `cad*` = Cadastros (`cadcond`, `cadveiculo`)
  - `mov*` = Movimentações (`movcar`)
  - `log*` = Logs (`log_usuarios`)
  - `vw_*` = Views (`vw_usuarios_completo`)

### **Campos Padrão**
- **IDs**: Auto increment, prefixo `id` + nome
- **Timestamps**: `data_criacao`, `lup` (last update)
- **Status**: `ativo` (boolean), `status` (enum)
- **Auditoria**: `criado_por`, `atualizado_por`

### **Relacionamentos**
- **FKs explícitas**: `idcond`, `idgente`, `idmodelo`
- **Tabelas de junção**: `usuario_condominios`
- **Soft deletes**: Campo `ativo` ao invés de DELETE

---

## 🌐 Padrões de APIs

### **Estrutura de URLs**
```
/                              # Páginas HTML
/api/                          # APIs JSON
/api/auth/                     # Autenticação
/api/admin/                    # Administrativo
/relatorio/                    # APIs de relatório
```

### **Respostas Padronizadas**
```json
{
    "success": true|false,
    "message": "Mensagem descritiva",
    "data": { ... },           // Opcional
    "error_code": "CODIGO"     // Para APIs
}
```

### **Métodos HTTP**
- **GET**: Consultas e listagens
- **POST**: Criações e ações
- **PUT**: Atualizações completas
- **DELETE**: Remoções (pouco usado)

---

## 📱 Frontend e Templates

### **Sistema de Templates**
- **Engine**: Jinja2 (Flask padrão)
- **Layout**: Template base (`base.html`)
- **Recursos**: CSS/JS em `/static/`
- **Responsividade**: Bootstrap (implícito)

### **Padrões JavaScript**
- **Vanilla JS**: Sem frameworks externos
- **AJAX**: Para comunicação com APIs
- **Validação**: Client-side + server-side

---

## 🔄 Integração Externa

### **Sistema Heimdall (LPR)**
- **Endpoint**: `/api/heimdall/webservice/lpr`
- **Método**: POST JSON
- **Processamento**: Assíncrono via `apilib`

### **Telegram**
- **Notificações**: Automáticas por eventos
- **Configuração**: Por condomínio
- **Biblioteca**: `python-telegram-bot`

---

## 📊 Sistema de Relatórios

### **Padrão de Relatórios**
- **APIs**: `/relatorio/{tipo}/{condominio_id}`
- **Views**: Páginas HTML dedicadas
- **Formato**: JSON + renderização client-side
- **Filtros**: Por período e condomínio

### **Tipos Disponíveis**
- Permissões válidas
- Movimento de veículos
- Mapa de vagas
- Veículos do condomínio
- Não cadastrados

---

## ⚡ Otimizações e Performance

### **Banco de Dados**
- **Views materialized**: Para consultas complexas
- **Índices**: Em campos de busca frequente
- **Connection pooling**: Conexões gerenciadas

### **Cache e Session**
- **Flask sessions**: Para autenticação
- **Rate limiting**: Por usuário/IP
- **Cleanup automático**: Tokens expirados

---

## 🧪 Testing e Debug

### **Arquivos de Teste**
```
test_access.py          # Testes de acesso
test_apis.py           # Testes de API
test_user.py           # Testes de usuário
test_real_session.py   # Testes de sessão
test_report_apis.py    # Testes de relatórios
```

### **Debug e Logging**
- **Print statements**: Debug no console
- **Log database**: Auditoria em tabelas
- **Error handling**: Try/catch padronizado

---

## 🚀 Deploy e Configuração

### **Dependências**
```
Flask==2.3.3           # Framework web
gunicorn==21.2.0       # WSGI server
mysql-connector-python # Driver MySQL
requests==2.31.0       # HTTP client
python-telegram-bot==22.3  # Telegram API
pytz                   # Timezone handling
```

### **Configuração de Ambiente**
- **Timezone**: America/Sao_Paulo (hardcoded)
- **Database**: MySQL (configurações em `config/database.py`)
- **Secrets**: Geração automática de chaves de sessão

---

## 📝 Recomendações para Futuras Implementações

### **1. Mantenha a Consistência**
- Siga os padrões de nomenclatura estabelecidos
- Use a estrutura modular existente (`*lib`)
- Mantenha o padrão de resposta JSON das APIs

### **2. Segurança**
- Sempre use os decorators de autenticação
- Valide dados de entrada (client + server)
- Registre ações importantes no log de auditoria

### **3. Banco de Dados**
- Use transações para operações críticas
- Sempre feche conexões no bloco `finally`
- Mantenha o padrão de nomenclatura de tabelas

### **4. APIs**
- Mantenha URLs RESTful
- Use validação de permissões por condomínio
- Retorne mensagens de erro descritivas

### **5. Testes**
- Crie testes para novas funcionalidades
- Use os arquivos de teste existentes como referência
- Teste tanto sucesso quanto cenários de erro

---

## 🎯 Exemplos Práticos

### **Criando Nova Biblioteca**
```python
# visionlib/novalib/__init__.py
from config.database import get_db_connection
from visionlib.authlib import verificar_autenticacao_usuario
from flask import jsonify, request

def nova_funcao():
    """Nova funcionalidade seguindo padrões"""
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão"
    
    # ... implementação
    
def api_nova_funcao():
    """API para nova funcionalidade"""
    autenticado, usuario = verificar_autenticacao_usuario()
    if not autenticado:
        return jsonify({'success': False, 'message': 'Não autorizado'})
    
    success, message = nova_funcao()
    return jsonify({'success': success, 'message': message})
```

### **Adicionando Nova Rota**
```python
# No main.py
from visionlib.novalib import api_nova_funcao

@app.route('/api/nova-funcao', methods=['POST'])
def route_nova_funcao():
    return api_nova_funcao()
```

---

## 📚 Conclusão

O projeto PromptVision demonstra uma arquitetura bem estruturada e consistente, com padrões claros que facilitam a manutenção e extensão do sistema. A organização modular, convenções de nomenclatura e padrões de código estabelecidos fornecem uma base sólida para futuras implementações.

**Pontos Fortes:**
- Arquitetura modular bem definida
- Padrões de nomenclatura consistentes
- Sistema de autenticação robusto
- APIs bem estruturadas
- Separação clara de responsabilidades

**Recomendações:**
- Continuar seguindo os padrões estabelecidos
- Manter a documentação atualizada
- Implementar testes unitários mais abrangentes
- Considerar migração para um sistema de logging mais robusto

Este documento serve como guia para desenvolvedores que trabalharão no projeto, garantindo que futuras implementações mantenham a consistência e qualidade do código existente.