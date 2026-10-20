"""Import every model so Base.metadata is complete (used by Alembic)."""
from app.models import *  # noqa: F401,F403
from app.projects.models import *  # noqa: F401,F403
from app.boq.models import *  # noqa: F401,F403
from app.budgets.models import *  # noqa: F401,F403
from app.inventory.models import *  # noqa: F401,F403
from app.procurement.models import *  # noqa: F401,F403
from app.labour.models import *  # noqa: F401,F403
from app.dailylogs.models import *  # noqa: F401,F403
from app.documents.models import *  # noqa: F401,F403
from app.rag.models import *  # noqa: F401,F403
from app.ai_assistant.models import *  # noqa: F401,F403
from app.dashboards.models import *  # noqa: F401,F403
from app.cv.models import *  # noqa: F401,F403
from app.ml.models import *  # noqa: F401,F403
from app.commercial.models import *  # noqa: F401,F403
from app.tasks.models import *  # noqa: F401,F403
from app.expenses.models import *  # noqa: F401,F403
