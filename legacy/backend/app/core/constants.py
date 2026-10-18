"""GraphRAG Copilot - 全局常量"""

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".txt", ".md",
    ".jpg", ".jpeg", ".png",
    ".mp3", ".wav", ".mp4",
}

ALLOWED_ENTITY_TYPES = {
    "Person",
    "Organization",
    "Product",
    "Technology",
    "Concept",
    "Document",
    "Event",
    "Location",
    "Entity",
}

ALLOWED_RELATION_TYPES = {
    "USES",
    "BELONGS_TO",
    "DEPENDS_ON",
    "RELATED_TO",
    "CAUSES",
    "PART_OF",
    "COMPARES_WITH",
    "CONTAINS",
    "CREATED",
    "WORKS_FOR",
}

DEFAULT_ENTITY_TYPE = "Entity"
DEFAULT_RELATION_TYPE = "RELATED_TO"
