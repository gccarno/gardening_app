"""
Optional MLflow tracing for the chat agent.

MLflow lives in the `evaluation` extra and is deliberately ABSENT in production:
Render builds with `uv sync --frozen --no-dev`, which installs no extras, and
MLflow has no business on a 512 MB free instance.

`chat_tools.py` is imported by the live backend, so everything here must degrade
to a no-op rather than raise. Importing this module is always safe; a bare
`import mlflow` in the agent code would take production down.

Enable locally with:
    uv pip install "mlflow>=3.8"
    uv run python -m ml.chat_eval.run_eval      # calls setup() for you
    uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
"""
import os
from contextlib import contextmanager
from pathlib import Path

try:
    import mlflow
    from mlflow.entities import SpanType

    TRACING_AVAILABLE = True
except ImportError:                                    # production path
    TRACING_AVAILABLE = False

    class SpanType:                                    # keeps annotations valid
        CHAIN = 'CHAIN'
        LLM = 'LLM'
        TOOL = 'TOOL'
        RETRIEVER = 'RETRIEVER'
        AGENT = 'AGENT'


_REPO_ROOT = Path(__file__).resolve().parents[3]
# MLflow 3.x put the './mlruns' file store into maintenance mode and refuses to
# open one without an opt-out env var, so the local default is SQLite. Any
# SQLAlchemy URL works here — including a Postgres/Neon branch for a shared store.
DEFAULT_TRACKING_URI = f'sqlite:///{_REPO_ROOT / "mlflow.db"}'
DEFAULT_EXPERIMENT = 'garden-chat-agent'


def trace(name=None, span_type=None):
    """`@mlflow.trace` when MLflow is installed, identity decorator otherwise."""
    def decorator(fn):
        if not TRACING_AVAILABLE:
            return fn
        return mlflow.trace(name=name or fn.__name__, span_type=span_type)(fn)
    return decorator


@contextmanager
def span(name, span_type=None, inputs=None):
    """Context-manager span. Yields None (not a span) when MLflow is absent."""
    if not TRACING_AVAILABLE:
        yield None
        return
    with mlflow.start_span(name=name, span_type=span_type) as s:
        if inputs is not None:
            s.set_inputs(inputs)
        yield s


def set_outputs(active_span, outputs):
    """Set span outputs, tolerating the no-op span from the context manager."""
    if active_span is not None:
        active_span.set_outputs(outputs)


def setup(experiment_name=DEFAULT_EXPERIMENT, tracking_uri=None):
    """Point MLflow at a local file store.

    Called by the offline eval harness only — never by the running app, which is
    why it raises loudly instead of no-oping. Honours MLFLOW_TRACKING_URI /
    MLFLOW_EXPERIMENT_NAME when they are already set (the eval skill's
    pre-configured-environment case).
    """
    if not TRACING_AVAILABLE:
        raise RuntimeError(
            'MLflow is not installed. Run: uv pip install "mlflow>=3.8"'
        )
    uri = tracking_uri or os.environ.get('MLFLOW_TRACKING_URI') or DEFAULT_TRACKING_URI
    mlflow.set_tracking_uri(uri)
    name = os.environ.get('MLFLOW_EXPERIMENT_NAME') or experiment_name
    mlflow.set_experiment(name)
    return uri, name
