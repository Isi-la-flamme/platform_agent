from src.domain.entities.plan import Plan, Task
from src.domain.protocols.llm_provider import LLMProvider
from src.application.orchestrators.response_parser import ResponseParser


class Planner:
    def __init__(self, llm: LLMProvider, parser: ResponseParser):
        self.llm = llm
        self.parser = parser

    async def create_plan(self, goal: str) -> Plan:
        prompt = f"""
Tu es un planificateur.

Découpe l'objectif en étapes simples et exécutables.

Retourne UNIQUEMENT un JSON valide:

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

        raw = await self.llm.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": goal}
        ])

        parsed = self.parser._extract_json(raw)

        tasks = []
        for t in parsed.get("tasks", []):
            tasks.append(Task(
                description=t["description"],
                depends_on=t.get("depends_on", []),
                status="pending"
            ))

        return Plan(
            goal=parsed.get("goal", goal),
            tasks=tasks
        )