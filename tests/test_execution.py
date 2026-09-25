"""tests/test_execution.py — SubprocessBackend response-frame parsing.

The parent identifies the worker's response by job_id correlation, not by
position, so stray native stdout noise on either side of the frame is skipped
rather than fatal (issue #23).
"""

from arcgis_mcp.contracts import WorkerResult
from arcgis_mcp.execution import SubprocessBackend

_NOISE = "WARNING 000635: 输入为空或 NULL 作为空。"


def _ok(job_id: str) -> str:
    return WorkerResult(job_id=job_id, ok=True, result={"pong": True}).model_dump_json()


def _parse(job_id: str, *lines: str) -> WorkerResult:
    return SubprocessBackend._parse_response(job_id, "\n".join(lines).encode("utf-8"))


def test_single_frame_is_returned() -> None:
    res = _parse("j1", _ok("j1"))
    assert res.ok is True and res.job_id == "j1"


def test_noise_after_frame_is_skipped() -> None:
    res = _parse("j1", _ok("j1"), _NOISE)
    assert res.ok is True and res.job_id == "j1"


def test_noise_before_frame_is_skipped() -> None:
    res = _parse("j1", _NOISE, "", _ok("j1"))
    assert res.ok is True and res.job_id == "j1"


def test_crlf_line_endings_are_accepted() -> None:
    raw = f"{_NOISE}\r\n{_ok('j1')}\r\n".encode()
    assert SubprocessBackend._parse_response("j1", raw).ok is True


def test_frame_for_another_job_is_a_correlation_mismatch() -> None:
    res = _parse("j1", _ok("other"))
    assert res.ok is False and res.error is not None
    assert "Correlation mismatch" in res.error.message


def test_noise_only_is_malformed() -> None:
    res = _parse("j1", _NOISE, "{ not json")
    assert res.ok is False and res.error is not None
    assert "malformed" in res.error.message


def test_empty_stdout_reports_no_frame() -> None:
    res = SubprocessBackend._parse_response("j1", b"\n  \n")
    assert res.ok is False and res.error is not None
    assert "no response frame" in res.error.message
