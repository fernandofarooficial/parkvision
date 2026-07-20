# ParkVision — Guia para Claude Code

![Logo](static/images/logo.svg)

Sistema Flask + MySQL de gestão de estacionamento condominial com câmeras LPR (Heimdall).
Consulte `PADROES_PROJETO.md` para convenções detalhadas.

**Domínio de produção:** https://parkvision.tech

## Infraestrutura de Produção (VPS)

| Item | Valor |
|------|-------|
| **VPS** | Hostinger — `srv980686.hstgr.cloud` |
| **IP** | `72.60.58.241` |
| **OS** | Ubuntu (systemd) |
| **App dir** | `/home/workuser/parkvision` |
| **Venv** | `/home/workuser/parkvision/venv` |
| **Serviço** | `flaskapp.service` (systemd, usuário `workuser`) |
| **Porta interna** | `127.0.0.1:8000` (Gunicorn) |
| **Nginx config** | `/etc/nginx/sites-available/parkvision` |
| **SSL** | Let's Encrypt via Certbot — renova automaticamente |
| **Cert expira** | 2026-09-25 |

**Comandos úteis no VPS:**
```bash
systemctl status flaskapp          # status da aplicação
systemctl restart flaskapp         # reiniciar após deploy
journalctl -u flaskapp -f          # logs em tempo real
systemctl reload nginx             # recarregar Nginx sem derrubar
certbot renew --dry-run            # testar renovação do certificado
```

**Deploy é manual, não automático.** `git commit`/`git push` não afetam a VPS nem o banco de produção — não há CI/CD nem webhook configurado. Só entra no ar quando alguém faz SSH na VPS e roda (ver `ArquivosApoio/deploy_parkvision_tech.txt`):
```bash
cd /home/workuser/parkvision
git pull
systemctl restart flaskapp
```
A VPS tem seu próprio `.env` (`/home/workuser/parkvision/.env`), independente do `.env` local — mudanças de configuração local (ex: apontar para banco de teste) não se propagam para lá.

## Desenvolvimento Local

**Nunca rodar a aplicação local nem testes apontando para o banco de produção.** O app local (`127.0.0.1:5000`) e a instância da VPS são processos independentes, mas se o `.env` local apontar para `DB_HOST=72.60.58.241`, qualquer escrita feita localmente grava direto em dados reais — e algumas ações (ex: `enviar_pulso_por_direcao` em `visionlib/operlib/__init__.py`) fazem uma chamada HTTP real para o relé físico do portão (`caddisp.urldisp`), ou seja, um teste de "abrir porta" local pode acionar o portão de verdade em um condomínio real.

Use um MySQL local para desenvolvimento e testes:
- Serviço MySQL local (Windows: `MySQL80`, porta `3306`)
- Banco `parkvision_test`, schema idêntico ao de produção (importado de `doc_suporte/BaseDeDados/base_parkvision.txt` + `views.txt`)
- A tabela `logsistema` não faz parte do dump — é criada automaticamente pelo `loglib` (`CREATE TABLE IF NOT EXISTS`) na primeira execução do app; isso é esperado, não é um gap de schema
- `.env.example` já reflete essa configuração (`DB_HOST=localhost`, `DB_NAME=parkvision_test`) — copiar para `.env` e preencher a senha real do MySQL local

## Stack

- **Backend:** Python 3.13 + Flask 2.x + MySQL (sem ORM — SQL direto)
- **Frontend:** Jinja2 + Bootstrap 5 + jQuery (via CDN)
- **Servidor:** Gunicorn + Nginx em produção
- **Timezone:** America/Sao_Paulo

## Estrutura de Arquivos

