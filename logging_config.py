"""
Configuração de logging para ParkVision com Gunicorn
"""
import logging
import threading
import collections
import os
from logging.handlers import RotatingFileHandler

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parkvision.log')

MAX_BUFFER = 300

_buffer = collections.deque()
_lock   = threading.Lock()
_seq    = 0          # contador crescente — usado como "offset" pelo frontend


class MemoryLogHandler(logging.Handler):
    """Mantém as últimas MAX_BUFFER linhas em memória para a UI de logs."""

    def emit(self, record):
        global _seq
        try:
            msg = self.format(record)
            with _lock:
                _seq += 1
                _buffer.append((_seq, msg))
                if len(_buffer) > MAX_BUFFER:
                    _buffer.popleft()
        except Exception:
            self.handleError(record)


def obter_logs_desde(desde_seq: int):
    """Retorna (entradas, total, ultimo_seq) para linhas com seq > desde_seq."""
    with _lock:
        entradas   = [(s, m) for s, m in _buffer if s > desde_seq]
        total      = len(_buffer)
        ultimo_seq = _buffer[-1][0] if _buffer else 0
    return entradas, total, ultimo_seq


def limpar_log_buffer():
    """Limpa o buffer em memória."""
    with _lock:
        _buffer.clear()


def setup_logging(app):
    """Configura logging para arquivo (persistência) + memória (UI)."""
    try:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )

        # Handler em memória (sempre funciona)
        mem_handler = MemoryLogHandler()
        mem_handler.setFormatter(formatter)
        mem_handler.setLevel(logging.INFO)

        # Handler em arquivo (opcional — falha silenciosamente se sem permissão)
        file_handler = None
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)
        except Exception as e:
            print(f"[logging_config] Aviso: não foi possível criar handler de arquivo: {e}")

        # Limpar handlers anteriores do app (evita duplicatas em reloads)
        for h in app.logger.handlers[:]:
            app.logger.removeHandler(h)

        app.logger.setLevel(logging.INFO)
        app.logger.addHandler(mem_handler)
        if file_handler:
            app.logger.addHandler(file_handler)
        app.logger.propagate = False

        # Logger raiz de visionlib (camlib, dblib, operlib, etc.)
        vl = logging.getLogger('visionlib')
        vl.setLevel(logging.INFO)
        vl.addHandler(mem_handler)
        if file_handler:
            vl.addHandler(file_handler)
        vl.propagate = False

        app.logger.info('ParkVision iniciado — sistema de logs ativo')
        return app

    except Exception as e:
        print(f"ERRO no setup_logging: {e}")
        return app
