"""llama-server lifecycle against a stub executable (real subprocess)."""

import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from molchat_agent.runtime.llama_server import (
    LlamaServer,
    LlamaServerError,
    detect_vram_gb,
    gpu_layers_for,
    resolve_binary,
)

STUB = textwrap.dedent("""\
    import sys
    from http.server import BaseHTTPRequestHandler, HTTPServer

    port = int([a for a in sys.argv if a.isdigit()][-1])

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"status":"ok"}' if self.path == "/health" else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a):
            pass

    HTTPServer(("127.0.0.1", port), H).serve_forever()
    """)


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def stub_exe(tmp_path):
    script = tmp_path / "stub-server.py"
    script.write_text(STUB, encoding="utf-8")
    model = tmp_path / "tiny.gguf"
    model.write_bytes(b"GGUF-stub")
    return script, model


def _server(stub_exe, port, **kwargs):
    script, model = stub_exe
    kwargs.setdefault("health_timeout_s", 15.0)
    return LlamaServer(
        binary=script, model=model, port=port,
        argv_builder=lambda _b, _m, p: [sys.executable, str(script), str(p)],
        gpu_layers=0, **kwargs)


def test_start_stop_lifecycle(stub_exe):
    server = _server(stub_exe, _free_port())
    try:
        assert "listening on" in server.start()
        assert server.alive() and server.healthy()
        assert server.start() == "already running"
    finally:
        assert server.stop() == "stopped"
    assert not server.alive()
    assert server.stop() == "not running"


def test_missing_binary_and_model_fail_loudly(tmp_path):
    with pytest.raises(LlamaServerError, match="no encontrado"):
        LlamaServer(binary=tmp_path / "nope.exe", model=tmp_path / "m.gguf",
                    gpu_layers=0).start()
    script = tmp_path / "s.py"
    script.write_text("x", encoding="utf-8")
    with pytest.raises(LlamaServerError, match="Modelo no encontrado"):
        LlamaServer(binary=script, model=tmp_path / "nope.gguf",
                    gpu_layers=0).start()
    with pytest.raises(LlamaServerError, match="falta el modelo"):
        LlamaServer(binary=script, gpu_layers=0).start()


def test_unhealthy_process_is_killed(tmp_path):
    sleepy = LlamaServer(
        binary=sys.executable, model=tmp_path / "m.gguf", port=_free_port(),
        argv_builder=lambda _b, _m, _p: [
            sys.executable, "-c", "import time; time.sleep(60)"],
        gpu_layers=0, health_timeout_s=1.0)
    (tmp_path / "m.gguf").write_bytes(b"x")
    with pytest.raises(LlamaServerError, match="no respondió /health"):
        sleepy.start()
    assert not sleepy.alive()


def test_default_argv_matches_llama_cli(tmp_path):
    server = LlamaServer(binary=tmp_path / "llama-server", model=tmp_path / "m.gguf",
                         port=8400, gpu_layers=0)
    argv = server._llama_argv(Path("llama-server"), Path("m.gguf"), 8400)
    assert argv[:8] == ["llama-server", "-m", "m.gguf", "--port", "8400",
                        "-c", "16384", "-ngl"]
    assert argv[8] == "0"
    assert "--jinja" in argv and "--no-webui" in argv


def test_resolve_binary_search_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(LlamaServerError):
        resolve_binary()
    local = tmp_path / "tools" / "llama"
    local.mkdir(parents=True)
    (local / "llama-server.exe").write_bytes(b"x")
    assert resolve_binary().name == "llama-server.exe"
    explicit = tmp_path / "custom.exe"
    explicit.write_bytes(b"x")
    assert resolve_binary(explicit) == explicit


def test_gpu_detection_falls_back_to_cpu(monkeypatch):
    class Done:
        returncode = 0
        stdout = "6144\n"

    assert detect_vram_gb(run=lambda *a, **k: Done()) == pytest.approx(6.0)
    assert detect_vram_gb(run=lambda *a, **k: (_ for _ in ()).throw(
        OSError("sin nvidia-smi"))) == 0.0
    assert gpu_layers_for(8.0) == -1
    assert gpu_layers_for(0.0) == 0
    assert gpu_layers_for(1.0) == 0  # model + buffer do not fit
    with pytest.raises(LlamaServerError, match="gpu_layers"):
        LlamaServer(gpu_layers="muchos")._resolve_layers()  # noqa: SLF001


def test_subprocess_leaves_no_window_flags_on_windows():
    import inspect

    source = inspect.getsource(LlamaServer.start)
    assert "creationflags" in source  # literal, reviewable (internal AST lesson)
