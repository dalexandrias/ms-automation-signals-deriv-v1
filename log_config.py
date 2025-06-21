# log_config.py
import os
import logging
from logging.handlers import TimedRotatingFileHandler

def setup_logging(base_dir=None):
    """
    Configura logging para arquivo e console,
    criando dois loggers: o root e o 'signals'.
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Formatter único para todos handlers
    fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

    # --- Logger root ---
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # File handler para app.log
    fh = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, 'app.log'),
        when='midnight', interval=1, backupCount=10,
        encoding='utf-8', utc=True
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler para terminal
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    root.info("=== Logging ROOT inicializado ===")

    # --- Logger de sinais ---
    sig_logger = logging.getLogger('signals')
    sig_logger.setLevel(logging.INFO)
    sig_logger.propagate = False  # evita duplicar no root

    # File handler para signals.log
    sfh = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, 'signals.log'),
        when='midnight', interval=1, backupCount=10,
        encoding='utf-8', utc=True
    )
    sfh.setFormatter(fmt)
    sig_logger.addHandler(sfh)

    # Console handler para sinais
    sch = logging.StreamHandler()
    sch.setLevel(logging.INFO)
    sch.setFormatter(fmt)
    sig_logger.addHandler(sch)

    sig_logger.info("=== Signal logger inicializado ===")
