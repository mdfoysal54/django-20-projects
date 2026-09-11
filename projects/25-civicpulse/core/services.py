from django.db import transaction
from .models import Issue, WorkOrder

class DomainError(ValueError):
    pass

@transaction.atomic
def dispatch(issue, crew, note=""):
    if issue.status in (Issue.Status.DONE, Issue.Status.DUP):
        raise DomainError("Closed issues cannot take new crews.")
    if not crew.strip():
        raise DomainError("Name a crew.")
    if WorkOrder.objects.filter(issue=issue, closed=False).exists():
        raise DomainError("An open work order already exists.")
    wo = WorkOrder.objects.create(issue=issue, crew=crew, note=note)
    issue.status = Issue.Status.WORK
    issue.save(update_fields=["status"])
    return wo

@transaction.atomic
def resolve(issue):
    open_wo = issue.orders.filter(closed=False)
    if not open_wo.exists():
        raise DomainError("Dispatch a crew before resolving.")
    open_wo.update(closed=True)
    issue.status = Issue.Status.DONE
    issue.save(update_fields=["status"])
    return issue
