import shutil
from pathlib import Path
from typing import Any


class FileCrudTool:
    name = "file_crud"
    description = (
        "Cree, lit, modifie ou supprime un fichier ou un dossier dans le workspace. "
        "Les chemins doivent etre relatifs au projet."
    )
    args_schema = {
        "action": "Action: create, read, update, delete.",
        "path": "Chemin relatif du fichier dans le workspace.",
        "content": "Contenu du fichier. Pour un dossier: omets ce champ ou termine le 'path' par '/'.",
        "mode": "Pour update: overwrite ou append. Defaut: overwrite.",
    }
    optional_args = ("mode",)
    return_direct = True
    trigger_words: tuple[str, ...] = (
        "fichier",
        "file",
        "créer",
        "creer",
        "crée",
        "cree",
        "lire",
        "lit",
        "modifier",
        "modifie",
        "supprimer",
        "supprime",
        "écrire",
        "ecrire",
        "dossier",
        "folder",
        "repertoire",
    )


    _blocked_parts = {
        ".git",
        ".venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
    _blocked_names = {
        ".env",
    }
    # ✅ AJOUT
    _blocked_extensions = {
        ".exe", ".dll", ".so", ".dylib", ".sh", ".bash", ".bat", ".cmd",
        ".ps1", ".vbs", ".reg", ".msi", ".apk", ".app", ".bin", ".run",
        ".cpl", ".scr", ".jar", ".pyc", ".pyo",
    }
    _max_read_bytes = 100_000
    _max_output_chars = 4_000

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or Path.cwd()).resolve()

    async def execute(self, **kwargs: Any) -> str:
        action = str(kwargs.get("action", "")).strip().lower()
        raw_path = str(kwargs.get("path", "")).strip()
        content_val = kwargs.get("content")
        mode = str(kwargs.get("mode", "overwrite")).strip().lower()

        if action not in {"create", "read", "update", "delete"}:
            return "Action invalide. Actions supportees: create, read, update, delete."

        try:
            path = self._safe_path(raw_path)
        except ValueError as exc:
            return str(exc)

        if action == "create":
            # Détection intelligente du type (Fichier vs Dossier)
            user_req = str(kwargs.get("user_input", "")).lower()
            is_explicit_dir = any(w in user_req for w in ["dossier", "folder", "repertoire"])
            
            is_dir_request = (
                raw_path.endswith(("/", "\\")) or 
                content_val is None or 
                (isinstance(content_val, str) and not content_val.strip() and is_explicit_dir)
            )

            if is_dir_request:
                if path.exists():
                    return f"Creation refusee: {self._relative(path)} existe deja."
                path.mkdir(parents=True, exist_ok=True)
                return f"Dossier cree: {self._relative(path)}"
            return self._create(path, str(content_val))
            
        if action == "read":
            return self._read(path)
            
        if action == "update":
            if path.is_dir():
                return "Modification impossible: les dossiers ne peuvent pas etre modifies via update."
            return self._update(path, str(content_val or ""), mode)
            
        return self._delete(path)

    def _safe_path(self, raw_path: str) -> Path:
        if not raw_path:
            raise ValueError("Chemin manquant.")

        candidate = Path(raw_path)
        if candidate.is_absolute():
            raise ValueError("Chemin refuse: utilise un chemin relatif au workspace.")

        resolved = (self.root / candidate).resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError("Chemin refuse: sortie du workspace interdite.")

        relative_parts = resolved.relative_to(self.root).parts
        if any(part in self._blocked_parts for part in relative_parts):
            raise ValueError("Chemin refuse: dossier protege.")
        if resolved.name in self._blocked_names:
            raise ValueError("Chemin refuse: fichier protege.")
        # ✅ AJOUT
        if resolved.suffix.lower() in self._blocked_extensions:
            raise ValueError(f"Chemin refuse: extension bloquée '{resolved.suffix}'.")

        return resolved
    
    def _create(self, path: Path, content: str) -> str:
        if path.exists():
            return f"Creation refusee: {self._relative(path)} existe deja."

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Fichier cree: {self._relative(path)}"

    def _read(self, path: Path) -> str:
        if not path.exists():
            return f"Lecture impossible: {self._relative(path)} introuvable."
        
        if path.is_dir():
            items = sorted([f"{p.name}/" if p.is_dir() else p.name for p in path.iterdir()])
            header = f"Contenu du dossier {self._relative(path)} :\n"
            return header + ("\n".join(items) if items else "(dossier vide)")

        if path.stat().st_size > self._max_read_bytes:
            return "Lecture refusee: fichier trop volumineux."

        content = path.read_text(encoding="utf-8", errors="replace")
        return self._truncate(content)
    
    def _delete(self, path: Path) -> str:
        if not path.exists():
            return f"Suppression impossible: {self._relative(path)} introuvable."
        
        if path == self.root:
            return "Suppression refusee: impossible de supprimer la racine du workspace."

        if path.is_dir():
            shutil.rmtree(path)
            return f"Dossier supprime recursivement : {self._relative(path)}"
        else:
            path.unlink()
            return f"Fichier supprime : {self._relative(path)}"

    def _relative(self, path: Path) -> str:
        if path == self.root:
            return "."
        return path.relative_to(self.root).as_posix()

    def _update(self, path: Path, content: str, mode: str) -> str:
        if not path.exists():
            return f"Modification impossible: {self._relative(path)} introuvable."
        if not path.is_file():
            return "Modification impossible: ce chemin n'est pas un fichier."
        if mode not in {"overwrite", "append"}:
            return "Mode invalide. Modes supportes: overwrite, append."

        if mode == "append":
            with path.open("a", encoding="utf-8") as file:
                file.write(content)
        else:
            path.write_text(content, encoding="utf-8")

        return f"Fichier modifie: {self._relative(path)}"

    def _truncate(self, text: str) -> str:
        if len(text) <= self._max_output_chars:
            return text
        return f"{text[: self._max_output_chars]}\n...[sortie tronquee]"
