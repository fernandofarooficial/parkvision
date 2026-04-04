#!/usr/bin/env python3
"""
Script para testar as APIs de relatórios e veículos não cadastrados
"""

import requests
import json

def testar_apis_relatorios():
    print("=== Testando APIs de relatórios ===")
    
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
    
    if login_response.status_code != 200:
        print(f"ERRO: Login falhou - {login_response.status_code}")
        return
    
    print("Login OK")
    
    # 2. Testar API de veículos não cadastrados
    print("\n2. Testando /api/veiculos-nao-cadastrados/1...")
    vnc_response = session.get('http://127.0.0.1:5000/api/veiculos-nao-cadastrados/1')
    print(f"Status: {vnc_response.status_code}")
    if vnc_response.status_code == 200:
        try:
            data = vnc_response.json()
            if isinstance(data, list):
                print(f"Total veiculos nao cadastrados: {len(data)}")
            elif isinstance(data, dict):
                print(f"Resposta: {data}")
        except:
            print(f"Conteudo nao-JSON: {vnc_response.text[:200]}")
    
    # 3. Testar APIs de relatórios
    apis_relatorios = [
        '/relatorio/permissoes-validas/1',
        '/relatorio/movimento-veiculos/1',
        '/relatorio/mapa-vagas/1',
        '/api/relatorio/veiculos-condominio/1',
        '/api/relatorio/nao-cadastrados/1'
    ]
    
    for api in apis_relatorios:
        print(f"\n3. Testando {api}...")
        rel_response = session.get(f'http://127.0.0.1:5000{api}')
        print(f"Status: {rel_response.status_code}")
        if rel_response.status_code == 200:
            try:
                data = rel_response.json()
                if isinstance(data, dict):
                    if data.get('success'):
                        print(f"Sucesso: dados carregados")
                    else:
                        print(f"Erro: {data.get('message')}")
                else:
                    print(f"Dados: {str(data)[:100]}...")
            except:
                print(f"Conteudo nao-JSON: {rel_response.text[:200]}")

if __name__ == '__main__':
    testar_apis_relatorios()