import os
import streamlit as st
from dotenv import load_dotenv
from config import LoggingConfig

from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# Load environment variables
load_dotenv(override=True)

# Initialize logging configuration
log_config = LoggingConfig()
logger = log_config.setup_logging(logger_name="healthcare_chatbot", folder_name="healthcare_chatbot", deploy_env=st.secrets("DEPLOY_ENV"))

def load_and_split_documents(chunk_size: int = 500, chunk_overlap: int = 50):
    """
    Load PDF documents from a directory and split them into chunks.

    Args:
        chunk_size (int): Size of each chunk.
        chunk_overlap (int): Overlap between chunks.

    Returns:
        list: List of document chunks.
    """
    try:
        directory_path = "../data"
        if not os.path.isdir(directory_path):
            logger.error(f"Directory path does not exist: {directory_path}")
            raise ValueError(f"Directory path not found: {directory_path}")
        
        logger.info(f"Loading PDF documents from directory: {directory_path}")
        pdf_loader = DirectoryLoader(directory_path, glob="*.pdf", loader_cls=PyPDFLoader)
        pdf_documents = pdf_loader.load()

        logger.info(f"Splitting documents into chunks with chunk_size={chunk_size} and chunk_overlap={chunk_overlap}")
        chunk_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        document_chunks = chunk_splitter.split_documents(pdf_documents)

        logger.info("Document chunks created successfully.")

        return document_chunks
    
    except Exception as e:
        logger.error(f"Failed to load and split documents: {e}")
        raise

def initialize_models_and_store(document_chunks: list):
    """
    Initialize the language model and vector store.

    Args:
        document_chunks (list): List of document chunks.

    Returns:
        tuple: Language model and vector retriever.
    """
    try:
        groq_api_key = st.secrets('GROQ_API_KEY')
        if not groq_api_key:
            logger.error("GROQ API key not found in environment variables.")
            raise ValueError("GROQ API key not found.")
        
        logger.info("Initializing language model.")
        groq_model_name = st.secrets('GROQ_MODEL_NAME')
        language_model = ChatGroq(groq_api_key=groq_api_key, model_name=groq_model_name)

        embedding_model_name = st.secrets("EMBEDDING_MODEL_NAME")
        logger.info(f"Initializing embedding model with model name: {embedding_model_name}")
        embeddings_model = HuggingFaceEmbeddings(model_name=embedding_model_name, model_kwargs={'device': "cpu"})

        logger.info("Creating vector database from document chunks.")
        vector_database = FAISS.from_documents(document_chunks, embeddings_model)
        retriever=vector_database.as_retriever()

        logger.info("Language model and vector retriever initialized successfully.")

        return language_model, retriever
    
    except Exception as e:
        logger.error(f"Failed to initialize models and store: {e}")
        raise


def create_conversational_chain(language_model: ChatGroq, retriever: FAISS):
    """
    Create the conversational retrieval chain.

    Args:
        language_model (ChatGroq): The language model.
        retriever (FAISS): The vector database retriever.

    Returns:
        create_retrieval_chain: The conversational retrieval chain.
    """

    contextualize_q_system_prompt = "Given a chat history and the latest user question \
    which might reference context in the chat history, formulate a standalone question \
    which can be understood without the chat history. Do NOT answer the question, \
    just reformulate it if needed and otherwise return it as is."

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    history_aware_retriever = create_history_aware_retriever(language_model, retriever, contextualize_q_prompt)

    qa_system_prompt = """You are an assistant for question-answering tasks. \
    Use the following pieces of retrieved context to answer the question. \
    If you don't know the answer, just say that you don't know. \

    {context}.
    """

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    question_answer_chain = create_stuff_documents_chain(language_model, qa_prompt)
    conversation_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)  

    logger.info("Conversational chain created successfully.")

    return conversation_chain

def get_session_history(store:dict, session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def initialize_session_state():
    """
    Initialize session state variables for chat history and messages.
    """
    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []

    if "messages" not in st.session_state:
        st.session_state['messages'] = []

def handle_user_query(get_conversation_chain: RunnableWithMessageHistory, user_query: str):
    """
    Handle the user query and get the response from the conversation chain.

    Args:
        conversational_rag_chain (RunnableWithMessageHistory): The conversational retrieval chain.
        user_query (str): The user's query.

    Returns:
        str: The response from the conversation rag chain.
    """
    try:
        logger.info(f"Processing user query: {user_query}")
        response = get_conversation_chain.invoke(
        {"input": user_query},
        config={
            "configurable": {"session_id": "mental_health"}
        },
        )
        st.session_state['chat_history'].append((user_query, response["answer"]))

        logger.info("User query processed successfully.")

        return response["answer"]
    except Exception as e:
        logger.error(f"Error handling user query: {e}")
        raise

def display_chat_interface(conversational_rag_chain: RunnableWithMessageHistory):
    """
    Display the chat interface using Streamlit.

    Args:
        conversational_rag_chain (RunnableWithMessageHistory): The conversational retrieval chain.
    """
    st.title("Healthcare Chatbot")

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if user_query := st.chat_input("Ask about your Mental Health"):
        # Display user message in chat message container
        st.chat_message("user").markdown(user_query)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_query})

        response = handle_user_query(conversational_rag_chain, user_query)

        # Display assistant response in chat message container
        st.chat_message("assistant").markdown(response)
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

def main():
    """
    Main function to run the Streamlit application.
    """
    try:
        logger.info("Starting the main application.")
        
        document_chunks = load_and_split_documents()
        language_model, vector_database = initialize_models_and_store(document_chunks)
        conversation_chain = create_conversational_chain(language_model, vector_database)

        store = {}
        conversational_rag_chain = RunnableWithMessageHistory(
        conversation_chain,
        lambda session_id: get_session_history(store, session_id),
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
        )

        initialize_session_state()
        display_chat_interface(conversational_rag_chain)

        logger.info("Application initialized successfully.")

    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        raise

if __name__ == "__main__":
    main()
