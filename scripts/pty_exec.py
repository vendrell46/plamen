"""PTY-backed Claude Code execution helpers."""
from __future__ import annotations

import json
import os
import re
import select
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO


_DONE_RE = re.compile(r"\bDONE\s*:", re.IGNORECASE)
_RATE_LIMIT_STATUSES = {429, 529}


def encode_claude_project_dir(cwd: str | Path) -> str:
    """Return Claude Code's project-directory encoding for a working dir."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", str(Path(cwd).resolve()))


def claude_transcript_path(
    session_id: str,
    cwd: str | Path,
    claude_home: str | Path | None = None,
) -> Path:
    home = Path(claude_home) if claude_home else Path.home() / ".claude"
    return home / "projects" / encode_claude_project_dir(cwd) / f"{session_id}.jsonl"


def _event_message(event: dict[str, Any]) -> dict[str, Any]:
    msg = event.get("message")
    return msg if isinstance(msg, dict) else {}


def _event_text(event: dict[str, Any]) -> str:
    msg = _event_message(event)
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(parts)


def event_is_turn_end(event: dict[str, Any]) -> bool:
    if event.get("type") != "assistant":
        return False
    msg = _event_message(event)
    stop_reason = (msg.get("stop_reason") or "").lower()
    if stop_reason == "end_turn":
        return True
    content = msg.get("content")
    if stop_reason in ("", "stop", "complete", "completed") and isinstance(content, list):
        return any(isinstance(i, dict) and i.get("type") == "text" for i in content)
    return False


def event_has_done(event: dict[str, Any]) -> bool:
    return bool(_DONE_RE.search(_event_text(event)))


def event_is_rate_limited(event: dict[str, Any]) -> bool:
    status = event.get("api_error_status")
    if status in _RATE_LIMIT_STATUSES:
        return True
    for source in (event, _event_message(event), event.get("error")):
        if not isinstance(source, dict):
            continue
        status = source.get("api_error_status") or source.get("status")
        if status in _RATE_LIMIT_STATUSES:
            return True
        err = source.get("error")
        if isinstance(err, dict):
            typ = str(err.get("type") or err.get("code") or "").lower()
            if "rate_limit" in typ or "overloaded" in typ:
                return True
        typ = str(source.get("type") or source.get("code") or "").lower()
        if "rate_limit" in typ or "overloaded" in typ:
            return True
        stop = str(source.get("stop_reason") or "").lower()
        if stop in ("rate_limited", "rate_limit", "overloaded"):
            return True
    text = json.dumps(event, ensure_ascii=True).lower()
    return "rate_limit_error" in text or "overloaded_error" in text


@dataclass
class TurnCompleteState:
    complete: bool
    done_seen: bool = False
    rate_limited: bool = False
    line_count: int = 0
    last_event_time: float | None = None
    last_assistant: dict[str, Any] | None = None


def inspect_transcript(path: Path) -> TurnCompleteState:
    state = TurnCompleteState(complete=False)
    if not path.exists():
        return state
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                state.line_count += 1
                if event_is_rate_limited(event):
                    state.rate_limited = True
                if event.get("type") == "assistant":
                    state.last_assistant = event
                    if event_has_done(event):
                        state.done_seen = True
                    if event_is_turn_end(event):
                        state.complete = True
                        try:
                            state.last_event_time = path.stat().st_mtime
                        except OSError:
                            state.last_event_time = time.time()
    except OSError:
        return state
    return state


def parse_transcript_usage(path: Path) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "num_turns": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "stop_reason": "?",
        "is_error": False,
    }
    if not path.exists():
        return fields
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                if event_is_rate_limited(event):
                    fields["is_error"] = True
                    fields["api_error_status"] = 429
                    fields["stop_reason"] = "rate_limited"
                if event.get("type") != "assistant":
                    continue
                msg = _event_message(event)
                stop = msg.get("stop_reason")
                if stop:
                    fields["stop_reason"] = stop
                if event_is_turn_end(event):
                    fields["num_turns"] = int(fields.get("num_turns") or 0) + 1
                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                ):
                    try:
                        fields[key] = int(fields.get(key) or 0) + int(usage.get(key) or 0)
                    except Exception:
                        pass
    except OSError:
        pass
    if not fields.get("num_turns"):
        fields["num_turns"] = 1
    return fields


class ClaudePtySession:
    def __init__(
        self,
        argv: list[str],
        cwd: str | Path,
        env: dict[str, str],
        session_id: str,
        prompt_path: str | Path,
        log_file: TextIO,
        claude_home: str | Path | None = None,
    ) -> None:
        self.argv = argv
        self.cwd = str(cwd)
        self.env = env
        self.session_id = session_id
        self.prompt_path = Path(prompt_path)
        self.transcript_path = claude_transcript_path(session_id, cwd, claude_home)
        self.log_file = log_file
        self.proc: Any = None
        self._reader_stop = threading.Event()
        self._reader_thread: threading.Thread | None = None

    def spawn(self) -> None:
        if sys.platform == "win32":
            import winpty  # type: ignore

            self.proc = winpty.PtyProcess.spawn(
                self.argv,
                cwd=self.cwd,
                env=self.env,
                dimensions=(40, 120),
            )
        else:
            import pty

            child_pid, master_fd = pty.fork()
            if child_pid == 0:
                os.chdir(self.cwd)
                os.execvpe(self.argv[0], self.argv, self.env)
            self._child_pid = child_pid
            self._master_fd = master_fd
        self._start_reader()

    def send_bootstrap(self) -> None:
        if self.env.get("PLAMEN_BOOTSTRAP_IN_ARGV") == "1":
            return
        prompt = (
            "Read and fully execute every instruction in "
            f"{self.prompt_path.as_posix()}. When done, output your one-line "
            "DONE summary."
        )
        if sys.platform == "win32":
            self.write(prompt)
            time.sleep(0.75)
            try:
                self.proc.sendcontrol("m")
            except Exception:
                self.write("\r\n")
        else:
            self.write(prompt + "\n")

    def write(self, text: str) -> None:
        if sys.platform == "win32":
            self.proc.write(text)
        else:
            os.write(self._master_fd, text.encode("utf-8", errors="replace"))

    def is_alive(self) -> bool:
        if self.proc is None:
            return False
        if sys.platform == "win32":
            return bool(self.proc.isalive())
        try:
            pid, _status = os.waitpid(self._child_pid, os.WNOHANG)
            return pid == 0
        except ChildProcessError:
            return False

    def terminate(self, grace_s: float = 5.0) -> None:
        self._reader_stop.set()
        try:
            if self.proc is None:
                return
            if sys.platform == "win32":
                try:
                    self.proc.terminate(force=False)
                    deadline = time.time() + grace_s
                    while time.time() < deadline and self.proc.isalive():
                        time.sleep(0.1)
                    if self.proc.isalive():
                        self.proc.kill()
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
            else:
                try:
                    os.killpg(os.getpgid(self._child_pid), signal.SIGTERM)
                except Exception:
                    try:
                        os.kill(self._child_pid, signal.SIGTERM)
                    except Exception:
                        pass
                deadline = time.time() + grace_s
                while time.time() < deadline and self.is_alive():
                    time.sleep(0.1)
                if self.is_alive():
                    try:
                        os.killpg(os.getpgid(self._child_pid), signal.SIGKILL)
                    except Exception:
                        pass
        finally:
            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=1.0)

    def wait_for_turn_complete(
        self,
        timeout_s: float,
        quiescence_s: float = 8.0,
        poll_s: float = 0.1,
        transcript_poll_s: float = 0.5,
        on_poll: Any = None,
    ) -> TurnCompleteState:
        deadline = time.time() + timeout_s
        state = TurnCompleteState(complete=False)
        last_transcript_poll = 0.0
        while True:
            now = time.time()
            if now - last_transcript_poll >= transcript_poll_s:
                state = inspect_transcript(self.transcript_path)
                last_transcript_poll = now
            if on_poll:
                on_poll(now, state)
            if state.rate_limited:
                return state
            if state.complete and state.last_event_time is not None:
                if now - state.last_event_time >= quiescence_s:
                    return state
            if not self.is_alive():
                return state
            if now >= deadline:
                return state
            time.sleep(poll_s)

    def _start_reader(self) -> None:
        def _reader() -> None:
            while not self._reader_stop.is_set():
                try:
                    if sys.platform == "win32":
                        if not self.proc or not self.proc.isalive():
                            break
                        chunk = self.proc.read(4096)
                    else:
                        readable, _, _ = select.select([self._master_fd], [], [], 0.25)
                        if not readable:
                            if not self.is_alive():
                                break
                            continue
                        data = os.read(self._master_fd, 4096)
                        if not data:
                            break
                        chunk = data.decode("utf-8", errors="replace")
                    if chunk:
                        self.log_file.write(chunk)
                        self.log_file.flush()
                except Exception:
                    time.sleep(0.1)

        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()
