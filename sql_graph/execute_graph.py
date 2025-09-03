import asyncio
from langgraph.graph import MessagesState

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from sql_graph.my_llm import llm

from sql_graph.text2sql_graph import make_graph




async def execute_graph():
    """执行该工作流"""
    async with make_graph() as graph:
        while True:
            user_input = input("用户：")
            if user_input.lower() in ['q', 'exit', 'quit']:
                print('对话结束，感谢您的使用！')
                break
            else:
                try:
                    # 调用异步工作流
                    async for event in graph.astream(
                        {"messages": [{"role": "user", "content": user_input}]},
                        stream_mode="values"
                    ):
                        event["messages"][-1].pretty_print()
                except Exception as e:
                    print(f"❌ 出现错误：{e}")
                    print("请重新输入问题，或输入 'quit' 退出。")



if __name__ == '__main__':
    asyncio.run(execute_graph())

