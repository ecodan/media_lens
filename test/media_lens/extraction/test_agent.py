import pytest
from unittest.mock import patch, MagicMock

from src.media_lens.extraction.agent import Agent, ClaudeLLMAgent


def test_agent_abstract_class():
    """Test that Agent is an abstract class that can't be instantiated directly."""
    with pytest.raises(TypeError):
        Agent()  # Should fail because Agent is abstract


@patch('src.media_lens.extraction.agent.Anthropic')
def test_claude_llm_agent_init(mock_anthropic):
    """Test ClaudeLLMAgent initialization."""
    # Create a mock Anthropic client
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    
    # Create agent
    agent = ClaudeLLMAgent(api_key="test_key", model="claude-3-opus-20240229")
    
    # Verify initialization
    assert agent.model == "claude-3-opus-20240229"
    assert agent.client == mock_client
    mock_anthropic.assert_called_once_with(api_key="test_key")


@patch('src.media_lens.extraction.agent.Anthropic')
def test_claude_llm_agent_invoke(mock_anthropic):
    """Test ClaudeLLMAgent invoke method."""
    # Create a mock Anthropic client with response
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Test response")]
    mock_client.messages.create.return_value = mock_message
    mock_anthropic.return_value = mock_client
    
    # Create agent
    agent = ClaudeLLMAgent(api_key="test_key", model="claude-3-opus-20240229")
    
    # Call invoke
    response = agent.invoke(
        system_prompt="You are a helpful assistant",
        user_prompt="Tell me about testing"
    )
    
    # Verify calls and response
    mock_client.messages.create.assert_called_once()
    create_args = mock_client.messages.create.call_args[1]
    assert create_args["model"] == "claude-3-opus-20240229"
    assert create_args["system"] == "You are a helpful assistant"
    assert create_args["max_tokens"] < 5000  # Should have a reasonable token limit
    assert "Tell me about testing" in create_args["messages"][0]["content"]
    assert response == "Test response"


@patch('src.media_lens.extraction.agent.Anthropic')
def test_claude_llm_agent_default_max_tokens(mock_anthropic):
    """Test ClaudeLLMAgent with default max_tokens parameter."""
    # Create a mock Anthropic client
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Test response")]
    mock_client.messages.create.return_value = mock_message
    mock_anthropic.return_value = mock_client
    
    # Create agent with default parameters
    agent = ClaudeLLMAgent(api_key="test_key", model="claude-3-opus-20240229")
    
    # Call invoke
    agent.invoke(
        system_prompt="You are a helpful assistant",
        user_prompt="Tell me about testing"
    )
    
    # Verify default max_tokens was used
    create_args = mock_client.messages.create.call_args[1]
    assert create_args["max_tokens"] == 4096