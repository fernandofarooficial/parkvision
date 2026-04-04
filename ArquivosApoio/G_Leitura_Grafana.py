import requests
import json
from datetime import datetime, timedelta


def extrair_via_api():
    # Tentar acessar a API do dashboard público
    dashboard_uid = "f8bfe8e54a494de9b59218743d70381c"
    base_url = "https://zions.grafana.net"

    # Headers para simular requisição do navegador
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    try:
        # Tentar endpoint de dashboard público
        url = f"{base_url}/api/public/dashboards/{dashboard_uid}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            print("Dashboard data:", json.dumps(data, indent=2))
            return data
    except Exception as e:
        print(f"Erro na API: {e}")
        return None