```
main.py               # Todas as rotas Flask (único arquivo — não usar Blueprints)
globals.py            # Funções legadas de autenticação (manter compatibilidade)
logging_config.py     # Logging centralizado
config/database.py    # get_db_connection() — conexão MySQL

visionlib/
  middleware.py       # @requer_autenticacao, @requer_tipo_usuario, @requer_acesso_condominio, @api_requer_admin
  authlib/            # Login bcrypt, sessões, recuperação de senha
  userlib/            # CRUD usuários, solicitações de inscrição
  dblib/              # NÚCLEO: gravar_movimento() + queries auxiliares
  vplib/              # Validação e correção de placas (fuzzy matching, OCR)
  operlib/            # Store de eventos em memória + ações do operador
  permlib/            # Permissões de estacionamento (cadperm)
  carlib/             # CRUD cadveiculo, não-cadastrados, apelidos
  listlib/            # Listagens (usa vw_movimentos)
  dashlib/            # Mapa de vagas (usa vw_estacionados)
  rellib/             # Relatórios
  camlib/             # Daemon RTSP health-check de câmeras
  loglib/             # Persistência assíncrona de logs (tabela logsistema) + limpeza automática (retenção 3 dias)
  condlib/            # Dados de condomínios
  apontlib/           # Apontamento manual (bypass câmera)
  unidlib/            # Gestão de unidades habitacionais
  teleglib/           # Notificações Telegram
  apilib/             # Receptor webhook Heimdall (wrapper sobre gravar_movimento)
  mobilelib/          # Queries para a versão mobile (movimentos, estacionados, mapa, permissões, novo veículo)

templates/
  mobile/             # Templates da versão mobile PWA (login, condominio, monitoramento)
static/               # CSS, imagens
  icons/              # Ícones PWA (apple-touch-icon, favicon, icon-192, icon-512)
  manifest.json       # Web App Manifest (PWA)
  sw.js               # Service Worker (PWA — cache offline básico)
ArquivosApoio/        # Scripts utilitários (não entram em produção)
doc_suporte/BaseDeDados/
  base_parkvision.txt # Schema MySQL completo
  views.txt           # Definições SQL das views
```

## Regras Críticas

### Multi-tenant
Todo dado deve ser filtrado por `idcond`. Nunca misturar dados de condomínios diferentes.

### Banco de dados
- SQL direto — sem ORM
- `get_db_connection()` abre e fecha por função (não reaproveitar conexões entre chamadas)
- Sempre `cursor.close()` + `conn.close()` no `finally`
- `cursor(dictionary=True)` para facilitar manipulação
- Prepared statements obrigatórios: `cursor.execute("... WHERE id = %s", (valor,))`

```python
def funcao_exemplo(idcond):
    conn = get_db_connection()
    if not conn:
        return False, "Erro de conexão"
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM tabela WHERE idcond = %s", (idcond,))
        resultado = cursor.fetchall()
        conn.commit()  # se houver escrita
        return True, resultado
    except Exception as err:
        conn.rollback()
        return False, str(err)
    finally:
        cursor.close()
        conn.close()
```

### Resposta JSON (obrigatório em todas as APIs)
```python
return jsonify({'success': True, 'message': 'OK', 'data': dados})
return jsonify({'success': False, 'message': 'Mensagem de erro'})
```

### Autenticação
- Usar decorators de `visionlib/middleware.py` nas rotas novas
- `session['usuario']` contém: `idgente`, `nome_curto`, `tipo_usuario`, `condominios`
- Tipos: `ADM` (total), `MONITOR` (leitura + edição), `SINDICO` (somente leitura — visualização e relatórios)
- Em código legado: `globals.verificar_autenticacao()` / `globals.verificar_acesso_condominio(idcond)`

**Enforcement de SINDICO somente leitura:** hook global `bloquear_escrita_sindico` (`@app.before_request` em `main.py`) bloqueia qualquer requisição `POST`/`PUT`/`DELETE`/`PATCH` de usuário `SINDICO`, exceto as rotas em `_ROTAS_ESCRITA_LIVRES_SINDICO` (login/logout/alterar-senha/recuperação de senha, solicitação de inscrição e o webhook do Heimdall). Novas rotas de escrita ficam bloqueadas para SINDICO por padrão — só adicionar à allowlist se for autoatendimento de conta ou endpoint público/webhook sem sessão de usuário.

### Logging
```python
import logging
logger = logging.getLogger(__name__)
logger.info("mensagem")
logger.error(f"erro: {err}")
```

Logs de `app.logger` e do logger raiz `visionlib` são gravados tanto no arquivo (`parkvision.log`, rotativo) quanto na tabela `logsistema` (retenção de 3 dias, via `loglib`). A gravação no banco é assíncrona (fila em memória + thread), então `logger.info()`/`logger.error()` nunca bloqueiam esperando o MySQL.

