# Neo4j graph development

The infrastructure topology graph is stored in Neo4j. Diagnostic playbooks,
approvals, and investigation records still use the existing SQLite repository.
These are deliberately separate storage concerns.

Install the optional driver:

```bash
pip install "neo4j>=5,<7"
```

Start Neo4j with a strong password:

```bash
export NEO4J_AUTH='neo4j/change-this-password'
docker compose -f docker-compose.neo4j.yml up -d
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD='change-this-password'
pytest -q tests/test_neo4j_graph.py
```

Use `Neo4jRepository.connect(...)` and call `initialize()` before writing.
The graph API accepts a repository protocol, allowing a future Apache AGE
adapter and contract tests. Do not pass unverified LLM entity guesses to
`KnowledgeGraph.add_entity`; the current `verified=True` gate is a placeholder,
not an authenticated MCP verification boundary.

Neo4j Community Edition licensing and customer deployment requirements
must be reviewed before redistribution.
