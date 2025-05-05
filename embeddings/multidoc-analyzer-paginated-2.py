import os
import psycopg2
from psycopg2.extras import execute_values
from PyPDF2 import PdfReader
import tiktoken
from openai import OpenAI

# === CONFIGURATION ===
embedModel = "text-embedding-3-small"
gptModel = "gpt-4-turbo"
chunkSize = 500

dbConfig = {
    "dbname": "embeddings",
    "user": "emb_writer",
    "password": None,
    "host": "localhost",
    "port": "5432"
}

dbConfig['password'] = os.getenv("DB_PWD")

# === OPENAI CLIENT ===
apiKey=os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=apiKey)

# === TOKENIZATION ===
def chunkText(text, maxTokens=chunkSize):
    encoder = tiktoken.encoding_for_model(embedModel)
    tokens = encoder.encode(text)
    return [encoder.decode(tokens[i:i + maxTokens]) for i in range(0, len(tokens), maxTokens)]

# === READ PDF WITH PAGE NUMBERS ===
def readPdfWithPages(path):
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append((i + 1, text))  # 1-based page numbers
    return pages

# === STORE EMBEDDINGS ===
def storeChunksWithEmbeddings(documentName, pageChunks):
    embeddings = []
    for pageNumber, chunk in pageChunks:
        response = client.embeddings.create(input=[chunk], model=embedModel)
        embedding = response.data[0].embedding
        embeddings.append((documentName, pageNumber, chunk, embedding))

    conn = psycopg2.connect(**dbConfig)
    cur = conn.cursor()
    execute_values(
        cur,
        "INSERT INTO document_chunks_paginated (document_name, page_number, content, embedding) VALUES %s",
        embeddings
    )
    conn.commit()
    cur.close()
    conn.close()

# === LIST DOCUMENTS ===
def listDocuments():
    conn = psycopg2.connect(**dbConfig)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT document_name FROM document_chunks_paginated ORDER BY document_name")
    documents = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return documents

# === SEARCH CHUNKS WITH PAGE NUMBERS ===
def searchSimilarChunks(question, documentNames, topK=5):
    response = client.embeddings.create(input=[question], model=embedModel)
    queryEmbedding = response.data[0].embedding

    placeholders = ','.join(['%s'] * len(documentNames))
    query = f"""
        SELECT document_name, content, page_number FROM document_chunks_paginated
        WHERE document_name IN ({placeholders})
        ORDER BY embedding <-> CAST(%s AS vector)
        LIMIT %s
    """

    conn = psycopg2.connect(**dbConfig)
    cur = conn.cursor()
    cur.execute(query, (*documentNames, queryEmbedding, topK))
    results = cur.fetchall()
    cur.close()
    conn.close()

    return [{"document": row[0], "content": row[1], "page": row[2]} for row in results]


# === GPT Q&A INCLUDING PAGE NUMBERS ===
def askGpt(question, contextChunks):
    context = "\n\n".join(
        f"(Page {chunk['page']} from {chunk['document']}): {chunk['content']}"
        for chunk in contextChunks
    )
    response = client.chat.completions.create(
        model=gptModel,
        messages=[
            {"role": "system", "content": "You are a financial assistant. Use the provided context to answer and be concise."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ],
        temperature=0.2,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()


# === INGEST A NEW DOCUMENT ===
def ingestPdf(pdfPath, documentName):
    print(f"Reading PDF: {pdfPath}")
    pages = readPdfWithPages(pdfPath)
    allChunks = []
    for pageNumber, text in pages:
        chunks = chunkText(text)
        for chunk in chunks:
            allChunks.append((pageNumber, chunk))
    print(f"{len(allChunks)} chunks generated.")
    print(f"Storing in DB under '{documentName}'...")
    storeChunksWithEmbeddings(documentName, allChunks)
    print("Done.")

# === MAIN INTERFACE ===
def main():
    print("Choose an action:\n1. Ingest a new PDF\n2. Ask questions")
    action = input("Enter 1 or 2: ").strip()

    if action == "1":
        pdfPath = input("Enter full path to PDF file: ").strip()
        documentName = input("Enter a name to identify this document: ").strip()
        ingestPdf(pdfPath, documentName)

    elif action == "2":
        documents = listDocuments()
        if not documents:
            print("No documents found in the database.")
            return

        print("\nAvailable documents:")
        for i, doc in enumerate(documents, 1):
            print(f"{i}. {doc}")

        selectedIndexes = input("Enter the numbers of documents to use (comma-separated): ")
        try:
            selectedDocs = [documents[int(i.strip()) - 1] for i in selectedIndexes.split(',')]
        except (ValueError, IndexError):
            print("Invalid selection.")
            return

        print("You can now ask questions (type 'exit' to quit):")
        while True:
            question = input("\nYour question: ")
            if question.lower() in ("exit", "quit"):
                break

            relevantChunks = searchSimilarChunks(question, selectedDocs)
            answer = askGpt(question, relevantChunks)

            print(f"\n## ✅ Answer:\n{answer}")
            print("\n## 📚 Sources (Markdown-formatted):")

            for i, chunk in enumerate(relevantChunks, 1):
                doc = chunk['document']
                page = chunk['page']
                quote = chunk['content'].strip().replace("\n", " ")
                print(f"\n> **[{i}]** From *{doc}*, page {page}:\n> \"{quote}\"")

    else:
        print("Invalid option.")

if __name__ == "__main__":
    main()
