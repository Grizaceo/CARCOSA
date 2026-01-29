FROM carcosa:deps

WORKDIR /app

# Copy only application code (this layer changes frequently)
COPY . .

ENV PYTHONPATH=/app

CMD ["python", "-m", "sim.runner"]
