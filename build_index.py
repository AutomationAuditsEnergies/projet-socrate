from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import CharacterTextSplitter
import os

# 1. Charger tous les fichiers .txt dans docs/
docs_path = "./docs"
all_docs = []

for filename in os.listdir(docs_path):
    path = os.path.join(docs_path, filename)
    if filename.endswith(".txt"):
        loader = TextLoader(path, encoding = "utf-8")
    elif filename.endswith(".pdf"):
        loader = PyPDFLoader(path)
    else:
        continue
    documents = loader.load()
    all_docs.extend(documents)

# 2. Splitter les documents en chunks
text_splitter = CharacterTextSplitter(chunk_size = 1000, chunk_overlap = 200)
split_docs = text_splitter.split_documents(all_docs)

# 3. Embedding & FAISS
embedding_model = HuggingFaceEmbeddings(model_name = "all-MiniLM-L6-v2")
vectordb = FAISS.from_documents(split_docs, embedding_model)
vectordb.save_local("faiss_index")

print("✅  Index FAISS généré et sauvegardé.")