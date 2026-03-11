"""RAGConfig — RAG quality, confidence, iteration settings."""
from pydantic import BaseModel


class RAGConfig(BaseModel):
    """RAG quality, confidence, iteration settings."""
    enable_corrective_rag: bool = True
    quality_mode: str = "balanced"
    confidence_high: float = 0.70
    confidence_medium: float = 0.60
    max_iterations: int = 2
    enable_reflection: bool = True
    early_exit_on_high_confidence: bool = True
    grading_threshold: float = 6.0
    retrieval_grade_threshold: float = 7.0
    enable_answer_verification: bool = True
