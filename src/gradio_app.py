import json
import logging
import os
from collections.abc import AsyncIterator

import gradio as gr
import httpx

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("FALCO_API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
CONSOLE_BIND_ADDRESS = os.getenv("FALCO_CONSOLE_BIND_ADDRESS", "127.0.0.1")
CONSOLE_PORT = int(os.getenv("FALCO_CONSOLE_PORT", "7861"))
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
AVAILABLE_CATEGORIES = ["cs.AI", "cs.LG"]


async def stream_response(
    query: str, top_k: int = 3, use_hybrid: bool = True, model: str = DEFAULT_MODEL, categories: str = ""
) -> AsyncIterator[str]:
    """Stream a response from the Falco RAG API."""
    if not query.strip():
        yield "Please enter a research question."
        return

    category_list = [cat.strip() for cat in categories.split(",") if cat.strip()] if categories else None
    payload = {"query": query, "top_k": top_k, "use_hybrid": use_hybrid, "model": model, "categories": category_list}

    try:
        url = f"{API_BASE_URL}/stream"
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload, headers={"Accept": "text/event-stream"}) as response:
                if response.status_code != 200:
                    yield f"Falco API returned status {response.status_code}."
                    return

                current_answer = ""
                sources = []
                chunks_used = 0
                search_mode = ""

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if "error" in data:
                        yield f"Request failed: {data['error']}"
                        return

                    if "sources" in data:
                        sources = data["sources"]
                        chunks_used = data.get("chunks_used", 0)
                        search_mode = data.get("search_mode", "unknown")
                        if not data.get("done", False):
                            continue

                    if "chunk" in data:
                        current_answer += data["chunk"]
                        yield _format_response(current_answer, sources, chunks_used, search_mode)

                    if data.get("done", False):
                        final_answer = data.get("answer", current_answer)
                        yield _format_response(final_answer, sources, chunks_used, search_mode)
                        break

    except httpx.RequestError:
        logger.exception("Cannot reach Falco API at %s", API_BASE_URL)
        yield "Cannot reach the Falco API. Verify the API endpoint and service status."
    except Exception:
        logger.exception("Falco Research Console request failed")
        yield "The request could not be completed. Check the Falco service logs for details."


def _format_response(answer: str, sources: list, chunks_used: int, search_mode: str) -> str:
    formatted = answer
    if not sources and not chunks_used:
        return formatted

    formatted += "\n\n**Retrieval details**\n"
    formatted += f"- Mode: {search_mode}\n"
    formatted += f"- Chunks used: {chunks_used}\n"
    if sources:
        formatted += f"- Sources: {len(sources)} papers\n"
        for i, source in enumerate(sources[:3], 1):
            formatted += f"  {i}. [{source.split('/')[-1]}]({source})\n"
        if len(sources) > 3:
            formatted += f"  ... and {len(sources) - 3} more\n"
    return formatted


def create_gradio_interface():
    """Create the Falco Research Console."""
    with gr.Blocks(title="Falco Agentic RAG — Research Console", theme=gr.themes.Soft()) as interface:
        gr.Markdown(
            """
            # Falco Agentic RAG
            ### Research Console

            Query your indexed research corpus with grounded retrieval and local LLM generation.
            """
        )

        with gr.Row():
            with gr.Column(scale=3):
                query_input = gr.Textbox(
                    label="Research question",
                    placeholder="How do retrieval-augmented systems reduce hallucination?",
                    lines=2,
                    max_lines=5,
                )
            with gr.Column(scale=1):
                submit_btn = gr.Button("Ask Falco", variant="primary", size="lg")

        with gr.Row():
            with gr.Column():
                with gr.Accordion("Retrieval and model options", open=False):
                    top_k = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value=3,
                        step=1,
                        label="Chunks to retrieve",
                        info="Higher values provide more context at the cost of additional retrieval/generation work.",
                    )
                    use_hybrid = gr.Checkbox(
                        value=True,
                        label="Hybrid retrieval (BM25 + vector)",
                        info="Disable to use keyword-only BM25 retrieval.",
                    )
                    model_choice = gr.Dropdown(
                        choices=["llama3.2:1b", "llama3.2:3b", "llama3.1:8b", "qwen2.5:7b"],
                        value=DEFAULT_MODEL,
                        allow_custom_value=True,
                        label="Ollama model",
                    )
                    categories = gr.Textbox(
                        label="arXiv categories",
                        placeholder="cs.AI, cs.LG, cs.CL",
                        info="Optional comma-separated category filter.",
                    )

        response_output = gr.Markdown(
            label="Falco response",
            value="Ask a research question to get started.",
            height=400,
            elem_classes=["response-markdown"],
        )

        gr.Examples(
            examples=[
                ["What are transformer architectures in machine learning?", 3, True, DEFAULT_MODEL, "cs.AI, cs.LG"],
                ["How does retrieval augmented generation reduce hallucination?", 5, True, DEFAULT_MODEL, "cs.AI, cs.CL"],
                ["Explain recent approaches to efficient attention.", 4, True, DEFAULT_MODEL, "cs.AI, cs.LG"],
            ],
            inputs=[query_input, top_k, use_hybrid, model_choice, categories],
        )

        submit_btn.click(
            fn=stream_response,
            inputs=[query_input, top_k, use_hybrid, model_choice, categories],
            outputs=[response_output],
            show_progress=True,
        )
        query_input.submit(
            fn=stream_response,
            inputs=[query_input, top_k, use_hybrid, model_choice, categories],
            outputs=[response_output],
            show_progress=True,
        )

        gr.Markdown(
            f"""
            ---
            **Falco Research Console** uses the streaming API at `{API_BASE_URL}`.
            Configure retrieval and model options to match your deployment and indexed corpus.
            """
        )

    return interface


def main():
    """Start the Falco Research Console."""
    print("Starting Falco Agentic RAG Research Console...")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Console URL: http://{CONSOLE_BIND_ADDRESS}:{CONSOLE_PORT}")
    interface = create_gradio_interface()
    interface.launch(
        server_name=CONSOLE_BIND_ADDRESS,
        server_port=CONSOLE_PORT,
        share=False,
        show_error=False,
        quiet=False,
    )


if __name__ == "__main__":
    main()
