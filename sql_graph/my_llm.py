from langchain_openai import ChatOpenAI
# from zhipuai import ZhipuAI

from sql_graph.env_utils import ZHIPU_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, Qwen_API_KEY

# zhipuai_client = ZhipuAI(api_key=ZHIPU_API_KEY)  # 填写您自己的APIKey

#
# llm = ChatOpenAI(  # zhipuai的
#     temperature=0,
#     model='glm-4-air-250414',
#     api_key=ZHIPU_API_KEY,
#     base_url="https://open.bigmodel.cn/api/paas/v4/")


# llm = ChatOpenAI(  # openai的
#     temperature=0,
#     model='gpt-4o-mini',
#     api_key=OPENAI_API_KEY,
#     base_url="https://xiaoai.plus/v1")


# llm = ChatOpenAI(
#     temperature=0.5,
#     model='deepseek-chat',
#     api_key=DEEPSEEK_API_KEY,
#     base_url="https://api.deepseek.com")

# llm = ChatOpenAI( # qwen3
#     temperature=0.5,
#     model="qwen-plus",
#     api_key=Qwen_API_KEY,
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")


llm = ChatOpenAI(
    temperature=0,
    model="qwen3-8b",
    openai_api_key="EMPTY",
    openai_api_base="http://localhost:6006/v1",
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)

# free-qwen3
# llm = ChatOpenAI(
#     temperature=0,
#     model="free:Qwen3-30B-A3B",
#     openai_api_key="sk-W0rpStc95T7JVYVwDYc29IyirjtpPPby6SozFMQr17m8KWeo",
#     openai_api_base="https://api.suanli.cn/v1",
#     extra_body={"chat_template_kwargs": {"enable_thinking": False}},
# )