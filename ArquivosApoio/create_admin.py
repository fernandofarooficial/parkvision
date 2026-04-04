#!/usr/bin/env python3
"""
Script para criar usuário administrador padrão
Execute este script após aplicar as migrações SQL
"""

import bcrypt
import mysql.connector

DB_CONFIG = {
    'user': 'fefa_dev',
    'password': 'Fd7493dt',
    'host': '72.60.58.241',
    'database': 'parkvision',
    'time_zone': '-03:00'
}


def criar_admin():
    print("=== Criando usuário administrador padrão ===")
    
    # Dados do admin
    email = 'admin@parkvision.com'
    senha = 'admin123'
    nome_completo = 'Administrador do Sistema'
    nome_curto = 'Admin'
    telefone = '(11) 99999-9999'
    tipo_usuario = 'ADM'
    
    # Gerar hash da senha
    print("Gerando hash da senha...")
    senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print(f"Hash gerado: {senha_hash}")
    
    # Conectar ao banco
    print("Conectando ao banco de dados...")
    conn = mysql.connector.connect(**DB_CONFIG)
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados!")
        print("Verifique as configurações em config/database.py")
        return False
    
    cursor = conn.cursor()
    
    try:
        # Verificar se usuário já existe
        cursor.execute("SELECT idgente FROM usuarios WHERE email = %s", (email,))
        if cursor.fetchone():
            print(f"⚠️  Usuário {email} já existe!")
            
            # Perguntar se quer atualizar a senha
            resposta = input("Deseja atualizar a senha para 'admin123'? (s/N): ").lower()
            if resposta == 's':
                cursor.execute("""
                    UPDATE usuarios 
                    SET senha_hash = %s, lup = NOW()
                    WHERE email = %s
                """, (senha_hash, email))
                conn.commit()
                print("✅ Senha do administrador atualizada com sucesso!")
                print(f"📧 Email: {email}")
                print(f"🔑 Senha: {senha}")
                return True
            else:
                print("❌ Operação cancelada.")
                return False
        
        # Criar novo usuário
        cursor.execute("""
            INSERT INTO usuarios (nome_completo, nome_curto, email, telefone, senha_hash, tipo_usuario)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (nome_completo, nome_curto, email, telefone, senha_hash, tipo_usuario))
        
        idgente = cursor.lastrowid
        conn.commit()
        
        print("✅ Usuário administrador criado com sucesso!")
        print(f"🆔 ID: {idgente}")
        print(f"👤 Nome: {nome_completo}")
        print(f"📧 Email: {email}")
        print(f"🔑 Senha: {senha}")
        print(f"🏷️  Tipo: {tipo_usuario}")
        print("\n⚠️  IMPORTANTE: Altere a senha após o primeiro login!")
        
        return True
        
    except mysql.connector.Error as err:
        print(f"❌ Erro ao criar usuário: {err}")
        conn.rollback()
        return False
        
    finally:
        cursor.close()
        conn.close()

def testar_login():
    """Testa se o login funciona com as credenciais criadas"""
    print("\n=== Testando credenciais ===")
    
    email = 'admin@parkvision.com'
    senha = 'admin123'
    
    conn = mysql.connector.connect(**DB_CONFIG)
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados!")
        return False
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar usuário
        cursor.execute("""
            SELECT idgente, nome_completo, email, senha_hash, tipo_usuario
            FROM usuarios 
            WHERE email = %s AND ativo = TRUE
        """, (email,))
        
        usuario = cursor.fetchone()
        
        if not usuario:
            print("❌ Usuário não encontrado!")
            return False
        
        # Verificar senha
        senha_correta = bcrypt.checkpw(senha.encode('utf-8'), usuario['senha_hash'].encode('utf-8'))
        
        if senha_correta:
            print("✅ Login testado com sucesso!")
            print(f"👤 Usuário: {usuario['nome_completo']}")
            print(f"🏷️  Tipo: {usuario['tipo_usuario']}")
            return True
        else:
            print("❌ Senha incorreta!")
            return False
            
    except mysql.connector.Error as err:
        print(f"❌ Erro ao testar login: {err}")
        return False
        
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    print("🚀 Script de criação do usuário administrador")
    print("=" * 50)
    
    # Criar admin
    if criar_admin():
        # Testar login
        if testar_login():
            print("\n🎉 Tudo configurado corretamente!")
            print("\nVocê pode agora:")
            print("1. Acessar /login no navegador")
            print("2. Usar as credenciais:")
            print("   📧 Email: admin@parkvision.com")
            print("   🔑 Senha: admin123")
            print("3. Alterar a senha após o login")
        else:
            print("\n⚠️  Admin criado, mas há problemas no login. Verifique a implementação.")
    else:
        print("\n❌ Falha na criação do administrador.")
    
    print("\n" + "=" * 50)