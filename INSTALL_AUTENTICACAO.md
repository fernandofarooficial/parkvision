# 🔐 Instalação do Sistema de Autenticação por Usuário

## 📋 Pré-requisitos

1. Projeto ParkVision funcionando
2. MySQL/MariaDB configurado
3. Python com pip instalado

## 🚀 Instalação Passo a Passo

### 1. Instalar Dependência

```bash
pip install bcrypt==4.0.1
```

### 2. Aplicar Migrações no Banco de Dados

Execute o script SQL no seu banco de dados:

```bash
# Opção 1: Via linha de comando MySQL
mysql -u SEU_USUARIO -p SEU_BANCO_DE_DADOS < database_migration.sql

# Opção 2: Via interface gráfica (phpMyAdmin, MySQL Workbench, etc.)
# Abrir e executar o conteúdo do arquivo database_migration.sql
```

### 3. Criar Usuário Administrador

Execute o script Python para criar o usuário admin:

```bash
python create_admin.py
```

**Credenciais criadas:**
- 📧 **Email:** `admin@parkvision.com`
- 🔑 **Senha:** `admin123`
- 🏷️ **Tipo:** ADM (Administrador)

⚠️ **IMPORTANTE:** Altere a senha após o primeiro login!

### 4. Testar o Sistema

1. **Inicie o servidor:**
   ```bash
   python main.py
   ```

2. **Acesse no navegador:**
   ```
   http://localhost:5000/login
   ```

3. **Faça login com as credenciais:**
   - Email: `admin@parkvision.com`
   - Senha: `admin123`

4. **Se o login funcionar, você verá:**
   - Menu do usuário no canto superior direito
   - Badge "ADM" ao lado do nome
   - Acesso à "Gestão de Usuários" no dropdown

## 🎯 Funcionalidades Disponíveis

### Para Usuários ADM (Administradores)
- ✅ Acesso total a todos os condomínios
- ✅ Gestão de usuários (criar, editar, desativar)
- ✅ Aprovar/rejeitar solicitações de cadastro
- ✅ Liberar condomínios para usuários
- ✅ Acessar área administrativa em `/admin/usuarios`

### Para Usuários MONITOR
- ✅ Acesso de edição nos condomínios liberados
- ✅ Modificar dados de veículos e permissões
- ✅ Visualizar relatórios operacionais

### Para Usuários SINDICO
- ✅ Acesso somente leitura nos condomínios liberados
- ✅ Visualizar relatórios e dashboards
- ❌ Sem permissões de edição

## 🔗 Rotas Principais

### Páginas
- `/login` - Tela de login
- `/solicitar-inscricao` - Formulário de solicitação de cadastro
- `/alterar-senha` - Alteração de senha (usuários logados)
- `/recuperar-senha` - Recuperação de senha por email
- `/admin/usuarios` - Gestão de usuários (apenas ADM)

### APIs
- `POST /api/auth/login` - Fazer login
- `POST /api/auth/logout` - Fazer logout
- `GET /api/auth/status` - Status de autenticação
- `POST /api/solicitar-inscricao` - Solicitar cadastro
- `GET /api/admin/usuarios` - Listar usuários (ADM)
- `POST /api/admin/usuarios` - Criar usuário (ADM)

## 🛠️ Solução de Problemas

### Problema: Login não funciona
**Soluções:**
1. Verificar se o script `create_admin.py` foi executado com sucesso
2. Confirmar que as migrações SQL foram aplicadas
3. Verificar configurações de banco em `config/database.py`
4. Executar novamente `python create_admin.py` para recriar o admin

### Problema: Erro "bcrypt not found"
**Solução:**
```bash
pip install bcrypt==4.0.1
```

### Problema: Erro de conexão com banco
**Soluções:**
1. Verificar se MySQL está rodando
2. Confirmar credenciais em `config/database.py`
3. Testar conexão manualmente:
   ```bash
   mysql -u SEU_USUARIO -p
   ```

### Problema: Página de login não carrega
**Soluções:**
1. Verificar se o servidor Flask está rodando
2. Confirmar que todos os templates foram criados
3. Verificar logs de erro do Flask

## 📊 Estrutura do Banco de Dados

### Principais Tabelas Criadas:
- **usuarios** - Dados dos usuários (idgente, nome, email, senha_hash, tipo)
- **usuario_condominios** - Permissões por condomínio
- **solicitacoes_inscricao** - Pedidos de cadastro
- **tokens_recuperacao** - Tokens para recuperação de senha
- **log_usuarios** - Auditoria de ações

### Views Criadas:
- **vw_usuarios_completo** - Usuários com lista de condomínios
- **vw_solicitacoes_pendentes** - Pedidos não processados

## 🔄 Migração Gradual

O sistema foi projetado para **coexistir** com o sistema antigo:

1. **Rotas antigas mantidas** com sufixo `-legado`
2. **Função `verificar_autenticacao()`** atualizada para suportar ambos
3. **Migração gradual** - pode converter usuários aos poucos
4. **Zero downtime** - não quebra funcionalidades existentes

## 🔐 Segurança Implementada

- ✅ Senhas hasheadas com bcrypt (custo 12)
- ✅ Validação de senhas fortes (8+ chars, maiús/minús, números, símbolos)
- ✅ Tokens de recuperação com expiração (24h)
- ✅ Logs de auditoria para ações críticas
- ✅ Proteção contra acesso não autorizado
- ✅ Rate limiting básico implementado
- ✅ Validação de entrada em todos os endpoints

## 📞 Suporte

Se encontrar problemas:

1. **Verificar logs** do Flask para erros detalhados
2. **Executar `create_admin.py`** novamente se login não funcionar  
3. **Confirmar que todas as dependências** estão instaladas
4. **Testar conexão com banco** manualmente

---

**✅ Após seguir estes passos, o sistema de autenticação estará funcionando!**

Você poderá:
- Fazer login como administrador
- Criar novos usuários
- Aprovar solicitações de cadastro
- Gerenciar permissões por condomínio
- Usar todas as funcionalidades de segurança implementadas