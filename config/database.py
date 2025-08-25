# ----------------
# CONFIG.PY
# ----------------

import mysql.connector
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações do banco de dados usando variáveis de ambiente
DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'time_zone': '-03:00'
}

# 'host': 'mysql.linen-curlew-934510.hostingersite.com',
# 'host': '195.35.61.14',
# 'host': 'srv1922.hstgr.io',

# Função para conectar ao banco de dados
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Erro ao conectar ao banco de dados: {err}")
        return None
