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
  condlib/            # Dados de condomínios
  apontlib/           # Apontamento manual (bypass câmera)
  unidlib/            # Gestão de unidades habitacionais
  teleglib/           # Notificações Telegram
  apilib/             # Receptor webhook Heimdall (wrapper sobre gravar_movimento)

templates/            # HTML Jinja2
static/               # CSS, imagens
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
- Tipos: `ADM` (total), `MONITOR`, `SINDICO`
- Em código legado: `globals.verificar_autenticacao()` / `globals.verificar_acesso_condominio(idcond)`

### Logging
```python
import logging
logger = logging.getLogger(__name__)
logger.info("mensagem")
logger.error(f"erro: {err}")
```

## Banco de Dados — Tabelas e Convenções

Nomenclatura legacy compacta (não mudar):

| Tabela | Descrição |
|--------|-----------|
| `cadcond` | Condomínios (`idcond`, `nmcond`) |
| `cadcamera` | Câmeras (`idcam`, `idcond`, `direcao` E/S/I) |
| `cadveiculo` | Veículos (`placa` PK, sem unidade/condomínio) |
| `cadperm` | Permissões (`idperm`, `placa`, `idcond`, `unidade`, `data_inicio`, `data_fim` NULL=indefinida) |
| `movcar` | Movimentos (`idmov`, `idcond`, `placa`, `contav`, `idgente`, `direcao`, `nowpost`) |
| `vagasunidades` | Vagas por unidade (`idcond`, `unidade`, `vperm`, `seqcond`) |
| `logbruto` | JSON bruto do Heimdall |
| `usuarios` | Usuários (`idgente`, `tipo_usuario`, `ativo`) |

**Views principais:** `vw_autorizacoes`, `vw_estacionados`, `vw_movimentos`, `vw_last_mov`, `vw_veiculos_cond`

**Semântica de `contav` em `movcar`:**
- `contav=0` + `idgente IS NULL` → evento pendente (aguardando operador)
- `contav=0` + `idgente IS NOT NULL` → rejeitado pelo operador
- `contav=1` → confirmado, conta vaga

**Unidades especiais:** 'Prestador', 'Avulso', 'Visitante' → recebem 10 vagas fixas (não consultam `vagasunidades`)

## Bug Conhecido — Veículo com 2 Permissões Ativas

Se uma placa tem `cadperm` em duas unidades do mesmo condomínio, a `vw_movimentos` retorna o movimento duplicado (2 linhas por `idmov`). Causa raiz: `vw_veiculos_cond` retorna 2 linhas → JOIN multiplica. Ao implementar relatórios ou listagens, deduplique por `idmov` após fetchall.

## Fluxo LPR (informação para contexto)

```
POST /api/receber-dados → apilib → dblib.gravar_movimento()
  ├─ vplib.process_heimdall_plate()  # valida/corrige placa
  ├─ checar_anteriores()             # anti-duplicata (90s)
  ├─ gravar_log() → INSERT movcar (contav=0, sem operador)
  └─ operlib.adicionar_evento()      # push para polling do front
```

## Convenções de Nomenclatura

- **Python:** `snake_case` funções e variáveis, `UPPER_SNAKE_CASE` constantes
- **Templates HTML:** `kebab-case` (ex: `mapa-vagas.html`)
- **Banco:** abreviações compactas em português (`idgente`, `nmcond`, `nowpost`, `lup`)
- **Views SQL:** prefixo `vw_`
- **CSS/IDs HTML:** `kebab-case`
- **JavaScript:** `camelCase`

## Env Vars Relevantes

`SECRET_KEY`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `CAMERAS_ENABLED`, `CAM_MONITOR_INTERVAL_MIN`, `SESSION_COOKIE_SECURE`

## O que Não Fazer

- Não usar ORM (SQLAlchemy, etc.)
- Não criar arquivos de rota separados nem Blueprints (toda rota vai em `main.py`)
- Não reaproveitar conexão MySQL entre funções diferentes
- Não filtrar dados sem `idcond`
- Não retornar JSON sem o campo `success`
- Não usar `print()` para debug — usar `logger`
- Não modificar views SQL sem atualizar `doc_suporte/BaseDeDados/views.txt`
