import contextlib
import io
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import resource as resource_module
else:
    try:
        import resource as resource_module  # Uniquement sur Unix
    except ImportError:
        resource_module = None  # type: ignore


class PythonCodeTool:
    name = "python_code"
    description = (
        "Execute du code Python isole. Utile pour les calculs complexes, "
        "le traitement de donnees ou la logique algorithmique. "
        "Securise : pas d'acces au systeme de fichiers ou au reseau."
    )
    args_schema = {
        "code": "Code Python complet a executer.",
    }
    return_direct = True
    trigger_words: tuple[str, ...] = ("python", "execute", "code")
    
    # Limites de ressources
    MAX_MEMORY_MB = 128
    
    # Whitelist de mots interdits (protection supplémentaire contre l'évasion)
    FORBIDDEN_KEYWORDS = {"__subclasses__", "__mro__", "getattr", "setattr", "eval", "exec", "pickle"}

    def infer_args(self, user_input: str, args: dict[str, Any]) -> dict[str, Any]:
        """Tente d'extraire le bloc de code Python si le LLM l'oublie dans les args."""
        if args.get("code"):
            return args

        if "```python" in user_input:
            code = user_input.split("```python")[1].split("```")[0].strip()
            return {**args, "code": code}
        
        return args

    async def execute(self, **kwargs: Any) -> str:
        code = str(kwargs.get("code", "")).strip()
        if not code:
            return "Erreur: Aucun code fourni."
            
        # 1. Whitelist / Blacklist statique du code
        for forbidden in self.FORBIDDEN_KEYWORDS:
            if forbidden in code:
                return f"Erreur de sécurité : Mot-clé interdit '{forbidden}' détecté."

        # 2. Limitation des ressources (RAM)
        if resource_module:
            # On limite la mémoire vive allouée (Soft & Hard limits)
            limit_bytes = self.MAX_MEMORY_MB * 1024 * 1024
            resource_module.setrlimit(resource_module.RLIMIT_AS, (limit_bytes, limit_bytes))  # type: ignore
            resource_module.setrlimit(resource_module.RLIMIT_CPU, (5, 5))  # type: ignore  # Max 5 sec CPU

        # Environnement restreint (Sandbox)
        # On limite les builtins pour empecher __import__, open, eval, etc.
        allowed_builtins = {
            "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
            "dict": dict, "enumerate": enumerate, "filter": filter,
            "float": float, "int": int, "len": len, "list": list,
            "map": map, "max": max, "min": min, "pow": pow, "print": print,
            "range": range, "reversed": reversed, "round": round,
            "set": set, "sorted": sorted, "str": str, "sum": sum,
            "tuple": tuple, "zip": zip,
        }

        # Utilisation d'un dictionnaire de globals restreint
        # On passe allowed_builtins explicitement pour outrepasser le defaut de Python
        safe_globals = {"__builtins__": allowed_builtins, "__name__": "__main__"}
        stdout_capture = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, safe_globals)
            output = stdout_capture.getvalue()
            return output if output else "Succes (aucune sortie console)."
        except Exception as exc:
            return f"Erreur d'execution ({type(exc).__name__}): {exc}"