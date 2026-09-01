import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.schemas.api.ask import AskResponse
from src.services.agents.agentic_rag import AgenticRAGService

logger = logging.getLogger(__name__)


class TelegramBot:
    """Optional Falco Telegram interface backed by the shared Agentic RAG service."""

    def __init__(
        self,
        bot_token: str,
        opensearch_client,
        embeddings_client,
        agentic_rag_service: AgenticRAGService,
    ):
        self.bot_token = bot_token
        self.opensearch = opensearch_client
        self.embeddings = embeddings_client
        self.agentic_rag = agentic_rag_service
        self.application: Optional[Application] = None

    async def start(self) -> None:
        logger.info("Starting Falco Telegram interface...")
        self.application = Application.builder().token(self.bot_token).build()
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("search", self._search_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_question))

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Falco Telegram interface started successfully")

    async def stop(self) -> None:
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Falco Telegram interface stopped")

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Welcome to Falco Agentic RAG!\n\n"
            "Ask a question about CS/AI research and Falco will retrieve relevant papers and answer with sources.\n\n"
            "Commands:\n"
            "/help - Show usage information\n"
            "/search <keywords> - Search indexed papers"
        )

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Send Falco a question about computer science or AI research.\n\n"
            "Examples:\n"
            "- What are transformer architectures?\n"
            "- How does BERT work?\n"
            "- Explain retrieval-augmented generation\n\n"
            "Use /search to retrieve paper titles directly."
        )

    async def _search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Usage: /search <keywords>\nExample: /search neural networks")
            return

        query = " ".join(context.args)
        await update.message.chat.send_action("typing")

        try:
            query_embedding = None
            try:
                query_embedding = await self.embeddings.embed_query(query)
            except Exception as exc:
                logger.warning("Telegram search embedding failed; using BM25: %s", exc)

            results = self.opensearch.search_unified(
                query=query,
                query_embedding=query_embedding,
                size=10,
                use_hybrid=query_embedding is not None,
            )

            hits = results.get("hits", [])
            if not hits:
                await update.message.reply_text("No papers found. Try different keywords.")
                return

            seen_ids = set()
            unique_papers = []
            for hit in hits:
                arxiv_id = hit.get("arxiv_id", "")
                if arxiv_id and arxiv_id not in seen_ids:
                    seen_ids.add(arxiv_id)
                    unique_papers.append(hit)
                if len(unique_papers) >= 5:
                    break

            response = f"Found {len(unique_papers)} papers:\n\n"
            for idx, hit in enumerate(unique_papers, 1):
                title = hit.get("title", "Untitled")
                arxiv_id = hit.get("arxiv_id", "")
                response += f"{idx}. {title}\nhttps://arxiv.org/abs/{arxiv_id}\n\n"

            await update.message.reply_text(response, disable_web_page_preview=True)
        except Exception as exc:
            logger.error("Telegram search failed: %s", exc, exc_info=True)
            await update.message.reply_text(f"Search failed: {str(exc)}")

    async def _handle_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.message.text
        await update.message.chat.send_action("typing")

        try:
            chat_id = getattr(update.effective_chat, "id", "unknown")
            user_id = getattr(update.effective_user, "id", "unknown")
            result = await self.agentic_rag.ask(
                query=query,
                user_id=f"telegram:{user_id}",
                session_id=f"telegram-chat:{chat_id}",
                top_k=3,
                use_hybrid=True,
            )

            response = AskResponse(
                query=result["query"],
                answer=result["answer"],
                sources=result.get("sources", []),
                chunks_used=result.get("chunks_used", 0),
                search_mode=result.get("search_mode", "hybrid"),
            )
            await self._send_answer(update, response)
        except Exception as exc:
            logger.error("Telegram question handling failed: %s", exc, exc_info=True)
            await update.message.reply_text(f"Error: {str(exc)}")

    async def _send_answer(self, update: Update, response: AskResponse) -> None:
        message = f"*Falco answer:*\n{response.answer}\n"

        if response.sources:
            message += "\n*Sources:*\n"
            for idx, source_url in enumerate(response.sources[:5], 1):
                arxiv_id = source_url.split("/")[-1].replace(".pdf", "")
                message += f"{idx}. https://arxiv.org/abs/{arxiv_id}\n"

        try:
            await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception:
            await update.message.reply_text(message, disable_web_page_preview=True)
