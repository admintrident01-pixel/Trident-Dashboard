import ast,unittest
from pathlib import Path
class DeploymentModules(unittest.TestCase):
 def test_every_local_import_is_in_the_backend_container(self):
  root=Path(__file__).resolve().parent
  copied=set()
  for line in (root/'Dockerfile').read_text().splitlines():
   if line.startswith('COPY '):copied.update(line.split()[1:-1])
  for name in copied:
   if not name.endswith('.py'):continue
   tree=ast.parse((root/name).read_text(encoding='utf-8'))
   for node in ast.walk(tree):
    imports=[alias.name.split('.')[0] for alias in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else []
    for module in imports:
     if (root/(module+'.py')).exists():self.assertIn(module+'.py',copied,f'{name} imports {module}, which is missing from the deployment')
