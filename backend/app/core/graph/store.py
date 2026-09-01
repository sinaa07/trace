"""Neo4j persistence for case-scoped causal graphs."""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import GraphDatabase, Driver

from app.core.config import settings
from app.core.graph.builder import GraphEdge, GraphNode


class Neo4jGraphStore:
    """Read/write evidence-linked graph to Neo4j Community."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self._driver: Driver | None = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def replace_case_graph(
        self,
        case_id: uuid.UUID,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> dict[str, int]:
        with self.driver.session() as session:
            session.execute_write(self._delete_case_graph, str(case_id))
            for node in nodes:
                session.execute_write(self._merge_node, str(case_id), node)
            for edge in edges:
                session.execute_write(self._merge_edge, str(case_id), edge)
        return {"nodes": len(nodes), "edges": len(edges)}

    def get_case_graph(self, case_id: uuid.UUID) -> dict[str, Any]:
        with self.driver.session() as session:
            nodes = session.execute_read(self._read_nodes, str(case_id))
            edges = session.execute_read(self._read_edges, str(case_id))
        return {"nodes": nodes, "edges": edges}

    def find_path(
        self,
        case_id: uuid.UUID,
        *,
        from_id: str,
        to_id: str,
        max_depth: int = 8,
    ) -> dict[str, Any]:
        with self.driver.session() as session:
            record = session.execute_read(
                self._shortest_path,
                str(case_id),
                from_id,
                to_id,
                max_depth,
            )
        if record is None:
            return {"found": False, "nodes": [], "edges": []}
        return record

    @staticmethod
    def _delete_case_graph(tx: Any, case_id: str) -> None:
        tx.run(
            """
            MATCH (n {case_id: $case_id})
            DETACH DELETE n
            """,
            case_id=case_id,
        )

    @staticmethod
    def _merge_node(tx: Any, case_id: str, node: GraphNode) -> None:
        props = {
            "id": node.id,
            "case_id": case_id,
            "label": node.label,
            "node_type": node.node_type,
            **node.properties,
        }
        tx.run(
            """
            MERGE (n:TraceNode {id: $id, case_id: $case_id})
            SET n += $props
            """,
            id=node.id,
            case_id=case_id,
            props=props,
        )

    @staticmethod
    def _merge_edge(tx: Any, case_id: str, edge: GraphEdge) -> None:
        tx.run(
            f"""
            MATCH (a:TraceNode {{id: $source, case_id: $case_id}})
            MATCH (b:TraceNode {{id: $target, case_id: $case_id}})
            MERGE (a)-[r:{edge.edge_type} {{case_id: $case_id}}]->(b)
            SET r += $props
            """,
            source=edge.source,
            target=edge.target,
            case_id=case_id,
            props=edge.properties,
        )

    @staticmethod
    def _read_nodes(tx: Any, case_id: str) -> list[dict[str, Any]]:
        result = tx.run(
            """
            MATCH (n:TraceNode {case_id: $case_id})
            RETURN n
            ORDER BY n.node_type, n.label
            """,
            case_id=case_id,
        )
        return [dict(record["n"]) for record in result]

    @staticmethod
    def _read_edges(tx: Any, case_id: str) -> list[dict[str, Any]]:
        result = tx.run(
            """
            MATCH (a:TraceNode {case_id: $case_id})-[r]->(b:TraceNode {case_id: $case_id})
            RETURN a.id AS source, b.id AS target, type(r) AS edge_type, properties(r) AS properties
            """,
            case_id=case_id,
        )
        return [
            {
                "source": rec["source"],
                "target": rec["target"],
                "edge_type": rec["edge_type"],
                "properties": dict(rec["properties"] or {}),
            }
            for rec in result
        ]

    @staticmethod
    def _shortest_path(
        tx: Any,
        case_id: str,
        from_id: str,
        to_id: str,
        max_depth: int,
    ) -> dict[str, Any] | None:
        result = tx.run(
            """
            MATCH (start:TraceNode {id: $from_id, case_id: $case_id}),
                  (end:TraceNode {id: $to_id, case_id: $case_id})
            MATCH p = shortestPath((start)-[*..8]->(end))
            RETURN p
            """,
            case_id=case_id,
            from_id=from_id,
            to_id=to_id,
        )
        record = result.single()
        if record is None:
            return None
        path = record["p"]
        nodes = [dict(n) for n in path.nodes]
        edges = [
            {
                "source": rel.start_node["id"],
                "target": rel.end_node["id"],
                "edge_type": rel.type,
                "properties": dict(rel),
            }
            for rel in path.relationships
        ]
        return {"found": True, "nodes": nodes, "edges": edges}
