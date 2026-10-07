# docs-keeper memory

## Known facts (2026-10-05)
- `ACKNOWLEDGMENTS.md` line 169 "Most of upstream Odysseus's code was written *with* AI models": historical credit about how upstream Odysseus was built, not flagged by product-reference patterns. Needs scanner pattern update for "upstream" credit lines or will require LINE_EXCEPTIONS entry.
- ACKNOWLEDGEMTS.md line 3 "modified version of Odysseus, Copyright (c) Odysseus Contributors": matches credit_based_on and credit_contributors patterns, scanner-allowed.
- ACKNOWLEDGMENTS.md line 34 "scripts/odysseus-cookbook": legacy CLI shim, file-level exemption applies.
- CONTRIBUTING.md lines 98-99 have ODYSSEUS_DATA_DIR and ODYSSEUS_INTERNAL_BASE env vars, matched by env_var_names pattern.
- CONTRIBUTING.md line 57 "docker compose logs --tail=120 odysseus": compose service name, matches compose_service_names pattern.

## Edits made (S-1 sprint leftovers, 2026-10-05)
- ACKNOWLEDGMENTS.md line 37: "Odysseus's Deep Research" → "Maven's Deep Research"
- ACKNOWLEDGMENTS.md line 47: "run alongside Odysseus" → "run alongside Maven"
- ACKNOWLEDGMENTS.md line 137: "Odysseus talks to" → "Maven talks to"
- ACKNOWLEDGMENTS.md line 169: "Most of Odysseus's" → "Most of upstream Odysseus's"
- CONTRIBUTING.md line 78: "Odysseus has" → "Maven has"
