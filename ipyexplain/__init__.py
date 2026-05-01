"""
ipyexplain – JupyterLab extension for AI-powered error explanation, code fixing,
and code generation using OpenAI's API.
"""
from ._version import __version__


def _jupyter_labextension_paths():
    """Called by JupyterLab to discover the frontend extension."""
    return [{"src": "labextension", "dest": "ipyexplain"}]


def _jupyter_server_extension_points():
    """Called by Jupyter server to discover the server extension."""
    return [{"module": "ipyexplain"}]


def _load_jupyter_server_extension(server_app):
    """Load the Jupyter server extension."""
    from .handlers import setup_handlers

    setup_handlers(server_app.web_app)
    server_app.log.info("Registered ipyexplain server extension")
