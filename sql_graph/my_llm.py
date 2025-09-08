from langchain_openai import ChatOpenAI

from sql_graph.env_utils import OPENAI_API_KEY, DEEPSEEK_API_KEY, Qwen_API_KEY



# llm = ChatOpenAI(  # openai的
#     temperature=0,
#     model='gpt-4o-mini',
#     api_key=OPENAI_API_KEY,
#     base_url="https://xiaoai.plus/v1")


llm = ChatOpenAI(
    temperature=0.5,
    model='deepseek-chat',
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com")


# llm = ChatOpenAI(
#     temperature=0,
#     model="qwen3-8b",
#     openai_api_key="EMPTY",
#     openai_api_base="http://localhost:6006/v1",
#     extra_body={"chat_template_kwargs": {"enable_thinking": False}},
# )

# free-qwen3
# llm = ChatOpenAI(
#     temperature=0,
#     model="free:Qwen3-30B-A3B",
#     openai_api_key="sk-W0rpStc95T7JVYVwDYc29IyirjtpPPby6SozFMQr17m8KWeo",
#     openai_api_base="https://api.suanli.cn/v1",
#     extra_body={"chat_template_kwargs": {"enable_thinking": False}},
# )