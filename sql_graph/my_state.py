from typing import TypedDict, Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages

# 存储节点输出的任何类型的Message，把每个节点输出的message加入到list
class SQLState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]