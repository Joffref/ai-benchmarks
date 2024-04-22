import argparse
import asyncio
import dataclasses
import datetime
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import gcloud.aio.storage as gcs

import llm_benchmark

DEFAULT_DISPLAY_LENGTH = 64
DEFAULT_GCS_BUCKET = "thefastest-data"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--format",
    "-F",
    choices=["text", "json"],
    default="text",
    help="Output results in the specified format",
)
parser.add_argument(
    "--mode",
    "-m",
    choices=["text", "image", "audio", "video"],
    default="text",
    help="Mode to run benchmarks for",
)
parser.add_argument(
    "--filter",
    "-r",
    help="Filter models by name",
)
parser.add_argument(
    "--display-length",
    "-l",
    type=int,
    default=DEFAULT_DISPLAY_LENGTH,
    help="Amount of the generation response to display",
)
parser.add_argument(
    "--store",
    action="store_true",
    help="Store the results in the configured GCP bucket",
)


def _dict_to_argv(d: Dict[str, str]) -> List[str]:
    return [f"--{k.replace('_', '-')}={v}" for k, v in d.items()]


class _Llm:
    """
    We maintain a dict of params for the llm, as well as any
    command-line flags that we didn't already handle. We'll
    turn this into a single command line for llm_benchmark.run
    to consume, which allows us to reuse the parsing logic
    from that script, rather than having to duplicate it here.
    """

    def __init__(self, model, **kwargs):
        self.pass_argv = []
        self.args = {"model": model, **kwargs, "format": "none"}

    def apply(self, pass_argv: List[str], **kwargs):
        self.pass_argv = pass_argv
        self.args.update(kwargs)
        return self

    def run(self):
        full_argv = _dict_to_argv(self.args) + self.pass_argv
        return asyncio.create_task(llm_benchmark.run(full_argv))


class _AnyscaleLlm(_Llm):
    def __init__(self, model):
        super().__init__(
            model,
            api_key=os.getenv("ANYSCALE_API_KEY"),
            base_url="https://api.endpoints.anyscale.com/v1",
        )


class _FireworksLlm(_Llm):
    def __init__(self, model):
        super().__init__(
            model,
            api_key=os.getenv("FIREWORKS_API_KEY"),
            base_url="https://api.fireworks.ai/inference/v1",
        )


class _GroqLlm(_Llm):
    def __init__(self, model):
        super().__init__(
            model,
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )


class _OctoLlm(_Llm):
    def __init__(self, model):
        super().__init__(
            model,
            api_key=os.getenv("OCTOML_API_KEY"),
            base_url="https://text.octoai.run/v1",
        )


class _PerplexityLlm(_Llm):
    def __init__(self, model):
        super().__init__(
            model,
            api_key=os.getenv("PERPLEXITY_API_KEY"),
            base_url="https://api.perplexity.ai",
        )


class _TogetherLlm(_Llm):
    def __init__(self, model):
        super().__init__(
            model,
            api_key=os.getenv("TOGETHER_API_KEY"),
            base_url="https://api.together.xyz/v1",
        )


