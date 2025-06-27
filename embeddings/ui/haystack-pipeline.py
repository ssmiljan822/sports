# requirements:
# pip install gradio farm-haystack[postgres] pymupdf nltk psycopg2-binary

import os
import fitz  # PyMuPDF
import nltk
import gradio as gr
from nltk import sent_tokenize

from haystack.document_stores import SQLDocumentStore
from haystack.nodes import BM25Retriever, OpenAIAnswerGenerator
from haystack.pipelines import GenerativeQAPipeline

nltk.download("punkt")

# ----------- Azure OpenAI Config -----------
os.environ["AZURE_OPENAI_API_KEY"] = "your-azure-api-key"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://your-resource-name.openai.azure.com"
os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = "your-gpt-deployment-name"
os.environ["AZURE_OPENAI_API_VERSION"] = "2023-07-01-preview"

# ----------- PostgreSQL Config -----------
pgHost = "localhost"
pgUser = "your_user"
pgPassword = "your_password"
pgDb = "haystack_db"
pgPort = 5432

# ----------- Helper Functions -----------
def pdfToChunks(pdfPath, chunkSize=5):
    doc = fitz.open(pdfPath)
    documents = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if not text.strip():
            continue
        sentences = sent_tokenize(text)
        for j in range(0, len(sentences), chunkSize):
            chunk = " ".join(sentences[j:j+chunkSize])
            documents.append({
                "content": chunk,
                "meta": {
                    "name": os.path.basename(pdfPath),
                    "page": i + 1
                }
            })
    return documents

def highlightContextInPdf(pdfPath, context, sourcePage, outputPath):
    doc = fitz.open(pdfPath)
    found = False
    for pageNum in range(len(doc)):
        if pageNum + 1 != sourcePage:
            continue
        page = doc[pageNum]
        matches = page.search_for(context)
        for inst in matches:
            highlight = page.add_highlight_annot(inst)
            highlight.set_info({"title": "RAG Source", "content": "Used to answer question"})
            highlight.update()
            found = True
    if found:
        doc.save(outputPath, garbage=4, deflate=True)
    doc.close()
    return found

# ----------- Haystack Setup -----------
documentStore = SQLDocumentStore(
    url=f"postgresql://{pgUser}:{pgPassword}@{pgHost}:{pgPort}/{pgDb}",
    index="pdf_documents",
    content_field="content",
    embedding_field=None,
    recreate_index=True
)

retriever = BM25Retriever(document_store=documentStore)

reader = OpenAIAnswerGenerator(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    model="gpt-35-turbo"
)

pipeline = GenerativeQAPipeline(generator=reader, retriever=retriever)

# ----------- Main App Logic -----------
def qaPipeline(pdfFile, question):
    if not pdfFile or not question.strip():
        return "No question or PDF provided.", None, None

    pdfPath = pdfFile.name
    documents = pdfToChunks(pdfPath)

    if not documents:
        return "No text found in PDF.", None, None

    documentStore.delete_documents()
    documentStore.write_documents(documents)

    prediction = pipeline.run(query=question, params={"Retriever": {"top_k": 3}})

    if not prediction["answers"]:
        return "No answer found.", None, None

    answer = prediction["answers"][0]
    context = answer.meta.get("context", "")
    sourcePage = answer.meta.get("page", "unknown")
    sourceDoc = answer.meta.get("name", "unknown")
    confidence = answer.score if hasattr(answer, "score") else None
    confidenceStr = f"{confidence * 100:.1f}%" if confidence else "N/A"

    highlightedPdf = "highlighted_output.pdf"
    found = highlightContextInPdf(pdfPath, context, sourcePage, highlightedPdf)

    resultText = f"**Answer:** {answer.answer}\n\n"
    resultText += f"**Confidence:** {confidenceStr}\n\n"
    resultText += f"**From:** Page {sourcePage} of `{sourceDoc}`\n\n"
    resultText += f"**Context:**\n{context}"

    if not found:
        resultText += "\n\n⚠️ Context not found in PDF to highlight."

    return resultText, highlightedPdf, "Download highlighted PDF"

# ----------- Gradio Interface -----------
demo = gr.Interface(
    fn=qaPipeline,
    inputs=[
        gr.File(label="Upload PDF"),
        gr.Textbox(label="Ask a question")
    ],
    outputs=[
        gr.Markdown(label="Answer and Source"),
        gr.File(label="Highlighted PDF"),
        gr.Label(visible=False)
    ],
    title="Azure OpenAI PDF QA with Highlighting",
    description="Upload a PDF, ask a question, and get an answer with the source highlighted. Powered by Azure OpenAI + PostgreSQL.",
    allow_flagging="never"
)

if __name__ == "__main__":
    demo.launch()
