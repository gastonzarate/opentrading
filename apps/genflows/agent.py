import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import json_repair
from jinja2 import Environment, FileSystemLoader
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.prompts import RichPromptTemplate
from llama_index.llms.bedrock_converse import BedrockConverse
from llama_index.llms.openai import OpenAI

PROMPTS_DIR = Path(__file__).parent.parent / "genflows/prompts"


class AgentType(Enum):
    STR = "str"
    JSON = "json"
    BOOL = "bool"


class LLMModel(Enum):
    BEDROCK_CLAUDE_OPUS_4_8 = "global.anthropic.claude-opus-4-8"
    BEDROCK_CLAUDE_5_SONNET = "global.anthropic.claude-sonnet-5"
    BEDROCK_CLAUDE_4_6_SONNET = "global.anthropic.claude-sonnet-4-6"
    BEDROCK_CLAUDE_4_5_HAIKU = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    BEDROCK_DEEPSEEK_R1 = "global.deepseek.r1-v1:0"
    GPT_4_1_MINI = "gpt-4.1-mini"


class EmbeddingModel(Enum):
    TEST = "test"


class AgentModel:
    # Providers
    OPENAI = [LLMModel.GPT_4_1_MINI]
    BEDROCK = [
        LLMModel.BEDROCK_CLAUDE_OPUS_4_8,
        LLMModel.BEDROCK_CLAUDE_5_SONNET,
        LLMModel.BEDROCK_CLAUDE_4_6_SONNET,
        LLMModel.BEDROCK_CLAUDE_4_5_HAIKU,
        LLMModel.BEDROCK_DEEPSEEK_R1,
    ]
    MAX_TOKENS = {
        LLMModel.BEDROCK_CLAUDE_OPUS_4_8: 50000,
        LLMModel.BEDROCK_CLAUDE_5_SONNET: 50000,
        LLMModel.BEDROCK_CLAUDE_4_6_SONNET: 50000,
        LLMModel.BEDROCK_CLAUDE_4_5_HAIKU: 32786,
        LLMModel.BEDROCK_DEEPSEEK_R1: 32786,
    }

    @classmethod
    def llm(cls, model: "LLMModel", temperature: float = 0.5) -> LLM:
        if model in cls.OPENAI:
            return OpenAI(
                model=model,
                temperature=temperature,
                api_key=os.getenv("OPENAI_API_KEY"),
            )
        elif model in cls.BEDROCK:
            return BedrockConverse(
                model=model.value,
                max_tokens=cls.MAX_TOKENS.get(model),
                temperature=temperature,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_DEFAULT_REGION"),
            )
        else:
            raise ValueError(f"Model {model} not supported")

    @classmethod
    def embedding(cls, model: "EmbeddingModel") -> BaseEmbedding:
        if model == EmbeddingModel.TEST:
            return None
        else:
            raise ValueError(f"Model {model} not supported")


@dataclass
class Agent:
    prompt_name: str
    messages: list[ChatMessage] = field(default_factory=list)
    model: AgentModel = LLMModel.BEDROCK_CLAUDE_4_5_HAIKU
    temperature: float = 0.5
    context: dict = field(default_factory=dict)
    type: AgentType = AgentType.JSON
    verbose: bool = False

    @property
    def llm(self) -> LLM:
        return AgentModel.llm(self.model, self.temperature)

    async def run(self, context: dict = None) -> str | dict | bool:
        prompt = await self.load_prompt()
        llm = self.llm

        system_prompt = prompt.format(**context)
        if self.verbose:
            print(system_prompt)

        messages = [
            ChatMessage(role="system", content=system_prompt),
            *self.messages,
        ]
        is_chat = len(messages) > 1
        resp = await llm.achat(messages) if is_chat else await llm.acomplete(system_prompt)
        content = resp.message.content if is_chat else resp.text
        if self.verbose:
            print(content)
        return await self.cast_response(content)

    async def cast_response(self, response: str) -> str:
        method_name = f"cast_{self.type.value}"
        cast_method = getattr(self, method_name)
        return await cast_method(response)

    async def cast_str(self, response: str) -> str:
        return response

    async def cast_json(self, response: str) -> dict:
        json_str = response[response.find("{"): response.rfind("}") + 1]
        return json_repair.loads(json_str.replace("\n", ""))

    async def cast_bool(self, response: str) -> bool:
        return "true" in response.lower()

    async def load_prompt(self) -> RichPromptTemplate:
        """
        Loads a .txt file and converts it to RichPromptTemplate

        Args:
            prompt_path: relative path from prompts/ (e.g. "system/qa")

        Returns:
            RichPromptTemplate ready to use
        """
        file_path = PROMPTS_DIR / f"{self.prompt_name}.txt"

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return RichPromptTemplate(content)

    async def render_prompt(self, context: dict | None = None) -> str:
        """Render the prompt using Jinja2 with a FileSystemLoader to support includes.
        This expands any Jinja tags (e.g., {% include %}) and returns the final string.
        """
        file_path = PROMPTS_DIR / f"{self.prompt_name}.txt"
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Configure Jinja2 environment with loader pointing to `apps/genflows`
        # so paths like 'prompts/system/browser_snapshot.txt' can be resolved.
        base_dir = Path(__file__).parent.parent / "genflows"
        env = Environment(loader=FileSystemLoader(str(base_dir)), autoescape=False)
        template = env.from_string(content)
        rendered = template.render(**(context or {}))
        return rendered
