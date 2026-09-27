"""MLflow tracing integration with PHI redaction.

Story 1.4: real implementation replacing the 1.1 stub.

Key responsibilities
--------------------
* ``init_tracing()`` — configure MLflow tracking URI + experiment, register the
  :class:`RedactingSpanExporter`, call LangChain/LiteLLM autolog, and install a
  :class:`RedactingFormatter` on the root logger.
* ``span()`` — thin context manager wrapper around ``mlflow.start_span`` that
  preserves the call-site signature from story 1.1.
* :class:`RedactingSpanExporter` — subclasses the MLflow V2 exporter; redacts
  span inputs/outputs before they are written to the tracking server.
* :class:`RedactingFormatter` — Python :class:`logging.Formatter` that passes
  each log record message through :func:`~observability.redaction.redact`.
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import Any

import mlflow
import mlflow.langchain
import mlflow.litellm
import mlflow.tracing.provider as _mlflow_prov
from mlflow.tracing.constant import SpanAttributeKey
from mlflow.tracing.export.mlflow_v2 import MlflowV2SpanExporter
from mlflow.tracing.processor.mlflow_v2 import MlflowV2SpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ReadableSpan, SimpleSpanProcessor

from observability.redaction import redact

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redacting span exporter
# ---------------------------------------------------------------------------


class RedactingSpanExporter(MlflowV2SpanExporter):
    """MLflow V2 exporter that redacts PHI from span inputs/outputs before export.

    The exporter intercepts each completed trace, walks every span's
    ``mlflow.spanInputs`` and ``mlflow.spanOutputs`` OTel attributes, runs
    :func:`~observability.redaction.redact` on the deserialised values, and
    writes the sanitised JSON back into the span attribute dict *before*
    passing the trace to the upstream ``_log_trace`` machinery.

    The underlying ``BoundedAttributes`` dict is immutable once the span has
    ended, so redaction writes directly to the internal ``_dict`` after
    temporarily lifting the immutability guard.
    """

    # Keys whose string values contain JSON-serialised PHI
    _PHI_KEYS: tuple[str, ...] = (
        SpanAttributeKey.INPUTS,
        SpanAttributeKey.OUTPUTS,
    )

    def export(self, spans: Sequence[ReadableSpan]) -> None:  # type: ignore[override]
        for otel_span in spans:
            if otel_span._parent is not None:
                _logger.debug("Received non-root span – skipping.")
                continue

            manager_trace = self._trace_manager.pop_trace(otel_span.context.trace_id)
            if manager_trace is None:
                _logger.debug("Trace not found in InMemoryTraceManager – skipping.")
                continue

            trace = manager_trace.trace

            # --- redact every span in the trace ----------------------------
            for mlflow_span in trace.data.spans:
                self._redact_span(mlflow_span._span)

            # Also redact the summary preview stored in trace metadata
            self._redact_trace_metadata(trace)

            # Delegate the actual upload to the parent class machinery
            self._log_trace(trace)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _redact_span(otel_span: Any) -> None:
        """Redact PHI keys in an OTel span's BoundedAttributes in-place."""
        attrs = getattr(otel_span, "_attributes", None)
        if attrs is None:
            return
        internal: dict[str, Any] = getattr(attrs, "_dict", {})
        for key in (SpanAttributeKey.INPUTS, SpanAttributeKey.OUTPUTS):
            raw = internal.get(key)
            if raw is None:
                continue
            try:
                parsed = json.loads(raw)
                redacted = redact(parsed)
                # BoundedAttributes is immutable after span.end(); bypass the
                # guard by temporarily lowering the immutability flag.
                was_immutable = getattr(attrs, "_immutable", False)
                attrs._immutable = False
                internal[key] = json.dumps(redacted, ensure_ascii=False)
                attrs._immutable = was_immutable
            except Exception:  # noqa: BLE001
                _logger.debug("Failed to redact key %s", key, exc_info=True)

    @staticmethod
    def _redact_trace_metadata(trace: Any) -> None:
        """Redact the truncated input/output preview stored in trace metadata."""
        try:
            meta = trace.info.request_metadata
            for key in list(meta):
                if key.endswith(".inputs") or key.endswith(".outputs"):
                    val = meta[key]
                    if isinstance(val, str):
                        try:
                            parsed = json.loads(val)
                            meta[key] = json.dumps(
                                redact(parsed), ensure_ascii=False
                            )
                        except (json.JSONDecodeError, TypeError):
                            meta[key] = redact(val)
        except Exception:  # noqa: BLE001
            _logger.debug("Failed to redact trace metadata", exc_info=True)


# ---------------------------------------------------------------------------
# Redacting log formatter
# ---------------------------------------------------------------------------


