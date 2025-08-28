import gradio as gr

# Dummy authentication
USERNAME = "admin"
PASSWORD = "1234"

# Global state to store file content
userSessions = {}

def login(userName, passWord, sessionId):
    if userName == USERNAME and passWord == PASSWORD:
        return gr.update(visible=False), gr.update(visible=True), sessionId
    else:
        return gr.update(value="Invalid login!"), gr.update(visible=False), sessionId

def uploadFile(file, sessionId):
    if file is None:
        return "Please upload a file first."
    with open(file.name, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    userSessions[sessionId] = content
    return "File uploaded successfully!"

def answerQuestion(question, sessionId):
    content = userSessions.get(sessionId, "")
    if not content:
        return "No file uploaded."
    # Very simple retrieval: check if question words appear in file
    words = question.lower().split()
    matches = [line for line in content.split("\n") if any(w in line.lower() for w in words)]
    if matches:
        return "\n".join(matches[:5])
    else:
        return "No relevant information found."

with gr.Blocks() as demo:
    sessionId = gr.State("user1")

    # Screen 1: Login
    with gr.Group(visible=True) as loginScreen:
        gr.Markdown("### Login")
        userName = gr.Textbox(label="Username")
        passWord = gr.Textbox(label="Password", type="password")
        loginStatus = gr.Textbox(label="Status")
        loginBtn = gr.Button("Login")

    # Screen 2: File Upload
    with gr.Group(visible=False) as uploadScreen:
        gr.Markdown("### Upload File")
        file = gr.File(label="Upload a text file", file_types=[".txt"])
        uploadStatus = gr.Textbox(label="Upload Status")
        uploadBtn = gr.Button("Submit File")

    # Screen 3: Ask/Answer
    with gr.Group(visible=False) as qaScreen:
        gr.Markdown("### Ask Questions about File")
        question = gr.Textbox(label="Your Question")
        answer = gr.Textbox(label="Answer")
        askBtn = gr.Button("Ask")

    # Button Logic
    loginBtn.click(login, [userName, passWord, sessionId], [loginStatus, uploadScreen, sessionId])
    uploadBtn.click(uploadFile, [file, sessionId], uploadStatus)
    askBtn.click(answerQuestion, [question, sessionId], answer)

    # Show Q&A after file uploaded
    uploadBtn.click(lambda: gr.update(visible=True), None, qaScreen)

if __name__ == "__main__":
    demo.launch()
