from agent.adk.runner_adapter import _format_stream_error


def test_format_stream_error_for_ollama_connectivity():
    err = Exception(
        "litellm.APIConnectionError: OllamaException - Cannot connect to host 192.168.5.162:11434 [No route to host]"
    )

    message = _format_stream_error(err)

    assert "无法连接到本地模型服务" in message
    assert "Ollama" in message


def test_format_stream_error_for_generic_connectivity():
    err = Exception("All connection attempts failed")

    message = _format_stream_error(err)

    assert message.startswith("模型服务连接失败：")
