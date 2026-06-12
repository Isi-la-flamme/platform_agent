from src.domain.entities.plan import Plan, Task
from src.domain.protocols.llm_provider import LLMProvider
from src.application.orchestrators.response_parser import ResponseParser
from src.application.memory_v2.memory_v2 import MemoryV2

class Planner:
    def __init__(
        self,
        llm: LLMProvider,
        parser: ResponseParser,
        memory_v2: MemoryV2 | None = None,
    ):
        self.llm = llm
        self.parser = parser
        self.memory_v2 = memory_v2

    async def create_plan(self, goal: str) -> Plan:

        skills_context = ""

        if self.memory_v2:
            skills = self.memory_v2.retrieve_skills(goal)

            if skills:
                skills_context = "\n".join(
                    f"- Tâche: {s.task} | Étapes: {', '.join(s.steps)}"
                    for s in skills[:5]
                )

        prompt = f"""
Tu es un planificateur autonome.

OBJECTIF:
{goal}

COMPETENCES APPRENTES:
{skills_context or "Aucune"}

Découpe l'objectif en sous-tâches simples.

Respecte les dépendances.

Réutilise les méthodes déjà apprises si elles sont pertinentes.

Retourne UNIQUEMENT un JSON valide :

{{
    "goal": "{goal}",
    "tasks": [
        {{
            "description": "...",
            "depends_on": [],
            "status": "pending"
        }}
    ]
}}
"""

        raw = await self.llm.chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": goal},
            ]
        )

        parsed = self.parser._extract_json(raw)

        tasks: list[Task] = []

        # planner.py - dans la boucle for t in parsed.get("tasks", []):

        for t in parsed.get("tasks", []):
            depends = t.get("depends_on", [])
            # ✅ Filtrer les valeurs non-string
            if isinstance(depends, list):
                depends = [str(d) for d in depends if d is not None]
            else:
                depends = []

            tasks.append(
                Task(
                    description=t.get("description", ""),
                    depends_on=depends,
                    status="pending",
                )
            )
        if not tasks:
            tasks.append(
                Task(
                    description=goal,
                    depends_on=[],
                    status="pending",
                )
            )

        return Plan(
            goal=parsed.get("goal", goal),
            tasks=tasks,
        )