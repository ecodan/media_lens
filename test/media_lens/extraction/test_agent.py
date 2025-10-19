from unittest.mock import MagicMock, patch

import pytest

from src.media_lens.extraction.agent import Agent, LiteLLMAgent, ResponseFormat


def test_agent_abstract_class():
    """Test that Agent is an abstract class that can't be instantiated directly."""
    with pytest.raises(TypeError):
        Agent()  # Should fail because Agent is abstract


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_litellm_agent_init(mock_completion):
    """Test LiteLLMAgent initialization."""
    agent = LiteLLMAgent(model="anthropic/claude-3-opus-20240229")

    assert agent.model == "anthropic/claude-3-opus-20240229"
    assert agent._model == "anthropic/claude-3-opus-20240229"


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_litellm_agent_invoke(mock_completion):
    """Test LiteLLMAgent invoke method."""
    # Create mock response
    mock_message = MagicMock()
    mock_message.content = "Test response"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    # Create agent
    agent = LiteLLMAgent(model="anthropic/claude-3-opus-20240229")

    # Call invoke
    response = agent.invoke(
        system_prompt="You are a helpful assistant", user_prompt="Tell me about testing"
    )

    # Verify completion was called correctly
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args[1]
    assert call_kwargs["model"] == "anthropic/claude-3-opus-20240229"
    assert call_kwargs["temperature"] == 0
    assert call_kwargs["max_tokens"] == 4096

    # Verify messages structure
    messages = call_kwargs["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Tell me about testing"

    assert response == "Test response"


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_litellm_agent_with_vertex_params(mock_completion):
    """Test LiteLLMAgent with Vertex AI parameters."""
    # Create mock response
    mock_message = MagicMock()
    mock_message.content = "Vertex response"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    # Create agent with Vertex parameters
    agent = LiteLLMAgent(
        model="vertex_ai/gemini-2.5-flash",
        vertex_project="test-project",
        vertex_location="us-central1",
    )

    # Call invoke
    response = agent.invoke(system_prompt="You are a helpful assistant", user_prompt="Test prompt")

    # Verify Vertex parameters were passed through
    call_kwargs = mock_completion.call_args[1]
    assert call_kwargs["vertex_project"] == "test-project"
    assert call_kwargs["vertex_location"] == "us-central1"
    assert response == "Vertex response"


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_litellm_agent_json_response_format(mock_completion):
    """Test LiteLLMAgent with JSON response format cleaning."""
    # Create mock response with markdown fences
    mock_message = MagicMock()
    mock_message.content = '```json\n{"key": "value"}\n```'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    agent = LiteLLMAgent(model="anthropic/claude-3-5-haiku-latest")

    # Call invoke with JSON format
    response = agent.invoke(
        system_prompt="System", user_prompt="User", response_format=ResponseFormat.JSON
    )

    # Verify response_format parameter was passed to completion
    call_kwargs = mock_completion.call_args[1]
    assert call_kwargs["response_format"] == {"type": "json_object"}

    # Verify JSON cleaning still works (for legacy/edge cases)
    assert response == '{"key": "value"}'
    assert "```" not in response


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_litellm_agent_json_with_thinking_tags(mock_completion):
    """Test JSON cleaning with thinking tags."""
    # Create mock response with thinking tags
    mock_message = MagicMock()
    mock_message.content = '<thinking>Analysis here</thinking>\n```json\n{"result": "data"}\n```'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    agent = LiteLLMAgent(model="anthropic/claude-3-5-haiku-latest")

    response = agent.invoke(
        system_prompt="System", user_prompt="User", response_format=ResponseFormat.JSON
    )

    # Verify thinking tags and fences are removed
    assert response == '{"result": "data"}'
    assert "thinking" not in response
    assert "```" not in response


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_litellm_agent_error_handling(mock_completion):
    """Test LiteLLMAgent error handling."""
    # Mock an exception
    mock_completion.side_effect = Exception("API Error")

    agent = LiteLLMAgent(model="anthropic/claude-3-5-haiku-latest")

    # Verify exception is raised
    with pytest.raises(Exception, match="API Error"):
        agent.invoke(system_prompt="System", user_prompt="User")


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_litellm_agent_json_with_output_tags(mock_completion):
    """Test JSON cleaning with output tags."""
    # Create mock response with output tags
    mock_message = MagicMock()
    mock_message.content = (
        '<thinking>Analysis here</thinking>\n<output>```json\n{"result": "data"}```</output>'
    )
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    agent = LiteLLMAgent(model="anthropic/claude-3-5-haiku-latest")

    response = agent.invoke(
        system_prompt="System", user_prompt="User", response_format=ResponseFormat.JSON
    )

    # Verify output tags and fences are removed
    assert response == '{"result": "data"}'
    assert "output" not in response
    assert "```" not in response


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_litellm_agent_json_with_preamble(mock_completion):
    """Test JSON cleaning with text preamble before JSON."""
    # Create mock response with text before JSON
    mock_message = MagicMock()
    mock_message.content = 'analysis\nHere is the result:\n{"result": "data"}'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    agent = LiteLLMAgent(model="anthropic/claude-3-5-haiku-latest")

    response = agent.invoke(
        system_prompt="System", user_prompt="User", response_format=ResponseFormat.JSON
    )

    # Verify preamble is removed and only JSON remains
    assert response == '{"result": "data"}'
    assert "analysis" not in response


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_clean_json_response_with_schema_wrapper(mock_completion):
    """Test JSON Schema wrapper detection and unwrapping."""
    # Create mock response with JSON Schema wrapper format
    mock_message = MagicMock()
    mock_message.content = '{"properties": {"stories": [{"title": "News 1"}, {"title": "News 2"}]}, "additionalProperties": false}'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    agent = LiteLLMAgent(model="vertex_ai/gemini-2.5-flash")

    response = agent.invoke(
        system_prompt="System", user_prompt="User", response_format=ResponseFormat.JSON
    )

    # Verify schema wrapper is unwrapped
    assert response == '{"stories": [{"title": "News 1"}, {"title": "News 2"}]}'
    assert "properties" not in response
    assert "additionalProperties" not in response


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_clean_json_response_with_trailing_text(mock_completion):
    """Test JSON cleaning returns response with trailing text (error handling is in caller)."""
    # Create mock response with valid JSON followed by trailing text
    mock_message = MagicMock()
    mock_message.content = '{"stories": [{"title": "News 1"}]} This is extra text'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    agent = LiteLLMAgent(model="anthropic/claude-3-5-haiku-latest")

    response = agent.invoke(
        system_prompt="System", user_prompt="User", response_format=ResponseFormat.JSON
    )

    # Agent returns the cleaned response (trailing text may still be present)
    # The caller (headliner.py) is responsible for catching JSONDecodeError
    # Verify the response starts with valid JSON
    assert response.startswith('{"stories":')

    # Verify that json.loads would raise an error (expected behavior)
    import json

    with pytest.raises(json.JSONDecodeError, match="Extra data"):
        json.loads(response)


@patch("src.media_lens.extraction.agent.litellm.completion")
def test_clean_json_response_with_schema_wrapper_and_fences(mock_completion):
    """Test JSON Schema wrapper with markdown fences."""
    # Create mock response combining schema wrapper and markdown
    mock_message = MagicMock()
    mock_message.content = '```json\n{"properties": {"stories": [{"title": "News 1"}]}}\n```'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_completion.return_value = mock_response

    agent = LiteLLMAgent(model="vertex_ai/gemini-2.5-flash")

    response = agent.invoke(
        system_prompt="System", user_prompt="User", response_format=ResponseFormat.JSON
    )

    # Verify both markdown fences and schema wrapper are removed
    assert response == '{"stories": [{"title": "News 1"}]}'
    assert "properties" not in response
    assert "```" not in response
