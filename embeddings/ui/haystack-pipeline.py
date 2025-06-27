import os
import nltk
import fitz  # PyMuPDF
import gradio as gr
import pdfplumber
from nltk import sent_tokenize
from tempfile import NamedTemporaryFile

from haystack.document_stores import SQLDocumentStore
from haystack.nodes import BM25Retriever, OpenAIAnswerGenerator
from haystack.pipelines import GenerativeQAPipeline

nltk.download("punkt")

# -------------------- Configuration --------------------

pgUser = os.environ.get("PG_USER", "postgres")
pgPassword = os.environ.get("PG_PW", "postgres")
pgDb = os.environ.get("PG_DB", "haystack_db")
pgHost = os.environ.get("PG_HOST", "localhost")
pgPort = os.environ.get("PG_PORT", "5432")

azureApiKey = os.environ["AZURE_OPENAI_API_KEY"]
azureEndpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azureDeployment = os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
azureApiVersion = os.environ.get("AZURE_OPENAI_API_VERSION", "2023-07-01-preview")

# -------------------- Predefined Prompts --------------------

predefinedPrompts = {
    "summary": "Summarize the key points in this document.",
    "legal_risks": "What are the legal risks mentioned in the document?",
    "financial_terms": "List all financial terms defined in this PDF.",
    "custom": ""  # freeform user prompt
}

# -------------------- Haystack Setup --------------------

documentStore = SQLDocumentStore(
    url=f"postgresql://{pgUser}:{pgPassword}@{pgHost}:{pgPort}/{pgDb}",
    index="pdf_docs",
    content_field="content",
    recreate_index=True
)

retriever = BM25Retriever(document_store=documentStore)

reader = OpenAIAnswerGenerator(
    api_key=azureApiKey,
    azure_deployment=azureDeployment,
    azure_endpoint=azureEndpoint,
    azure_api_version=azureApiVersion,
    model="gpt-35-turbo",
    max_tokens=512,
    return_answer=True,
    return_context=True,
    top_k=3
)

pipeline = GenerativeQAPipeline(retriever=retriever, generator=reader)

# -------------------- Session State --------------------

sessionData = {
    "pdfPath": None,
    "highlightedPath": None,
    "pdfIndexed": False,
    "pdfName": None,
}

# -------------------- PDF Chunking --------------------

def pdfToChunks(pdfPath, chunkSize=5):
    documents = []
    with pdfplumber.open(pdfPath) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text or not text.strip():
                continue
            sentences = sent_tokenize(text)
            for j in range(0, len(sentences), chunkSize):
                chunk = " ".join(sentences[j:j + chunkSize])
                documents.append({
                    "content": chunk,
                    "meta": {"name": os.path.basename(pdfPath), "page": i + 1}
                })
    return documents

# -------------------- Highlighting in PyMuPDF --------------------

def highlightContextsInPdf(originalPath, answers, outputPath):
    doc = fitz.open(originalPath)
    foundAny = False

    for answer in answers:
        context = answer.context.strip()
        pageNum = answer.meta.get("page")
        if not context or not isinstance(pageNum, int):
            continue
        page = doc[pageNum - 1]
        matches = page.search_for(context, hit_max=10)
        for inst in matches:
            highlight = page.add_highlight_annot(inst)
            highlight.set_info({"title": "Answer Context", "content": "Used as context for an answer."})
            highlight.update()
            foundAny = True

    if foundAny:
        doc.save(outputPath, garbage=4, deflate=True)
    doc.close()
    return foundAny

# -------------------- Handlers --------------------

def uploadPdf(pdfFile):
    if pdfFile is None:
        return "⚠️ Please upload a valid PDF file."
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdfFile.read())
        sessionData["pdfPath"] = tmp.name
        sessionData["highlightedPath"] = tmp.name  # Initially unmodified
        sessionData["pdfName"] = os.path.basename(pdfFile.name)

    # Chunk and index
    documents = pdfToChunks(sessionData["pdfPath"])
    if not documents:
        return "⚠️ No readable text found in the PDF."
    documentStore.delete_documents()
    documentStore.write_documents(documents)
    sessionData["pdfIndexed"] = True

    return f"✅ PDF uploaded and indexed: `{sessionData['pdfName']}`"

def askQuestion(promptText):
    if not sessionData["pdfIndexed"]:
        return "⚠️ Please upload and index a PDF first.", None, None

    if not promptText or not promptText.strip():
        return "⚠️ Please enter a prompt/question.", None, None

    result = pipeline.run(query=promptText, params={"Retriever": {"top_k": 5}})
    answers = result.get("answers", [])

    if not answers:
        return "No answers found.", None, None

    newHighlightedPath = "highlighted_output.pdf"
    highlightContextsInPdf(sessionData["highlightedPath"], answers, newHighlightedPath)
    sessionData["highlightedPath"] = newHighlightedPath

    resultText = ""
    for i, ans in enumerate(answers, 1):
        page = ans.meta.get("page", "unknown")
        name = ans.meta.get("name", "unknown")
        score = ans.score or 0.0
        resultText += f"### 🔹 Answer {i}\n"
        resultText += f"**Answer:** {ans.answer}\n\n"
        resultText += f"**Confidence:** {score * 100:.1f}%\n"
        resultText += f"**Page:** {page} from `{name}`\n"
        resultText += f"**Context:** {ans.context.strip()}\n\n---\n\n"

    return resultText, sessionData["highlightedPath"], "Download highlighted PDF"

def updatePromptText(promptId):
    return predefinedPrompts.get(promptId, "")

# -------------------- Gradio Interface --------------------

with gr.Blocks(title="PDF Multi-Question QA with Prompts") as demo:
    gr.Markdown("## 📄 Ask Multiple Questions about a Single PDF Document")
    with gr.Row():
        with gr.Column():
            pdfInput = gr.File(label="Upload PDF", type="binary")
            uploadBtn = gr.Button("Upload & Index PDF")
            uploadStatus = gr.Markdown()

        with gr.Column():
            promptIdDropdown = gr.Dropdown(
                label="Select Prompt",
                choices=list(predefinedPrompts.keys()),
                value="custom"
            )
            questionBox = gr.Textbox(label="Prompt Text (editable)")
            askBtn = gr.Button("Ask")
            answerBox = gr.Markdown()
            highlightedOutput = gr.File(label="Highlighted PDF", visible=True)

    promptIdDropdown.change(fn=updatePromptText, inputs=promptIdDropdown, outputs=questionBox)
    uploadBtn.click(fn=uploadPdf, inputs=[pdfInput], outputs=[uploadStatus])
    askBtn.click(fn=askQuestion, inputs=[questionBox], outputs=[answerBox, highlightedOutput, gr.Label(visible=False)])

if __name__ == "__main__":
    demo.launch()
