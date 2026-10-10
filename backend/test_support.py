"""Disposable fixture directories compatible with restricted Windows accounts."""
from pathlib import Path
import shutil, uuid

class TestDirectory:
    def __init__(self):
        self.path = Path(__file__).resolve().parents[4] / 'work' / ('test-' + uuid.uuid4().hex)
        self.path.mkdir(parents=True)
        self.name = str(self.path)

    def cleanup(self):
        shutil.rmtree(self.path)
