"""
=============================================================================
AI-POWERED RESUME ANALYZER - COMPLETE APPLICATION
Your API Keys Configured
=============================================================================
"""

import streamlit as st
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from PyPDF2 import PdfReader
import os
from dotenv import load_dotenv
import uuid

# Load environment variables
load_dotenv()

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_text_from_pdf(pdf_file):
    """Extract all text from PDF file"""
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text


def chunk_text(text):
    """Split text into smaller chunks"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks


def create_collection(client, collection_name):
    """Create a collection in Qdrant Cloud"""
    try:
        collections = client.get_collections().collections
        collection_names = [col.name for col in collections]
        
        if collection_name in collection_names:
            client.delete_collection(collection_name=collection_name)
        
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=1536,
                distance=Distance.COSINE
            )
        )
    except Exception as e:
        st.error(f"Error creating collection: {e}")
        raise e


def store_chunks_in_qdrant(client, collection_name, chunks, embeddings):
    """Convert chunks to vectors and store in Qdrant"""
    points = []
    
    for idx, chunk in enumerate(chunks):
        vector = embeddings.embed_query(chunk)
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={"text": chunk, "chunk_id": idx}
        )
        points.append(point)
    
    client.upsert(
        collection_name=collection_name,
        points=points
    )
    
    return len(chunks)


def search_resume(client, collection_name, query, embeddings, top_k=3):
    """Search Qdrant for relevant chunks"""
    query_vector = embeddings.embed_query(query)
    
    search_results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k
    )
    
    relevant_chunks = [result.payload["text"] for result in search_results]
    return relevant_chunks


def generate_answer(query, relevant_chunks, llm):
    """Generate answer using ChatGPT"""
    context = "\n\n".join(relevant_chunks)
    
    prompt = f"""You are an AI assistant analyzing a resume. Answer the question based ONLY on the resume sections below.

RESUME SECTIONS:
{context}

QUESTION: {query}

Provide a detailed answer based on the resume content. If the information is not available, say so.

