#!/usr/bin/env python3
"""
Script para testar o usuário admin no banco de dados
"""

import mysql.connector
from config.database import get_db_connection

def testar_usuario_admin():
    print("=== Verificando usuário admin ===")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não foi possível conectar ao banco de dados!")
        return
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Verificar se usuário admin existe
        cursor.execute("""
            SELECT idgente, nome_completo, nome_curto, email, tipo_usuario, ativo
            FROM usuarios 
            WHERE email = %s
        """, ('admin@parkvision.com',))
        
        usuario = cursor.fetchone()
        
        if usuario:
            print("SUCESSO: Usuario admin encontrado:")
            print(f"   ID: {usuario['idgente']}")
            print(f"   Nome: {usuario['nome_completo']}")
            print(f"   Email: {usuario['email']}")
            print(f"   Tipo: {usuario['tipo_usuario']}")
            print(f"   Ativo: {usuario['ativo']}")
            
            # Verificar condomínios do usuário
            cursor.execute("""
                SELECT uc.idcond, c.nmcond 
                FROM usuario_condominios uc
                INNER JOIN cadcond c ON uc.idcond = c.idcond
                WHERE uc.idgente = %s
            """, (usuario['idgente'],))
            
            condominios = cursor.fetchall()
            print(f"   Condominios permitidos: {len(condominios)}")
            for cond in condominios:
                print(f"     - ID {cond['idcond']}: {cond['nmcond']}")
            
        else:
            print("ERRO: Usuario admin nao encontrado!")
            
        # Verificar quantos condomínios existem no sistema
        cursor.execute("SELECT COUNT(*) as total FROM cadcond")
        total_cond = cursor.fetchone()
        print(f"\nTotal de condominios no sistema: {total_cond['total']}")
        
        # Listar alguns condomínios
        cursor.execute("SELECT idcond, nmcond FROM cadcond LIMIT 5")
        condominios_sistema = cursor.fetchall()
        print("   Exemplos de condominios:")
        for cond in condominios_sistema:
            print(f"     - ID {cond['idcond']}: {cond['nmcond']}")
        
    except mysql.connector.Error as err:
        print(f"ERRO na consulta: {err}")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    testar_usuario_admin()