import ast
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class PythonCodeTool:
    name = "python_exec"
    description = (
        "Execute un court script Python dans un processus isole avec timeout. "
        "Retourne stdout, stderr et code de sortie."
    )
    args_schema = {
        "code": "Code Python a executer. Utilise print(...) pour afficher.",
    }
    return_direct = True
    trigger_words: tuple[str, ...] = (
        "python",
        "code python",
        "execute python",
        "exécute python",
        "lance ce code",
    )

    _blocked_modules = {
        "os",
        "pathlib",
        "shutil",
        "socket",
        "subprocess",
        "sys",
        "requests",
        "httpx",
    }
    _blocked_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "input",
        "open",
    }

    async def execute(self, **kwargs: Any) -> str:
        code = str(kwargs.get("code", "")).strip()
        if not code:
            return "Code Python manquant."
        if len(code) > 4000:
            return "Code Python trop long: limite 4000 caracteres."

        error = self._validate_code(code)
        if error:
            return error

        with tempfile.TemporaryDirectory(prefix="agent-python-") as temp_dir:
            script_path = Path(temp_dir) / "script.py"
            script_path.write_text(code, encoding="utf-8")

            try:
                completed = subprocess.run(
                    [sys.executable, "-I", str(script_path)],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return "Execution interrompue: timeout de 3 secondes."

        stdout = self._truncate(completed.stdout.strip())
        stderr = self._truncate(completed.stderr.strip())

        parts = [f"Code sortie: {completed.returncode}"]
        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        return "\n".join(parts)

    def _validate_code(self, code: str) -> str | None:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return f"Syntaxe Python invalide: {exc}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                blocked = {
                    alias.name.split(".", 1)[0]
                    for alias in node.names
                    if alias.name.split(".", 1)[0] in self._blocked_modules
                }
                if blocked:
                    return f"Import interdit: {', '.join(sorted(blocked))}"

            if isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".", 1)[0]
                if module in self._blocked_modules:
                    return f"Import interdit: {module}"

            if isinstance(node, ast.Call):
                call_name = self._call_name(node.func)
                if call_name in self._blocked_calls:
                    return f"Appel interdit: {call_name}"

        return None

    def _call_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _truncate(self, text: str) -> str:
        if len(text) <= 2000:
            return text
        return f"{text[:2000]}\n...[sortie tronquee]"
