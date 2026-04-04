#!/usr/bin/env python3
"""
Script para testar a sessão real do usuário admin
"""

import requests
import json

def testar_login_real():
    print("=== Testando login real ===")
    
    # Criar uma sessão para manter cookies
    session = requests.Session()
    
    # 1. Fazer login
    print("1. Fazendo login...")
    login_data = {
        'email': 'admin@parkvision.com',
        'senha': 'admin123'
    }
    
    login_response = session.post('http://127.0.0.1:5000/api/auth/login', 
                                 json=login_data,
                                 headers={'Content-Type': 'application/json'})
    
    print(f"Status login: {login_response.status_code}")
    if login_response.status_code == 200:
        login_result = login_response.json()
        print(f"Login result: {login_result}")
    
    # 2. Verificar status de autenticação
    print("\n2. Verificando status...")
    status_response = session.get('http://127.0.0.1:5000/api/auth/status')
    print(f"Status autenticação: {status_response.status_code}")
    if status_response.status_code == 200:
        status_result = status_response.json()
        print(f"Status result: {json.dumps(status_result, indent=2)}")
    
    # 3. Tentar acessar um condomínio específico
    print("\n3. Tentando acessar condomínio 1...")
    veiculos_response = session.get('http://127.0.0.1:5000/veiculos/1', allow_redirects=False)
    print(f"Status acesso condomínio: {veiculos_response.status_code}")
    print(f"Headers: {dict(veiculos_response.headers)}")
    
    if veiculos_response.status_code == 302:
        print(f"Redirecionado para: {veiculos_response.headers.get('Location')}")

if __name__ == '__main__':
    testar_login_real()