"""
Document parsing service for extracting text from PDF and DOCX files.

This module provides functionality to extract requirement text from uploaded documents
for LLM processing. Supports PDF and DOCX formats with comprehensive error handling
and text truncation to manage document size limits.

Character Limit:
- Documents are truncated at 50,000 characters to prevent excessive memory usage
  and ensure efficient LLM processing. This limit balances completeness with
  performance considerations.
"""

import logging
from io import BytesIO

from docx import Document
from pypdf import PdfReader

# Configure logging
logger = logging.getLogger(__name__)

# Character limit for extracted text (prevents excessive memory usage)
MAX_TEXT_LENGTH = 50000


class DocumentParser:
    """
    Document parser service for extracting text from PDF and DOCX files.
    
    This class provides static methods for parsing documents without maintaining
    instance state. All methods are designed to handle various edge cases including
    corrupted files, empty documents, encrypted PDFs, and unsupported features.
    
    Supported Formats:
    - PDF (.pdf)
    - DOCX (.docx, .doc)
    - Text (.txt)
    """
    
    @staticmethod
    def parse_pdf(file_content: bytes) -> str:
        """
        Extract text from a PDF file.
        
        Processes all pages in the PDF document, extracting text sequentially.
        Handles various PDF edge cases including corrupted files, empty PDFs,
        encrypted PDFs, and documents with unsupported features.
        
        Args:
            file_content: Raw PDF file content as bytes
            
        Returns:
            Extracted text as a string. If the document exceeds the character limit,
            the text will be truncated and a warning message will be appended.
            
        Raises:
            ValueError: If the PDF is encrypted or cannot be read
            Exception: For other PDF parsing errors (corrupted files, etc.)
        """
        try:
            logger.info("Starting PDF parsing...")
            
            # Validate input
            if not file_content:
                logger.warning("Empty PDF file content provided")
                return ""
            
            # Create PdfReader from bytes
            pdf_file = BytesIO(file_content)
            pdf_reader = PdfReader(pdf_file)
            
            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                error_msg = "PDF file is encrypted and cannot be processed"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Check if PDF has pages
            num_pages = len(pdf_reader.pages)
            if num_pages == 0:
                logger.warning("PDF file contains no pages")
                return ""
            
            logger.info(f"Processing PDF with {num_pages} pages...")
            
            # Extract text from all pages
            extracted_text_parts = []
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text_parts.append(page_text)
                        logger.debug(f"Extracted text from page {page_num}")
                    else:
                        logger.debug(f"Page {page_num} contains no extractable text")
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num}: {e}")
                    # Continue processing other pages even if one fails
                    continue
            
            # Combine all extracted text with newline separators
            full_text = "\n".join(extracted_text_parts)
            
            # Check and handle text length limit
            if len(full_text) > MAX_TEXT_LENGTH:
                logger.warning(
                    f"PDF text exceeds {MAX_TEXT_LENGTH} character limit. "
                    f"Truncating from {len(full_text)} characters."
                )
                full_text = full_text[:MAX_TEXT_LENGTH]
                full_text += f"\n\n[WARNING: Document truncated at {MAX_TEXT_LENGTH} characters]"
            
            logger.info(f"Successfully extracted {len(full_text)} characters from PDF")
            return full_text
            
        except ValueError:
            # Re-raise ValueError (e.g., encrypted PDF)
            raise
        except Exception as e:
            error_msg = f"Failed to parse PDF file: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
    
    @staticmethod
    def parse_docx(file_content: bytes) -> str:
        """
        Extract text from a DOCX file.
        
        Processes all paragraphs in the DOCX document, extracting text in order.
        Handles various edge cases including corrupted files, empty documents,
        and documents with unsupported features.
        
        Args:
            file_content: Raw DOCX file content as bytes
            
        Returns:
            Extracted text as a string. If the document exceeds the character limit,
            the text will be truncated and a warning message will be appended.
            
        Raises:
            Exception: For DOCX parsing errors (corrupted files, unsupported features, etc.)
        """
        try:
            logger.info("Starting DOCX parsing...")
            
            # Validate input
            if not file_content:
                logger.warning("Empty DOCX file content provided")
                return ""
            
            # Create Document object from bytes
            docx_file = BytesIO(file_content)
            doc = Document(docx_file)
            
            # Extract text from all paragraphs
            extracted_text_parts = []
            for para_num, paragraph in enumerate(doc.paragraphs, start=1):
                try:
                    para_text = paragraph.text
                    if para_text:
                        extracted_text_parts.append(para_text)
                        logger.debug(f"Extracted text from paragraph {para_num}")
                except Exception as e:
                    logger.warning(f"Error extracting text from paragraph {para_num}: {e}")
                    # Continue processing other paragraphs even if one fails
                    continue
            
            # Combine all extracted text with newline separators
            full_text = "\n".join(extracted_text_parts)
            
            # Check if document is empty
            if not full_text.strip():
                logger.warning("DOCX file contains no extractable text")
                return ""
            
            # Check and handle text length limit
            if len(full_text) > MAX_TEXT_LENGTH:
                logger.warning(
                    f"DOCX text exceeds {MAX_TEXT_LENGTH} character limit. "
                    f"Truncating from {len(full_text)} characters."
                )
                full_text = full_text[:MAX_TEXT_LENGTH]
                full_text += f"\n\n[WARNING: Document truncated at {MAX_TEXT_LENGTH} characters]"
            
            logger.info(f"Successfully extracted {len(full_text)} characters from DOCX")
            return full_text
            
        except Exception as e:
            error_msg = f"Failed to parse DOCX file: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
    
    @staticmethod
    def parse_txt(file_content: bytes) -> str:
        """
        Extract text from a TXT file.
        
        Simply decodes the bytes to UTF-8 text. Handles encoding errors gracefully.
        
        Args:
            file_content: Raw TXT file content as bytes
            
        Returns:
            Extracted text as a string. If the document exceeds the character limit,
            the text will be truncated and a warning message will be appended.
            
        Raises:
            Exception: For text decoding errors
        """
        try:
            logger.info("Starting TXT parsing...")
            
            # Validate input
            if not file_content:
                logger.warning("Empty TXT file content provided")
                return ""
            
            # Decode bytes to UTF-8 text (with fallback for encoding errors)
            try:
                full_text = file_content.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning("UTF-8 decoding failed, trying latin-1")
                full_text = file_content.decode('latin-1', errors='replace')
            
            # Check and handle text length limit
            if len(full_text) > MAX_TEXT_LENGTH:
                logger.warning(
                    f"TXT text exceeds {MAX_TEXT_LENGTH} character limit. "
                    f"Truncating from {len(full_text)} characters."
                )
                full_text = full_text[:MAX_TEXT_LENGTH]
                full_text += f"\n\n[WARNING: Document truncated at {MAX_TEXT_LENGTH} characters]"
            
            logger.info(f"Successfully extracted {len(full_text)} characters from TXT")
            return full_text
            
        except Exception as e:
            error_msg = f"Failed to parse TXT file: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
    
    @staticmethod
    def parse_document(file_content: bytes, filename: str) -> str:
        """
        Detect document format and dispatch to appropriate parser.
        
        Analyzes the file extension to determine the document type and routes
        to the appropriate parsing method. Supports PDF, DOCX, and TXT formats.
        
        Args:
            file_content: Raw file content as bytes
            filename: Name of the file (used to determine format from extension)
            
        Returns:
            Extracted text as a string from the parsed document
            
        Raises:
            ValueError: If the file format is unsupported
            Exception: For parsing errors (re-raised with context)
        """
        try:
            # Extract file extension from filename
            if not filename:
                raise ValueError("Filename is required to determine document format")
            
            # Get file extension and normalize to lowercase
            if '.' not in filename:
                raise ValueError(f"Cannot determine file format from filename: {filename}")
            
            file_extension = '.' + filename.lower().split('.')[-1]
            
            logger.info(f"Detected file format: {file_extension} for file: {filename}")
            
            # Dispatch to appropriate parser based on extension
            if file_extension == ".pdf":
                logger.info("Routing to PDF parser")
                return DocumentParser.parse_pdf(file_content)
            elif file_extension in [".docx", ".doc"]:
                logger.info("Routing to DOCX parser")
                return DocumentParser.parse_docx(file_content)
            elif file_extension == ".txt":
                logger.info("Routing to TXT parser")
                return DocumentParser.parse_txt(file_content)
            else:
                error_msg = (
                    f"Unsupported file format: {file_extension}. "
                    f"Supported formats are: .pdf, .docx, .doc, .txt"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        except ValueError:
            # Re-raise ValueError (unsupported format)
            raise
        except Exception as e:
            # Re-raise parsing errors with context
            error_msg = f"Error parsing document '{filename}': {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

