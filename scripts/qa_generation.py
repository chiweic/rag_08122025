#!/usr/bin/env python3
"""
Q&A Generation Tool - Production Version

This script generates high-quality question-answer pairs from PDF topic outlines.
It supports multiple LLM providers (DeepSeek, OpenAI, DashScope, Gemini, local vLLM)
and extracts evidence-based Q&As with page references.

This is Stage 2 of the RAG data preparation pipeline:
    Stage 1: PDF → Topic Outline with extracted text (pdf_topic_detection.py)
    Stage 2: Topic Outline → Q&A Pairs (this script)
    Stage 3: Q&A Pairs → Vector Embeddings (init_collections.py)

Key Features:
- Multi-provider support with configurable backends
- Evidence-based Q&A with page number citations
- Adaptive Q&A quantity based on topic length
- Uses pre-extracted text from outline JSON (no PDF loading needed)
- Robust error handling and retry mechanisms
- Structured output using Pydantic models
- Progress logging to file and console

Important: This script expects outline JSON files with the new format that includes
          a 'text' field in each topic containing the extracted text content.
          Generate outlines using pdf_topic_detection.py to get this format.

Usage:
    # Using default provider (deepseek)
    python qa_generation.py --outline pdf_outlines/deepseek-chat/01.01.pdf.outline.json

    # Using specific provider
    python qa_generation.py --outline "pdf_outlines/deepseek-chat/*.json" --provider gemini

    # With custom output directory
    python qa_generation.py --outline pdf_outlines/deepseek-chat/01.01.pdf.outline.json --out_dir qas

Author: DDM RAG Team
Last Updated: 2025-11-15 (Updated to use new outline format with pre-extracted text)
"""
import os
import logging
import json
import glob
import argparse
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import pymupdf  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
import time
from opencc import OpenCC  # Simplified to Traditional Chinese conversion

