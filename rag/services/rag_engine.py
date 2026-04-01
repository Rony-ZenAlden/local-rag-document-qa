# rag/services/rag_engine.py - COMPLETE FIXED VERSION
import os
import logging
from pathlib import Path
from typing import Optional
from langchain_community.document_loaders import PyPDFLoader  # ✅ Fixed import
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.llms import Ollama
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from django.conf import settings

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    RAG Engine with support for:
    - Public mode (all users share same vector index)
    - Session-based anonymous users (separate index per session)
    - Traditional user_id mode (separate index per authenticated user)
    """
    
    def __init__(
        self, 
        user_id: Optional[int] = None, 
        session_id: Optional[str] = None, 
        public: bool = False
    ):
        """
        Initialize RAG Engine with flexible ID modes.
        
        Args:
            user_id: Traditional authenticated user ID (optional)
            session_id: Session-based anonymous user ID (optional, without 'session_' prefix)
            public: If True, all users share the same "public" index
        """
        # Determine index path based on mode
        if public:
            self.index_identifier = "public"
            self.index_path = Path(settings.VECTOR_DB_PATH) / "public"
        elif session_id:
            # ✅ Ensure session_id doesn't have 'session_' prefix (handle both cases)
            clean_session_id = session_id.replace("session_", "")
            self.index_identifier = f"session_{clean_session_id}"
            self.index_path = Path(settings.VECTOR_DB_PATH) / self.index_identifier
        else:
            self.index_identifier = f"user_{user_id or 0}"
            self.index_path = Path(settings.VECTOR_DB_PATH) / self.index_identifier
        
        self.embeddings = None
        self.vectorstore = None
        self.llm = None
        
        logger.info(f"RAGEngine initialized for: {self.index_identifier} | Path: {self.index_path}")
    
    def initialize_embeddings(self):
        """Initialize HuggingFace embeddings model (singleton pattern)"""
        if self.embeddings is None:
            logger.info("Loading HuggingFace embeddings model...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
        return self.embeddings
    
    def initialize_llm(self):
        """Initialize Ollama LLM with timeouts"""
        if self.llm is None:
            logger.info("Connecting to Ollama...")
            self.llm = Ollama(
                base_url=settings.OLLAMA_BASE_URL,
                model="phi",  # Smaller/faster model for CPU
                temperature=0.7,
                request_timeout=120,  # ✅ 2 minutes for CPU inference
                num_predict=512,      # ✅ Limit response length for speed
            )
        return self.llm
    
    def process_pdf(self, file_path: str) -> tuple[bool, str]:
        """
        Process PDF and create/update FAISS index.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            logger.info(f"Processing PDF: {file_path} for {self.index_identifier}")
            logger.info(f"Index path: {self.index_path}")
            
            # 1. Load PDF
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} pages from PDF")
            
            # 2. Split text
            logger.info(f"Splitting {len(documents)} documents...")
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            texts = splitter.split_documents(documents)
            logger.info(f"Split into {len(texts)} chunks")
            
            # 3. Initialize embeddings
            self.initialize_embeddings()
            
            # 4. Create or update vector store
            if self.index_path.exists() and (self.index_path / "index.faiss").exists():
                logger.info("Loading existing index and adding new documents...")
                self.vectorstore = FAISS.load_local(
                    str(self.index_path),
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                self.vectorstore.add_documents(texts)
            else:
                logger.info("Creating new index...")
                self.vectorstore = FAISS.from_documents(texts, self.embeddings)
            
            # 5. Save index (ensure directory exists)
            os.makedirs(self.index_path, exist_ok=True)
            self.vectorstore.save_local(str(self.index_path))
            logger.info(f"Index saved to: {self.index_path}")
            
            # Verify index was saved
            index_files = list(self.index_path.glob("index.*"))
            logger.info(f"Index files created: {[f.name for f in index_files]}")
            
            logger.info(f"Index created/updated for {self.index_identifier} with {len(texts)} chunks")
            
            return True, f"Successfully processed {len(documents)} pages into {len(texts)} chunks"
            
        except Exception as e:
            logger.error(f"Error processing PDF for {self.index_identifier}: {str(e)}", exc_info=True)
            return False, str(e)
    
    def load_index(self) -> bool:
        """Load existing FAISS index for the current identifier."""
        try:
            logger.info(f"Checking for index at: {self.index_path}")
            
            if not self.index_path.exists():
                logger.warning(f"Index path does not exist: {self.index_path}")
                return False
            
            if not (self.index_path / "index.faiss").exists():
                logger.warning(f"Index files not found in: {self.index_path}")
                # List what IS there for debugging
                if self.index_path.exists():
                    files = list(self.index_path.iterdir())
                    logger.warning(f"Files in path: {[f.name for f in files]}")
                return False
            
            self.initialize_embeddings()
            self.vectorstore = FAISS.load_local(
                str(self.index_path),
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            logger.info(f"Index loaded for {self.index_identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading index for {self.index_identifier}: {str(e)}", exc_info=True)
            return False
    
    def ask(self, query: str) -> dict:
        """
        Ask a question and get answer with sources.
        
        Args:
            query: The question to ask
            
        Returns:
            Dict with keys: success, answer, sources, latency_ms (optional)
        """
        import time
        start_time = time.time()
        
        # Load index if not already loaded
        if self.vectorstore is None:
            if not self.load_index():
                return {
                    'success': False,
                    'answer': "No documents uploaded yet. Please upload PDFs first.",
                    'sources': [],
                    'latency_ms': 0
                }
        
        # Initialize LLM
        self.initialize_llm()
        
        # Create custom prompt
        prompt_template = """Use the following pieces of context to answer the question at the end. 
If you don't know the answer based on the context, say you don't know, don't try to make up an answer.
Always cite which document the information comes from.

CONTEXT:
{context}

QUESTION: {question}

ANSWER (with sources):"""

        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        # Create QA chain
        qa = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=True,
            chain_type_kwargs={"prompt": PROMPT}
        )
        
        # Get answer
        try:
            result = qa.invoke({"query": query})  # ✅ Use invoke() instead of __call__()
            elapsed = time.time() - start_time
            
            # Extract sources
            sources = []
            for doc in result.get('source_documents', []):
                source_info = {
                    'content': doc.page_content[:200] + '...' if len(doc.page_content) > 200 else doc.page_content,
                    'metadata': doc.metadata
                }
                sources.append(source_info)
            
            return {
                'success': True,
                'answer': result['result'],
                'sources': sources,
                'latency_ms': int(elapsed * 1000),
                'query': query
            }
            
        except Exception as e:
            logger.error(f"Error during QA for {self.index_identifier}: {str(e)}", exc_info=True)
            return {
                'success': False,
                'answer': f"Error processing question: {str(e)}",
                'sources': [],
                'latency_ms': int((time.time() - start_time) * 1000)
            }
    
    def delete_index(self) -> bool:
        """Delete the vector index for the current identifier."""
        try:
            if self.index_path.exists():
                import shutil
                shutil.rmtree(self.index_path)
                self.vectorstore = None
                logger.info(f"Index deleted for {self.index_identifier}")
                return True
            logger.warning(f"No index to delete for {self.index_identifier}")
            return False
        except Exception as e:
            logger.error(f"Error deleting index for {self.index_identifier}: {str(e)}")
            return False
    
    def get_index_info(self) -> dict:
        """Get information about the current index."""
        import os
        
        info = {
            'identifier': self.index_identifier,
            'path': str(self.index_path),
            'exists': self.index_path.exists(),
            'size_mb': 0,
            'num_files': 0
        }
        
        if self.index_path.exists():
            total_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(self.index_path)
                for filename in filenames
            )
            info['size_mb'] = round(total_size / (1024 * 1024), 2)
            info['num_files'] = sum(
                len(filenames)
                for dirpath, dirnames, filenames in os.walk(self.index_path)
            )
        
        return info


# =============================================================================
# Helper Functions
# =============================================================================

def get_embeddings():
    """Helper function to get embeddings instance (singleton pattern)."""
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )


def get_index_path_for_identifier(identifier: str) -> Path:
    """Get the index path for a given identifier without instantiating RAGEngine."""
    return Path(settings.VECTOR_DB_PATH) / identifier


def list_all_indexes() -> list:
    """List all existing vector indexes in the VECTOR_DB_PATH."""
    vector_db_path = Path(settings.VECTOR_DB_PATH)
    if not vector_db_path.exists():
        return []
    
    indexes = []
    for item in vector_db_path.iterdir():
        if item.is_dir() and (item / "index.faiss").exists():
            indexes.append({
                'identifier': item.name,
                'path': str(item),
                'size_mb': round(
                    sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, dirnames, filenames in os.walk(item)
                        for filename in filenames
                    ) / (1024 * 1024), 2
                )
            })
    
    return indexes