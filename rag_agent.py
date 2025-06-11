import os
import time
import random
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
#from langchain_openai import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
#from langchain.chains.question_answering import load_qa_chain
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("OPENAI_API_KEY")

# Prompt pour guider l'agent
prompt_template = PromptTemplate(
    input_variables=["context", "question"],
    template="""
    Tu es un assistant pédagogique, bienveillant et naturel. Tu aides l'utilisateur à comprendre le contenu du cours suivant. 
    Tu ne dois utiliser que les informations présentes dans ce contenu pour répondre aux questions, sauf s'il s'agit de formules de politesse (bonjour, merci, etc.), auxquelles tu peux répondre naturellement.
    Tu tutoies les étudiants et tu réponds de manière simple et directe, comme un professeur qui explique à un élève.

    Si la question dépasse le cadre du cours, tu peux répondre de manière polie et honnête avec des formulations naturelles, comme :

    - "Je réponderai à ta question seulement si elle concerne le contenu du cours."
    - "Cela sort un peu du cadre de notre cours, mais je peux t'aider sur un autre point si tu veux."
    - "Je ne pense pas que ce soit dans le contenu du cours, mais n'hésite pas à poser une autre question."

    Contenu du cours :
    {context}

    Question :
    {question}

    Réponse :
    """
)

# Chargement du vecteur index
embedding_model = HuggingFaceEmbeddings(model_name = "all-MiniLM-L6-v2")
vectordb = FAISS.load_local("faiss_index", embedding_model, allow_dangerous_deserialization = True)

retriever = vectordb.as_retriever()
#llm = OpenAI(temperature = 0, openai_api_key = SECRET_KEY)
llm = ChatOpenAI(
    model_name = "gpt-4",
    temperature = 0.7,
    openai_api_key = SECRET_KEY,
    max_tokens = 1000,)

qa_chain = RetrievalQA.from_chain_type(
    llm = llm, 
    retriever = retriever,
    chain_type = "stuff",
    chain_type_kwargs = {"prompt" : prompt_template})

def rag_answer(question: str) -> str:
    try:
        response = qa_chain.invoke({"query": question})
        result = response["result"]
        
        # 💬 Simulation d'un temps de réponse humain
        base_delay = random.uniform(1.0, 2.0)
        length_delay = len(result) * 0.02 # 20ms par caractère
        total_delay = min(base_delay + length_delay, 4.5)
        time.sleep(total_delay)
        
        return result
    except Exception as e:
        print("Erreur RAG:", e)
        return "Je ne peux pas répondre à ta question pour le moment."