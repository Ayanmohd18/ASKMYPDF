import pytest
from app.memory import ConversationMemory
from app.generator import build_user_message, generate
from app.retriever import RetrievedChunk
from app.ingestion import Chunk

def test_build_user_message_format():
    chunks = [
        RetrievedChunk(Chunk("1", "docA", 1, "text1", 10), 0.9, 0.9, 0.9, 0.9),
        RetrievedChunk(Chunk("2", "docB", 2, "text2", 10), 0.8, 0.8, 0.8, 0.8)
    ]
    memory = ConversationMemory()
    memory.add_user("hello")
    memory.add_assistant("hi")
    
    output = build_user_message("query", chunks, memory)
    
    assert "CONTEXT:" in output
    assert "CONVERSATION HISTORY:" in output
    assert "QUESTION: query" in output
    assert "[1] Source: docA, Page 1" in output
    assert "[2] Source: docB, Page 2" in output

def test_build_user_message_empty_history():
    chunks = [
        RetrievedChunk(Chunk("1", "docA", 1, "text1", 10), 0.9, 0.9, 0.9, 0.9)
    ]
    memory = ConversationMemory()
    
    output = build_user_message("query", chunks, memory)
    
    assert "CONVERSATION HISTORY:" not in output
    assert "QUESTION: query" in output

def test_conversation_memory_max_turns():
    memory = ConversationMemory(max_turns=2)
    # Add 3 turns
    for i in range(3):
        memory.add_user(f"u{i}")
        memory.add_assistant(f"a{i}")
        
    assert len(memory) == 4
    hist = memory.get_history()
    # The first turn (u0, a0) should be dropped
    assert hist[0] == ("user", "u1")

def test_conversation_memory_format():
    memory = ConversationMemory()
    memory.add_user("hello")
    memory.add_assistant("hi")
    
    out = memory.format_history()
    assert out.startswith("Human: hello\nAssistant: hi\n")

def test_generate_unknown_backend():
    memory = ConversationMemory()
    with pytest.raises(ValueError, match="Choose: gemini"):
        generate("query", [], memory, backend="invalid")
