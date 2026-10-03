FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-extras.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-extras.txt

# Pre-download the rembg model the app actually uses (BG_REMOVAL_MODEL, default
# u2net) so the first background removal is instant. The model name must be
# explicit: rembg's own default is bria-rmbg (~1 GB), which the app never loads.
# REMBG_HOME points at a shared path because the app runs as appuser, not root,
# and would otherwise re-download into its own home after every container recreate.
# World-writable so a different BG_REMOVAL_MODEL can still be fetched at runtime.
ARG BG_REMOVAL_MODEL=u2net
ENV REMBG_HOME=/opt/rembg
RUN python -c "from rembg import new_session; new_session('${BG_REMOVAL_MODEL}')" \
    && chmod -R a+rwX /opt/rembg

# Copy application code
COPY . .

# Create non-root user and storage directory
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
RUN mkdir -p /data/wardrobe /data/uploads && chown -R appuser:appuser /data

# Entrypoint drops to appuser (remapped to PUID/PGID when set); when the
# container is started as a non-root uid (e.g. k8s runAsUser) it execs directly
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
