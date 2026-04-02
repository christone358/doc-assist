from agent.adk.runner_adapter import (
    _compute_stream_delta,
    _extract_text_from_content,
    _format_stream_error,
)


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


def test_compute_stream_delta_for_cumulative_stream():
    delta, buffer = _compute_stream_delta("", "你好")
    assert delta == "你好"
    assert buffer == "你好"

    delta, buffer = _compute_stream_delta(buffer, "你好，世界")
    assert delta == "，世界"
    assert buffer == "你好，世界"


def test_compute_stream_delta_for_incremental_stream():
    delta, buffer = _compute_stream_delta("", "你好")
    assert delta == "你好"
    assert buffer == "你好"

    delta, buffer = _compute_stream_delta(buffer, "，世界")
    assert delta == "，世界"
    assert buffer == "你好，世界"


def test_compute_stream_delta_ignores_repeated_suffix():
    delta, buffer = _compute_stream_delta("你好，世界", "世界")
    assert delta == ""
    assert buffer == "你好，世界"


def test_extract_text_from_content_joins_parts():
    class Part:
        def __init__(self, text):
            self.text = text

    class Content:
        def __init__(self, parts):
            self.parts = parts

    content = Content([Part("你好"), Part("，"), Part("世界")])

    assert _extract_text_from_content(content) == "你好，世界"
