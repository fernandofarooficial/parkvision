"""
Configuração de logging para ParkVision
"""
import logging
import datetime
import os
import pytz
from logging.handlers import RotatingFileHandler

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parkvision.log')

BRASIL_TZ = pytz.timezone('America/Sao_Paulo')


class BrasilFormatter(logging.Formatter):
    """Formatter que exibe o horário no fuso de São Paulo."""

    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created, tz=BRASIL_TZ)
        return dt.strftime(datefmt or '%H:%M:%S')


def setup_logging(app):
    """Configura logging para arquivo (compartilhado entre todos os workers)."""
    try:
        formatter = BrasilFormatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )

        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        # Limpar handlers anteriores (evita duplicatas em reloads)
        for h in app.logger.handlers[:]:
            app.logger.removeHandler(h)

        app.logger.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.propagate = False

        # Logger raiz de visionlib (camlib, dblib, operlib, etc.)
        vl = logging.getLogger('visionlib')
        for h in vl.handlers[:]:
            vl.removeHandler(h)
        vl.setLevel(logging.INFO)
        vl.addHandler(file_handler)
        vl.propagate = False

        app.logger.info('ParkVision iniciado — sistema de logs ativo')
        return app

    except Exception as e:
        print(f"ERRO no setup_logging: {e}")
        return app