ANSWER:"""
    
    response = llm.invoke(prompt)
    return response.content


def process_resume(pdf_file, client, collection_name, embeddings):
    """Complete RAG pipeline"""
    text = extract_text_from_pdf(pdf_file)
    chunks = chunk_text(text)
    create_collection(client, collection_name)
    num_chunks = store_chunks_in_qdrant(client, collection_name, chunks, embeddings)
    return num_chunks, text


def ask_question(query, client, collection_name, embeddings, llm):
    """Complete Q&A pipeline"""
    relevant_chunks = search_resume(client, collection_name, query, embeddings)
    answer = generate_answer(query, relevant_chunks, llm)
    return answer, relevant_chunks


# =============================================================================
# MAIN STREAMLIT APPLICATION
# =============================================================================

def main():
    """Main Streamlit application"""
    
    # Page configuration
    st.set_page_config(
        page_title="AI Resume Analyzer",
        page_icon="🤖",
        layout="wide"
    )
    
    # Header
    st.title("🤖 AI-Powered Resume Analyzer")
    st.markdown("""
    **Upload your resume and get AI-powered insights instantly!**
    
    **Your Configuration:**
    - ✅ OpenAI API: Connected
    - ✅ Qdrant Cloud: eu-west-2 cluster
    
    📤 Upload PDF → ⚙️ AI processes → 💬 Ask questions → 🎯 Get answers
    """)
    st.markdown("---")
    
    # Validate API keys
    if not os.getenv("QDRANT_URL") or not os.getenv("QDRANT_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        st.error("❌ **Missing API Keys!**")
        st.info("""
        Please create a `.env` file in the same folder with:
        ```
        OPENAI_API_KEY=sk-proj-ygGv4P_h_ESbtEXljBEt...
        QDRANT_URL=https://94d3d7fd-9535-47b8...qdrant.io:6333
        QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIs...
        ```
        """)
        st.stop()
    
    # Initialize connections
    try:
        with st.spinner("🔄 Connecting to your services..."):
            # Connect to YOUR Qdrant Cloud
            client = QdrantClient(
                url=os.getenv("QDRANT_URL"),
                api_key=os.getenv("QDRANT_API_KEY"),
            )
            
            # Initialize YOUR OpenAI embeddings
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
            
            # Initialize YOUR ChatGPT
            llm = ChatOpenAI(
                model="gpt-3.5-turbo",
                temperature=0,
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
            
            collection_name = "resume_collection"
        
        st.sidebar.success("✅ Connected to Qdrant Cloud & OpenAI!")
        
    except Exception as e:
        st.sidebar.error(f"❌ Connection failed: {e}")
        st.error("Please check your API keys in the .env file")
        st.stop()
    
    # Sidebar: File Upload
    with st.sidebar:
        st.header("📤 Upload Resume")
        st.markdown("**Format:** PDF only")
        
        uploaded_file = st.file_uploader(
            "Choose your resume PDF",
            type=['pdf'],
            help="Upload your resume in PDF format"
        )
        
        if uploaded_file is not None:
            st.success(f"✅ {uploaded_file.name}")
            st.info(f"📊 Size: {uploaded_file.size / 1024:.2f} KB")
            
            if st.button("🔄 Process Resume", type="primary"):
                with st.spinner("⏳ Processing your resume..."):
                    try:
                        num_chunks, extracted_text = process_resume(
                            uploaded_file, client, collection_name, embeddings
                        )
                        
                        st.session_state['resume_processed'] = True
                        st.session_state['num_chunks'] = num_chunks
                        st.session_state['resume_text'] = extracted_text
                        st.session_state['filename'] = uploaded_file.name
                        
                        st.success(f"""
                        ✅ **Processing Complete!**
                        - **Chunks:** {num_chunks}
                        - **Storage:** Qdrant Cloud
                        - **Status:** Ready for questions!
                        """)
                        
                    except Exception as e:
                        st.error(f"❌ Processing error: {e}")
        
        if 'resume_text' in st.session_state:
            st.markdown("---")
            st.subheader("📊 Resume Info")
            st.metric("Chunks Created", st.session_state['num_chunks'])
            st.metric("File Name", st.session_state['filename'])
            
            with st.expander("📄 View Extracted Text"):
                st.text_area(
                    "Preview (first 1000 chars):",
                    st.session_state['resume_text'][:1000] + "...",
                    height=250
                )
    
    # Main Area: Q&A Interface
    if 'resume_processed' in st.session_state and st.session_state['resume_processed']:
        
        st.header("💬 Ask Questions About Your Resume")
        
        # Quick question buttons
        st.subheader("⚡ Quick Questions:")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🛠️ Technical Skills", use_container_width=True):
                st.session_state['current_query'] = "What are my technical skills and technologies?"
        
        with col2:
            if st.button("💼 Work Experience", use_container_width=True):
                st.session_state['current_query'] = "Summarize my work experience and responsibilities"
        
        with col3:
            if st.button("🎓 Education", use_container_width=True):
                st.session_state['current_query'] = "What is my educational background?"
        
        col4, col5, col6 = st.columns(3)
        
        with col4:
            if st.button("🚀 Projects", use_container_width=True):
                st.session_state['current_query'] = "What projects have I worked on?"
        
        with col5:
            if st.button("🏆 Achievements", use_container_width=True):
                st.session_state['current_query'] = "List my key achievements and accomplishments"
        
        with col6:
            if st.button("📧 Contact Info", use_container_width=True):
                st.session_state['current_query'] = "What is my contact information?"
        
        # Custom question input
        st.markdown("---")
        st.subheader("✍️ Or Ask Your Own Question:")
        user_query = st.text_input(
            "Type your question here:",
            placeholder="e.g., What programming languages do I know?",
            key="user_input"
        )
        
        if st.button("🔍 Get Answer", type="primary"):
            if user_query.strip():
                st.session_state['current_query'] = user_query
            else:
                st.warning("⚠️ Please enter a question first!")
        
        # Display answer
        if 'current_query' in st.session_state and st.session_state['current_query']:
            query = st.session_state['current_query']
            
            st.markdown("---")
            st.subheader(f"❓ Question: *{query}*")
            
            with st.spinner("🤔 AI is analyzing your resume..."):
                try:
                    answer, chunks = ask_question(
                        query, client, collection_name, embeddings, llm
                    )
                    
                    st.markdown("### 💡 Answer:")
                    st.success(answer)
                    
                    with st.expander("🔎 View Source Chunks from Your Resume"):
                        st.markdown("*These sections from your resume were used to generate the answer:*")
                        for i, chunk in enumerate(chunks, 1):
                            st.markdown(f"**📄 Section {i}:**")
                            st.info(chunk)
                            st.markdown("---")
                    
                except Exception as e:
                    st.error(f"❌ Error generating answer: {e}")
    
    else:
        # Instructions for new users
        st.info("👈 **Get Started:** Upload your resume from the sidebar!")
        
        st.markdown("""
        ### 📚 How to Use This App:
        
        **Step 1:** Click the "Browse files" button in the left sidebar
        
        **Step 2:** Select your resume PDF file from your computer
        
        **Step 3:** Click the "🔄 Process Resume" button
        
        **Step 4:** Wait 10-30 seconds for AI processing
        
        **Step 5:** Ask questions using quick buttons or type your own!
        
        ---
        
        ### ✨ Example Questions You Can Ask:
        
        - What are my core competencies and technical skills?
        - Which companies have I worked for and what were my roles?
        - What is my highest level of education?
        - What programming languages and frameworks do I know?
        - Summarize my career highlights and achievements
        - What certifications or awards do I have?
        - What projects have I completed?
        - What are my strongest skills?
        
        ---
        
        ### 🔒 Privacy & Security:
        
        - Your resume is processed securely using **your** OpenAI API
        - Data is stored in **your** private Qdrant Cloud cluster
        - Only **you** have access to your API keys and data
        - Resume data can be deleted anytime from Qdrant dashboard
        
        ---
        
        ### ⚙️ Powered By:
        
        - **OpenAI GPT-3.5-turbo** for intelligent answers
        - **Qdrant Cloud** (eu-west-2) for vector storage
        - **RAG Technology** for accurate, context-aware responses
        """)


# =============================================================================
# RUN THE APPLICATION
# =============================================================================

if __name__ == "__main__":
    main()
