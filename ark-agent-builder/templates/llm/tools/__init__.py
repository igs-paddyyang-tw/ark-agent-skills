"""內建 Tools — import 時自動註冊到全域 registry。"""
from src.llm.tools.wiki_write import register_tools as _reg_wiki_write
from src.llm.tools.wiki_search import register_tools as _reg_wiki_search
from src.llm.tools.memory_tools import register_tools as _reg_memory
from src.llm.tools.skill_executor import register_tools as _reg_skill
from src.llm.tools.web_search import register_tools as _reg_web_search
from src.llm.tools.dispatch import register_tools as _reg_dispatch

_reg_wiki_write()
_reg_wiki_search()
_reg_memory()
_reg_skill()
_reg_web_search()
_reg_dispatch()
