from neo4j import GraphDatabase
from langchain_huggingface import HuggingFaceEmbeddings
from src.config import Config

class Neo4jHandler:
    def __init__(self):
        # Kết nối Neo4j
        self.driver = GraphDatabase.driver(
            Config.NEO4J_URI, 
            auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
        )
        
        # SỬ DỤNG MODEL MIỄN PHÍ
        print("   ⏳ Loading Embedding Model (all-MiniLM-L6-v2)...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        self._init_indices()

    def _init_indices(self):
        # Tạo Vector Index với 384 dimensions
        query = """
        CREATE VECTOR INDEX bird_desc_index IF NOT EXISTS
        FOR (w:WikiInfo) ON (w.embedding)
        OPTIONS {indexConfig: {
            `vector.dimensions`: 384, 
            `vector.similarity_function`: 'cosine'
        }}
        """
        with self.driver.session() as session:
            session.run(query)

    def close(self):
        self.driver.close()

    def check_data_status(self, scientific_name):
        """Kiểm tra xem dữ liệu đã có những gì (bao gồm Ảnh và Cân nặng)"""
        query = """
        MATCH (b:Bird {scientific_name: $sci})
        RETURN b,
               EXISTS((b)-[:HAS_INFO]->(:WikiInfo)) as has_wiki,
               EXISTS((b)-[:HAS_SOUND]->(:Audio)) as has_audio,
               EXISTS((b)-[:HAS_ECOLOGY]->(:Ecology)) as has_ecology,
               EXISTS((b)-[:HAS_STATUS]->(:IUCN)) as has_status,
               b.image_url IS NOT NULL as has_image,  // Kiểm tra ảnh
               b.mass IS NOT NULL as has_mass         // Kiểm tra cân nặng
        """
        with self.driver.session() as session:
            res = session.run(query, sci=scientific_name).single()
            
            if not res:
                return {"exists": False}
            
            return {
                "exists": True,
                "common_name": res['b'].get('common_name'),
                "has_wiki": res['has_wiki'],
                "has_audio": res['has_audio'],
                "has_status": res['has_status'],
                "has_ecology": res['has_ecology'],
                "has_image": res['has_image'], # MỚI
                "has_mass": res['has_mass']    # MỚI
            }

    def update_details(self, scientific_name, image_url, mass):
        """
        HÀM MỚI: Cập nhật thông tin chi tiết (Ảnh + Cân nặng) từ Wikidata
        """
        if not image_url and not mass: return

        query = """
        MERGE (b:Bird {scientific_name: $sci})
        SET b.image_url = COALESCE($url, b.image_url),
            b.mass = COALESCE($mass, b.mass)
        """
        with self.driver.session() as session:
            session.run(query, sci=scientific_name, url=image_url, mass=mass)

    def update_wiki(self, scientific_name, common_name, summary):
        if not summary: return
        vector = self.embeddings.embed_query(summary)
        query = """
        MERGE (b:Bird {scientific_name: $sci})
        SET b.common_name = COALESCE(b.common_name, $common)
        MERGE (w:WikiInfo {bird_id: $sci})
        SET w.summary = $summary, w.embedding = $vector
        MERGE (b)-[:HAS_INFO]->(w)
        """
        with self.driver.session() as session:
            session.run(query, sci=scientific_name, common=common_name, summary=summary, vector=vector)

    def update_audio(self, scientific_name, audio_url):
        if not audio_url: return
        query = """
        MATCH (b:Bird {scientific_name: $sci})
        MERGE (a:Audio {bird_id: $sci})
        SET a.url = $url
        MERGE (b)-[:HAS_SOUND]->(a)
        """
        with self.driver.session() as session:
            session.run(query, sci=scientific_name, url=audio_url)

    def update_status(self, scientific_name, status_text):
        if not status_text: return
        query = """
        MATCH (b:Bird {scientific_name: $sci})
        MERGE (i:IUCN {bird_id: $sci})
        SET i.status = $status
        MERGE (b)-[:HAS_STATUS]->(i)
        """
        with self.driver.session() as session:
            session.run(query, sci=scientific_name, status=status_text)

    def update_ecology(self, scientific_name, data):
        if not data: return
        query = """
        MATCH (b:Bird {scientific_name: $sci})
        MERGE (e:Ecology {bird_id: $sci})
        SET e.diet = $diet, e.habitat = $habitat, e.migration = $mig
        MERGE (b)-[:HAS_ECOLOGY]->(e)
        """
        with self.driver.session() as session:
            session.run(query, sci=scientific_name, 
                        diet=data.get('diet'), 
                        habitat=data.get('habitat'), 
                        mig=data.get('migration'))

    def get_full_context(self, scientific_name):
        """Lấy toàn bộ dữ liệu (bao gồm cả Mass và Image) để gửi cho LLM"""
        query = """
        MATCH (b:Bird {scientific_name: $sci})
        OPTIONAL MATCH (b)-[:HAS_INFO]->(w:WikiInfo)
        OPTIONAL MATCH (b)-[:HAS_SOUND]->(a:Audio)
        OPTIONAL MATCH (b)-[:HAS_STATUS]->(i:IUCN)
        OPTIONAL MATCH (b)-[:HAS_ECOLOGY]->(e:Ecology)
        RETURN b.common_name as Name,
               b.scientific_name as ScientificName,
               b.image_url as ImageURL,  // <--- Lấy ảnh
               b.mass as Mass,           // <--- Lấy cân nặng
               w.summary as Description,
               a.url as AudioURL,
               i.status as ConservationStatus,
               e.diet as Diet,
               e.habitat as Habitat
        """
        with self.driver.session() as session:
            rec = session.run(query, sci=scientific_name).single()
            if not rec:
                return "No data found in graph."
            return rec.data()