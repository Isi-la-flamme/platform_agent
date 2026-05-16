import ast
import operator
from collections.abc import Callable
from typing import Any


class CalculatorTool:
    name = "calculator"
    description = (
        "Evalue une expression mathematique simple et sure. "
        "Operations supportees: +, -, *, /, //, %, ** et parentheses."
    )
    args_schema = {
        "expression": "Expression mathematique a evaluer, exemple: 2 + 2 * 3.",
    }
    return_direct = True
    trigger_words: tuple[str, ...] = (
        "calcule",
        "calcul",
        "combien font",
        "combien fait",
        "+",
        "-",
        "*",
        "/",
        "=",
    )

    _binary_operators: dict[type[ast.operator], Callable[[float, float], float]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary_operators: dict[type[ast.unaryop], Callable[[float], float]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def infer_args(self, user_input: str, args: dict[str, Any]) -> dict[str, Any]:
        """Tente d'extraire l'expression mathématique depuis l'entrée utilisateur."""
        if args.get("expression"):
            return args

        expression = user_input.lower()
        prefixes = (
            "calcule",
            "calcul",
            "combien font",
            "combien fait",
        )
        for prefix in prefixes:
            if expression.startswith(prefix):
                expression = expression[len(prefix) :]
                break

        expression = expression.replace("?", "").replace("=", "")
        return {**args, "expression": expression.strip()}

    async def execute(self, **kwargs: Any) -> str:
        expression = str(kwargs.get("expression", "")).strip()
        if not expression:
            return "Expression manquante."

        try:
            tree = ast.parse(expression, mode="eval")
            result = self._evaluate(tree.body)
        except Exception as exc:
            return f"Calcul impossible: {exc}"

        if result.is_integer():
            return str(int(result))
        return str(result)

    def _evaluate(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)

        if isinstance(node, ast.BinOp):
            binary_operator_fn = self._binary_operators.get(type(node.op))
            if not binary_operator_fn:
                raise ValueError("operateur non supporte")

            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("puissance trop grande")
            return float(binary_operator_fn(left, right))

        if isinstance(node, ast.UnaryOp):
            unary_operator_fn = self._unary_operators.get(type(node.op))
            if not unary_operator_fn:
                raise ValueError("operateur unaire non supporte")
            return float(unary_operator_fn(self._evaluate(node.operand)))

        raise ValueError("expression non supportee")
