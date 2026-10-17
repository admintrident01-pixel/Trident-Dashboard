"""Disposable test fixtures with ordinary inherited Windows permissions."""
from pathlib import Path
import os,shutil,uuid
class TestDirectory:
    def __init__(self):
        self.root=Path(os.environ.get('TRIDENT_TEST_ROOT',str(Path(__file__).resolve().parent.parent/'.local-data'/'test-runs'))).resolve()
        self.path=self.root/('test-'+uuid.uuid4().hex)
        self.path.mkdir(parents=True)
        self.name=str(self.path)
    def cleanup(self):
        resolved=self.path.resolve()
        if resolved.parent!=self.root or not resolved.name.startswith('test-'):raise RuntimeError('Unsafe test cleanup target')
        shutil.rmtree(resolved)