> Exceção à regra "não usar `print()`": dentro de `visionlib/loglib/` os erros do próprio pipeline de log usam `print()` propositalmente, para evitar recursão infinita (um `logger.error()` ali reentraria no handler que está falhando).

## Banco de Dados — Tabelas e Convenções

Nomenclatura legacy compacta (não mudar):

| Tabela | Descrição |
|--------|-----------|
| `cadcond` | Condomínios (`idcond`, `nmcond`, `limite` — total de vagas do condomínio, prevalece sobre a soma de `vagasunidades.vperm` quando > 0; qualquer tela que exiba "total de vagas" deve seguir esse fallback — `dashlib.obter_mapa_vagas` e `unidlib.listar_unidades_vagas` já fazem isso) |
| `cadcamera` | Câmeras (`idcam`, `idcond`, `direcao` E/S/I) |
| `cadveiculo` | Veículos (`placa` PK, sem unidade/condomínio) |
| `cadperm` | Permissões (`idperm`, `placa`, `idcond`, `unidade`, `data_inicio`, `data_fim` NULL=indefinida) |
| `movcar` | Movimentos (`idmov`, `idcond`, `placa`, `contav`, `idgente`, `direcao`, `nowpost`, `origem`) |
| `vagasunidades` | Vagas por unidade (`idcond`, `unidade`, `vperm`, `seqcond`) |
| `logbruto` | JSON bruto do Heimdall (`idlog`, `placalida`, `nowpost`, `nomecam`, `idcam`, `jsonbruto`) — inclui a foto do veículo em `jsonbruto.data.image_base64`; retenção automática de `LOGBRUTO_RETENCAO_POR_COND` (20) registros por condomínio (via `idcam`→`cadcamera.idcond`), apagando os mais antigos a cada novo insert (`visionlib/dblib/limitar_logbruto_por_condominio`) — não há mascaramento de conteúdo, o volume é controlado só pela quantidade de linhas |
| `logsistema` | Logs do sistema (`idlog`, `nivel`, `mensagem`, `criado_em`) — gravação assíncrona via `loglib`, retenção de 3 dias (limpeza automática a cada hora) |
| `usuarios` | Usuários (`idgente`, `tipo_usuario`, `ativo`) |

**Views principais:** `vw_autorizacoes`, `vw_estacionados`, `vw_movimentos`, `vw_last_mov`, `vw_veiculos_cond`, `vw_veiculos_autorizados`

**Semântica de `contav` em `movcar`:**
- `contav=0` + `idgente IS NULL` → evento pendente (aguardando operador)
- `contav=0` + `idgente IS NOT NULL` → rejeitado pelo operador
- `contav=1` → confirmado, conta vaga

**Unidades especiais:** 'Prestador', 'Avulso', 'Visitante' → recebem 10 vagas fixas (não consultam `vagasunidades`)

**Campo `origem` em `movcar`:** identifica a fonte do movimento — `'LPR'` (câmera Heimdall), `'MANUAL'` (apontamento manual), `NULL` → tratado como `'MANUAL'` via `COALESCE`.

## Tela de Monitoramento de Veículos (Desktop)

`templates/veiculos.html` (rota `/veiculos/<int:condominio_id>`) é a tela principal de gestão desktop. A barra de ações usa um único CSS grid de 6 colunas (classe `.acoes-grid`) em vez de flexbox — cada coluna se ajusta ao maior dos dois botões que contém, então o botão da linha superior tem sempre a mesma largura do botão correspondente na linha inferior:

| Coluna | Linha superior | Linha inferior |
|--------|-----------------|-----------------|
| 1 | Mapa de Vagas | Consultar |
| 2 | Operador | Veículo |
| 3 | De<>Para — modal com as últimas 10 fotos de veículos | Veículo + Permissão |
| 4 | Unidades | Permissão |
| 5 | Relatórios | Apontamento |
| 6 | Ocupadas — exibe `ocupadas/permitidas` (ex: `21/80`) | Veículo não cadastrado |

Responsivo: 3 colunas em telas médias (`≤991px`), 2 colunas em telas pequenas (`≤575px`). Os IDs dos botões (`btn-mapa-vagas`, `btn-cadastrar-veiculo`, etc.) não mudaram — o JS de show/hide por perfil (ADM/MONITOR vs. leitura) e os handlers de clique continuam os mesmos.