# TODO: mosaic
def _text_models():
    AZURE_EASTUS2_OPENAI_API_KEY = os.getenv("AZURE_EASTUS2_OPENAI_API_KEY")
    return [
        # GPT-4
        _Llm("gpt-4-turbo"),
        _Llm("gpt-4-0125-preview"),
        _Llm(
            "gpt-4-0125-preview",
            api_key=os.getenv("AZURE_SCENTRALUS_OPENAI_API_KEY"),
            base_url="https://fixie-scentralus.openai.azure.com",
        ),
        _Llm("gpt-4-1106-preview"),
        _Llm("gpt-4-1106-preview", base_url="https://fixie-westus.openai.azure.com"),
        _Llm(
            "gpt-4-1106-preview",
            api_key=AZURE_EASTUS2_OPENAI_API_KEY,
            base_url="https://fixie-openai-sub-with-gpt4.openai.azure.com",
        ),
        _Llm(
            "gpt-4-1106-preview",
            api_key=os.getenv("AZURE_FRCENTRAL_OPENAI_API_KEY"),
            base_url="https://fixie-frcentral.openai.azure.com",
        ),
        _Llm(
            "gpt-4-1106-preview",
            api_key=os.getenv("AZURE_SECENTRAL_OPENAI_API_KEY"),
            base_url="https://fixie-secentral.openai.azure.com",
        ),
        _Llm(
            "gpt-4-1106-preview",
            api_key=os.getenv("AZURE_UKSOUTH_OPENAI_API_KEY"),
            base_url="https://fixie-uksouth.openai.azure.com",
        ),
        # GPT-3.5
        _Llm("gpt-3.5-turbo-0125"),
        _Llm("gpt-3.5-turbo-1106"),
        _Llm("gpt-3.5-turbo-1106", base_url="https://fixie-westus.openai.azure.com"),
        _Llm(
            "gpt-3.5-turbo",
            api_key=AZURE_EASTUS2_OPENAI_API_KEY,
            base_url="https://fixie-openai-sub-with-gpt4.openai.azure.com",
        ),
        # Claude
        _Llm("claude-3-opus-20240229"),
        _Llm("claude-3-sonnet-20240229"),
        _Llm("claude-3-haiku-20240307"),
        _Llm("claude-2.1"),
        _Llm("claude-instant-1.2"),
        # Cohere
        _Llm("command-r-plus"),
        _Llm("command-r"),
        _Llm("command-light"),
        # Gemini
        _Llm("gemini-pro"),
        _Llm("gemini-1.5-pro-preview-0409"),
        # Mistral
        _Llm(
            "",
            api_key=os.getenv("AZURE_EASTUS2_MISTRAL_API_KEY"),
            base_url="https://fixie-mistral-serverless.eastus2.inference.ai.azure.com/v1",
        ),
        _AnyscaleLlm("mistralai/Mixtral-8x7B-Instruct-v0.1"),
        _FireworksLlm("accounts/fireworks/models/mixtral-8x7b-instruct"),
        _GroqLlm("mixtral-8x7b-32768"),
        _OctoLlm("mixtral-8x7b-instruct"),
        _PerplexityLlm("mixtral-8x7b-instruct"),
        _PerplexityLlm("sonar-medium-chat"),
        # Llama 3 70b
        _AnyscaleLlm("meta-llama/Llama-3-70b-chat-hf"),
        _FireworksLlm("accounts/fireworks/models/llama-v3-70b-instruct"),
        _GroqLlm("llama3-70b-8192"),
        _PerplexityLlm("llama-3-70b-instruct"),
        _TogetherLlm("meta-llama/Llama-3-70b-chat-hf"),
        # Llama 2 70b
        _Llm(
            "",
            api_key=os.getenv("AZURE_WESTUS3_LLAMA2_API_KEY"),
            base_url="https://fixie-llama-2-70b-serverless.westus3.inference.ai.azure.com/v1",
        ),
        _Llm(
            "",
            api_key=os.getenv("AZURE_EASTUS2_LLAMA2_API_KEY"),
            base_url="https://fixie-llama-2-70b-serverless.eastus2.inference.ai.azure.com/v1",
        ),
        _AnyscaleLlm("meta-llama/Llama-2-70b-chat-hf"),
        _FireworksLlm("accounts/fireworks/models/llama-v2-70b-chat"),
        _GroqLlm("llama2-70b-4096"),
        _OctoLlm("llama-2-70b-chat-fp16"),
        _TogetherLlm("togethercomputer/llama-2-70b-chat"),
        _FireworksLlm("accounts/fireworks/models/llama-v2-13b-chat"),
        # Llama 2 13b
        _AnyscaleLlm("meta-llama/Llama-2-13b-chat-hf"),
        _TogetherLlm("togethercomputer/llama-2-13b-chat"),
        _OctoLlm("llama-2-13b-chat-fp16"),
        # Llama 3 8b
        _AnyscaleLlm("meta-llama/Llama-3-8b-chat-hf"),
        _FireworksLlm("accounts/fireworks/models/llama-v3-8b-instruct"),
        _GroqLlm("llama3-8b-8192"),
        _PerplexityLlm("llama-3-8b-instruct"),
        _TogetherLlm("meta-llama/Llama-3-8b-chat-hf"),
        # Llama 2 7b
        _AnyscaleLlm("meta-llama/Llama-2-7b-chat-hf"),
        _FireworksLlm("accounts/fireworks/models/llama-v2-7b-chat"),
        _TogetherLlm("togethercomputer/llama-2-7b-chat"),
        _Llm("@cf/meta/llama-2-7b-chat-fp16"),
        _Llm("@cf/meta/llama-2-7b-chat-int8"),
    ]