# ================================
# Logging Configuration
# ================================
log_file=time.strftime('logs/qa_generation_%Y%m%d_%H%M%S.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ================================
# Chinese Conversion
# ================================
# Initialize OpenCC converter (Simplified to Traditional Chinese)
cc = OpenCC('s2t')  # s2t = Simplified to Traditional

# ================================
# Pydantic Data Models
# ================================
from enum import Enum
from pydantic import field_validator

class QuestionType(str, Enum):
    """Cognitive level of questions for Buddhist learning.

    認知層次分類（使用英文標識符確保跨LLM相容性）：
    - factual: 事實性 - 針對經文或論述中的明確內容提問
    - conceptual: 概念理解 - 釐清佛學名相或理論間的關係
    - practical: 應用修行 - 將理論帶入日常修行或生活
    - analytical: 思辨分析 - 鼓勵深入思考與比較
    - reflective: 反思省察 - 引導學習者內觀自身經驗或信念
    """
    FACTUAL = "factual"         # 事實性 - Fact-based questions about explicit content
    CONCEPTUAL = "conceptual"   # 概念理解 - Conceptual understanding of Buddhist terms
    PRACTICAL = "practical"     # 應用修行 - Practical application in daily practice
    ANALYTICAL = "analytical"   # 思辨分析 - Analytical/critical thinking questions
    REFLECTIVE = "reflective"   # 反思省察 - Reflective questions for self-examination

class LearningPurpose(str, Enum):
    """Learning purpose / target persona for Q&A generation.

    學習目的分類（使用英文標識符確保跨LLM相容性）：
    - foundation: 基礎學習 - 適合初學者建立基礎認知
    - advanced_study: 深入研討 - 適合進階學習者分析義理
    - life_practice: 生活修行 - 適合實踐者將佛法融入日常生活
    - inspirational: 啟發思考 - 適合尋求人生反省與觀念轉化者
    - assessment: 測驗用題 - 適合知識測驗
    """
    FOUNDATION = "foundation"           # 基礎學習 - Beginner understanding
    ADVANCED_STUDY = "advanced_study"   # 深入研討 - Advanced analysis
    LIFE_PRACTICE = "life_practice"     # 生活修行 - Practical application
    INSPIRATIONAL = "inspirational"     # 啟發思考 - Transformative reflection
    ASSESSMENT = "assessment"           # 測驗用題 - Knowledge testing

class Evidence(BaseModel):
    """Evidence supporting a Q&A pair with page reference and quote."""
    page: int = Field(description="PDF page number where evidence is found")
    quote: str = Field(description="Short quote (1-2 sentences, max 200 chars) supporting the answer")

class TopicQA(BaseModel):
    """A single question-answer pair with evidence, question type, and learning purpose."""
    question: str = Field(description="Question in Traditional Chinese")
    question_type: QuestionType = Field(description="Cognitive level: factual, conceptual, practical, analytical, reflective")
    learning_purpose: LearningPurpose = Field(description="Learning purpose: foundation, advanced_study, life_practice, inspirational, assessment")
    answer: str = Field(description="Answer in Traditional Chinese, grounded in provided text")
    evidence: List[Evidence] = Field(description="List of evidence items with page numbers and quotes")

    @field_validator('question_type', mode='before')
    @classmethod
    def validate_question_type(cls, v):
        """Validate question_type and fall back to default if invalid."""
        if isinstance(v, str):
            v_lower = v.lower()
            # Check if it's a valid QuestionType value
            valid_values = {qt.value for qt in QuestionType}
            if v_lower in valid_values:
                return v_lower
            else:
                # Invalid value - log warning and return default
                logger.warning(f"Invalid question_type '{v}' - using default 'conceptual'")
                return "conceptual"  # Default fallback
        return v

    @field_validator('learning_purpose', mode='before')
    @classmethod
    def validate_learning_purpose(cls, v):
        """Validate learning_purpose and fall back to default if invalid."""
        if isinstance(v, str):
            v_lower = v.lower()
            # Check if it's a valid LearningPurpose value
            valid_values = {lp.value for lp in LearningPurpose}
            if v_lower in valid_values:
                return v_lower
            else:
                # Invalid value - log warning and return default
                logger.warning(f"Invalid learning_purpose '{v}' - using default 'foundation'")
                return "foundation"  # Default fallback
        return v

class QACollection(BaseModel):
    """Collection of Q&A pairs for a single topic."""
    qas: List[TopicQA] = Field(description="List of question-answer pairs")

class DocumentTopic(BaseModel):
    """Topic metadata from Stage 1 outline."""
    topic_title: str
    topic_summary: str
    topic_keywords: List[str]
    starting_page_number: int
    ending_page_number: int
    text: str = Field(default="", description="主題對應的文本內容（從起訖頁碼提取）")

class DocumentOutline(BaseModel):
    """Document outline from Stage 1 (llm_topic_detect.py output)."""
    filename: str
    document_title: str
    full_text: str = Field(default="", description="完整 PDF 文本內容（所有頁面）")
    main_topics: List[DocumentTopic]

def clamp_text(text: str, limit: int) -> str:
    """
    Truncate text to limit, preferring paragraph boundaries.

    Args:
        text: Text to truncate
        limit: Maximum character count

    Returns:
        Truncated text (at paragraph boundary if possible)
    """
    if len(text) <= limit:
        return text
    # Try to cut at paragraph boundary
    cut = text.rfind("\n\n", 0, limit)
    if cut < 0:
        cut = limit
    return text[:cut]

# NOTE: Removed estimate_num_qas() function - LLM now autonomously determines
# the appropriate number of Q&A pairs based on content richness and depth.
# This allows for more adaptive generation that better matches each topic's
# actual information density.

# ================================
# Main Q&A Generation Function
# ================================
def generate_qas_for_topic(
    client: OpenAI,
    document_title: str,
    filename: str,
    topic: DocumentTopic,
    topic_text: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    max_context_chars: int
) -> Optional[QACollection]:
    """
    Generate Q&A pairs for a single topic using LLM.

    The LLM autonomously determines the appropriate number of Q&A pairs based on
    content richness, depth, and importance. This allows for adaptive generation
    that matches the actual information density of each topic.

    Supports multiple LLM providers:
    - GPT models (OpenAI): Uses beta.chat.completions.parse()
    - DeepSeek/Qwen3 models: Uses chat.completions with JSON mode
    - vLLM local models (cpatonn/Qwen3-*): Uses beta.chat.completions.parse()
    - Gemini models: Uses beta.chat.completions.parse()

    Args:
        client: OpenAI-compatible client instance
        document_title: Title of source document
        filename: PDF filename
        topic: DocumentTopic object with metadata
        topic_text: Extracted text content for this topic
        model_name: Model identifier (e.g., "gpt-4", "deepseek-chat")
        temperature: LLM temperature (0.0-1.0)
        max_tokens: Maximum output tokens
        max_context_chars: Maximum characters to send to LLM

    Returns:
        QACollection: Collection of Q&A pairs, or None if generation fails
    """
    # Build system instruction
    system_instruction = (
        "你是一位嚴謹的知識助教。根據提供的『主題正文文本』產生與其高度相關的問答組。\n\n"

        "【重要：必須使用繁體中文】\n"
        "所有輸出必須使用繁體中文（Traditional Chinese），包括問題、答案、引文、以及所有欄位值。\n"
        "嚴禁使用簡體中文。例如：必須使用「學習」而非「学习」、「實」而非「实」、「繁體」而非「繁体」。\n\n"

        "【核心原則：自含式問題（Self-contained Questions）】\n"
            "- 每個「question」必須可單獨成立，在沒有原始文本時也能被理解。\n"
            "- 問題中必須顯式提及主題或關鍵名相（例如：「明末禪宗」「雲棲袾宏」「禪淨雙修」）。\n"
            "- 嚴禁出現以下指稱或其同義變體：本文、本章、文中、上文、下文、此處、作者、編者、該文、該段、如上所述、前文/後文等。\n"
            "- 若需要指涉來源，請改為：「根據〈{topic_title}〉章節…」或直接寫明主題名稱。\n"

        "重要規則：\n"
        "1. 輸出必須是完整且有效的 JSON 格式\n"
        "2. 所有字符串必須用雙引號包圍\n"
        "3. 確保所有括號正確閉合\n"
        "4. 沒有未終止的字符串\n"
        "5. 不要包含 JSON 之外的任何文字\n"
        "6. 每組問答必須提供至少一則證據（包含頁碼與短句式引文）\n"
        "7. 頁碼請使用提供的原始 PDF 頁碼\n"
        "8. 引文不得超過 200 字\n"
        "9. 每個問題必須同時標註問題類型（question_type）和學習目的（learning_purpose）\n\n"

        "問題類型說明（認知層次 - Question Type）：\n"
        "- factual（事實性）：針對經文或論述中的明確內容提問（例如：「般若波羅蜜多」是什麼意思？）\n"
        "- conceptual（概念理解）：釐清佛學名相或理論間的關係（例如：「空」與「無常」有什麼不同？）\n"
        "- practical（應用修行）：將理論帶入日常修行或生活（例如：如何在日常生活中實踐「觀心無常」？）\n"
        "- analytical（思辨分析）：鼓勵深入思考與比較（例如：為什麼佛教不主張靈魂？）\n"
        "- reflective（反思省察）：引導學習者內觀自身經驗或信念（例如：我是否能真正體會「無我」？）\n\n"

        "學習目的說明（適用場景 - Learning Purpose）：\n"
        "- foundation（基礎學習）：適合初學者建立基礎認知，理解經文與佛學名相（例如：什麼是「四聖諦」？）\n"
        "- advanced_study（深入研討）：適合進階學習者分析義理、比較不同思想體系（例如：天台宗與華嚴宗的「止觀」有何差異？）\n"
        "- life_practice（生活修行）：適合實踐者將佛法融入日常生活、獲得心理輔助（例如：面對失落時如何運用「無常」觀？）\n"
        "- inspirational（啟發思考）：適合尋求人生反省與觀念轉化者（例如：我的執著從何而來？）\n"
        "- assessment（測驗用題）：適合知識測驗，問題應明確且答案客觀（例如：「八正道」包括哪些項目？）\n\n"

        "【重要：兩個欄位的英文標識符不同，請勿混淆】\n"
        "對於每組問答，請提供以下欄位：\n\n"

        "1. question: 問題（繁體中文，清晰具體）\n\n"

        "2. question_type: 問題類型（英文標識符）\n"
        "   只能選擇以下5個值之一：\n"
        "   • factual（事實性）\n"
        "   • conceptual（概念理解）\n"
        "   • practical（應用修行）\n"
        "   • analytical（思辨分析）\n"
        "   • reflective（反思省察）\n\n"

        "3. learning_purpose: 學習目的（英文標識符）\n"
        "   只能選擇以下5個值之一：\n"
        "   • foundation（基礎學習）\n"
        "   • advanced_study（深入研討）\n"
        "   • life_practice（生活修行）\n"
        "   • inspirational（啟發思考）\n"
        "   • assessment（測驗用題）\n\n"

        "4. answer: 答案（繁體中文，應詳細完整，直接提供實質內容而非簡短摘要。若原文有詳細說明或列舉，答案中應包含這些細節）\n\n"

        "5. evidence: 證據列表（陣列格式），每個證據包含：\n"
        "   • page: 頁碼（整數）\n"
        "   • quote: 引文（字符串，從原文直接摘錄的關鍵句子，2-4 句話，最多 200 字。用於標註答案來源的具體位置）\n\n"

        "【範例（Few-shot 示範）】\n"
        "壞例：「本文如何闡述佛教的三大實踐方法？」\n"
        "好例：「佛教的三大實踐方法為何？在〈明末淨土教的修證方法〉中如何被說明？」\n"

        "壞例：「作者歸納明末禪者在修證經驗上的十點共通性有哪些？」\n"
        "好例：「在〈明末的禪宗人物及其特色〉章節，明末禪者的修證（省悟）經驗呈現哪些共通重點？請條列說明。」\n"

        "壞例：「文中提到的『性相融會』指什麼？」\n"
        "好例：「何謂『性相融會』？在明末佛教思想中具有何種義理意涵？」\n"
        
        "請參照這些示範，確保最終輸出問題均為「可獨立理解、具明確主題」的問句。\n"

        "重要提醒：\n"
        "1. answer 應該是完整的學習內容，而 quote 是用來標註出處的原文引用。避免 answer 過於簡略而將實質內容都放在 quote 中。\n"
        "2. 每個問答都應該在「問題類型」和「學習目的」兩個維度上保持多樣性，確保涵蓋不同認知層次和學習場景。\n\n"

        "【JSON 輸出格式範例】\n"
        "注意：question_type 和 learning_purpose 使用不同的英文標識符集合\n\n"
        '{\n'
        '  "qas": [\n'
        '    {\n'
        '      "question": "什麼是四聖諦？",\n'
        '      "question_type": "factual",\n'
        '      "learning_purpose": "foundation",\n'
        '      "answer": "四聖諦是佛教的核心教義...",\n'
        '      "evidence": [{"page": 10, "quote": "引文內容"}]\n'
        '    },\n'
        '    {\n'
        '      "question": "如何在日常生活中實踐正念？",\n'
        '      "question_type": "practical",\n'
        '      "learning_purpose": "life_practice",\n'
        '      "answer": "在日常生活中實踐正念...",\n'
        '      "evidence": [{"page": 15, "quote": "引文內容"}]\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    # Build user prompt
    prompt = (
        f"【文件標題】{document_title}\n"
        f"【檔名】{filename}\n"
        f"【主題】{topic.topic_title}\n"
        f"【頁碼範圍】{topic.starting_page_number}-{topic.ending_page_number}\n\n"
        f"【主題摘要】\n{topic.topic_summary}\n\n"
        f"【主題正文文本】（僅能根據此內容回答）\n"
        f"{clamp_text(topic_text, max_context_chars)}\n\n"
        f"任務：請根據主題內容的豐富程度和重要性，產生適量的高品質問答（繁體中文）。"
        f"數量應與內容深度相匹配，確保涵蓋主要概念和關鍵細節。\n\n"
        f"【重要】每個問題都必須同時標註兩個不同的分類維度：\n\n"
        f"維度1 - question_type（問題類型，認知層次）：\n"
        f"必須從以下5個值選一個：factual, conceptual, practical, analytical, reflective\n\n"
        f"維度2 - learning_purpose（學習目的，適用場景）：\n"
        f"必須從以下5個值選一個：foundation, advanced_study, life_practice, inspirational, assessment\n\n"
        f"注意：這兩個欄位使用不同的英文標識符，請勿混淆！\n\n"
        f"請在兩個維度上都保持多樣性，以支援不同學習需求：\n"
        f"- 初學者需要 foundation（基礎學習）類問題來理解名相\n"
        f"- 進階者需要 advanced_study（深入研討）類問題來比較義理\n"
        f"- 實踐者需要 life_practice（生活修行）類問題來應用佛法\n"
        f"- 尋求啟發者需要 inspirational（啟發思考）類問題來反省人生\n"
        f"- 測驗系統需要 assessment（測驗用題）類問題來評估理解\n\n"
        f"每個答案必須能在正文中找到依據，並於 evidence 中列出對應頁碼與 2~4 句短引文。\n\n"
        f"請直接輸出 JSON 格式，不要包含任何其他文字。"
    )

    try:
        # Route to appropriate API based on model name
        if model_name.startswith("gpt-"):
            # OpenAI GPT models
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                #max_tokens=max_tokens,
                #temperature=temperature,
                response_format=QACollection
            )
            qa_collection = response.choices[0].message.parsed

        elif model_name.startswith("deepseek-") or model_name.startswith("qwen3-"):
            # DeepSeek/Qwen3 models with JSON mode
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            json_data = json.loads(response.choices[0].message.content)
            # Parse into QACollection with English enum validation
            qa_collection = QACollection(**json_data)

        elif model_name.startswith("cpatonn/Qwen3-"):
            # vLLM local models
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=QACollection
            )
            qa_collection = response.choices[0].message.parsed

        elif model_name.startswith("gemini-"):
            # Gemini models (OpenAI-compatible mode)
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=QACollection
            )
            qa_collection = response.choices[0].message.parsed

        else:
            raise ValueError(f"未知的模型名稱格式: {model_name}")

        logger.info(f"   ✅ 成功生成 {len(qa_collection.qas)} 組問答")
        return qa_collection

    except Exception as e:
        logger.error(f"   ❌ Q&A 生成失敗: {e}")
        return None

