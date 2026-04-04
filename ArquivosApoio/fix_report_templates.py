#!/usr/bin/env python3
"""
Script para corrigir todos os templates de relatórios
"""

import os
import re

def corrigir_template(arquivo):
    print(f"Corrigindo {arquivo}...")
    
    with open(arquivo, 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    # Padrão antigo de verificação
    padrao_antigo = r'''success: function\(response\) \{
                if \(!response\.authenticated \|\| response\.condominio_id != condominioId\) \{
                    window\.location\.href = '/condominios';
                    return;
                \}'''
    
    # Novo padrão de verificação
    padrao_novo = '''success: function(response) {
                if (!response.authenticated || !response.usuario) {
                    // Não autenticado - redirecionar para login
                    window.location.href = '/login';
                    return;
                }
                
                const usuario = response.usuario;
                
                // Verificar se usuário tem acesso ao condomínio
                if (usuario.tipo_usuario !== 'ADM') {
                    // Para usuários não-ADM, verificar se tem acesso ao condomínio específico
                    const condominiosPermitidos = usuario.condominios || [];
                    const temAcesso = condominiosPermitidos.some(c => c.idcond == condominioId);
                    
                    if (!temAcesso) {
                        // Sem acesso - redirecionar para página de condomínios
                        window.location.href = '/condominios';
                        return;
                    }
                }
                // Usuários ADM têm acesso a todos os condomínios'''
    
    # Substituir
    conteudo_novo = re.sub(padrao_antigo, padrao_novo, conteudo, flags=re.MULTILINE)
    
    # Também corrigir erro handlers
    conteudo_novo = re.sub(
        r'error: function\(\) \{\s*window\.location\.href = \'/condominios\';',
        "error: function() {\n                // Erro na verificação - redirecionar para login\n                window.location.href = '/login';",
        conteudo_novo
    )
    
    # Salvar se houve mudanças
    if conteudo_novo != conteudo:
        with open(arquivo, 'w', encoding='utf-8') as f:
            f.write(conteudo_novo)
        print(f"  OK {arquivo} corrigido")
    else:
        print(f"  SKIP {arquivo} - nenhuma mudança necessária")

def main():
    templates_dir = "../templates"
    
    # Lista de templates para corrigir
    templates = [
        "relatorio-permissoes-validas.html",
        "relatorio-movimento-veiculos.html", 
        "relatorio-mapa-vagas.html",
        "relatorio-veiculos-condominio.html",
        "relatorio-nao-cadastrados.html"
    ]
    
    for template in templates:
        arquivo = os.path.join(templates_dir, template)
        if os.path.exists(arquivo):
            corrigir_template(arquivo)
        else:
            print(f"ERRO Arquivo não encontrado: {arquivo}")

if __name__ == '__main__':
    main()