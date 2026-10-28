from fei_assistant.routing import classify_route, route_for_explicit_module


def test_simple_message_routes_to_general_assistant() -> None:
    assert classify_route("你好") == "general"


def test_job_request_routes_to_job_module() -> None:
    assert classify_route("请分析这份后端工程师岗位和我的简历是否匹配") == "job_search"


def test_interview_request_routes_to_job_module() -> None:
    assert classify_route("帮我做一次模拟面试") == "job_search"


def test_long_general_message_stays_in_general_module() -> None:
    assert classify_route("请帮我整理今天的工作任务。" * 20) == "general"


def test_generic_analysis_and_company_words_do_not_enter_job_module() -> None:
    assert classify_route("请分析这家公司的商业模式并和竞品比较") == "general"


def test_explicit_module_selection_has_priority() -> None:
    assert route_for_explicit_module("job_search") == "job_search"
    assert route_for_explicit_module("general") == "general"
    assert route_for_explicit_module("household") == "household"


def test_household_put_sentence_routes_to_household() -> None:
    assert classify_route("洗衣液放衣柜第二层") == "household"
    assert classify_route("抽纸收在储物间的纸箱里") == "household"


def test_household_keywords_do_not_steal_job_requests() -> None:
    assert classify_route("帮我分析这份岗位的面试要求") == "job_search"


def test_assistant_graph_registers_household_node() -> None:
    from fei_assistant.graph import build_graph

    graph = build_graph(lambda: None)
    assert "household" in graph.get_graph().nodes