class RedactingFormatter(logging.Formatter):
    """Python :class:`logging.Formatter` that redacts PHI from log messages.

    Install on any handler to ensure log lines are sanitised::

        handler.setFormatter(RedactingFormatter("%(levelname)s %(message)s"))
    """

    def format(self, record: logging.LogRecord) -> str:
        record.msg = redact(record.msg) if isinstance(record.msg, str) else record.msg
        # Also scrub pre-formatted args if they look like dicts/lists
        if record.args:
            try:
                record.args = redact(record.args)  # type: ignore[assignment]
            except Exception:  # noqa: BLE001
                pass
        return super().format(record)


# ---------------------------------------------------------------------------
# init_tracing()
# ---------------------------------------------------------------------------


def init_tracing(
    tracking_uri: str | None = None,
    experiment: str | None = None,
    git_sha: str | None = None,
    app_env: str | None = None,
    llm_mode: str | None = None,
) -> None:
    """Initialise MLflow tracing with PHI redaction.

    Parameters
    ----------
    tracking_uri:
        MLflow tracking server URI (default: ``$MLFLOW_TRACKING_URI``).
    experiment:
        MLflow experiment name (default: ``$MLFLOW_EXPERIMENT``).
    git_sha:
        Current git commit SHA for trace tagging (default: ``$GIT_SHA``).
    app_env:
        Deployment environment label, e.g. ``local`` / ``prod``
        (default: ``$APP_ENV``).
    llm_mode:
        ``mock`` or ``bedrock`` (default: ``$LLM_MODE``).
    """
    uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "")
    exp = experiment or os.getenv("MLFLOW_EXPERIMENT", "claims-intake-agent")
    _git_sha = git_sha or os.getenv("GIT_SHA", "unknown")
    _app_env = app_env or os.getenv("APP_ENV", "local")
    _llm_mode = llm_mode or os.getenv("LLM_MODE", "mock")

    # ------------------------------------------------------------------
    # Configure MLflow backend
    # ------------------------------------------------------------------
    if uri:
        mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(exp)

    # ------------------------------------------------------------------
    # Build a custom TracerProvider backed by RedactingSpanExporter
    # ------------------------------------------------------------------
    exporter = RedactingSpanExporter(tracking_uri=uri or None)
    processor = MlflowV2SpanProcessor(
        span_exporter=exporter,
        tracking_uri=uri or None,
    )

    # MLflow 3.1.0: BaseMlflowSpanProcessor.__init__ does not call
    # super().__init__(), so the OTel SimpleSpanProcessor attributes
    # (_shutdown, _metrics) are never set.  Fix this here.
    if not hasattr(processor, "_metrics"):
        SimpleSpanProcessor.__init__(processor, exporter)

    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(processor)

    # Replace the global MLflow tracer provider (type: ignore needed because
    # mlflow.tracing.provider types _MLFLOW_TRACER_PROVIDER as None initially)
    _mlflow_prov._MLFLOW_TRACER_PROVIDER = tracer_provider  # type: ignore[assignment]
    _mlflow_prov._MLFLOW_TRACER_PROVIDER_INITIALIZED.done = True

    # ------------------------------------------------------------------
    # GenAI autolog for LangChain + LiteLLM
    # ------------------------------------------------------------------
    try:
        mlflow.langchain.autolog()
    except Exception:  # noqa: BLE001
        _logger.debug("mlflow.langchain.autolog() failed", exc_info=True)

    try:
        mlflow.litellm.autolog()
    except Exception:  # noqa: BLE001
        _logger.debug("mlflow.litellm.autolog() failed", exc_info=True)

    # ------------------------------------------------------------------
    # Attach RedactingFormatter to the root logger
    # ------------------------------------------------------------------
    root = logging.getLogger()
    for handler in root.handlers:
        if not isinstance(handler.formatter, RedactingFormatter):
            handler.setFormatter(
                RedactingFormatter(
                    fmt=getattr(handler.formatter, "_fmt", None)
                    or "%(levelname)s %(name)s %(message)s"
                )
            )

    _logger.info(
        "MLflow tracing initialised: uri=%s experiment=%s app_env=%s "
        "git_sha=%s llm_mode=%s",
        uri or "(default)",
        exp,
        _app_env,
        _git_sha,
        _llm_mode,
    )


# ---------------------------------------------------------------------------
# span() context manager
# ---------------------------------------------------------------------------


@contextmanager
def span(name: str, **attributes: Any) -> Generator[None]:
    """Context manager that records an MLflow span.

    Wraps :func:`mlflow.start_span`.  Attributes are passed directly to the
    span's ``inputs`` so they appear in the MLflow UI.  PHI is redacted by
    the :class:`RedactingSpanExporter` before the trace is persisted.

    The signature (name + **attributes, yields None) is stable across
    stories — downstream code must not rely on the yielded value.

    Example::

        with tracing.span("node.router", intent="coverage"):
            ...
    """
    with mlflow.start_span(name=name) as mlflow_span:
        if attributes:
            mlflow_span.set_inputs(attributes)
        yield