**Botão Ocupadas:** rótulo `Ocupadas: <span id="total-ocupadas-header">` no formato `ocupadas/permitidas` (`total_ocupadas`/`total_vagas_permitidas` — mesmos campos usados no card "Permitidas" do mapa mobile). Preenchido em `atualizarTotalNaoCadastrados()`, que reaproveita a chamada já existente a `/api/mapa-vagas/<id>` (mesma requisição que alimenta o contador de "não cadastrados") — não criar uma chamada AJAX separada para isso.

**Botão De<>Para:** abre `#modalDePara` (`data-bs-toggle="modal"`), que ao exibir (`show.bs.modal`) chama `carregarFotosDePara()` → `GET /api/logbruto/ultimas-fotos/<condominio_id>` → `dblib.obter_ultimas_fotos(idcond, 10)`. Lista as últimas 10 fotos de veículos direto de `logbruto.jsonbruto.data.image_base64` (JOIN com `cadcamera` para filtrar por `idcond`, e JOIN com `movcar` pelo `idlog` compartilhado — mesmo valor gravado em ambas as tabelas no momento do evento), renderizadas como `<img>` com prefixo `data:image/jpeg;base64,`. Depende da retenção de 20 registros por condomínio em `logbruto` (ver seção Banco de Dados) para não crescer indefinidamente.

Filtro adicional (via JOIN com `movcar`): só entram fotos de eventos com `movcar.contav = 0` (ainda pendentes, aguardando confirmação do operador — ver semântica de `contav` na seção Banco de Dados) e `movcar.placa != '*ERROR*'` (sentinel usado em `dblib`/`vplib`/`operlib` para placa não reconhecida pelo OCR). Ou seja, a tela De<>Para mostra apenas capturas com placa lida corretamente que ainda não foram processadas/confirmadas — não é mais só "as últimas 10 fotos do condomínio" em bruto.

## Versão Mobile (PWA)

Rotas sob o prefixo `/app/` servem a interface mobile — uma PWA instalável via `static/manifest.json` + `static/sw.js`.

### Rotas de página

| Rota | Descrição |
|------|-----------|
| `/app/` | Redirect para login ou monitoramento |
| `/app/login` | Login mobile |
| `/app/condominio` | Seleção de condomínio |
| `/app/selecionar/<idcond>` | Salva condomínio em `session['mobile_idcond']` |
| `/app/monitoramento` | SPA principal com menu inferior |
| `/app/logout` | Logout |

### APIs mobile (`/api/m/`)

Todas exigem autenticação via `verificar_autenticacao_usuario()` e leem `idcond` de `session['mobile_idcond']`.

| Rota | Método | Lib usada | Descrição |
|------|--------|-----------|-----------|
| `/api/m/movimentos` | GET | `mobilelib` | Últimos 20 movimentos (polling 30s) |
| `/api/m/mapa-vagas` | GET | `dashlib` | Mapa de vagas (unidades + ocupação) |
| `/api/m/estacionados` | GET | `mobilelib` | Veículos atualmente estacionados |
| `/api/m/unidade-veiculos/<unidade>` | GET | `mobilelib` | Veículos em uma unidade (detalhe do mapa) |
| `/api/m/unidades` | GET | `permlib` | Lista de unidades do condomínio |
| `/api/m/buscar-veiculo/<placa>` | GET | `carlib` | Busca veículo em `cadveiculo` |
| `/api/m/buscar-permissao/<placa>` | GET | `mobilelib` | Busca permissão vigente/indefinida |
| `/api/m/criar-permissao` | POST | `permlib` | Cria nova permissão (veículo já cadastrado) |
| `/api/m/modificar-permissao` | PUT | `permlib` | Altera prazo de permissão vigente |
| `/api/m/novo-veiculo` | POST | `mobilelib` | Cria veículo + permissão em uma operação |

> Para marcas/modelos/cores, o frontend mobile usa as APIs públicas já existentes: `/api/marcas`, `/api/modelos/<marca>`, `/api/cores`.

### Funcionalidades da SPA (`/app/monitoramento`)

