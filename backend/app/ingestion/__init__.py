"""Deterministic ingestion of the Phase 1 source datasets.

The two files in ``data/raw/`` are read-only inputs. This package turns them
into normalised, reviewable outputs in ``data/processed/`` and never writes back
to the source.

Normalisation is deliberately conservative. Three tiers are applied, in order:

1. **Mechanical folding** (always applied): unicode NFKC, whitespace collapsing,
   case folding and trailing-punctuation stripping. No judgment involved, so
   this tier is safe to run unattended.
2. **Signed-off aliases** (applied only if present in ``aliases.csv``): merges
   that a human has reviewed and approved. Ships empty of clinical synonym
   merges by design.
3. **Candidate suggestions** (never applied): near-miss pairs that a reviewer
   may want to merge. Written to a review queue instead of being applied, so
   the pipeline cannot invent a clinical vocabulary.

Rule 3 of the project rules forbids guessing medical meaning. Tier 1 is
arithmetic; tiers 2 and 3 keep judgment with a person.
"""
