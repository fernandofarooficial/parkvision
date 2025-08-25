#!/usr/bin/env python3
"""
Script para testar a função verificar_acesso_condominio
"""

import sys
sys.path.append('.')

from flask import Flask, session
from globals import verificar_acesso_condominio

app = Flask(__name__)
app.secret_key = 'test'

def simular_usuario_admin():
    """Simula um usuário ADM logado"""
    with app.test_request_context():
        # Simular sessão de usuário ADM
        session['usuario'] = {
            'idgente': 3,
            'nome_completo': 'Administrador do Sistema',
            'nome_curto': 'Admin',
            'email': 'admin@parkvision.com',
            'tipo_usuario': 'ADM',
            'condominios': []  # ADM não precisa de condomínios específicos
        }
        
        print("=== Testando acesso de usuário ADM ===")
        print(f"Sessão simulada: {dict(session)}")
        
        # Testar acesso aos condomínios 1, 4, 5
        for cond_id in [1, 4, 5]:
            tem_acesso, usuario = verificar_acesso_condominio(cond_id)
            print(f"\nCondomínio {cond_id}:")
            print(f"  Tem acesso: {tem_acesso}")
            print(f"  Usuário retornado: {usuario is not None}")
            if usuario:
                print(f"  Tipo usuário: {usuario.get('tipo_usuario')}")

def simular_usuario_monitor():
    """Simula um usuário MONITOR com acesso limitado"""
    with app.test_request_context():
        # Simular sessão de usuário MONITOR
        session['usuario'] = {
            'idgente': 999,
            'nome_completo': 'Monitor Teste',
            'nome_curto': 'Monitor',
            'email': 'monitor@test.com',
            'tipo_usuario': 'MONITOR',
            'condominios': [
                {'idcond': 1, 'nmcond': 'Blaia'},
                {'idcond': 4, 'nmcond': 'Cotia Park 2'}
            ]
        }
        
        print("\n\n=== Testando acesso de usuário MONITOR ===")
        print(f"Sessão simulada: {dict(session)}")
        
        # Testar acesso aos condomínios 1, 4, 5
        for cond_id in [1, 4, 5]:
            tem_acesso, usuario = verificar_acesso_condominio(cond_id)
            print(f"\nCondomínio {cond_id}:")
            print(f"  Tem acesso: {tem_acesso}")
            print(f"  Usuário retornado: {usuario is not None}")

if __name__ == '__main__':
    simular_usuario_admin()
    simular_usuario_monitor()