Menu inferior com 4 abas:
- **Início** — monitoramento em tempo real (polling 30 s)
- **Mapa** — barra de estatísticas (Unidades, Permitidas, Ocupadas, Livres) + grid de unidades com código de cores (Excesso=vermelho, Completo=azul, Parcial=amarelo, Livre=branco); cada unidade exibe `vocup/vperm` e vagas disponíveis (`vperm - vocup`); toque na unidade abre veículos estacionados
  - `total_vagas_permitidas` (card "Permitidas") vem de `cadcond.limite`, com fallback para soma de `vagasunidades.vperm` (`dashlib`)
  - Classe CSS de status "Livre" é `livre` (não usar `vazio` — colide com a classe genérica de lista vazia e desconfigura o tamanho da célula/legenda)
- **Estacionados** — lista de veículos com placa, unidade, veículo, hora de entrada
- **Mais (⋮)** — abre 4 formulários deslizantes: Novo Veículo, Criar Permissão, Alterar Permissão, Consulta
  - Perfil `SINDICO` (somente leitura) não vê os itens Novo Veículo, Criar Permissão e Alterar Permissão no menu — apenas Consulta (`templates/mobile/monitoramento.html`, condicional `{% if usuario.tipo_usuario != 'SINDICO' %}`). É reforço de UI: o bloqueio real já é feito no backend por `bloquear_escrita_sindico`.

### Funções do `mobilelib`

| Função | Descrição |
|--------|-----------|
| `obter_ultimos_movimentos_mobile(idcond, limit)` | Usa `vw_movimentos` |
| `obter_estacionados_mobile(idcond)` | Usa `vw_autorizacoes` + `vw_last_mov` |
| `obter_veiculos_unidade_mobile(idcond, unidade)` | Igual ao anterior, filtrado por unidade |
| `buscar_permissao_mobile(idcond, placa)` | Usa `vw_veiculos_autorizados` |
| `novo_veiculo_mobile(idcond, placa, ...)` | Cria em `cadveiculo` + `cadperm` atomicamente |

### Sessão e autenticação mobile

- Usa a **mesma sessão web** (`session['usuario']`, `session['autenticado']`)
- `session['mobile_idcond']` armazena o condomínio selecionado na versão mobile
- O `verificar_acesso_condominio()` do `globals.py` funciona normalmente (lê `session['usuario']`)
- Ícones PWA ficam em `static/icons/`; Apple exige `apple-touch-icon.png` na raiz (rota dedicada em `main.py`)

## Visualizador de Logs (`/logs`)

Página web (somente `ADM`) para acompanhar os logs do sistema em tempo real, lendo da tabela `logsistema` (via `loglib`).

| Rota | Método | Descrição |
|------|--------|-----------|
| `/logs` | GET | Renderiza `templates/logs.html` — tabela com polling incremental |
| `/api/logs/tail` | GET | `?offset=<idlog>` — retorna logs com `idlog > offset` (cursor incremental, até 300 por chamada) + `total_lines` |
| `/api/logs/limpar` | POST | `TRUNCATE` na tabela `logsistema` (ação manual do admin) |

- Formato de linha exibido: `DD/MM HH:MM:SS [NIVEL] mensagem` (parseado no front via regex `RE_LOG` em `logs.html`)
- Todas as 3 rotas checam `verificar_permissao_tipo_usuario(['ADM'])` e retornam 403/redirect para não-admin

## Bug Conhecido — Veículo com 2 Permissões Ativas

Se uma placa tem `cadperm` em duas unidades do mesmo condomínio, a `vw_movimentos` retorna o movimento duplicado (2 linhas por `idmov`). Causa raiz: `vw_veiculos_cond` retorna 2 linhas → JOIN multiplica. Ao implementar relatórios ou listagens, deduplique por `idmov` após fetchall.

## Fluxo LPR (informação para contexto)

