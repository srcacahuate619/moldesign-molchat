FROM python:3.12-slim
WORKDIR /molchat
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN python -m pip install --no-cache-dir '.[dev]'
COPY tests/ tests/
COPY kit/vmat2-run/ kit/vmat2-run/
COPY benchmarks/ benchmarks/
ENV PYTHONPATH=/molchat/src:/molchat
EXPOSE 8771
CMD ["python", "benchmarks/run_benchmark.py", "--output", "/molchat/reports/benchmark-run", "--repetitions", "3"]
