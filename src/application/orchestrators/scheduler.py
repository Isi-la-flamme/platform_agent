from src.domain.entities.plan import Plan


class Scheduler:
    def get_next_task(self, plan: Plan):
        completed = {t.id for t in plan.tasks if t.status == "completed"}

        for task in plan.tasks:
            if task.status != "pending":
                continue

            if all(dep in completed for dep in task.depends_on):
                return task

        return None