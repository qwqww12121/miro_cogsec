"""Alias to backend implementation."""

from backend.app.modules.threat_rag import AttackStrategy, FraudCase, ThreatKnowledgeRAG

__all__ = ["AttackStrategy", "FraudCase", "ThreatKnowledgeRAG"]
