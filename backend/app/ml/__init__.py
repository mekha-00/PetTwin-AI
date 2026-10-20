"""Similar-case retrieval over the external labelled case table.

This is **retrieval, not prediction**. The project explicitly does not train a
disease classifier: the only labelled dataset is 431 rows across 139 diseases,
with a largest class of 15, which cannot support a trustworthy model. Instead:

1. :mod:`app.ml.dataset` parses the external CSV into case records.
2. :mod:`app.ml.features` turns a case or a pet into a comparable feature string.
3. :mod:`app.ml.similar` embeds the cases and answers nearest-neighbour queries.
4. :mod:`app.ml.service` builds the query from a pet's Digital Twin and runs it.

A result shows the diagnosis *recorded for that case* beside the resemblance the
search found. It is not a claim about the pet.
"""

from app.ml.service import SimilarCasesResult, find_similar_cases

__all__ = ["SimilarCasesResult", "find_similar_cases"]
