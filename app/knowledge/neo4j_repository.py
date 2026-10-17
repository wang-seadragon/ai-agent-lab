"""Neo4j graph adapter. Cypher stays in this module for AGE portability."""
from app.knowledge.models import Relationship, VerifiedEntity

# Relationship types cannot be query parameters; restrict them to this allowlist.
RELATIONSHIP_TYPES = frozenset({
    "DEPENDS_ON", "CONSUMES_FROM", "WRITES_TO", "RUNS_ON", "CALLS",
})


class Neo4jRepository:
    def __init__(self, driver, database: str = "neo4j"):
        self.driver = driver
        self.database = database

    @classmethod
    def connect(cls, uri: str, username: str, password: str,
                database: str = "neo4j"):
        from neo4j import GraphDatabase
        return cls(GraphDatabase.driver(uri, auth=(username, password)), database)

    def close(self):
        self.driver.close()

    def initialize(self):
        with self.driver.session(database=self.database) as session:
            session.run("CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
                        "FOR (e:Entity) REQUIRE e.id IS UNIQUE").consume()

    def upsert_entity(self, entity: VerifiedEntity) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(
                "MERGE (e:Entity {id:$id}) SET e.kind=$kind",
                id=entity.entity_id, kind=entity.kind,
            ).consume()

    def get_entity(self, entity_id: str) -> VerifiedEntity | None:
        with self.driver.session(database=self.database) as session:
            row = session.run(
                "MATCH (e:Entity {id:$id}) RETURN e.id AS id,e.kind AS kind",
                id=entity_id,
            ).single()
            return VerifiedEntity(row["id"], row["kind"]) if row else None

    def add_relationship(self, relationship: Relationship) -> None:
        kind = relationship.relationship_type
        if kind not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unsupported relationship type: {kind}")
        with self.driver.session(database=self.database) as session:
            # MATCH rather than MERGE nodes: only pre-verified entities may connect.
            result = session.run(
                f"MATCH (s:Entity {{id:$source}}), (t:Entity {{id:$target}}) "
                f"MERGE (s)-[:{kind}]->(t) RETURN count(*) AS count",
                source=relationship.source_id, target=relationship.target_id,
            ).single()
            if not result or result["count"] != 1:
                raise ValueError("Both relationship endpoints must be verified entities")

    def get_related(self, entity_id: str, *, direction: str = "outgoing",
                    relationship_type: str | None = None) -> list[VerifiedEntity]:
        if direction not in {"outgoing", "incoming"}:
            raise ValueError("Direction must be outgoing or incoming")
        if relationship_type is not None and relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError("Unsupported relationship type")
        rel = f":{relationship_type}" if relationship_type else ""
        edge = (f"-[{rel}]->" if direction == "outgoing" else f"<-[{rel}]-")
        query = (f"MATCH (e:Entity {{id:$id}}){edge}(other:Entity) "
                 "RETURN DISTINCT other.id AS id,other.kind AS kind ORDER BY id")
        with self.driver.session(database=self.database) as session:
            rows = session.run(query, id=entity_id)
            return [VerifiedEntity(row["id"], row["kind"]) for row in rows]