```
POST /api/receber-dados → apilib → dblib.gravar_movimento()
  ├─ vplib.process_heimdall_plate()  # valida/corrige placa
  ├─ checar_anteriores()             # anti-duplicata (90s)
  ├─ gravar_log() → INSERT movcar (contav=0, sem operador)
  └─ decisão de liberação automática (server-side, por direção da câmera):
       ├─ Saída (S) + placa cadastrada → auto_confirmar = True (não depende do status da permissão)
       ├─ Entrada (E) + permissão VIGENTE/INDEFINIDA + vaga disponível → auto_confirmar = True
       ├─ Câmera interna (I), ou entrada/saída fora dos critérios acima → fica pendente
       ├─ auto_confirmar=True  → operlib.executar_acao_operador(idmov,'confirmar',None,origem='AUTO')
       │                          (envia pulso ao relé, sem intervenção humana)
       └─ auto_confirmar=False → operlib.adicionar_evento()  # push para tela Operador decidir manualmente
```

> A liberação automática é decidida inteiramente no backend (`dblib.gravar_movimento`, `visionlib/dblib/__init__.py`).
> Não depende de nenhuma aba de navegador aberta na tela `/operador` — antes essa lógica vivia em JS em
> `templates/operador.html` e só funcionava enquanto um operador tivesse a tela aberta e conectada; foi movida
> para o servidor porque isso deixava a abertura automática do portão frágil (parava silenciosamente se a aba
> fechasse, a sessão expirasse ou a rede caísse). A tela Operador ainda mostra o evento auto-liberado via
> `pollAcoes`/`registrar_acao_store` (badge "AUTO"), mas não precisa estar aberta para o pulso ser enviado.

## Convenções de Nomenclatura

- **Python:** `snake_case` funções e variáveis, `UPPER_SNAKE_CASE` constantes
- **Templates HTML:** `kebab-case` (ex: `mapa-vagas.html`)
- **Banco:** abreviações compactas em português (`idgente`, `nmcond`, `nowpost`, `lup`)
- **Views SQL:** prefixo `vw_`
- **CSS/IDs HTML:** `kebab-case`
- **JavaScript:** `camelCase`

## Env Vars Relevantes

`SECRET_KEY`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `CAMERAS_ENABLED`, `CAM_MONITOR_INTERVAL_MIN`, `SESSION_COOKIE_SECURE`

## Reuso de Queries — Verificar Antes de Escrever SQL

Antes de escrever qualquer query nova, verificar nesta ordem:

1. **Views SQL** — as views já encapsulam os JOINs mais comuns. Preferir sempre uma view a reescrever os mesmos JOINs à mão:
   - `vw_movimentos` → movimentos confirmados com unidade, marca, modelo, cor, status de vaga
   - `vw_autorizacoes` → permissões com dados do veículo e status (VIGENTE/VENCIDA/INDEFINIDA)
   - `vw_estacionados` → contagem de veículos estacionados por unidade
   - `vw_last_mov` → último movimento confirmado por veículo
   - `vw_veiculos_cond` → permissão ativa de cada veículo por condomínio
   - `vw_veiculos_autorizados` → veículos com permissão vigente no momento

2. **Funções das libs** — verificar se a lib responsável pelo domínio já expõe a query necessária:
   - `listlib` → listagens de movimentos e detalhes de veículo/unidade
   - `dashlib` → mapa de vagas
   - `condlib` → dados de condomínios
   - `carlib` → CRUD de veículos, não-cadastrados, apelidos
   - `permlib` → permissões (`cadperm`)
   - `mobilelib` → todas as queries da versão mobile (movimentos, estacionados, veículos por unidade, busca de permissão, criação de veículo+permissão)

3. **Só então** escrever SQL novo — e colocá-lo na lib do domínio correto, nunca direto em `main.py`.

> Exemplo do que não fazer: reescrever os JOINs `cadveiculo → cadmodelo → cadmarca → cadcores` manualmente quando `vw_movimentos` ou `vw_autorizacoes` já os entregam prontos.

## O que Não Fazer

- Não usar ORM (SQLAlchemy, etc.)
- Não criar arquivos de rota separados nem Blueprints (toda rota vai em `main.py`)
- Não reaproveitar conexão MySQL entre funções diferentes
- Não filtrar dados sem `idcond`
- Não retornar JSON sem o campo `success`
- Não usar `print()` para debug — usar `logger`
- Não modificar views SQL sem atualizar `doc_suporte/BaseDeDados/views.txt`
- Não reescrever JOINs que já existem em views — consultar a seção "Reuso de Queries" acima
