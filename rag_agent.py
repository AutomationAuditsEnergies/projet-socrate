from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAI
from langchain.chains import RetrievalQA
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("OPENAI_API_KEY")

# Chargement du vecteur index
embedding_model = HuggingFaceEmbeddings(model_name = "all-MiniLM-L6-v2")
vectordb = FAISS.load_local("faiss_index", embedding_model, allow_dangerous_deserialization = True)

retriever = vectordb.as_retriever()
llm = OpenAI(temperature = 0, openai_api_key = SECRET_KEY)

qa_chain = RetrievalQA.from_chain_type(llm = llm, retriever = retriever)

def rag_answer(question: str) -> str:
    try:
        response = qa_chain.invoke({"query": question})
        return response["result"]
    except Exception as e:
        print("Erreur RAG:", e)
        return "Je ne peux pas répondre à ta question pour le moment."