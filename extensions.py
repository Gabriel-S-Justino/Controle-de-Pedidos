"""
extensions.py

Instâncias de extensões Flask compartilhadas entre o app principal e os
blueprints. Ficam aqui (sem estarem ligadas a nenhum app ainda) para
evitar import circular: app.py chama .init_app(app), e os blueprints
podem importar o objeto (ex.: limiter) para usar decorators como
@limiter.limit(...).
"""

from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf = CSRFProtect()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"],
)