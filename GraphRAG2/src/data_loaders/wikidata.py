import sys
from SPARQLWrapper import SPARQLWrapper, JSON

class WikidataFetcher:
    def __init__(self):
        self.sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        self.sparql.setReturnFormat(JSON)
        # Thêm User-Agent để tránh bị Wikidata chặn request
        self.sparql.addCustomHttpHeader("User-Agent", "BirdGraphRAG/1.0 (contact@example.com)")

        # TỪ ĐIỂN CỨNG: Sửa sai ngay lập tức cho các loài phổ biến ở VN
        self.common_map = {
            "chim bói cá": "Alcedo atthis",
            "bói cá": "Alcedo atthis",
            "bói cá thường": "Alcedo atthis",
            "chào mào": "Pycnonotus jocosus",
            "chim sẻ": "Passer domesticus",
            "sẻ nhà": "Passer domesticus",
            "chim sâu": "Dicaeidae",
            "vành khuyên": "Zosterops",
            "chích chòe": "Copsychus saularis",
            "chích chòe than": "Copsychus saularis",
            "cu gáy": "Spilopelia chinensis",
            "chim sáo": "Acridotheres",
            "đại bàng": "Aquila",
            "họa mi": "Garrulax canorus",
            "chim công": "Pavo cristatus",
            "công": "Pavo cristatus"
        }

    def get_bird_data(self, common_name: str):
        """
        Hàm mới: Trả về cả Tên khoa học VÀ Link ảnh.
        Output: {'scientific_name': '...', 'image_url': '...'}
        """
        if not common_name: return None

        # 1. Xử lý từ điển cứng
        normalized_name = common_name.strip().lower()
        if normalized_name in self.common_map:
            # Nếu tìm thấy trong dict, lấy tên khoa học làm từ khóa tìm kiếm
            search_term = self.common_map[normalized_name]
            print(f"      [Wikidata] Found in local dict: {normalized_name} -> {search_term}")
        else:
            search_term = common_name

        # Chuẩn bị biến thể viết hoa (Title Case)
        name_title = search_term.title()

        # QUERY SPARQL MỚI (Thêm ?mass)
        query = f"""
        SELECT ?scientificName ?image ?mass WHERE {{
          {{ ?item rdfs:label "{search_term}"@vi. }}
          UNION
          {{ ?item rdfs:label "{search_term}"@en. }}
          UNION
          {{ ?item rdfs:label "{name_title}"@vi. }}
          UNION
          {{ ?item rdfs:label "{name_title}"@en. }}
          UNION
          {{ ?item wdt:P225 "{search_term}". }}
          
          ?item wdt:P225 ?scientificName.
          
          OPTIONAL {{ ?item wdt:P18 ?image. }}
          
          # --- MỚI: Lấy khối lượng (P2067) ---
          OPTIONAL {{ ?item wdt:P2067 ?mass. }}
        }}
        LIMIT 1
        """
        
        self.sparql.setQuery(query)
        try:
            results = self.sparql.query().convert()
            bindings = results["results"]["bindings"]
            
            if bindings:
                data = bindings[0]
                sci_name = data["scientificName"]["value"]
                img_url = data.get("image", {}).get("value", None)
                
                # Lấy cân nặng (Wikidata thường trả về đơn vị Gram hoặc Kg)
                mass_val = data.get("mass", {}).get("value", None)
                
                print(f"      [Wikidata] Resolved: {sci_name} | Mass: {mass_val}")
                
                return {
                    "scientific_name": sci_name,
                    "image_url": img_url,
                    "mass": mass_val # Trả về cân nặng
                }
                
        except Exception as e:
            print(f"      [Wikidata Error] {e}")
            
        return None

    def get_scientific_name(self, common_name: str) -> str:
        """
        Hàm cũ (giữ lại để tương thích ngược với main.py nếu cần)
        """
        data = self.get_bird_data(common_name)
        return data['scientific_name'] if data else None