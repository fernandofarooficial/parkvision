#!/usr/bin/env python3
"""
Script para testar as APIs que fornecem dados
"""

import requests
import json

def testar_apis():
    print("=== Testando APIs de dados ===")
    
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
    
    # 2. Testar API de condomínio
    print("\n2. Testando /api/condominio/1...")
    cond_response = session.get('http://127.0.0.1:5000/api/condominio/1')
    print(f"Status: {cond_response.status_code}")
    if cond_response.status_code == 200:
        try:
            data = cond_response.json()
            print(f"Condominio: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            print(f"Conteudo nao-JSON: {cond_response.text[:200]}")
    
    # 3. Testar API de veículos  
    print("\n3. Testando /api/veiculos/1...")
    veic_response = session.get('http://127.0.0.1:5000/api/veiculos/1')
    print(f"Status: {veic_response.status_code}")
    if veic_response.status_code == 200:
        try:
            data = veic_response.json()
            print(f"Total veiculos: {len(data) if isinstance(data, list) else 'N/A'}")
            if isinstance(data, list) and len(data) > 0:
                print(f"Primeiro veiculo: {json.dumps(data[0], indent=2, ensure_ascii=False)}")
            elif isinstance(data, dict):
                print(f"Dados: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            print(f"Conteudo nao-JSON: {veic_response.text[:200]}")
    
    # 4. Testar API de marcas
    print("\n4. Testando /api/marcas...")
    marcas_response = session.get('http://127.0.0.1:5000/api/marcas')
    print(f"Status: {marcas_response.status_code}")
    if marcas_response.status_code == 200:
        try:
            data = marcas_response.json()
            if data.get('success'):
                print(f"Total marcas: {len(data.get('data', []))}")
            else:
                print(f"Erro na API: {data.get('message')}")
        except:
            print(f"Conteudo nao-JSON: {marcas_response.text[:200]}")
    
    # 5. Testar API de mapa de vagas
    print("\n5. Testando /api/mapa-vagas/1...")
    vagas_response = session.get('http://127.0.0.1:5000/api/mapa-vagas/1')
    print(f"Status: {vagas_response.status_code}")
    if vagas_response.status_code == 200:
        try:
            data = vagas_response.json()
            print(f"Mapa vagas: {json.dumps(data, indent=2, ensure_ascii=False)[:300]}...")
        except:
            print(f"Conteudo nao-JSON: {vagas_response.text[:200]}")

if __name__ == '__main__':
    testar_apis()