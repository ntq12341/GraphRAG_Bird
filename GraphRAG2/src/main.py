import os
import sys
import json
from typing import Dict, List, Any

# Import LangChain
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Import Config
from src.config import Config

# Import Database Handler
from src.graph.neo4j_handler import Neo4jHandler

# Import Data Loaders
from src.data_loaders.wikidata import WikidataFetcher
from src.data_loaders.wikipedia import WikipediaFetcher
from src.data_loaders.xenocanto import XenoCantoFetcher
from src.data_loaders.iucn import IUCNFetcher
from src.data_loaders.birdspedia import BirdspediaFetcher

class BirdGraphRAG:
    def __init__(self):
        print("🚀 Initializing BirdGraphRAG System...")
        
        # 1. Khởi tạo LLM
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY")
        )
        
        # 2. Kết nối Database
        self.graph = Neo4jHandler()
        
        # 3. Khởi tạo các bộ nạp dữ liệu (Fetchers)
        self.wikidata = WikidataFetcher()
        self.wiki = WikipediaFetcher()
        self.xenocanto = XenoCantoFetcher()
        self.iucn = IUCNFetcher()
        self.birdspedia = BirdspediaFetcher()
        
        # 4. Bộ nhớ hội thoại (Chat Memory)
        self.chat_history = [] 
        
        print("✅ System Ready!\n")

    def _contextualize_query(self, raw_query: str) -> str:
        """
        Viết lại câu hỏi dựa trên lịch sử chat để xử lý đại từ (Nó, loài này...)
        """
        if not self.chat_history:
            return raw_query

        # Lấy 3 cặp hội thoại gần nhất
        history_str = "\n".join([f"{msg.type.upper()}: {msg.content}" for msg in self.chat_history[-6:]])

        prompt = PromptTemplate.from_template("""
        Combine the chat history and the latest user question into a standalone question.
        Ensure that pronouns (it, he, she, this bird) are replaced with the specific bird name from the history.
        Do NOT answer the question. Return ONLY the rewritten question.
        
        Chat History:
        {history}
        
        Latest Question: {question}
        
        Standalone Question:
        """)
        
        chain = prompt | self.llm
        rewritten = chain.invoke({"history": history_str, "question": raw_query}).content.strip()
        
        if rewritten != raw_query:
            print(f"🔄 [Context] Rewritten: '{raw_query}' -> '{rewritten}'")
        return rewritten

    def _extract_entity(self, query: str) -> str:
        # Prompt: Ép buộc trả về tên thông thường
        prompt = f"""
        Identify the bird common name in the query: "{query}".
        Return ONLY the common name (e.g., 'Chim sẻ', 'Kingfisher').
        Do NOT translate to scientific name.
        If no bird is mentioned, return 'None'.
        """
        res = self.llm.invoke(prompt)
        return res.content.strip().strip('"')

    def _lazy_load_data(self, scientific_name: str, common_name: str, status: Dict):
        """
        Chiến lược Lazy Loading: Chỉ tải những gì còn thiếu trong Graph.
        """
        
        # 0. HÌNH ẢNH & CÂN NẶNG (MỚI)
        # Kiểm tra nếu thiếu Ảnh HOẶC thiếu Cân nặng thì đi lấy từ Wikidata
        if not status.get('has_image') or not status.get('has_mass'):
            print(f"   📥 [Fetch] Details (Image/Mass) for '{common_name}'...")
            
            # Gọi hàm get_bird_data mới (trả về cả tên, ảnh, cân nặng)
            wiki_data = self.wikidata.get_bird_data(common_name)
            
            if wiki_data:
                # Gọi hàm update_details mới trong Neo4j
                self.graph.update_details(
                    scientific_name, 
                    wiki_data.get('image_url'), 
                    wiki_data.get('mass')
                )

        # 1. Wiki (Mô tả)
        if not status.get('has_wiki'):
            print(f"   📥 [Fetch] Wikipedia for '{common_name}'...")
            summary = self.wiki.get_summary(common_name, lang='vi')
            if summary:
                self.graph.update_wiki(scientific_name, common_name, summary)
        
        # 2. IUCN (Bảo tồn)
        if not status.get('has_status'):
            print(f"   📥 [Fetch] IUCN Status for '{scientific_name}'...")
            iucn_status = self.iucn.get_conservation_status(scientific_name)
            if iucn_status:
                self.graph.update_status(scientific_name, iucn_status)

        # 3. Xeno-canto (Âm thanh)
        if not status.get('has_audio'):
            print(f"   📥 [Fetch] Audio for '{scientific_name}'...")
            audio_data = self.xenocanto.get_audio(scientific_name)
            if audio_data:
                self.graph.update_audio(scientific_name, audio_data['url'])

        # 4. Birdspedia (Sinh thái)
        if not status.get('has_ecology'):
            print(f"   📥 [Fetch] Ecology info from Birdspedia...")
            eco_data = self.birdspedia.fetch_ecology_data(scientific_name)
            if eco_data:
                self.graph.update_ecology(scientific_name, eco_data)

    def process_turn(self, user_input: str) -> str:
        print(f"👤 User: {user_input}")
        
        # --- BƯỚC 1: Xử lý ngữ cảnh ---
        standalone_query = self._contextualize_query(user_input)

        # --- BƯỚC 2: Nhận diện thực thể ---
        bird_name = self._extract_entity(standalone_query)
        
        if not bird_name or bird_name.lower() == 'none':
            response = self.llm.invoke(user_input).content
            self.chat_history.append(HumanMessage(content=user_input))
            self.chat_history.append(AIMessage(content=response))
            return response

        print(f"   🐦 Target Bird: {bird_name}")

        # --- BƯỚC 3: Định danh (Tên thường -> Tên khoa học) ---
        # Hàm get_bird_data giờ trả về dict, ta lấy scientific_name
        bird_data = self.wikidata.get_bird_data(bird_name)
        
        if bird_data:
            sci_name = bird_data['scientific_name']
        else:
            # Fallback LLM
            sci_name = self.llm.invoke(f"Scientific name of '{bird_name}'? Return only the name.").content.strip()
        
        print(f"   🔬 Scientific Name: {sci_name}")

        # --- BƯỚC 4: Kiểm tra Graph (Check Cache) ---
        status = self.graph.check_data_status(sci_name)
        
        if not status['exists']:
            print("   ✨ New Entity detected! Creating base node...")
        
        # --- BƯỚC 5: Lazy Loading (Chạy fetch các phần thiếu) ---
        self._lazy_load_data(sci_name, bird_name, status)

        # --- BƯỚC 6: Truy xuất ngữ cảnh đầy đủ ---
        context_data = self.graph.get_full_context(sci_name)
        
        # --- BƯỚC 7: Tổng hợp câu trả lời (RAG Generation) ---
        # Prompt mới: Bắt buộc hiển thị hình ảnh
        system_prompt = """
        You are an expert Ornithologist representing the Vietnam Bird Association. 
        
        TASK:
        Use the provided Knowledge Graph Context to answer the user's question in VIETNAMESE (Tiếng Việt).
        
        GUIDELINES:
        1. IMAGE: If 'ImageURL' is provided in the context, YOU MUST DISPLAY IT at the very top of your answer using Markdown format: ![Bird Image](ImageURL).
        2. TRANSLATION: Translate technical terms (e.g., "Least Concern" -> "Ít quan tâm", "Omnivore" -> "Động vật ăn tạp") naturally.
        3. AUDIO: If audio is available, link it as: [🔊 Nghe giọng hót](AudioURL).
        4. TONE: Friendly and educational.
        """
        
        rag_prompt = f"""
        {system_prompt}
        
        --- CONTEXT DATA ---
        {context_data}
        
        --- USER QUESTION ---
        {standalone_query}
        """
        
        final_response = self.llm.invoke(rag_prompt).content
        
        # --- BƯỚC 8: Cập nhật lịch sử ---
        self.chat_history.append(HumanMessage(content=user_input))
        self.chat_history.append(AIMessage(content=final_response))
        
        return final_response

    def close(self):
        self.graph.close()
        print("👋 Connection closed.")

# ==========================================
# MAIN EXECUTION LOOP
# ==========================================
if __name__ == "__main__":
    agent = BirdGraphRAG()
    
    print("----------------------------------------------------------------")
    print("🤖 BIRD BOT: Xin chào! Bạn muốn hỏi về loài chim nào?")
    print("   (Gõ 'exit' để thoát)")
    print("----------------------------------------------------------------")

    try:
        while True:
            user_input = input("\n👉 Bạn: ")
            if user_input.lower() in ['exit', 'quit', 'thoat']:
                print("BIRD BOT: Tạm biệt!")
                break
            
            if not user_input.strip():
                continue

            try:
                response = agent.process_turn(user_input)
                print(f"\n🤖 Bot: {response}")
            except Exception as e:
                print(f"❌ Error processing query: {e}")
                import traceback
                traceback.print_exc()
                
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        agent.close()