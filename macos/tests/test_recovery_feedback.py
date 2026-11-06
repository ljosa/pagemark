"""Recovery failures remain visible without repeatedly interrupting typing."""
import pytest

objc = pytest.importorskip("objc")

from pagemark_app import application  # noqa: E402
from pagemark_app.codec import StyledText  # noqa: E402
from pagemark_app.recovery import RecoveryStore  # noqa: E402
from pagemark_app.session import Snapshot  # noqa: E402


class RecoveryFeedbackDocument(application.PagemarkDocument):
    @objc.python_method
    def report_error(self, error):
        self.errors.append(str(error))


@pytest.mark.parametrize("operation", ["write", "remove"])
def test_recovery_failure_reports_once_until_success_and_preserves_document(tmp_path, monkeypatch, operation):
    store = RecoveryStore(tmp_path)
    monkeypatch.setattr(application, "recovery_store", lambda: store)
    document = RecoveryFeedbackDocument.alloc().init()
    document.errors = []
    document.session.restore(Snapshot(StyledText("edited", (0,) * 6), 3, 0, 0))
    before = document.session.snapshot()
    original = getattr(store, operation)
    call = (lambda: document.writeRecovery_(None)) if operation == "write" else document.clear_recovery

    def fail(*args):
        raise OSError("disk error")

    monkeypatch.setattr(store, operation, fail)
    call()
    call()
    assert len(document.errors) == 1
    assert "disk error" in document.errors[0]
    monkeypatch.setattr(store, operation, original)
    call()
    assert document.recovery_error is None
    monkeypatch.setattr(store, operation, fail)
    call()
    assert len(document.errors) == 2
    assert document.session.snapshot() == before
