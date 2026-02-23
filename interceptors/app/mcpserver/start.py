"""OTEL-instrumented entry point for the MCP server.

AgentCore Runtime code configuration EntryPoint only accepts single-script
format (e.g. ["start.py"]). Multi-command format like
["opentelemetry-instrument", "python", "main.py"] fails CFN validation.

This wrapper programmatically invokes the opentelemetry-instrument bootstrap,
which sets up PYTHONPATH with a custom sitecustomize.py that loads the AWS
distro, configurator, and all available instrumentors, then runs main.py
as a subprocess with full OTEL auto-instrumentation.

The runtime container provides OTEL env vars (OTEL_PYTHON_DISTRO=aws_distro,
OTEL_PYTHON_CONFIGURATOR=aws_configurator, OTEL_EXPORTER_OTLP_LOGS_HEADERS)
that the auto-instrumentation reads during bootstrap.
"""
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
main_py = os.path.join(script_dir, "main.py")

sys.argv = ["opentelemetry-instrument", sys.executable, main_py]

from opentelemetry.instrumentation.auto_instrumentation import run  # noqa: E402

run()
