from fei_assistant.routing import classify_route


def test_simple_message_routes_directly() -> None:
    assert classify_route("你好") == "direct"


def test_complex_message_routes_to_supervisor() -> None:
    assert classify_route("分析这个项目中的代码并给出测试建议") == "supervisor"


def test_long_message_routes_to_supervisor() -> None:
    assert classify_route("请处理这个任务。" * 20) == "supervisor"

