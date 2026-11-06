"""Atomic recovery copies; paths in records are labels, never authority to open files."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import tempfile
import uuid

from .codec import MAX_DOCUMENT_BYTES, StyledText
from .session import Snapshot

MAX_RECORD_BYTES = MAX_DOCUMENT_BYTES * 12


class RecoveryStore:
    def __init__(self, directory):
        self.directory = Path(directory)

    def path(self, identifier):
        if str(uuid.UUID(identifier)) != identifier:
            raise ValueError("Invalid recovery identifier")
        return self.directory / (identifier + ".json")

    def write(self, identifier, snapshot, title, original=None):
        # RLE keeps a plain document's recovery copy close to its source size.
        runs = []
        for flag in snapshot.value.styles:
            if runs and runs[-1][1] == flag:
                runs[-1][0] += 1
            else:
                runs.append([1, flag])
        record = {"version": 1, "title": title, "text": snapshot.value.text, "styles": runs,
                  "cursor": snapshot.cursor, "anchor": snapshot.anchor,
                  "caret_style": snapshot.caret_style,
                  "desired_column": snapshot.desired_column,
                  "original": base64.b64encode(original).decode("ascii") if original else None}
        payload = json.dumps(record, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_RECORD_BYTES:
            raise ValueError("Document is too large for a recovery copy")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = self.path(identifier)
        fd, temporary = tempfile.mkstemp(prefix=".recovery-", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def read(self, identifier):
        path = self.path(identifier)
        with path.open("rb") as stream:
            payload = stream.read(MAX_RECORD_BYTES + 1)
        if len(payload) > MAX_RECORD_BYTES:
            raise ValueError("Recovery copy is too large")
        record = json.loads(payload)
        if record.get("version") != 1 or not isinstance(record.get("text"), str):
            raise ValueError("Unsupported recovery copy")
        text = record["text"]
        styles = []
        for run in record["styles"]:
            count, flag = run
            if (type(count) is not int or count <= 0 or flag not in (0, 1, 2, 3)
                    or len(styles) + count > len(text)):
                raise ValueError("Invalid recovery formatting")
            styles.extend([flag] * count)
        value = StyledText(text, tuple(styles))
        cursor, anchor = record["cursor"], record["anchor"]
        for position in (cursor, anchor):
            if position is not None and (type(position) is not int or not 0 <= position <= len(text)):
                raise ValueError("Invalid recovery selection")
        if cursor is None or record["caret_style"] not in (0, 1, 2, 3):
            raise ValueError("Invalid recovery cursor")
        original = base64.b64decode(record["original"], validate=True) if record["original"] else None
        if original is not None and len(original) > MAX_DOCUMENT_BYTES:
            raise ValueError("Invalid recovery source")
        column = record.get("desired_column")
        if column is not None and (type(column) is not int or not 0 <= column <= 1_000_000):
            raise ValueError("Invalid recovery column")
        return Snapshot(value, cursor, anchor, record["caret_style"], column), str(record["title"]), original

    def identifiers(self):
        if not self.directory.exists():
            return []
        identifiers = []
        for path in sorted(self.directory.glob("*.json"), key=lambda path: path.stat().st_mtime):
            try:
                self.path(path.stem)
            except ValueError:
                continue
            identifiers.append(path.stem)
        return identifiers

    def remove(self, identifier):
        self.path(identifier).unlink(missing_ok=True)