def _image_models():
    return [
        _Llm("gpt-4-turbo"),
        _Llm("gpt-4-vision-preview", base_url="https://fixie-westus.openai.azure.com"),
        _Llm("claude-3-opus-20240229"),
        _Llm("claude-3-sonnet-20240229"),
        _Llm("gemini-pro-vision"),
        _Llm("gemini-1.5-pro-preview-0409"),
    ]


def _av_models():
    return [
        _Llm("gemini-1.5-pro-preview-0409"),
    ]


def _get_models(mode: str, filter: Optional[str] = None):
    mode_map = {
        "text": _text_models,
        "image": _image_models,
        "audio": _av_models,
        "video": _av_models,
    }
    if mode not in mode_map:
        raise ValueError(f"Unknown mode {mode}")
    models = mode_map[mode]()
    return [m for m in models if not filter or filter in m.args["model"]]


@dataclasses.dataclass
class _Response:
    time: str
    region: str
    cmd: str
    results: List[Dict[str, Any]]


def _format_response(response: _Response, format: str, dlen: int) -> Tuple[str, str]:
    if format == "json":
        return json.dumps(vars(response), indent=2), "application/json"
    else:
        s = (
            "| Provider/Model                             | TTR  | TTFT | TPS | Tok | Total |"
            f" {'Response':{dlen}.{dlen}} |\n"
            "| :----------------------------------------- | ---: | ---: | --: | --: | ----: |"
            f" {':--':-<{dlen}.{dlen}} |\n"
        )

        for r in response.results:
            output = r["output"].replace("\n", "\\n").strip()
            s += (
                f"| {r['model']:42} | {r['ttr']:4.2f} | {r['ttft']:4.2f} | "
                f"{r['tps']:3.0f} | {r['num_tokens']:3} | {r['total_time']:5.2f} | "
                f"{output:{dlen}.{dlen}} |\n"
            )

        s += (
            f"\ntime: {response.time}, region: {response.region}, cmd: {response.cmd}\n"
        )
        return s, "text/markdown"


async def _store_response(gcp_bucket: str, key: str, text: str, content_type: str):
    print(f"Storing results in {gcp_bucket}/{key}")
    storage = gcs.Storage(service_file="service_account.json")
    await storage.upload(gcp_bucket, key, text, content_type=content_type)
    await storage.close()


async def run(
    mode: str = "text",
    format: str = "text",
    display_length: Optional[int] = DEFAULT_DISPLAY_LENGTH,
    filter: Optional[str] = None,
    store: bool = False,
    pass_argv: Optional[List[str]] = None,
    **kwargs,
):
    """
    This function is invoked either from the webapp or the main function below.
    When invoked from the webapp, the arguments are passed as kwargs.
    When invoked from the main function, the arguments are passed as a list of flags.
    We'll give both to the _Llm.run function, which will turn them back into a
    single list of flags for consumption by the llm_benchmark.run function.
    """
    time_str = datetime.datetime.now().isoformat()
    region = os.getenv("FLY_REGION", "local")
    argv = _dict_to_argv(kwargs) + (pass_argv or [])
    models = _get_models(mode, filter)
    tasks = []
    for m in models:
        m.apply(pass_argv or [], **kwargs)
        tasks.append(m.run())
    await asyncio.gather(*tasks)
    results = [t.result() for t in tasks if t.result() is not None]
    response = _Response(time_str, region, " ".join(argv), results)
    if store:
        path = f"{region}/{mode}/{time_str.split('T')[0]}.json"
        json, content_type = _format_response(response, "json", display_length)
        await _store_response(DEFAULT_GCS_BUCKET, path, json, content_type)
    return _format_response(response, format, display_length)


async def main(args: argparse.Namespace, pass_argv: List[str]):
    text, _ = await run(
        args.mode, args.format, args.display_length, args.filter, args.store, pass_argv
    )
    print(text)


if __name__ == "__main__":
    args, unk_args = parser.parse_known_args()
    asyncio.run(main(args, unk_args))
