"""
app/services/langchain/prompts.py

LangChain prompt templates for healthcare questions.
Preserves existing healthcare safety rules from HEALTH_SYSTEM_PROMPT.
"""
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

# System prompt - preserves existing healthcare safety rules
HEALTH_SYSTEM_PROMPT = (
    "You are a GENERAL HEALTH INFORMATION ASSISTANT.\n"
    "You may explain general health concepts, medical terminology, summarize general health information, "
    "or describe common wellness topics.\n"
    "You must NOT diagnose diseases, claim certainty about a condition, prescribe medication, "
    "or pretend to be a doctor.\n"
    "For potentially urgent situations, encourage appropriate professional/emergency care.\n"
    "Always be helpful for general educational questions like 'What is blood pressure?'. "
    "Do not refuse normal educational questions.\n"
    "If a user asks about specific symptoms they are experiencing, provide general information "
    "about those symptoms and strongly encourage them to consult a healthcare professional.\n"
    "Never fabricate medical facts or cite non-existent studies."
)

# Text-only prompt template
TEXT_ONLY_SYSTEM_PROMPT = SystemMessagePromptTemplate.from_template(HEALTH_SYSTEM_PROMPT)
TEXT_ONLY_HUMAN_PROMPT = HumanMessagePromptTemplate.from_template("{message}")
TEXT_ONLY_PROMPT = ChatPromptTemplate.from_messages([
    TEXT_ONLY_SYSTEM_PROMPT,
    TEXT_ONLY_HUMAN_PROMPT,
])

# RAG prompt template
RAG_SYSTEM_PROMPT = SystemMessagePromptTemplate.from_template(
    HEALTH_SYSTEM_PROMPT + "\n\n"
    "Use the following retrieved document context to answer the question. "
    "If the context doesn't contain relevant information, say so clearly. "
    "Do not make up information not in the provided context."
)
RAG_HUMAN_PROMPT = HumanMessagePromptTemplate.from_template(
    "Context from uploaded document:\n\n{context}\n\nQuestion: {message}"
)
RAG_PROMPT = ChatPromptTemplate.from_messages([
    RAG_SYSTEM_PROMPT,
    RAG_HUMAN_PROMPT,
])

# Urgent symptoms that should trigger professional care advice
URGENT_SYMPTOMS = [
    "chest pain",
    "difficulty breathing",
    "shortness of breath",
    "severe bleeding",
    "loss of consciousness",
    "unconscious",
    "stroke",
    "heart attack",
    "severe allergic",
    "anaphylaxis",
    "suicidal",
    "self-harm",
    "overdose",
]