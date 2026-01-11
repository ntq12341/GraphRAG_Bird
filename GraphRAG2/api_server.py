# File: D:\UnityGame\GraphRAG2\api_server.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from src.main import BirdGraphRAG

app = Flask(__name__)
# Cho phép Frontend (port 3000) gọi sang Backend (port 5000)
CORS(app) 

print("⏳ Đang khởi động Bot... Vui lòng chờ!")
# Khởi tạo Bot 1 lần duy nhất khi server bật
bot = BirdGraphRAG()
print("✅ Bot đã sẵn sàng!")

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    try:
        # 1. Nhận dữ liệu từ React gửi sang
        data = request.json
        user_msg = data.get('message', '')

        if not user_msg:
            return jsonify({"error": "No message provided"}), 400

        print(f"📩 Nhận từ Web: {user_msg}")

        # 2. Gửi cho Bot xử lý (Logic cũ của bạn)
        ai_response = bot.process_turn(user_msg)

        # 3. Trả kết quả về cho React
        return jsonify({
            "response": ai_response,
            "status": "success"
        })

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Chạy server tại cổng 5000
    app.run(host='0.0.0.0', port=5000, debug=True)