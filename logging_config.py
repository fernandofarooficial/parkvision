"""
Configuração de logging para ParkVision com Gunicorn
"""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parkvision.log')

def setup_logging(app):
    """
    Configura sistema de logging TOTALMENTE LIMPO
    """
    try:
        import logging
        
        # Limpar apenas handlers do app (evita duplicatas em reloads)
        for handler in app.logger.handlers[:]:
            app.logger.removeHandler(handler)
        
        # FORMATO ÚNICO E SIMPLES
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'  # Só hora, sem data repetida
        )
        
        # UM ÚNICO HANDLER para arquivo
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)  # Só INFO e acima
        
        # Configurar o app.logger (rotas Flask)
        app.logger.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.propagate = False

        # Configurar o logger raiz de visionlib para capturar todos os módulos
        # (camlib, dblib, operlib, etc.) — sem este bloco esses logs eram descartados
        visionlib_logger = logging.getLogger('visionlib')
        visionlib_logger.setLevel(logging.INFO)
        visionlib_logger.addHandler(file_handler)
        visionlib_logger.propagate = False

        # Log inicial
        app.logger.info('ParkVision iniciado - Sistema de logs ativo')
        
        return app
        
    except Exception as e:
        print(f"ERRO no setup_logging: {e}")
        # Em caso de erro, retornar app sem logging configurado
        return app

# SISTEMA SIMPLIFICADO - SEM redirecionamento de prints
# Usar APENAS app.logger em todo lugar