# ================================
# Main Processing Function
# ================================
def process_outline_file(
    outline_path: str,
    client: OpenAI,
    model_name: str,
    temperature: float,
    max_tokens: int,
    max_context_chars: int,
    output_dir: str
) -> bool:
    """
    Process a single outline JSON file to generate Q&A pairs.

    Args:
        outline_path: Path to outline JSON file (from Stage 1)
        client: OpenAI-compatible client instance
        model_name: Model identifier
        temperature: LLM temperature
        max_tokens: Maximum output tokens
        max_context_chars: Maximum context characters
        output_dir: Output directory for Q&A JSON files

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"開始處理大綱文件：{outline_path}")

        # Load outline JSON
        with open(outline_path, 'r', encoding='utf-8') as f:
            outline_data = json.load(f)

        outline = DocumentOutline(**outline_data)
        logger.info(f"   文件：{outline.document_title}")
        logger.info(f"   主題數：{len(outline.main_topics)}")

        # Prepare output file
        output_filename = os.path.basename(outline_path).replace('.outline.json', '.qa.json')
        output_path = os.path.join(output_dir, output_filename)

        # No need to load PDF - text is now in the outline JSON
        logger.info(f"   使用大綱 JSON 中的預提取文本（無需載入 PDF）")

        # Process each topic
        all_topic_qas = []
        for i, topic in enumerate(outline.main_topics, 1):

            logger.info(f"   處理主題 {i}/{len(outline.main_topics)}: {topic.topic_title}")

            # Use text directly from outline JSON
            topic_text = topic.text

            if not topic_text or not topic_text.strip():
                logger.warning(f"      ⚠️  文本為空，跳過此主題")
                continue

            logger.info(f"      頁碼範圍 {topic.starting_page_number}-{topic.ending_page_number} ({len(topic_text)} 字符)")

            # Generate Q&As (LLM determines appropriate quantity)
            qa_collection = generate_qas_for_topic(
                client=client,
                document_title=outline.document_title,
                filename=outline.filename,
                topic=topic,
                topic_text=topic_text,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                max_context_chars=max_context_chars
            )

            if qa_collection:
                all_topic_qas.append({
                    "topic_title": topic.topic_title,
                    "topic_summary": topic.topic_summary,
                    "page_range": [topic.starting_page_number, topic.ending_page_number],
                    "qas": [qa.model_dump() for qa in qa_collection.qas]
                })

            # Pause between requests to avoid rate limits
            time.sleep(1)

        # Save results
        result = {
            "filename": outline.filename,
            "document_title": outline.document_title,
            "topics": all_topic_qas
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 已保存：{output_path} ({len(all_topic_qas)} 個主題)")
        return True

    except Exception as e:
        logger.error(f"❌ 處理大綱文件失敗: {e}")
        return False

# ================================
# Main Function
# ================================
from llm_config import config_manager

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Q&A 生成工具（從主題大綱生成問答對）")
    parser.add_argument("--outline", type=str, required=True,
                       help="大綱 JSON 檔案路徑或通配符模式（例如 pdf_outlines/deepseek-chat/*.json）")
    parser.add_argument("--out_dir", type=str, default="qa_pairs",
                       help="輸出目錄 (預設：qa_pairs)")
    parser.add_argument("--log_level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日誌級別")
    parser.add_argument("--provider", type=str,
                       choices=config_manager.get_available_providers(),
                       help="LLM 供應商選擇")
    parser.add_argument("--overwrite", action="store_true",
                       help="如果指定，將覆蓋已存在的輸出文件")

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Validate and get provider config
    try:
        provider_config = config_manager.get_provider_config(args.provider)
        if not config_manager.validate_config(args.provider):
            logger.error(f"{args.provider} 配置不完整，請檢查 .env 文件")
            return

        logger.info(f"使用供應商: {args.provider or config_manager.default_provider}")
        logger.info(f"模型: {provider_config.model_name}")

    except ValueError as e:
        logger.error(f"配置錯誤: {e}")
        return

    # Create OpenAI client
    client = OpenAI(
        api_key=provider_config.api_key,
        base_url=provider_config.base_url
    )

    # Find all matching outline files
    outline_files = glob.glob(args.outline)
    if not outline_files:
        logger.warning(f"沒有找到匹配的大綱文件: {args.outline}")
        return

    logger.info(f"找到 {len(outline_files)} 個大綱文件待處理")

    # Create output directory with model name subdirectory
    # Format: {out_dir}/{model_name}/
    # Sanitize model name for use in path (replace slashes with underscores)
    safe_model_name = provider_config.model_name.replace('/', '_').replace('\\', '_')
    model_output_dir = os.path.join(args.out_dir, safe_model_name)
    os.makedirs(model_output_dir, exist_ok=True)

    logger.info(f"輸出目錄: {model_output_dir}")

    # Process each outline file
    successful_count = 0
    for outline_file in outline_files:
        output_filename = os.path.basename(outline_file).replace('.outline.json', '.qa.json')
        output_file = os.path.join(model_output_dir, output_filename)

        if os.path.exists(output_file) and not args.overwrite:
            logger.info(f"跳過已存在的文件: {output_file}")
            successful_count += 1
            continue

        success = process_outline_file(
            outline_path=outline_file,
            client=client,
            model_name=provider_config.model_name,
            temperature=provider_config.temperature,
            max_tokens=provider_config.max_tokens,
            max_context_chars=provider_config.max_context_chars,
            output_dir=model_output_dir
        )

        if success:
            successful_count += 1

    logger.info(f"\n✅ 處理完成！成功: {successful_count}/{len(outline_files)} 個文件")
    logger.info(f"輸出目錄: {model_output_dir}")

if __name__ == "__main__":
    main()
